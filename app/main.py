# encoding: utf-8
"""薯管家 — FastAPI 入口：账号 API + WS 推流 + 静态 WebUI"""
import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .accounts import AccountPool, load_accounts, save_accounts
from .engine import XhsAccount
from .models import Account, Event
from .scheduler import Scheduler
from .ws import WsManager

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE, "web")

pool: AccountPool = None
scheduler: Scheduler = None
ws_manager = WsManager()


def on_event(event: Event) -> None:
    """调度器同步回调 → 异步广播到前端"""
    try:
        asyncio.get_running_loop().create_task(ws_manager.broadcast(event))
    except RuntimeError:
        pass  # 无事件循环（如测试时）


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool, scheduler
    accs = load_accounts()
    pool = AccountPool(accs)
    result = pool.verify_all()
    print("[startup] 账号校验:", result)
    scheduler = Scheduler(pool, on_event)
    scheduler.start()
    yield
    await scheduler.stop()


app = FastAPI(lifespan=lifespan)


# ---------- 账号 ----------
@app.get("/api/accounts")
async def get_accounts():
    out = []
    for n in pool.names():
        cfg = pool.config(n)
        unread = 0
        try:
            un = pool.get(n).get_unread() or {}
            unread = sum(v for v in un.values() if isinstance(v, int) and v > 0)
        except Exception:
            pass
        out.append({"name": cfg.name, "nickname": cfg.nickname,
                    "user_id": cfg.user_id, "avatar": cfg.avatar,
                    "proxy": cfg.proxy, "status": cfg.status,
                    "reply_text": cfg.reply_text or "", "unread": unread})
    return out


# ---------- IP 出口池（登录用） ----------
def load_exits() -> List[dict]:
    """读 data/exits.json，返回出口列表（每个含 proxy_url 完整代理地址）"""
    path = os.path.join(BASE, "data", "exits.json")
    with open(path, encoding="utf-8") as f:
        j = json.load(f)
    jb = j.get("jumpbox", {})
    out = []
    for e in j.get("exits", []):
        proxy_url = f"http://{jb['user']}:{jb['pass']}@{jb['ip']}:{e['proxy_port']}"
        out.append({**e, "proxy_url": proxy_url})
    return out


def find_exit(exit_name: str) -> dict:
    for e in load_exits():
        if e["name"] == exit_name:
            return e
    return None


@app.get("/api/exits")
async def get_exits():
    """出口池列表 + 空闲状态（被某账号 proxy 占用 = 不空闲）"""
    exits = load_exits()
    used = {pool.config(n).proxy for n in pool.names() if pool.config(n).proxy}
    out = []
    for e in exits:
        out.append({"name": e["name"], "cloud_ip": e["cloud_ip"],
                    "proxy_url": e["proxy_url"],
                    "free": e["proxy_url"] not in used})
    return out


class LoginBody(BaseModel):
    name: str        # 账号名（卡片标识）
    exit_name: str   # 出口名（云1~云5），空 = 直连


def _blocking_login(name: str, proxy_url: str):
    from .login import capture_login
    return capture_login(proxy_url, timeout_min=5)


@app.post("/api/login")
async def login(body: LoginBody):
    """扫码登录：起可见浏览器（走所选出口），扫码成功 → 存 cookie + proxy 到 accounts.json"""
    if not body.name.strip():
        raise HTTPException(400, "账号名不能为空")
    if pool.config(body.name.strip()):
        raise HTTPException(400, f"账号 [{body.name.strip()}] 已存在")

    proxy_url = None
    if body.exit_name:
        e = find_exit(body.exit_name)
        if not e:
            raise HTTPException(400, f"出口 [{body.exit_name}] 不存在")
        proxy_url = e["proxy_url"]

    # playwright 同步阻塞，放线程池跑，别卡事件循环（WS 推流还要活）
    ok, cookie_str, msg = await asyncio.to_thread(_blocking_login, body.name, proxy_url)
    if not ok:
        raise HTTPException(400, msg)

    acc = XhsAccount(body.name.strip(), cookie_str, proxy_url)
    try:
        acc.verify()
    except Exception as e:
        raise HTTPException(400, f"登录成功但 cookie 校验失败: {e}")

    cfg = Account(name=body.name.strip(), cookies=cookie_str, proxy=proxy_url,
                  user_id=acc.user_id, nickname=acc.nickname,
                  avatar=acc.avatar, status=acc.status)
    pool.add(cfg)
    save_accounts([pool.config(n) for n in pool.names()])
    return {"ok": True, "name": cfg.name, "nickname": cfg.nickname,
            "user_id": cfg.user_id, "proxy": proxy_url}


