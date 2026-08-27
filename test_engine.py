# encoding: utf-8
"""M1 引擎封装验证：单账号 verify + 私信读接口。用法: python test_engine.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))

from engine import XhsAccount

def _load_test_account():
    """从 data/accounts.json 读第一个账号（真实凭据不入库，格式见 accounts.example.json）。"""
    import json
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "accounts.json")
    with open(path, encoding="utf-8") as f:
        acc = json.load(f)[0]
    return acc["name"], acc["cookies"]


def main():
    name, cookies = _load_test_account()
    acc = XhsAccount(name, cookies)
    me = acc.verify()
    print("[verify] OK:", me["nickname"], me["user_id"], "状态=", acc.status)

    convs = acc.list_conversations()
    print("[会话] 共", len(convs), "个:")
    for c in convs:
        uid = c.get("user_id") or c.get("id")
        name = c.get("nickname")
        print("   -", name, uid)

    unread = acc.get_unread()
    print("[未读]", unread)


if __name__ == "__main__":
    try:
        main()
        print("RESULT: PASS")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("RESULT: FAIL", type(e).__name__, str(e))
