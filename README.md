# 📮 xhs-dispatch-relay

![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-GPL--3.0-red)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6)
![RWP 协议](https://img.shields.io/badge/RWP%20Protocol-逆向-blueviolet)

**[English](README_EN.md) · [中文](README.md)**

**名下账号，一把梭。**

xhs-dispatch-relay 是管理你名下多个账号的一个项目：统一收件箱收发私信、关键词自动回复、多账号多出口调度、内容浏览、写操作、发布、数据总览，一个面板全干了。开一个号是养，开十个号是管，中间那摊脏活累活，它替你扛。

---

## ⚖️ 法律声明

本项目**仅供个人学习与学术研究**，作者不保证其可用性，也不对其任何使用后果负责。请遵守相关平台的服务条款与所在国家/地区的法律法规，因滥用导致的任何后果由使用者自行承担。转载 / 再分发必须保留作者署名与仓库链接（见底部协议）。

---

## ⚙️ 它能干的事

- **统一收件箱** — 多个账号的私信聚到一个面板，谁发你、聊到哪、回没回，一眼全清
- **私信收发** — send / list / history / unread / revoke，带会话历史
- **自动回复** — 按关键词命中即回，每个账号独立话术，不串味
- **多出口调度** — 每个账号走独立出口，断了自动换路，互不串台，一个号出事不拖累全家
- **断点续跑** — 跑一半崩了，从断点接着来，不白跑一趟
- **防白跑锁** — 一批全没命中也知道刹车，不闷头空转烧资源
- **内容浏览** — 搜索笔记/用户 → 详情 → 评论 → 主页 → 关注/私信
- **写操作** — 点赞 / 收藏 / 关注 / 发评论（自研逆向，见技术架构 6.3）
- **发布笔记** — 图文发布（标题/正文/话题/地点/多图）
- **数据总览** — KPI 卡 + 笔记明细，一个面板看全
- **扫码登录** — 浏览器扫码，cookie 自动落库，换号不折腾

---

## 🚀 快速上手

```bash
git clone https://github.com/Liangqingkui8/xhs-dispatch-relay
cd xhs-dispatch-relay
pip install -r requirements.txt

# 1. 配好账号和出口（复制模板，别提交真实凭据）
cp data/accounts.example.json data/accounts.json
cp data/exits.example.json data/exits.json

# 2. 起服务
python app/main.py
```

浏览器打开控制台，扫码登录，开干。

---

## 🏗️ 架构

**多账号 × 多出口的调度骨架**是它的核心，这套东西跟具体平台无关，抽出来能用在任何"账号多、出口多、怕串台"的场景：

```
xhs-dispatch-relay/
├── app/
│   ├── engine.py      # 单账号引擎：私信收发、登录态校验
│   ├── scheduler.py   # 多账号调度：独立出口、断线重连、互不串台
│   ├── auto_reply.py  # 关键词自动回复规则
│   ├── accounts.py    # 账号/出口配置管理
│   ├── login.py       # 扫码登录入口
│   └── main.py        # Web 控制台服务（FastAPI）
├── web/               # 前端面板（原生 HTML/JS + WebSocket）
└── data/              # 运行态数据（不入库，见 .example 模板）
```

三层：**展示层**（FastAPI + 原生前端 + WS 实时推）→ **调度层**（账号池×IP出口 + 轮询 + jitter + 封号检测）→ **引擎层**（私信引擎 + 签名引擎）。

方向是人力大脑，代码由 AI 辅助生成——架构怎么定、边界怎么划是人拍的，剩下的脏活交给工具。

---

## 🔒 安全说明

- `data/` 是运行态数据，真实账号凭据**绝不进版本库**（见 `.gitignore`，只提交 `.example` 模板）
- 云服务器 / 账号 / 出口凭据全部通过**环境变量注入**，不硬编码在代码里
- 技术架构中的运行态资产一律以占位符打码，只公开技术实现

---

# 📡 技术架构（逆向深度）

> ⚖️ **仅供个人学习与学术研究**。以下逆向与工程细节仅为技术研究记录，请遵守相关平台服务条款与所在地区法律法规，任何滥用后果由使用者自行承担。

> 小红书多账号调度与管理工具 · 技术深度沉淀
> 版本：一期（私信 + WebUI + 内容浏览 + 数据总览 + 封面生成）
> 更新：2026-08-16
> 本文档公开的是**技术实现细节**：协议逆向、签名算法、环境搭建、链路设计。所有接口/链路均已实测验活 PASS，标注处为实测结论。个人运行态资产（服务器 IP、账号凭据、本地路径）一律以 `<占位符>` 打码，不在此公开。

## 一、项目定位

这是为管理你名下多个账号开发的调度工具，能力四件套（**发布 / 评论 / 私信 / 实时消息**）。

核心价值聚焦在别人没有的两层（账号×IP出口调度 + WebUI 壳），底层引擎与协议逆向全部自研。真正难啃的部分（私信协议、签名算法、DeepSeek 网页版逆向）全部验活过，本文档把它们沉淀下来。

## 二、架构总览（三层）

```
┌─ 展示层(自研) ── FastAPI + 原生 HTML/JS + WebSocket 实时推 ── 红白卡片式 UI
├─ 调度层(自研) ── 账号池 × IP出口映射 + 轮询 + jitter + 封号检测 ── 独门
└─ 引擎层 ── 私信引擎(私信/采集/发布) + 签名引擎(签名兜底)
```

| 组件 | 角色 | 说明 |
|---|---|---|
| **私信引擎** | 主骨架 | Rwp 协议逆向，私信全套 |
| **签名引擎** | 签名兜底 | 纯 HTTP 本地算全套签名 |
| **自研** | 独门价值 | 账号×IP调度 + WebUI + 封面生成 |

两条主线：**私信是命门**（Rwp 协议逆向）；**签名是命根子**（签名算法质量，决定能不能安稳跑）。

## 三、功能清单（已落地）

| 模块 | 能力 | 状态 |
|---|---|---|
| 账号管理 | 多账号登录（二维码→cookie）、出口绑定、状态机 | ✅ |
| 私信收发 | send / list / history / unread / revoke | ✅ 验活 |
| 实时消息 | 轮询 unread → WS 推前端卡片 | ✅ |
| 私信自动回复 | 轮询+去重+延迟回话术，关键词触发回复 | ✅ 验活 |
| 消息中心 | 私信/评论@/赞藏/新增关注 四 tab | ✅ |
| 内容浏览 | 搜索笔记/用户→详情→评论→主页→关注/私信 | ✅ |
| 写操作 | 点赞/收藏/关注/取关/发评论/回复评论 | ✅ 自研逆向 |
| 发布笔记 | 图文发布（标题/正文/话题/地点/多图） | ✅ |
| 数据总览 | KPI 卡 + 笔记明细表（数据中心接口） | ✅ |
| 封面生成 | DeepSeek 出文案 + 本地模板 + Playwright 出图 | ✅ |

## 四、技术栈

- **后端**：Python 3.10 + FastAPI + uvicorn（系统 Python，非 venv）
- **引擎**：Python 3.10，私信走 websocket-client，签名走 node 执行 JS + curl_cffi
- **前端**：原生 HTML/JS + WebSocket，红白卡片（品牌红 `#ff2442`）
- **HTTP**：curl_cffi（`impersonate="chrome120"`）
- **代理隧道**：paramiko 本地 SOCKS5 → 跳板机出网；python_socks 透传
- **渲染**：Playwright（封面出图 + cookie 采集）
- **持久化**：JSON（accounts.json / exits.json / replied.json）

## 五、懂的人自然懂

有些规矩，江湖上不会印成册子，但懂的人心照不宣。比如：有些事，**干的时候风平浪静，三天后才起风浪**。至于哪三天、为何、看哪几个指标——不展开，你细品。

反正记住一句老话：**别让机器看起来太像机器。** 底下每一项技术，说到底都是在为这一件事服务。至于各自背后的讲究，给你留着，看懂多少算多少：

| 技术手段 | 背后的讲究 |
|---|---|
| DeepSeek 出标题+内容（每篇不同） | 撞脸不如撞衫，撞衫总比撞稿强 |
| 内置生图脚本（标题嵌封面） | 图个"每张都不重样" |
| 纯 HTTP 签名（自研） | 有些浏览器脸皮薄，戴不了假发 |
| curl_cffi `chrome120` | 穿衣打扮要像本人 |
| 账号×IP 出口（socks5 + 出口池） | 一屋不住二主 |
| socks5h 远程 DNS | 别让人顺着网线摸到你家 |
| 私信自动回复延迟 10~30s + 去重 | 秒回是机器，人得墨迹一会儿 |
| 号池轮换 + 单号不并发 + 错开 1s | 一口气吃不成胖子，也成不了胖子 |
| PoW WASM 解算 | 有些门，要答对暗号才开 |
| 老号 cookie CDP 读 | 老房子的锁，得用对钥匙 |

### 为什么"文案 + 封面都每篇不同"是门面功夫（重点）

这一刀，是整本手册里最省力、也最管用的一下。核心就一句：**最扎眼的特征，是同一样东西发了一遍又一遍。** 所以：

**① 文案维度**：同一条消息发 N 个号，是最容易露出马脚的事。把同一段话，改写成**每篇都不重样的标题+正文**，等于每个号每一篇都换了一张脸。

**② 图片维度**：更细的是封面图。平台判图重，靠的是**感知哈希（pHash）**而非 MD5——实测结论（懂的往下看）：
- pHash 对缩放/压缩/加噪/二次截图**完全无感**（距离 = 0），改这些白费劲
- 只有**内容级变化**（裁剪、加元素、大色相、翻转、重新生成）才拉开距离
- 硬改哈希**没有现成方案**，且「越伪装越刻意」本身就是破绽

所以巧劲在：**封面里嵌进这篇独有的标题文字**。标题每篇不同 → 封面像素每篇不同 → pHash 天然不同。等于把"改哈希"这个死局，用"每篇重新生成一张真不一样的图"绕过去，不用事后做任何变体。

**一句话**：「文案每篇不同 + 封面每篇不同」双保险，从源头掐断最致命的雷同特征。这也是为什么坚持「HTML 本地模板 + 标题嵌入」，而不是「固定模板 + 事后改图」。

## 六、逆向核心（难啃的路子）

### 6.1 私信：Rwp 协议 WebSocket 逆向（命门）

小红书私信不走 HTTP，走 **TCP 自研长连接**，纯 HTTP 逆向不现实。私信引擎底层是**真 Rwp 协议 WebSocket 逆向**：

- 端点：`wss://apppush-rws.xiaohongshu.com/rwp`
- 流程：`get_login_token` → `AUTH(t=2)` → `BIND im(t=2)` → `sendMessage(t=3, ChatOneMessage protobuf)`
- 手写 **varint / protobuf 编码** + message_id 解析
- 私信 WebSocket 原生支持 `proxy_host`（`http_proxy_host`），天然接账号×IP 出口

**发方向填坑**（验活 PASS）：websocket-client 1.9.0 原生支持 socks5/socks5h（`proxy_type` 参数，依赖 python_socks），所以发方向 WS 能直接走现有 socks5 隧道，不用 http 转换。

### 6.2 签名引擎：Falcon 风控（命根）

签名引擎纯 HTTP 本地算小红书全套签名，免浏览器：

- 签名链：`a1 / web_id / b1 / websectiga / sec_poison_id / gid / x-s / x-t / x-s-common / x-b3-traceid / x-rap-param`
- 技术栈：Python 3.10 + **node**（执行 JS 签名算法）+ curl_cffi
- 三种登录：cookie / 二维码 / 手机验证码（二维码纯本地渲染 + App 扫码）

**为什么纯 HTTP 而非浏览器**：headless 浏览器被风控识别（`isRiskReason: HeadlessUA` → 笔记页 error_code=300031），所以走签名路线（签名参数生成 `generate_request_params`）才对，别走抓包。

### 6.3 内容写接口逆向（点赞/收藏/关注/评论）

读接口层现成，**写接口全是新逆向的**（读接口层没有），关键接口：

| 操作 | 接口 | body | 坑 |
|---|---|---|---|
| 点赞 | `POST /api/sns/web/v1/note/like` | `{"note_oid":id}` | 参数名是 `note_oid` **不是** `note_id` |
| 收藏 | `POST /api/sns/web/v1/note/collect` | `{"note_id":id}` | |
| 关注 | `POST /api/sns/web/v1/user/follow` | `{"target_user_id":uid}` | |
| 发评论 | `POST /api/sns/web/v1/comment/post` | `{"note_id","content"}` | **需 x-rap-param 头**；回复加 `parent_comment_id` |

另有频率限制（"评论过快"）。

### 6.4 陌生人消息接口逆向

未互关的陌生人会话，旧 `get_recent_chats` 的 `user_list` 看不到——不是 bug，是平台把未互关会话过滤了（消息其实到了）。正解是 **`/api/im/web/v3/chats`**（网页版消息页实际用的接口），返回 `data.chats[]` 含陌生人，字段 `chat_user_id` / `info.nickname` / `info.avatar` / `last_msg_content` / `info.follow_status`（NONE=未互关 / BOTH=互关）。

**GitHub 无人公开逆向**（付费隐藏），自己抓包拿到——playwright 注入 cookie 导航消息页抓 XHR。

### 6.5 老号 Cookie：DPAPI app-bound → CDP

拿登录态 cookie 三重阻碍，最终 CDP 才是正解：

1. `document.cookie` 拿不到 `web_session` / `id_token`（**HttpOnly**）
2. 读磁盘 DB + DPAPI 解密全失败：Edge 用了 **app-bound encryption**，单纯 `win32crypt.CryptUnprotectData` 解不开
3. **正解 = CDP**：Edge 加 `--remote-debugging-port=9222 --remote-allow-origins=*`，连 CDP 发 `Network.getAllCookies`，浏览器内部返回解密后的值（含 HttpOnly）

⚠️ 必须补 `--remote-allow-origins=*`，否则 WebSocket 握手 403。

### 6.6 SOCKS5 隧道 + 账号×IP 出口（独门）

`_socks_tunnel.py`（paramiko）在本地起 SOCKS5 监听 `127.0.0.1:1080`，走跳板机 `<jumpbox-ip>` 出网，自动重连。链路：

```
本机 → 127.0.0.1:1080 → 跳板机 <jumpbox-ip> → 目标
```

- 账号 proxy 用 `socks5h://`（**非 socks5**）= 远程 DNS 解析，避免 DNS 泄露
- 云号 http 代理带认证 `http://user:pass@host:port`，ws_client 要拆 `[user:pass@]` + `http_proxy_auth`
- 出口映射：N 个云号（`<cloud-exit-1>` … `<cloud-exit-N>`）→ 跳板机 `<port>~<port>` 端口
- 隧道支持 SSH 自动重连（指数退避 3s→60s），断线不空转撞跳板机

## 七、DeepSeek 网页版逆向 + 号池

> 把 DeepSeek 网页版（chat.deepseek.com）当**免费无限次**的算力池：出文案。纯 HTTP 全自动，零浏览器。

### 7.1 纯 HTTP 链路（核心秘密）

```
token(64char base64, biz_data.user.token) → POST /api/v0/chat_session/create 拿 session_id
→ POST /api/v0/chat/create_pow_challenge 拿 challenge
→ Node WASM 解 PoW(纯 Python 会被拒 INVALID_POW_RESPONSE)
→ POST /api/v0/chat/completion (x-ds-pow-response 头 + x-client-version: 2.3.0)
```

- token 是 64 字符 base64，iOS App Bearer token 对 web API 有效，`Authorization: Bearer <token>`
- 会话复用：`parent_message_id` 链，复用 5 次后重建（`_ensure_session`）
- curl_cffi `impersonate="chrome120"`

### 7.2 PoW 用 Node WASM 解

DeepSeek 的 PoW challenge 必须用 Node WASM 解（`pow_solver.js` + `sha3_wasm_bg.wasm`），纯 Python 会被拒。跑前加 `CREATE_NO_WINDOW` 防止 `--windowed` exe 下 subprocess 调 node 闪黑框。

### 7.3 DEEP_SEARCH 触发

多步联网搜索由 **`x-client-version: 2.3.0`** 触发，**不是 body 参数**，也不需要 `x-hif-*` 签名。一个 header 版本号就切到深度搜索模式。

### 7.4 SSE 流解析（`parse_deep`）

响应是逐行 SSE JSON，`parse_deep` 收集全部 content（含无 `p` 的 `v` 片段）：

- `p == "response/conversation_mode"` → 模式
- `p == "response/fragments/-1/content"` → 追加 content
- `p == ""` 的 `v` → 追加
- `p == "response/fragments"` 且 list → 遍历取 `type=="RESPONSE"` 的 content

**关键：这只收 content 片段，把 thinking 思考链过滤掉了**，拿到的是干净正文——这是生产用 `ds_client.ask` 而非 MCP 工具的根本原因（MCP 的 `deepseek_search` 把思考链和正文糊一起）。

### 7.5 号池 + 调度三刀

号池：多账号（存于 `<ds_tokens.json>`，存 email+password+token，password 留 token 失效重登用）。

调度三刀（防限流/防短路）：
1. **双账号错开 1 秒发**（不同时，降时间关联风控）
2. **barrier**：等这一轮全部落盘才下一批（不边完成边补）
3. **封号检测**：HTTP 401/403 或 mute 关键词 → 剔除账号，`fut.result(timeout=300)` 兜底防挂起；全封则终止

### 7.6 账号级静音（命门）

- 整个账号被 mute（**不是 token 级**），响应 `{"biz_code":5,"is_muted":1,"mute_until":...}`，约 24h 解封
- **触发本质 = 单请求内工具连发量**（63 TOOL_SEARCH/29s megaburst），不是请求并发——人不可能一次发 60+ 条
- **生产铁律**：多账号轮换 + 单账号永不并发（毫秒级双发 = 自动化指纹）+ 批间随机 sleep

### 7.7 结构化输出（封面文案）

让 DeepSeek 吐结构化两行，后端零解析成本：

```
标题：<12~20字封面钩子>
内容：<正文60~150字>
```

`parse_ds` 用正则 `标题\s*[:：]\s*(.+)` / `内容\s*[:：]\s*([\s\S]+)` 提取——冒号定位无视 DeepSeek 复述 prompt 的废话前缀，标题行 `.+` 不带 DOTALL 防串到内容行。

## 八、封面生成（DeepSeek 算力池 + 本地模板）

核心原则：**HTML 封面本地定死模板，DeepSeek 只当文案机**。因为要「定位 html 里的配色字符自动改色」，前提是配色字符 100% 一致——DeepSeek 每次吐的 HTML 配色写法会自己发挥，无法稳定定位。

三件套（`<cover-dir>`）：
- `cover_template.html` — 配色写成 CSS 变量 `--bg/--text/--accent`，字体粗斜(800+italic)，外双线花纹框 + 四角 L 形角花 + 散落圆点，字号 7vw
- `recolor.py` — 定位三个 CSS 变量换色 + 塞标题 + Playwright 截图(1080×1440 = 3:4)。5 配色：white_red / white_black / black_red / white_green / white_blue
- `gen_post.py` — 手动链路：`ds_client.ask()` → `parse_deep()` → `parse_ds()` → recolor 出图 + 写 post.txt 留档

## 九、坑与教训（高频命门）

1. **依赖升级会覆盖补丁**：私信引擎底层 ws_client.py 加的 socks5h + http 代理认证是改在依赖里的，升级后要重打补丁。
2. **隐私默认值**：`creator.publish` 的 `privacy_type` 默认 1=私密，必须显式传 0 才是公开。
3. **xsec_token 必带**：评论接口不带则 `data={}` 空。
4. **字段名不统一**：搜索 item 是 `item.id`，详情是 `note_card.desc`；点赞是 `note_oid` 不是 `note_id`。
5. **防盗链**：图片 `referrerpolicy="no-referrer"` 即可（仅 referer 校验，无 token）。
6. **同步阻塞**：`/api/login` 扫码最多 5min，必须 `asyncio.to_thread` 投线程池，否则 WS 事件循环被 playwright 卡死。
7. **Windows GBK**：print 中文崩，跑前 `PYTHONIOENCODING=utf-8`。

## 十、待办

- 视频发布
- 一稿多号 + DeepSeek 改写去重
- 定时批量排期
- 评论触达（笔记评论 → 自动私信）
- 账号健康管理（生命周期）

---

## ⚠️ 友好提醒

这玩意是用来运营**你自己名下**的账号的。拿去搞别人的号、群发垃圾、踩平台红线，出了事自己扛。

号是你的，风控是它的，成年人了，自己兜底。

---

## 📜 协议

[GPL-3.0](LICENSE) — 自由软件，转载 / 再分发必须保留作者署名与仓库链接。

Copyright (C) 2026 **Liangqingkui8** · [github.com/Liangqingkui8](https://github.com/Liangqingkui8)
