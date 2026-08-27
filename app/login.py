# encoding: utf-8
"""扫码登录 — 小红书账号注册入口（playwright 可见浏览器 + 云号 http 代理出口）

复用 1688 的 capture_login 思路，改成小红书：
  - 登录 URL = xhs 网页首页（未登录自动弹扫码）
  - 登录态金标准 = cookie 里 web_session + id_token 都非空
  - 出口 = http 代理（<user>:<pass>@<jumpbox-ip>:<port>）
  - 登录成功后返回 cookie 字符串（accounts.json 的 cookies 字段格式）

用法: 由 main.py 的 /api/login 调用（同步阻塞，扫码期间挂起该请求）。
"""
import sys
import time
from urllib.parse import urlparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LOGIN_URL = "https://www.xiaohongshu.com/explore"


def _fallback_launch(platform):
    """chrome → msedge → 系统 chromium 兜底"""
    for ch in ["chrome", "msedge"]:
        try:
            browser = platform.chromium.launch(
                channel=ch, headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            return browser
        except Exception:
            continue
    try:
        return platform.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
    except Exception:
        return None


def _split_proxy(proxy_url: str):
    """http://<user>:<pass>@<jumpbox-ip>:<port> → playwright proxy dict"""
    p = urlparse(proxy_url)
    server = f"{p.scheme}://{p.hostname}:{p.port}"
    return {"server": server, "username": p.username, "password": p.password}


def _has_login(cookies: list) -> bool:
    """小红书登录态金标准：web_session + id_token 都非空（缺一 = 未登录）"""
    has_ws = has_idt = False
    for c in cookies or []:
        if c.get("name") == "web_session" and (c.get("value") or "").strip():
            has_ws = True
        if c.get("name") == "id_token" and (c.get("value") or "").strip():
            has_idt = True
    return has_ws and has_idt


def _cookies_to_str(cookies: list) -> str:
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


def capture_login(proxy_url: str = None, timeout_min: int = 5):
    """
    打开可见浏览器（可选走云号出口），等用户扫码登录。
    返回 (ok: bool, cookie_str: str, msg: str)
    """
    from playwright.sync_api import sync_playwright

    pw = sync_playwright()
    platform = pw.start()
    browser = None
    try:
        browser = _fallback_launch(platform)
        if browser is None:
            return False, "", "浏览器启动失败（chrome/msedge/chromium 都起不来）"

        ctx_kwargs = dict(
            viewport={"width": 1280, "height": 900},
            locale="zh-CN", ignore_https_errors=True,
        )
        if proxy_url:
            ctx_kwargs["proxy"] = _split_proxy(proxy_url)
        context = browser.new_context(**ctx_kwargs)
        page = context.new_page()

        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass  # 加载慢/超时不致命，二维码照常弹

        print(f"[login] 浏览器已打开（出口 {proxy_url or '直连'}），"
              f"{timeout_min} 分钟内扫码完成，完成后自动保存", flush=True)

        deadline = time.time() + timeout_min * 60
        while time.time() < deadline:
            page.wait_for_timeout(2000)
            if page.is_closed() or not browser.is_connected():
                return False, "", "浏览器被关闭，登录未完成（cookie 未保存）"
            if _has_login(context.cookies()):
                page.wait_for_timeout(2000)  # 让 cookie 落定
                break

        cookies = context.cookies()
        if not cookies:
            return False, "", "没拿到任何 cookie，登录未完成"
        if not _has_login(cookies):
            return False, "", "未检测到登录态（可能没扫码就关了窗口）"
        cookie_str = _cookies_to_str(cookies)
        return True, cookie_str, f"登录成功（{len(cookies)} 条 cookie）"
    except Exception as e:
        return False, "", f"登录失败: {e}"
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass
        try:
            platform.stop()
        except Exception:
            pass


if __name__ == "__main__":
    # 手动测试: py app/login.py http://<user>:<pass>@<jumpbox-ip>:<port>
    p = sys.argv[1] if len(sys.argv) > 1 else None
    ok, cs, msg = capture_login(p)
    print("结果:", msg)
    if ok:
        print("cookie:", cs[:80], "...")
