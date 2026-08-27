# encoding: utf-8
"""抓小红书笔记页的写操作接口：点赞/收藏/关注。

用 playwright 注入账号登录态，打开笔记页，真实点按钮，抓 POST 请求。
"""
import json
import os

from playwright.sync_api import sync_playwright

# 目标笔记凭据走环境变量注入，不入库（开源版占位）
NOTE_ID = os.environ.get("NOTE_ID", "<note-id>")
XSEC = os.environ.get("XSEC_TOKEN", "<xsec-token>")
NOTE_URL = f"https://www.xiaohongshu.com/explore/{NOTE_ID}?xsec_token={XSEC}&xsec_source=pc_search"

accs = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "accounts.json"), encoding="utf-8"))
iooo = accs[0]  # 用 data/accounts.json 第一个账号

pairs = {}
for kv in iooo["cookies"].split(";"):
    kv = kv.strip()
    if "=" in kv:
        k, v = kv.split("=", 1)
        pairs[k] = v
cookies = [{"name": k, "value": v, "domain": ".xiaohongshu.com",
            "path": "/", "httpOnly": True, "secure": True, "sameSite": "Lax"}
           for k, v in pairs.items()]

captured = []


def dump_req(req):
    if "/api/" in req.url:
        info = f"{req.method} {req.url}"
        if req.method == "POST":
            try:
                info += f"\n    body: {req.post_data}"
            except Exception:
                pass
        print(info)
        captured.append(info)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context()
    ctx.add_cookies(cookies)
    page = ctx.new_page()
    page.on("request", dump_req)

    print(f"==== 打开笔记页 {NOTE_URL} ====")
    try:
        page.goto(NOTE_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(6000)
    except Exception as e:
        print("导航异常", str(e)[:120])

    # 探按钮：打印页面上可点的互动元素
    probe = page.evaluate("""() => {
        const out = [];
        const sels = [
            '.like-wrapper', '[class*="like"]', '[class*="collect"]',
            '[class*="favorite"]', '[class*="follow"]', '.interact'
        ];
        for (const s of sels) {
            document.querySelectorAll(s).forEach((el, i) => {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) {
                    out.push({sel: s, cls: el.className, txt: (el.textContent||'').trim().slice(0,20)});
                }
            });
        }
        return out.slice(0, 30);
    }""")
    print("\n== 互动元素 ==\n", json.dumps(probe, ensure_ascii=False, indent=1))

    browser.close()

print("\n\n==== 捕获的 API 请求（去重） ====")
for s in dict.fromkeys(captured):
    print(s)
