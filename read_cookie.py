# encoding: utf-8
"""读 Edge 配置目录里的 xiaohongshu cookie（含 HttpOnly），DPAPI 解密导出。

用法: python read_cookie.py [--dir C:\\xhs-login-tmp]
"""
import argparse
import glob
import os
import shutil
import sqlite3

import win32crypt


def find_cookie_db(base: str):
    candidates = [
        os.path.join(base, "Default", "Network", "Cookies"),
        os.path.join(base, "Default", "Cookies"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    hits = glob.glob(os.path.join(base, "**", "Cookies"), recursive=True)
    return hits[0] if hits else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=r"C:\xhs-login-tmp")
    args = ap.parse_args()

    db = find_cookie_db(args.dir)
    if not db:
        print("NO_DB")
        raise SystemExit(1)

    tmp = db + ".readtmp"
    shutil.copy2(db, tmp)  # 拷贝避开浏览器锁
    conn = sqlite3.connect(tmp)
    conn.text_factory = bytes
    cur = conn.cursor()
    cur.execute("SELECT host_key, name, encrypted_value FROM cookies "
                "WHERE host_key LIKE '%xiaohongshu.com'")
    rows = cur.fetchall()
    conn.close()
    os.remove(tmp)

    out = []
    failed = []
    for host_b, name_b, enc in rows:
        host = host_b.decode("utf-8", "ignore")
        name = name_b.decode("utf-8", "ignore")
        try:
            val = win32crypt.CryptUnprotectData(enc, None, None, None, 0)[1]
            out.append((host, name, val.decode("utf-8", "ignore")))
        except Exception as e:
            failed.append((host, name, type(e).__name__))

    out.sort()
    print(f"== 解密成功 {len(out)} 条 / 失败 {len(failed)} 条 ==")
    if failed:
        for h, n, e in failed:
            print(f"[失败] {h}  {n}  ({e})")
        print("== 若全失败=Edge 用了 app-bound encryption，需走 CDP 方案 ==")
    print("---- 完整 cookie 串 ----")
    print("; ".join(f"{n}={v}" for _, n, v in out))
    print("---- 关键字段 ----")
    for _, n, v in out:
        if n in ("web_session", "id_token", "a1", "webId", "gid",
                 "websectiga", "x-rednote-datactry", "x-rednote-holderctry",
                 "abRequestId", "xsecappid"):
            print(f"{n}={v}")


if __name__ == "__main__":
    main()
