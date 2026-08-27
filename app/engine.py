# encoding: utf-8
"""薯管家 — 引擎层：封装 xhs-api 私信能力 + 账号×IP出口

依赖 xhs-api（npm 全局装），通过 sys.path 注入源码目录 import Python SDK。
每个 XhsAccount = 一个小红书账号，绑 cookie + 可选 IP 出口代理。

xhs-api 私信接口（已验证 2026-08-15）：
  - 读：list_conversations / get_unread / get_history（HTTP edith.xiaohongshu.com，走 proxies）
  - 写：send（WebSocket Rwp 协议，proxy 需手动透传）/ revoke / mark_read
"""
import os
import sys

# xhs-api 源码目录（npm 全局装）。可被环境变量 XHS_SDK_DIR 覆盖，便于部署到别的机器
_XHS_SDK_DIR = os.environ.get("XHS_SDK_DIR", "")  # 指向本地 xhs-api SDK 安装目录（开源版留空，由使用者通过环境变量配置）
if os.path.isdir(_XHS_SDK_DIR) and _XHS_SDK_DIR not in sys.path:
    sys.path.insert(0, _XHS_SDK_DIR)

from xhs_api import XHSClient
from xhs_api.errors import ApiError, CookieExpiredError, RateLimitedError
from xhs_api.sign import generate_x_rap_param


def make_proxies(proxy: str) -> dict:
    """'host:port' 或 'http://host:port' → requests proxies dict（HTTP 读接口用）"""
    if not proxy:
        return None
    if "://" not in proxy:
        proxy = "http://" + proxy
    return {"http": proxy, "https": proxy}


