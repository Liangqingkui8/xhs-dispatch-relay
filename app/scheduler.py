# encoding: utf-8
"""轮询调度：每账号独立轮询 unread，新消息/状态变化 → on_event 回调 → WS 推前端"""
import asyncio
import random
from typing import Callable, Dict, List

from .models import Event
from .auto_reply import AutoReply

# 轮询间隔（秒）：低频 + 随机 jitter，规避风控
POLL_MIN = 3.0
POLL_MAX = 5.0


class Scheduler:
    """每账号一个 asyncio 轮询任务"""

    def __init__(self, pool, on_event: Callable[[Event], None]):
        self.pool = pool
        self.on_event = on_event
        self.auto_reply = AutoReply(pool)
        self._last_unread: Dict[str, Dict[str, int]] = {}
        self._tasks: List[asyncio.Task] = []

    def _jitter(self) -> float:
        return random.uniform(POLL_MIN, POLL_MAX)

    async def _poll(self, name: str):
        acc = self.pool.get(name)
        if acc is None:
            return
        while True:
            try:
                unread = acc.get_unread()
                prev = self._last_unread.get(name, {})
                # 检测新消息（未读数上升的会话）
                for uid, count in unread.items():
                    if count > prev.get(uid, 0):
                        latest = self._pull_latest(acc, uid)
                        self.auto_reply.on_new_message(name, uid)
                        # 卡片未读 = 账号总未读（所有会话未读之和），不是单会话 count
                        total = sum(v for v in unread.values() if isinstance(v, int) and v > 0)
                        self.on_event(Event("message", name, {
                            "conversation": uid,
                            "unread": total,
                            "latest": latest,
                        }))
                self._last_unread[name] = unread
                # 账号仍在正常轮询，状态健康
                if acc.status != "online":
                    acc.status = "online"
                    self.on_event(Event("status", name, {"status": "online"}))
            except Exception as e:
                self.on_event(Event("status", name, {
                    "status": acc.status, "error": str(e)
                }))
            await asyncio.sleep(self._jitter())

    def _pull_latest(self, acc, uid: str) -> dict:
        """拉会话最新一条消息（单聊）。群聊 uid 形如 'group:xxx' 一期跳过"""
        if uid.startswith("group:"):
            return {}
        try:
            history = acc.history(uid, limit=5)
            if history:
                m = history[0]
                return {
                    "sender_id": m.get("sender_id"),
                    "content": m.get("content"),
                    "created_at": m.get("created_at"),
                    "nickname": m.get("nickname"),
                    "store_id": m.get("store_id"),
                }
        except Exception:
            pass
        return {}

    def start(self) -> None:
        for name in self.pool.names():
            self._tasks.append(asyncio.create_task(self._poll(name)))

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
