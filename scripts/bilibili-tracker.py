#!/usr/bin/env python3
"""B站UP主视频追踪 + AI字幕提取（cookie过期自动刷新）"""
import requests, json, os, hashlib, time, sys
from datetime import datetime

try:
    import browser_cookie3
except ImportError:
    browser_cookie3 = None
from urllib.parse import urlencode
from bilibili_api import user, sync

UP_MASTERS = {
    "趋势天哥": 1372241958,
    "奇点财情": 336730296,
    "财经高一截": 269571531,
    "趋势风哥": 613230878,
    "邪修炒股笔记": 3546826766551823,
    "老柯复盘": 3546635351099881,
    "老丁逃顶": 1665414890,
    "笨笨的韭菜": 11473291,
    "小白投资笔记": 1221628467,
    "逻辑哥复盘": 433280310,
    "李长胜621": 19239427,
    "莫大韭菜": 525121722,
    "研报平权": 1646212867,
    "美股研报cc": 3706976613697550,
}
DATA_DIR = os.path.expanduser(os.environ.get("BILI_DATA_DIR", "~/.hermes/data/bilibili"))
STATE_FILE = os.path.join(DATA_DIR, "processed.json")
COOKIE_FILE = os.path.expanduser(os.environ.get("BILI_COOKIE_FILE", os.path.join(DATA_DIR, "cookies.json")))
REPORT_DIR = os.path.expanduser(os.environ.get("HERMES_REPORT_DIR", "~/Desktop/hermes/研报"))
SUBTITLE_DIR = os.path.expanduser(os.environ.get("HERMES_SUBTITLE_DIR", os.path.join(REPORT_DIR, "字幕")))
VIDEOS_PER_UP = int(os.environ.get("BILI_VIDEOS_PER_UP", "10"))
CUTOFF_DATE = os.environ.get("BILI_CUTOFF_DATE", "2026-05-28")  # 可由环境变量覆盖

MIXIN_ENC = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36', 'Referer': 'https://www.bilibili.com'}

os.makedirs(DATA_DIR, exist_ok=True)

_sessdata = None
_mixin_key = None
_sessdata_tried_refresh = False

def refresh_sessdata():
    """自动从Chrome刷新cookie，成功则保存到文件"""
    global _sessdata
    if browser_cookie3 is None:
        return False
    try:
        cj = browser_cookie3.chrome(domain_name='bilibili.com')
        for c in cj:
            if c.name == 'SESSDATA' and c.value:
                _sessdata = c.value
                os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
                with open(COOKIE_FILE, 'w') as f:
                    json.dump({'SESSDATA': _sessdata}, f)
                return True
    except:
        pass
    return False

def get_sessdata():
    global _sessdata
    if _sessdata is None:
        _sessdata = os.environ.get("BILI_SESSDATA", "").strip()
        if not _sessdata and os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE) as f:
                _sessdata = json.load(f).get("SESSDATA", "")
        if not _sessdata:
            refresh_sessdata()
    return _sessdata

def get_mixin_key():
    global _mixin_key
    if _mixin_key is None:
        nav = requests.get('https://api.bilibili.com/x/web-interface/nav', headers=HEADERS).json()
        img = nav['data']['wbi_img']['img_url'].split('/')[-1].split('.')[0]
        sub = nav['data']['wbi_img']['sub_url'].split('/')[-1].split('.')[0]
        _mixin_key = ''.join((img+sub)[i] for i in MIXIN_ENC)[:32]
    return _mixin_key

def wbi_sign(params):
    mk = get_mixin_key()
    sorted_str = '&'.join(f'{k}={params[k]}' for k in sorted(params.keys()))
    return hashlib.md5((sorted_str + mk).encode()).hexdigest()

def fetch_videos(uid):
    """用bilibili-api获取视频列表（它处理wbi）"""
    u = user.User(uid)
    data = sync(u.get_media_list(ps=VIDEOS_PER_UP))
    results = []
    for v in data.get("media_list", []):
        pubtime = v.get("pubtime", 0)
        results.append({
            "bvid": v.get("bv_id", ""),
            "title": v.get("title", ""),
            "pubtime": pubtime,
            "pubdate": datetime.fromtimestamp(pubtime).strftime("%m-%d") if pubtime else "?",
            "date": datetime.fromtimestamp(pubtime).strftime("%Y-%m-%d") if pubtime else datetime.now().strftime("%Y-%m-%d"),
        })
    return results