class XhsAccount:
    """单个小红书账号：绑 cookie + 代理，封装私信读写 + 状态机"""

    def __init__(self, name: str, cookies: str, proxy: str = None):
        self.name = name
        self.cookies = cookies
        self.proxy = proxy  # "host:port" 或 None
        self.client = XHSClient(cookies=cookies, proxies=make_proxies(proxy))
        self.me = None                # verify 后 {user_id, nickname}
        self.user_id = None
        self.nickname = None
        self.avatar = None            # verify 后填充（账号头像）
        self.status = "offline"       # offline / online / rate_limited / banned

    # ---- 登录 / 校验 ----
    def verify(self) -> dict:
        """校验 cookie，成功置 online；失败按异常归类状态"""
        try:
            self.me = self.client.verify()
            self.user_id = self.me.get("user_id")
            self.nickname = self.me.get("nickname")
            self.avatar = self._fetch_avatar()
            self.status = "online"
            return self.me
        except CookieExpiredError:
            self.status = "banned"
            raise
        except RateLimitedError:
            self.status = "rate_limited"
            raise
        except ApiError:
            self.status = "rate_limited"
            raise

    def _fetch_avatar(self) -> str:
        """从 me 接口拿账号头像（多候选字段兜底），失败返回空串"""
        try:
            j = self.client._http._request("GET", "/api/sns/web/v2/user/me")
            d = j.get("data") or {}
            for k in ("avatar", "avatar_url", "image", "images"):
                v = d.get(k)
                if v:
                    return v if isinstance(v, str) else str(v)
        except Exception:
            pass
        return ""

    # ---- 私信只读 ----
    def list_conversations(self):
        """会话列表（含陌生消息）。

        旧接口 get_recent_chats（/api/sns/v1/im/web/get_recent_chats）只返回
        正常会话，会把未互关的陌生人消息过滤掉；网页版消息页实际用的是
        /api/im/web/v3/chats，返回完整会话（含陌生消息），follow_status 区分关系。
        这里走 v3/chats 并归一成前端字段（user_id/nickname/image）。
        """
        j = self.client._http._request(
            "GET", "/api/im/web/v3/chats",
            params={"limit": 100, "complete": True, "page": 0, "source": "pc"})
        # 未读数 {user_id: count}，合并到会话项供前端显示小红字
        unread = {}
        try:
            unread = self.client.get_unread() or {}
        except Exception:
            pass
        out = []
        for ch in j.get("data", {}).get("chats", []):
            info = ch.get("info") or {}
            uid = ch.get("chat_user_id")
            out.append({
                "user_id": uid,
                "nickname": info.get("nickname"),
                "image": info.get("avatar"),
                "last_msg_content": ch.get("last_msg_content"),
                "last_msg_time": ch.get("last_msg_time"),
                "max_store_id": ch.get("max_store_id"),
                "follow_status": info.get("follow_status"),
                "is_friend": info.get("is_friend"),
                "unread": unread.get(str(uid), unread.get(uid, 0)),
            })
        return out

    def get_unread(self) -> dict:
        """未读数 {user_id: count, 'group:群id': count}"""
        return self.client.get_unread()

    def history(self, uid: str, group: bool = False, limit: int = 30):
        """拉一页消息历史（结构化 dict 列表，最新在前）"""
        return self.client.get_history(uid, group=group, limit=limit)

    # ---- 私信写 ----
    def send(self, receiver: str, content: str, group: bool = False) -> str:
        """发一条私信，返回 message_id。WS 写走 proxy_host（socks5 隧道透传）。"""
        from xhs_api.ws_client import send_message as _ws_send
        me = self.client.me
        return _ws_send(
            self.client._http, me["user_id"], receiver, content,
            me.get("nickname") or "",
            content_type=1, group_chat=group,
            proxy_host=self.proxy)

    def revoke(self, message_id: str, group: bool = False) -> bool:
        return self.client.revoke(message_id, group=group)

    def mark_read(self, uid: str, last_store_id: int, group: bool = False) -> bool:
        return self.client.mark_read(uid, last_store_id, group=group)

    # ---- 内容只读（转 PcApi，已逆向验证） ----
    def search_notes(self, query: str, page: int = 1, **kwargs):
        """搜索笔记。sort_type: 0综合 1最新 2最多赞 3最多评论 4最多收藏"""
        return self.client.pc.search_notes(query, page, **kwargs)

    def search_users(self, query: str, page: int = 1):
        """搜索用户"""
        return self.client.pc.search_users(query, page)

    def note_info(self, url: str):
        """笔记详情（传 explore URL，含 xsec_token）"""
        return self.client.pc.note_info(url)

    def note_comments(self, note_id: str, cursor: str = "", xsec_token: str = ""):
        """评论列表（一页）"""
        return self.client.pc.note_comments(note_id, cursor, xsec_token)

    def user_notes(self, user_id: str, cursor: str = "", xsec_token: str = ""):
        """用户主页笔记列表（一页）"""
        return self.client.pc.user_posted(user_id, cursor, xsec_token, "pc_user")

    def user_profile(self, user_id: str):
        """用户资料（粉丝/关注/笔记数）"""
        return self.client.pc.user_info(user_id)

    # ---- 互动消息（消息中心） ----
    def notifications(self, tab: str, cursor: str = ""):
        """消息中心三类：mentions 评论和@ / likes 赞和收藏 / connections 新增关注"""
        if tab == "mentions":
            return self.client.pc.mentions(cursor)
        if tab == "likes":
            return self.client.pc.likes_collects(cursor)
        if tab == "connections":
            return self.client.pc.new_connections(cursor)
        raise ValueError(f"未知消息类型: {tab}")

    # ---- 内容写（逆向接口，2026-08-15） ----
    def like(self, note_id: str):
        """点赞。返回 data（含 new_like: 是否首次点赞）"""
        return self.client.pc._post("/api/sns/web/v1/note/like",
                                    {"note_oid": note_id}).get("data")

    def collect(self, note_id: str):
        """收藏笔记。返回是否成功"""
        return self.client.pc._post("/api/sns/web/v1/note/collect",
                                    {"note_id": note_id}).get("success")

    def follow(self, user_id: str):
        """关注用户。返回 data（含 fstatus）"""
        return self.client.pc._post("/api/sns/web/v1/user/follow",
                                    {"target_user_id": user_id}).get("data")

    def unfollow(self, user_id: str):
        """取消关注"""
        return self.client.pc._post("/api/sns/web/v1/user/unfollow",
                                    {"target_user_id": user_id}).get("data")

    def comment(self, note_id: str, content: str, parent_comment_id: str = None):
        """发评论/回复评论。回复时带 parent_comment_id（回复的一级评论 id）。需 x-rap-param 头。"""
        body = {"note_id": note_id, "content": content}
        if parent_comment_id:
            body["parent_comment_id"] = parent_comment_id
        headers = {"x-rap-param": generate_x_rap_param(
            "/api/sns/web/v1/comment/post", body)}
        return self.client.pc._post("/api/sns/web/v1/comment/post", body,
                                    extra_headers=headers).get("data")

    # ---- 发布笔记（图文，creator API 现成） ----
    def publish_note(self, title: str, desc: str = "", images: list = None,
                     topics: list = None, location: str = None):
        """发布图文笔记。images=[bytes]（≤15 张）。privacy_type 0=公开（默认值 1 是私密，坑）。"""
        return self.client.creator.publish(
            title=title, desc=desc, media_type="image",
            images=images, topics=topics, location=location,
            privacy_type=0)

    # ---- 数据看板（creator 数据中心，2026-08-15） ----
    def note_analysis_list(self, type: int = 0, page_size: int = 20, page_num: int = 1):
        """笔记数据列表。每篇含 id/title/post_time/imp_count 曝光/read_count 观看/
        coverClickRate 封面点击率/like_count/comment_count/fav_count 收藏/
        share_count 分享/view_time_avg 人均观看秒/increase_fans_count 涨粉/
        audit_status 审核状态/cover_url 封面"""
        return self.client.creator.note_analysis_list(type, page_size, page_num)
