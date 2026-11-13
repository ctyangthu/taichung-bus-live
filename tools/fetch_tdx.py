#!/usr/bin/env python3
"""下載 TDX 臺中市公車靜態資料到 raw/。已存在的檔案會略過（加 --force 重抓）。

未登入的 TDX 每個 IP 一天只能查詢 20 次；設定環境變數 TDX_CLIENT_ID 與
TDX_CLIENT_SECRET（TDX 會員中心的 API 金鑰）就改用金鑰存取。
"""
import json, os, sys, urllib.parse, urllib.request, pathlib, gzip

BASE = "https://tdx.transportdata.tw/api/basic/v2/Bus/"
AUTH = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
CITY = "Taichung"
DATASETS = ["Route", "StopOfRoute", "Shape", "Schedule"]
RAW = pathlib.Path(__file__).resolve().parent.parent / "raw"


def token():
    cid, sec = os.environ.get("TDX_CLIENT_ID"), os.environ.get("TDX_CLIENT_SECRET")
    if not (cid and sec):
        return None
    body = urllib.parse.urlencode(
        {"grant_type": "client_credentials", "client_id": cid, "client_secret": sec}
    ).encode()
    with urllib.request.urlopen(urllib.request.Request(AUTH, data=body), timeout=30) as r:
        return json.load(r)["access_token"]


def get(name, tok):
    url = f"{BASE}{name}/City/{CITY}?%24format=JSON"
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"}
    if tok:
        headers["Authorization"] = "Bearer " + tok
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=180) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        print(f"  quota left today: {r.headers.get('x-ratelimit-remaining-day', '-')}")
        return data


def main():
    force = "--force" in sys.argv
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or DATASETS
    RAW.mkdir(exist_ok=True)
    tok = token()
    print("using TDX key" if tok else "anonymous access (20 requests a day)")
    for name in names:
        out = RAW / f"{name}.json"
        if out.exists() and not force:
            print(f"skip {name} (already downloaded)")
            continue
        print(f"fetch {name}")
        data = get(name, tok)
        json.loads(data)  # 確認是完整的 JSON 才寫檔
        out.write_bytes(data)
        print(f"  {len(data):,} bytes")


if __name__ == "__main__":
    main()