# ---------- 私信读 ----------
@app.get("/api/conversations/{name}")
async def get_conversations(name: str):
    acc = pool.get(name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    return acc.list_conversations()


@app.get("/api/history/{name}/{uid}")
async def get_history(name: str, uid: str):
    acc = pool.get(name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    return acc.history(uid, limit=30)


# ---------- 私信写 ----------
class SendBody(BaseModel):
    name: str
    receiver: str
    content: str


@app.post("/api/send")
async def send(body: SendBody):
    acc = pool.get(body.name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        mid = acc.send(body.receiver, body.content)
        return {"ok": True, "message_id": mid}
    except Exception as e:
        raise HTTPException(500, f"发送失败: {e}")


class MarkReadBody(BaseModel):
    name: str
    user_id: str
    last_store_id: int = 0


class SetReplyBody(BaseModel):
    name: str
    reply_text: str = ""


@app.post("/api/set_reply")
async def set_reply(body: SetReplyBody):
    """配置某账号的私信自动回复话术，空串=关闭自动回复"""
    cfg = pool.config(body.name)
    if not cfg:
        raise HTTPException(404, "账号不存在")
    cfg.reply_text = body.reply_text.strip() or None
    save_accounts([pool.config(n) for n in pool.names()])
    return {"ok": True, "reply_text": cfg.reply_text or ""}


@app.post("/api/mark_read")
async def mark_read(body: MarkReadBody):
    acc = pool.get(body.name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        ok = acc.mark_read(body.user_id, body.last_store_id)
        return {"ok": ok}
    except Exception as e:
        raise HTTPException(500, f"标记已读失败: {e}")


# ---------- 内容读 ----------
@app.get("/api/search/{name}")
async def search(name: str, q: str, type: str = "notes", page: int = 1):
    acc = pool.get(name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        if type == "users":
            return acc.search_users(q, page)
        return acc.search_notes(q, page)
    except Exception as e:
        raise HTTPException(500, f"搜索失败: {e}")


@app.get("/api/note/{name}")
async def note(name: str, url: str):
    acc = pool.get(name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        return acc.note_info(url)
    except Exception as e:
        raise HTTPException(500, f"笔记失败: {e}")


@app.get("/api/comments/{name}")
async def comments(name: str, note_id: str, cursor: str = "", xsec_token: str = ""):
    acc = pool.get(name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        return acc.note_comments(note_id, cursor, xsec_token)
    except Exception as e:
        raise HTTPException(500, f"评论失败: {e}")


@app.get("/api/user_notes/{name}")
async def user_notes(name: str, user_id: str, xsec_token: str = "", cursor: str = ""):
    acc = pool.get(name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        return acc.user_notes(user_id, cursor, xsec_token)
    except Exception as e:
        raise HTTPException(500, f"主页失败: {e}")


@app.get("/api/user/{name}")
async def user_profile(name: str, user_id: str):
    acc = pool.get(name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        return acc.user_profile(user_id)
    except Exception as e:
        raise HTTPException(500, f"资料失败: {e}")


@app.get("/api/note_analysis/{name}")
async def note_analysis(name: str, page_size: int = 20, page_num: int = 1):
    acc = pool.get(name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        return acc.note_analysis_list(0, page_size, page_num)
    except Exception as e:
        raise HTTPException(500, f"数据拉取失败: {e}")


@app.get("/api/note_analysis_all")
async def note_analysis_all():
    """汇总所有账号的笔记数据（数据总览用），每行带 account 字段"""
    out = []
    for n in pool.names():
        acc = pool.get(n)
        try:
            rows = acc.note_analysis_list(0, 100, 1)
        except Exception:
            rows = []
        for r in rows:
            r["account"] = n
            out.append(r)
    return out


@app.get("/api/notifications/{name}")
async def notifications(name: str, tab: str = "mentions", cursor: str = ""):
    acc = pool.get(name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        return acc.notifications(tab, cursor)
    except Exception as e:
        raise HTTPException(500, f"消息失败: {e}")


# ---------- 内容写 ----------
class ActionBody(BaseModel):
    name: str
    note_id: str = ""
    user_id: str = ""
    content: str = ""
    parent_comment_id: str = ""


@app.post("/api/like")
async def like(body: ActionBody):
    acc = pool.get(body.name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        return {"ok": True, "data": acc.like(body.note_id)}
    except Exception as e:
        raise HTTPException(500, f"点赞失败: {e}")


@app.post("/api/collect")
async def collect(body: ActionBody):
    acc = pool.get(body.name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        return {"ok": True, "success": acc.collect(body.note_id)}
    except Exception as e:
        raise HTTPException(500, f"收藏失败: {e}")


@app.post("/api/follow")
async def follow(body: ActionBody):
    acc = pool.get(body.name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        return {"ok": True, "data": acc.follow(body.user_id)}
    except Exception as e:
        raise HTTPException(500, f"关注失败: {e}")


@app.post("/api/unfollow")
async def unfollow(body: ActionBody):
    acc = pool.get(body.name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        return {"ok": True, "data": acc.unfollow(body.user_id)}
    except Exception as e:
        raise HTTPException(500, f"取关失败: {e}")


@app.post("/api/comment")
async def comment(body: ActionBody):
    acc = pool.get(body.name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        return {"ok": True, "data": acc.comment(body.note_id, body.content,
                                                body.parent_comment_id or None)}
    except Exception as e:
        raise HTTPException(500, f"评论失败: {e}")


# ---------- 发布笔记 ----------
@app.post("/api/publish")
async def publish_note(
    name: str = Form(...),
    title: str = Form(...),
    desc: str = Form(""),
    topics: str = Form(""),
    location: str = Form(""),
    images: List[UploadFile] = File(...),
):
    acc = pool.get(name)
    if not acc:
        raise HTTPException(404, "账号不存在")
    try:
        imgs = [await f.read() for f in images]
        topic_list = [t.strip() for t in topics.split(",") if t.strip()] or None
        loc = location.strip() or None
        result = acc.publish_note(title, desc, imgs, topic_list, loc)
        return {"ok": True, "data": result}
    except Exception as e:
        raise HTTPException(500, f"发布失败: {e}")


# ---------- WebSocket 推流 ----------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    ws_manager.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.remove(ws)


# ---------- 静态 WebUI ----------
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")


@app.get("/")
async def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))
