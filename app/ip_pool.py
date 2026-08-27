# encoding: utf-8
"""IP 出口池：账号 × 出口 映射。

一期：出口绑定在账号配置的 proxy 字段（accounts.json），这里只做出口格式归一 + 分配辅助。
二期：接肉鸡 frpc 出口（见 1688-new-jumpbox-deploy），做出口健康检查 + 自动切换。
"""
from typing import Dict, List, Optional


def resolve_proxy(proxy: Optional[str]) -> Optional[str]:
    """统一代理格式：'http://host:port' / 'host:port' → 'host:port'（WebSocket proxy_host 用）"""
    if not proxy:
        return None
    return proxy.replace("http://", "").replace("https://", "").strip("/")


def split_host_port(proxy: Optional[str]):
    """'host:port' → (host, port)"""
    if not proxy:
        return None, None
    host = resolve_proxy(proxy)
    if ":" in host:
        h, p = host.rsplit(":", 1)
        return h, int(p)
    return host, None


class IpPool:
    """出口池：维护出口列表 + 账号→出口分配。

    一期：从账号 proxy 字段读出口，无健康检查。
    """

    def __init__(self, proxies: List[str]):
        self._proxies = list(proxies)  # ["host:port", ...]

    def exits(self) -> List[str]:
        return list(self._proxies)

    def bind(self, account_name: str, index: int) -> Optional[str]:
        """按 index 轮转分配一个出口（超出则 None=直连）"""
        if not self._proxies:
            return None
        return self._proxies[index % len(self._proxies)]
