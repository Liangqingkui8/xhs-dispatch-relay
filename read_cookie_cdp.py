# encoding: utf-8
"""通过 CDP 读 Edge 里 xiaohongshu.com 的 cookie（含 HttpOnly，浏览器内部已解密）。

用法: python read_cookie_cdp.py [--port 9222]
"""
import argparse
import json
import urllib.request

import websocket


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9222)
    args = ap.parse_args()

    # 1. 拿 page target
    targets = json.load(urllib.request.urlopen(
        f"http://127.0.0.1:{args.port}/json", timeout=10))
    page = next((t for t in targets if t.get("type") == "page"), None)
    if not page:
        print("NO_PAGE_TARGET")
        raise SystemExit(1)
    ws_url = page["webSocketDebuggerUrl"]

    # 2. 连 WebSocket，读所有 cookie
    ws = websocket.create_connection(ws_url, timeout=15)
    ws.send(json.dumps({"id": 1, "method": "Network.getAllCookies"}))
    data = json.loads(ws.recv())
    cookies = data.get("result", {}).get("cookies", [])
    ws.close()

    xhs = [c for c in cookies if "xiaohongshu.com" in c.get("domain", "")]
    by_name = {c["name"]: c["value"] for c in xhs}

    print(f"== 共 {len(xhs)} 条 xiaohongshu cookie ==")
    print("---- 完整串 ----")
    print("; ".join(f"{k}={v}" for k, v in sorted(by_name.items())))
    print("---- 关键字段 ----")
    for n in ("web_session", "id_token", "a1", "webId", "gid", "websectiga",
              "x-rednote-datactry", "x-rednote-holderctry", "abRequestId",
              "xsecappid", "sec_poison_id"):
        if n in by_name:
            print(f"{n}={by_name[n]}")


if __name__ == "__main__":
    main()
