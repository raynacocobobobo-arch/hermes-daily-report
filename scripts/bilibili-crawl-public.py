#!/usr/bin/env python3
"""One-shot public Bilibili subtitle crawl for the tracked analyst list.

This intentionally uses no account cookie. It writes an isolated preview so a
partial public crawl can never be mistaken for the canonical subtitle corpus.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests


SHANGHAI = ZoneInfo("Asia/Shanghai")
TARGET_DATE = os.environ.get("TARGET_DATE") or datetime.now(SHANGHAI).strftime("%Y-%m-%d")
OUTPUT_DIR = Path("crawl-preview") / TARGET_DATE
VIDEOS_PER_UP = 12

UP_MASTERS = {
    "ETF战法": 3546854339905896,
    "趋势耿鬼": 3546761960360178,
    "财经高一截": 269571531,
    "老柯复盘": 3546635351099881,
    "趋势风哥": 613230878,
    "趋势天哥": 1372241958,
    "李长胜621": 19239427,
    "投资笔记-原创": 1584562031,
    "财经企鹅姐": 2075256224,
    "邪修炒股笔记": 3546826766551823,
    "杉门tepu大弟子": 3706937791219923,
    "逻辑哥复盘": 433280310,
    "李一恩": 3690991164852348,
    "莫大韭菜": 525121722,
    "青枫浦上Q": 1420210197,
    "奇点财情": 336730296,
    "研究员雷牛牛": 595658483,
}

MIXIN_ENC = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
    }
)


class BiliApiError(RuntimeError):
    def __init__(self, stage: str, code: int | str, message: str):
        super().__init__(f"{stage}: code={code} {message}")
        self.stage = stage
        self.code = code
        self.message = message


def api_json(url: str, *, stage: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = SESSION.get(url, params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()
    code = payload.get("code", 0)
    if code != 0:
        raise BiliApiError(stage, code, payload.get("message") or payload.get("msg") or "unknown")
    return payload


def get_mixin_key() -> str:
    payload = api_json("https://api.bilibili.com/x/web-interface/nav", stage="nav")
    wbi = payload["data"]["wbi_img"]
    img_key = wbi["img_url"].rsplit("/", 1)[-1].split(".", 1)[0]
    sub_key = wbi["sub_url"].rsplit("/", 1)[-1].split(".", 1)[0]
    joined = img_key + sub_key
    return "".join(joined[index] for index in MIXIN_ENC)[:32]


def signed_params(params: dict[str, Any], mixin_key: str) -> dict[str, Any]:
    clean = dict(params)
    clean["wts"] = int(time.time())
    for key, value in list(clean.items()):
        clean[key] = re.sub(r"[!'()*]", "", str(value))
    query = urlencode(sorted(clean.items()))
    clean["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return clean


def fetch_today_videos(name: str, uid: int, mixin_key: str) -> list[dict[str, Any]]:
    params = signed_params(
        {
            "mid": uid,
            "pn": 1,
            "ps": VIDEOS_PER_UP,
            "order": "pubdate",
            "platform": "web",
        },
        mixin_key,
    )
    payload = api_json(
        "https://api.bilibili.com/x/space/wbi/arc/search",
        stage=f"video-list:{name}",
        params=params,
    )
    videos = payload.get("data", {}).get("list", {}).get("vlist", [])
    result = []
    for item in videos:
        created = int(item.get("created") or 0)
        published = datetime.fromtimestamp(created, SHANGHAI) if created else None
        if published and published.strftime("%Y-%m-%d") == TARGET_DATE:
            result.append(
                {
                    "up": name,
                    "uid": uid,
                    "bvid": item.get("bvid", ""),
                    "title": item.get("title", ""),
                    "published_at": published.isoformat(),
                    "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}",
                }
            )
    return result


def fetch_public_subtitle(video: dict[str, Any], mixin_key: str) -> tuple[str | None, str]:
    bvid = video["bvid"]
    view = api_json(
        "https://api.bilibili.com/x/web-interface/view",
        stage=f"view:{bvid}",
        params={"bvid": bvid},
    )["data"]
    pages = view.get("pages") or []
    if not pages:
        return None, "missing_cid"
    cid = pages[0]["cid"]
    player_params = signed_params({"bvid": bvid, "cid": cid}, mixin_key)
    player = api_json(
        "https://api.bilibili.com/x/player/wbi/v2",
        stage=f"player:{bvid}",
        params=player_params,
    ).get("data", {})
    subtitles = player.get("subtitle", {}).get("subtitles", []) or []
    if not subtitles:
        if player.get("need_login_subtitle"):
            return None, "login_required"
        return None, "no_platform_subtitle"

    selected = next((s for s in subtitles if str(s.get("lan", "")).startswith("zh")), subtitles[0])
    subtitle_url = selected.get("subtitle_url", "")
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url
    if not subtitle_url:
        return None, "missing_subtitle_url"

    response = SESSION.get(subtitle_url, timeout=20)
    response.raise_for_status()
    body = response.json().get("body", [])
    text = " ".join(str(item.get("content", "")).strip() for item in body).strip()
    return (text or None), ("ok" if text else "empty_subtitle")


def safe_filename(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|\r\n]+", "-", value).strip(" .-")
    return value[:80] or "untitled"


def save_subtitle(video: dict[str, Any], text: str, ordinal: int) -> dict[str, Any]:
    filename = f"{safe_filename(video['up'])} {TARGET_DATE[5:].replace('-', '.')} 第{ordinal}篇.txt"
    path = OUTPUT_DIR / filename
    content = (
        f"UP主：{video['up']}\n"
        f"标题：{video['title']}\n"
        f"日期：{TARGET_DATE}\n"
        f"BV号：{video['bvid']}\n\n"
        f"{text}\n"
    )
    path.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(content.encode()).hexdigest()
    return {
        "source": filename,
        "up_name": video["up"],
        "title": video["title"],
        "bvid": video["bvid"],
        "repository_path": str(path),
        "format": "txt",
        "size_bytes": len(content.encode()),
        "sha256": digest,
    }


def main() -> None:
    datetime.strptime(TARGET_DATE, "%Y-%m-%d")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(SHANGHAI)
    report: dict[str, Any] = {
        "schema_version": "public-crawl-preview/1.0",
        "target_date": TARGET_DATE,
        "started_at": started_at.isoformat(),
        "tracked_up_count": len(UP_MASTERS),
        "cookie_used": False,
        "videos": [],
        "up_status": [],
        "blocked": False,
    }
    index_entries: list[dict[str, Any]] = []

    try:
        mixin_key = get_mixin_key()
    except Exception as exc:  # preserve a diagnostic artifact instead of crashing silently
        report["blocked"] = True
        report["fatal_error"] = str(exc)
        mixin_key = ""

    if mixin_key:
        for up_name, uid in UP_MASTERS.items():
            try:
                videos = fetch_today_videos(up_name, uid, mixin_key)
                report["up_status"].append({"up": up_name, "uid": uid, "status": "ok", "today_videos": len(videos)})
                for ordinal, video in enumerate(videos, start=1):
                    try:
                        subtitle, subtitle_status = fetch_public_subtitle(video, mixin_key)
                    except Exception as exc:
                        subtitle = None
                        subtitle_status = f"error:{exc}"
                    video["subtitle_status"] = subtitle_status
                    video["has_subtitle"] = bool(subtitle)
                    if subtitle:
                        index_entries.append(save_subtitle(video, subtitle, ordinal))
                    report["videos"].append(video)
                    time.sleep(0.6)
                time.sleep(1.2)
            except BiliApiError as exc:
                report["up_status"].append({"up": up_name, "uid": uid, "status": "error", "error": str(exc)})
                if str(exc.code) in {"-352", "-412", "412"}:
                    report["blocked"] = True
                    report["fatal_error"] = str(exc)
                    break
            except Exception as exc:
                report["up_status"].append({"up": up_name, "uid": uid, "status": "error", "error": str(exc)})
                time.sleep(1.2)

    report["finished_at"] = datetime.now(SHANGHAI).isoformat()
    report["today_video_count"] = len(report["videos"])
    report["subtitle_count"] = len(index_entries)
    (OUTPUT_DIR / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    index = {
        "schema_version": "public-crawl-preview/1.0",
        "date": TARGET_DATE,
        "generated_at": report["finished_at"],
        "total": len(index_entries),
        "entries": index_entries,
    }
    (OUTPUT_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"target_date": TARGET_DATE, "videos": len(report["videos"]), "subtitles": len(index_entries), "blocked": report["blocked"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
