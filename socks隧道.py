"""_socks_tunnel.py — 用 paramiko 在本地起 SOCKS5，走跳板机出网。

等价于 `ssh -D 1080 -N <user>@<jumpbox-host>`，但参数化密码、可后台跑。

加固（自动重连）:
  SSH transport 断了（跳板机网络抖动/重启）会自动重连，不再需要手动重启隧道。
  - is_active() 失效 → 下次请求前重连
  - open_channel 失败 → 立即标记断线，触发重连
  - 重连带指数退避（3s → 60s 封顶），不空转撞跳板机

用法: py _socks_tunnel.py [--port 1080] [--host <jumpbox-host>]
"""
import argparse
import select
import socket
import struct
import os
import threading
import sys
import time

import paramiko

# 出口凭据走环境变量注入，不入库（开源版占位）
DEFAULT_HOST = os.environ.get("TUNNEL_HOST", "")
USER = os.environ.get("TUNNEL_USER", "")
PASS = os.environ.get("TUNNEL_PASS", "")


class ReconnectTunnel:
    """SSH transport 封装：失效/断线时自动重连。"""

    def __init__(self, host):
        self.host = host
        self._cli = None
        self._transport = None
        self._lock = threading.Lock()

    def _dial(self):
        cli = paramiko.SSHClient()
        cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cli.connect(self.host, username=USER, password=PASS, timeout=25)
        tr = cli.get_transport()
        tr.set_keepalive(15)  # 15s 保活，断线更快被 is_active 捕捉
        return cli, tr

    def transport(self):
        """返回一个活的 transport；失效/断线时阻塞重连直到成功。"""
        with self._lock:
            tr = self._transport
            if tr is not None and tr.is_active():
                return tr
        # 断线 → 重连（指数退避，别死循环撞跳板机）
        backoff = 3
        while True:
            try:
                cli, tr = self._dial()
            except Exception as e:
                print(f"[隧道] 重连失败: {e}，{backoff}s 后重试", flush=True)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            with self._lock:
                old = self._cli
                self._cli = cli
                self._transport = tr
            if old is not None:
                try:
                    old.close()
                except Exception:
                    pass
            print(f"[隧道] SSH 已连接 {self.host}", flush=True)
            return tr

    def mark_broken(self):
        """open_channel 失败时调用：强制下次 transport() 走重连。"""
        with self._lock:
            if self._cli is not None:
                try:
                    self._cli.close()
                except Exception:
                    pass
            self._transport = None


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("对端提前断开")
        buf += chunk
    return buf


def _socks5_handshake(sock):
    """无认证 SOCKS5 握手，返回 (target_host, target_port)。"""
    ver, nmethods = _recv_exact(sock, 2)
    methods = _recv_exact(sock, nmethods)
    sock.sendall(b"\x05\x00")  # 选无认证
    ver, cmd, rsv, atyp = _recv_exact(sock, 4)
    if cmd != 1:  # 只支持 CONNECT
        sock.sendall(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")
        raise ConnectionError(f"不支持的命令 cmd={cmd}")
    if atyp == 1:  # IPv4
        host = socket.inet_ntoa(_recv_exact(sock, 4))
    elif atyp == 3:  # 域名
        ln = _recv_exact(sock, 1)[0]
        host = _recv_exact(sock, ln).decode("idna")
    elif atyp == 4:  # IPv6
        host = socket.inet_ntop(socket.AF_INET6, _recv_exact(sock, 16))
    else:
        raise ConnectionError(f"未知 atyp={atyp}")
    port = struct.unpack(">H", _recv_exact(sock, 2))[0]
    return host, port


def _handle(client, tunnel):
    try:
        client.settimeout(15)
        host, port = _socks5_handshake(client)
    except Exception:
        client.close()
        return

    tr = tunnel.transport()  # 确保 SSH 活
    try:
        chan = tr.open_channel(
            "direct-tcpip", (host, port), ("127.0.0.1", 0), timeout=15)
    except Exception:
        tunnel.mark_broken()  # transport 已废，下次请求强制重连
        try:
            client.sendall(b"\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00")
        except OSError:
            pass
        client.close()
        return

    client.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
    client.settimeout(None)
    chan.settimeout(0)

    # 双向转发，任一边关就收尾
    def one_way(src, dst):
        try:
            while True:
                r, _, _ = select.select([src], [], [], 60)
                if not r:
                    continue
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except (OSError, ConnectionError):
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    t1 = threading.Thread(target=one_way, args=(client, chan), daemon=True)
    t2 = threading.Thread(target=one_way, args=(chan, client), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    try:
        chan.close()
    except OSError:
        pass
    try:
        client.close()
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=1080)
    ap.add_argument("--host", default=DEFAULT_HOST)
    args = ap.parse_args()

    tunnel = ReconnectTunnel(args.host)
    tunnel.transport()  # 首次连接（失败会阻塞重试直到成功）

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", args.port))
    srv.listen(128)
    print(f"[隧道] SOCKS5 监听 127.0.0.1:{args.port}", flush=True)

    while True:
        try:
            client, _ = srv.accept()
        except OSError:
            break
        threading.Thread(target=_handle, args=(client, tunnel), daemon=True).start()


if __name__ == "__main__":
    main()
