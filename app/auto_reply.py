# encoding: utf-8
"""私信自动回复：轮询到新未读 → 延迟随机 10~30s 回一句话术。

最小实现（用户拍板，不接 DeepSeek / 状态机 / 关键词规则）：
  1. 轮询 unread 检测到某会话未读数上升 → 触发 on_new_message
  2. 去重：每账号每会话只回一次（已回 uid 持久化到 data/replied.json，防重启后重复骚扰）
  3. 延迟：随机 10~30s 后回，模拟真人（不秒回）
  4. 话术：账号配置 reply_text（含微信号），空=不自动回复

客户私信 → 回"哈哈我平时不咋在线，卫XXX" → 客户自己去加微信，不追问。
"""
import asyncio
import json
import os
import random

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPLIED_PATH = os.path.join(BASE, "data", "replied.json")

DELAY_MIN = 10.0
DELAY_MAX = 30.0


class AutoReply:
    """每个账号一个延迟回复调度，挂在 Scheduler 的 unread 轮询上"""

    def __init__(self, pool):
        self.pool = pool
        self._replied = self._load()          # {name: [uid, ...]}
        self._pending = set()                 # 已投递未回复的 name:uid，防轮询重复投递

    def _load(self) -> dict:
        if os.path.isfile(REPLIED_PATH):
            try:
                with open(REPLIED_PATH, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(REPLIED_PATH), exist_ok=True)
        with open(REPLIED_PATH, "w", encoding="utf-8") as f:
            json.dump(self._replied, f, ensure_ascii=False, indent=2)

    def reply_text(self, name: str) -> str:
        cfg = self.pool.config(name)
        return (cfg.reply_text or "").strip() if cfg else ""

    def on_new_message(self, name: str, uid: str) -> None:
        """轮询到某会话有新的对方消息时调用（uid = 对方 user_id）"""
        text = self.reply_text(name)
        if not text:
            return                       # 没配话术
        if uid.startswith("group:"):
            return                       # 群聊一期跳过
        if uid in self._replied.get(name, []):
            return                       # 这个会话已经回过
        key = f"{name}:{uid}"
        if key in self._pending:
            return                       # 已投递待回，别再重复
        self._pending.add(key)
        asyncio.create_task(self._reply_later(name, uid))

    async def _reply_later(self, name: str, uid: str) -> None:
        key = f"{name}:{uid}"
        try:
            await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            acc = self.pool.get(name)
            text = self.reply_text(name)
            if acc is None or not text:
                return
            acc.send(uid, text)
            self._replied.setdefault(name, []).append(uid)
            self._save()
            print(f"[auto_reply] {name} -> {uid} 已回: {text[:20]}...")
        except Exception as e:
            print(f"[auto_reply] {name} -> {uid} 回复失败: {e}")
        finally:
            self._pending.discard(key)