def fetch_subtitle(bvid):
    """用requests+login cookie获取AI字幕，cookie过期自动刷新重试"""
    global _sessdata_tried_refresh
    sessdata = get_sessdata()
    if not sessdata:
        print(f"[WARN] 缺少B站登录态，无法抓取 {bvid}", file=sys.stderr)
        return None
    try:
        r = requests.get(f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}',
                         headers=HEADERS, timeout=10)
        info = r.json()
        if info.get('code') != 0:
            return None
        aid = info['data']['aid']
        cid = info['data']['cid']
        
        params = {'aid': aid, 'cid': cid, 'wts': int(time.time())}
        params['w_rid'] = wbi_sign(params)
        query = '&'.join(f'{k}={params[k]}' for k in sorted(params.keys()))
        r2 = requests.get(f'https://api.bilibili.com/x/player/wbi/v2?{query}',
                          headers=HEADERS, cookies={'SESSDATA': sessdata}, timeout=10)
        pdata = r2.json()
        if pdata.get('code') != 0:
            return None
        
        # 检测cookie过期：need_login_subtitle=true 且 subtitles为空 → 自动刷新
        need_login = pdata.get('data', {}).get('need_login_subtitle', False)
        subs = pdata.get('data', {}).get('subtitle', {}).get('subtitles', [])
        if need_login and not subs and not _sessdata_tried_refresh:
            _sessdata_tried_refresh = True
            if refresh_sessdata():
                return fetch_subtitle(bvid)  # 用新cookie重试
        
        if not subs:
            return None
        
        sub_url = subs[0].get('subtitle_url', '')
        if sub_url.startswith('//'):
            sub_url = 'https:' + sub_url
        
        r3 = requests.get(sub_url, headers={'Referer': 'https://www.bilibili.com'}, timeout=10)
        body = r3.json().get('body', [])
        text = ' '.join(item.get('content', '') for item in body)
        return text if text else None
    except:
        return None

def save_subtitle_file(date_str, up_name, title, text):
    """保存完整原始字幕到文件"""
    dir_path = os.path.join(SUBTITLE_DIR, date_str)
    os.makedirs(dir_path, exist_ok=True)
    safe_title = title.replace("/", "-").replace(":", "：")[:50]
    filepath = os.path.join(dir_path, f"{up_name}-{safe_title}.txt")
    with open(filepath, 'w') as f:
        f.write(f"UP主：{up_name}\n标题：{title}\n日期：{date_str}\n\n{text}")
    return filepath

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def main():
    global _sessdata_tried_refresh
    state = load_state()
    new_videos = []
    _sessdata_tried_refresh = False
    cutoff_ts = datetime.strptime(CUTOFF_DATE, "%Y-%m-%d").timestamp()
    
    for name, uid in UP_MASTERS.items():
        videos = fetch_videos(uid)
        processed = set(state.get(str(uid), []))
        successful_bvids = []
        
        for v in videos:
            # 跳过5/28之前的视频
            if v["pubtime"] and v["pubtime"] < cutoff_ts:
                continue
            if v["bvid"] not in processed:
                v["up"] = name
                sub = fetch_subtitle(v["bvid"])
                v["subtitle"] = sub[:5000] if sub else None  # AI用截断版
                v["has_subtitle"] = sub is not None
                # 保存完整字幕到文件
                if sub:
                    save_subtitle_file(v["date"], name, v["title"], sub)
                    successful_bvids.append(v["bvid"])
                new_videos.append(v)
        
        # 只有字幕成功落盘才标记完成；B站AI字幕晚生成时，后续任务会继续补抓。
        state[str(uid)] = list(dict.fromkeys(list(processed) + successful_bvids))[-200:]
    
    save_state(state)
    
    print(json.dumps({
        "ts": datetime.now().isoformat(),
        "new_count": len(new_videos),
        "new_videos": new_videos,
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
