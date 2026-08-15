#!/usr/bin/env python3
"""Rebuild subtitle index.json files without rewriting unchanged indexes."""
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBTITLES = ROOT / "subtitles"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LEGACY_RE = re.compile(r"\s+\d{1,2}\.\d{1,2}\s+第\S+篇\.txt$")


def first_header(text, labels):
    for line in text.splitlines():
        for label in labels:
            if line.startswith(label):
                return line[len(label):].strip()
    return ""


def metadata(path):
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    up_name = first_header(text, ("UP主：", "UP主:"))
    title = first_header(text, ("标题：", "标题:"))
    if not up_name:
        up_name = LEGACY_RE.sub("", path.name).removesuffix(".txt")
    if not title:
        title = next((line.strip() for line in text.splitlines() if line.strip() and not line.startswith(("UP主：", "UP主:"))), path.stem)
    return {
        "source": path.name,
        "up_name": up_name,
        "title": title,
        "repository_path": path.relative_to(ROOT).as_posix(),
        "format": "txt",
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def main():
    changed = []
    SUBTITLES.mkdir(parents=True, exist_ok=True)
    for day in sorted(p for p in SUBTITLES.iterdir() if p.is_dir() and DATE_RE.match(p.name)):
        entries = [metadata(p) for p in sorted(day.glob("*.txt"), key=lambda x: x.name)]
        candidate = {
            "schema_version": "2.1",
            "date": day.name,
            "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "total": len(entries),
            "rejected": 0,
            "source_directory": f"subtitles/{day.name}",
            "entries": entries,
        }
        index_path = day / "index.json"
        old = None
        if index_path.exists():
            try:
                old = json.loads(index_path.read_text(encoding="utf-8"))
            except Exception:
                old = None
        comparable_old = {k: v for k, v in (old or {}).items() if k not in {"generated_at", "changed", "skipped"}}
        comparable_new = {k: v for k, v in candidate.items() if k != "generated_at"}
        if comparable_old != comparable_new:
            index_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed.append(day.name)
    print(json.dumps({"changed_dates": changed, "count": len(changed)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
