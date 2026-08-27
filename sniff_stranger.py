# encoding: utf-8
"""抓小红书网页版 im 页面的陌生消息接口。
用 playwright 注入账号登录态，导航到消息中心，抓所有 /api/ 请求路径。
"""
import json
import sys

from playwright.sync_api import sync_playwright

accs = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "accounts.json"), encoding="utf-8"))
iooo = accs[0]  # 用 data/accounts.json 第一个账号

# 解析 cookie 串
pairs = {}
for kv in iooo["cookies"].split(";"):
    kv = kv.strip()
    if "=" in kv:
        k, v = kv.split("=", 1)
        pairs[k] = v

cookies = []
for k, v in pairs.items():
    cookies.append({
        "name": k, "value": v,
        "domain": ".xiaohongshu.com", "path": "/",
        "httpOnly": True, "secure": True, "sameSite": "Lax",
    })

seen = set()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context()
    ctx.add_cookies(cookies)
    page = ctx.new_page()

    def on_req(req):
        url = req.url
        if "/api/" in url and ("im" in url or "sns" in url):
            if url not in seen:
                seen.add(url)
                print("REQ", req.method, url[:220])

    page.on("request", on_req)

    # 导航到消息中心
    for url in [
        "https://www.xiaohongshu.com/im",
        "https://www.xiaohongshu.com/im/stranger",
        "https://www.xiaohongshu.com/message",
    ]:
        try:
            print(f"\n==== 导航 {url} ====")
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(5000)
            print("title:", page.title())
        except Exception as e:
            print("导航异常", str(e)[:120])

    browser.close()

print("\n== 去重后接口清单 ==")
for s in sorted(seen):
    print(s)
