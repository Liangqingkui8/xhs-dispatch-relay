# encoding: utf-8
"""账号池：加载/持久化账号配置，管理 XhsAccount 实例"""
import json
import os
from typing import Dict, List, Optional

from .engine import XhsAccount
from .models import Account

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(BASE, "data", "accounts.json")


def load_accounts(path: str = DEFAULT_PATH) -> List[Account]:
    """从 accounts.json 加载账号配置"""
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [Account(**a) for a in raw]


def save_accounts(accounts: List[Account], path: str = DEFAULT_PATH) -> None:
    """持久化账号配置（含 verify 后回写的 user_id/nickname/status）"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([a.to_dict() for a in accounts], f, ensure_ascii=False, indent=2)


class AccountPool:
    """账号池：name → XhsAccount 实例 + 配置"""

    def __init__(self, accounts: List[Account]):
        self._configs: Dict[str, Account] = {a.name: a for a in accounts}
        self._instances: Dict[str, XhsAccount] = {
            a.name: XhsAccount(a.name, a.cookies, a.proxy) for a in accounts
        }

    def add(self, cfg: Account) -> XhsAccount:
        """运行时新增账号（登录流程用），返回实例"""
        self._configs[cfg.name] = cfg
        acc = XhsAccount(cfg.name, cfg.cookies, cfg.proxy)
        self._instances[cfg.name] = acc
        return acc

    def names(self) -> List[str]:
        return list(self._instances.keys())

    def get(self, name: str) -> Optional[XhsAccount]:
        return self._instances.get(name)

    def config(self, name: str) -> Optional[Account]:
        return self._configs.get(name)

    def verify_all(self) -> Dict[str, dict]:
        """校验所有账号，回写 config，返回 {name: {ok, user_id, nickname, error}}"""
        result = {}
        for name, acc in self._instances.items():
            try:
                me = acc.verify()
                cfg = self._configs[name]
                cfg.user_id = acc.user_id
                cfg.nickname = acc.nickname
                cfg.avatar = acc.avatar
                cfg.status = acc.status
                result[name] = {"ok": True, "user_id": acc.user_id,
                                "nickname": acc.nickname}
            except Exception as e:
                result[name] = {"ok": False, "error": str(e)}
        return result
