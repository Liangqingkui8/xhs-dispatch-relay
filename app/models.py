# encoding: utf-8
"""数据模型：账号 / 消息 / 事件"""
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Account:
    """账号配置（持久化到 data/accounts.json）"""
    name: str                       # 账号名（卡片标识）
    cookies: str                    # 登录 cookie 字符串
    proxy: Optional[str] = None     # IP 出口 "host:port" 或 None=直连
    user_id: Optional[str] = None   # verify 后填充
    nickname: Optional[str] = None
    avatar: Optional[str] = None    # verify 后填充（账号头像）
    status: str = "offline"         # offline/online/rate_limited/banned
    reply_text: Optional[str] = None  # 私信自动回复话术，空=不自动回复

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class Message:
    """一条私信消息（结构化，来自 history/unread）"""
    sender_id: str
    content: str
    created_at: Optional[str] = None
    store_id: Optional[int] = None
    message_id: Optional[str] = None
    conversation: Optional[str] = None  # 会话对方 uid
    account: Optional[str] = None       # 哪个账号收到的
    nickname: Optional[str] = None


@dataclass
class Event:
    """调度器 → WS → 前端 的事件"""
    type: str                        # message / status / send_ack
    account: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type, "account": self.account, "data": self.data}
