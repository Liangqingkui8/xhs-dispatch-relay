# 📮 xhs-dispatch-relay

![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-GPL--3.0-red)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6)
![RWP Protocol](https://img.shields.io/badge/RWP%20Protocol-reverse--engineered-blueviolet)
![Stars](https://img.shields.io/github/stars/Liangqingkui8/xhs-dispatch-relay?style=flat-square)
![Forks](https://img.shields.io/github/forks/Liangqingkui8/xhs-dispatch-relay?style=flat-square)

**[English](README_EN.md) · [中文](README.md)**

**One panel. All your accounts.**

xhs-dispatch-relay is a project for managing multiple accounts you own: a unified inbox for sending and receiving DMs, keyword auto-reply, per-account exit routing, content browsing, write operations, publishing, and a data overview — all in one panel. One account is a hobby; ten accounts is a job. The dirty grunt work in between, it carries for you.

---

## ⚖️ Legal Disclaimer

This project is provided **for personal study and academic research only**. The author makes no warranty of usability and accepts no responsibility for any consequence of its use. Please comply with the target platform's terms of service and the laws of your country/region; any misuse is entirely at your own risk. Redistribution must retain the author's attribution and the repository link (see the license at the bottom).

---

## ⚙️ What It Does

- **Unified inbox** — DMs from every account land in one panel. Who messaged you, where the chat is, whether you've replied — one glance.
- **DM send/receive** — send / list / history / unread / revoke, with full conversation history.
- **Auto-reply** — keyword-triggered responses, per-account copy that never bleeds into each other.
- **Exit routing** — each account walks its own exit; if one drops, it reroutes on its own. Accounts don't step on each other, and one account going down doesn't drag the family with it.
- **Resume on crash** — if it dies mid-run, it picks up from where it left off.
- **Anti-no-op lock** — if a batch comes up empty, it hits the brakes instead of burning resources in silence.
- **Content browsing** — search notes/users → detail → comments → profile → follow/DM.
- **Write operations** — like / favorite / follow / comment (self reverse-engineered, see tech deep-dive 6.3).
- **Publish notes** — image-text publishing (title / body / topics / location / multi-image).
- **Data overview** — KPI cards + note detail table in one view.
- **QR login** — browser scans the QR, cookie saved automatically, swapping accounts is painless.

## 🖼️ Preview

<p>
<img src="assets/screenshot/main.png" alt="Account management" width="420">
<img src="assets/screenshot/data.png" alt="Data overview" width="420">
</p>

---

## 🚀 Quick Start

```bash
git clone https://github.com/Liangqingkui8/xhs-dispatch-relay
cd xhs-dispatch-relay
pip install -r requirements.txt

# 1. Configure accounts and exits (copy the templates, never commit real credentials)
cp data/accounts.example.json data/accounts.json
cp data/exits.example.json data/exits.json

# 2. Start the service
python -m uvicorn app.main:app --port 8000
```

Open http://127.0.0.1:8000 in your browser, scan the QR, and go.

> Just want a look without setting up an environment? Double-click `web/index.html` — it ships with demo data and needs no backend.

---

## 🏗️ Architecture

The **multi-account × multi-exit scheduling skeleton** is the core, and it's platform-agnostic — you could lift it and reuse it for any "many accounts, many exits, don't cross the wires" scenario:

```
xhs-dispatch-relay/
├── app/
│   ├── engine.py      # Single-account engine: DM send/receive, login-state check
│   ├── scheduler.py   # Multi-account scheduler: per-account exits, reconnect, isolation
│   ├── auto_reply.py  # Keyword auto-reply rules
│   ├── accounts.py    # Account/exit config management
│   ├── login.py       # QR-login entry
│   └── main.py        # Web console service (FastAPI)
├── web/               # Frontend panel (vanilla HTML/JS + WebSocket)
└── data/              # Runtime state (not committed; see .example templates)
```

Three layers: **presentation** (FastAPI + vanilla frontend + real-time WS) → **scheduling** (account pool × IP exit + polling + jitter + status detection) → **engine** (DM engine + signature engine).

The direction is human brains; the code is AI-assisted. How the architecture is drawn and where the boundaries land is a human call — the grunt work goes to the tool.

---

## 🔒 Security Notes

- `data/` is runtime state; real account credentials **never enter version control** (see `.gitignore`, only `.example` templates are committed).
- Cloud server / account / exit credentials are all injected via **environment variables**, never hardcoded.
- Runtime assets in the tech deep-dive are redacted to placeholders; only the implementation is public.

---

# 📡 Tech Deep-Dive (reverse engineering)

> ⚖️ **For personal study and academic research only.** The following reverse-engineering and engineering details are recorded purely for research. Comply with the target platform's terms of service and local laws; any misuse is at your own risk.

> xhs-dispatch-relay · engineering deep-dive
> Version: phase 1 (DMs + WebUI + content browsing + data overview + cover generation)
> Updated: 2026-08-16
> What this documents is **implementation detail**: protocol reverse-engineering, signature algorithms, environment setup, link design. Every interface/link has been tested and verified (PASS). Personal runtime assets (server IPs, account credentials, local paths) are redacted to `<placeholders>` and are not published here.

## 1. Positioning

A dispatch tool for managing multiple accounts you own, with four capabilities (**publish / comment / DM / real-time messages**).

The value sits in the two layers nobody else ships (account × IP-exit scheduling + the WebUI shell), with the engine and protocol reverse-engineering entirely self-built. The genuinely hard parts — the DM protocol, the signature algorithm, the DeepSeek web reverse — are all verified working, and this document captures them.

## 2. Architecture Overview (three layers)

```
┌─ presentation (self-built) ── FastAPI + vanilla HTML/JS + WebSocket real-time ── red-white card UI
├─ scheduling (self-built) ── account pool × IP-exit mapping + polling + jitter + status detection ── unique
└─ engine ── DM engine (DM/collect/publish) + signature engine (signature fallback)
```

| Component | Role | Notes |
|---|---|---|
| **DM engine** | main skeleton | Rwp protocol reverse-engineered, full DM stack |
| **Signature engine** | signature fallback | full signatures computed locally over pure HTTP |
| **Self-built** | unique value | account × IP scheduling + WebUI + cover generation |

Two pillars: **DM is the lifeline** (Rwp protocol reverse-engineering); **signatures are the foundation** (signature quality decides whether it runs quietly).

## 3. Feature List (shipped)

| Module | Capability | Status |
|---|---|---|
| Account management | multi-account login (QR → cookie), exit binding, state machine | ✅ |
| DM send/receive | send / list / history / unread / revoke | ✅ verified |
| Real-time messages | poll unread → push cards over WS | ✅ |
| DM auto-reply | polling + dedup + delayed replies, keyword-triggered | ✅ verified |
| Message center | DM / @comments / likes-favs / new follows — four tabs | ✅ |
| Content browsing | search notes/users → detail → comments → profile → follow/DM | ✅ |
| Write ops | like / favorite / follow / unfollow / comment / reply | ✅ self reverse-engineered |
| Publish notes | image-text publish (title / body / topics / location / multi-image) | ✅ |
| Data overview | KPI cards + note detail table (data-center API) | ✅ |
| Cover generation | DeepSeek copy + local template + Playwright rendering | ✅ |

## 4. Tech Stack

- **Backend**: Python 3.10 + FastAPI + uvicorn (system Python, not a venv)
- **Engine**: Python 3.10, DMs via websocket-client, signatures via node executing JS + curl_cffi
- **Frontend**: vanilla HTML/JS + WebSocket, red-white cards (brand red `#ff2442`)
- **HTTP**: curl_cffi (`impersonate="chrome120"`)
- **Proxy tunnel**: paramiko local SOCKS5 → jumpbox egress; python_socks pass-through
- **Rendering**: Playwright (cover rendering + cookie capture)
- **Persistence**: JSON (accounts.json / exits.json / replied.json)

## 5. Those Who Know, Know

A lot of rules in this game don't get printed, but the ones in the know just know. Like: some things **look calm in the moment, then trouble rolls in three days later**. Which three days, why, and which signals — not expanding. You get it.

Here's the one sentence that matters: **don't make the machine look too much like a machine.** Every technique below, at the end of the day, serves that one thing. As for the reasoning behind each, it's left for you — get as much as you get:

| Technique | The thinking behind it |
|---|---|
| DeepSeek generates title+copy (unique each time) | Twins raise eyebrows; twins posting the same copy raise more |
| Built-in cover script (title embedded in cover) | Every picture deserves a fresh face |
| Pure-HTTP signature (self-built) | Some browsers are thin-skinned — can't wear a wig |
| curl_cffi `chrome120` | Dress like the real you |
| account × IP exit (socks5 + exit pool) | Two masters, one house, no |
| socks5h remote DNS | Don't let them trace the wire back to your place |
| auto-reply delay 10~30s + dedup | Instant reply is a robot; humans dither a bit |
| pool rotation + no concurrency + 1s stagger | You can't get fat in one bite |
| PoW WASM solving | Some doors need the right password |
| old-account cookie via CDP | Old locks need the right key |

### Why "unique copy + unique cover every time" is the highest-leverage move (key)

This one is the cheapest and most effective cut in the whole manual. One line: **the loudest tell is the same thing posted over and over.** So:

**① Copy dimension**: sending the same message to N accounts is the easiest way to slip up. Rewrite the same paragraph into **non-identical titles + bodies each time** — every account, every post, gets a different face.

**② Image dimension**: the subtler one is cover dedup. The platform judges image similarity by **perceptual hash (pHash)**, not MD5 — measured conclusions (knowing readers, keep reading):
- pHash is **completely insensitive** to resize / compress / noise / re-screenshot (distance = 0). Changing those is wasted effort.
- Only **content-level changes** (crop, add elements, major hue shift, flip, regenerate) open up the distance.
- There's **no off-the-shelf way** to force a hash change, and "the more you fake it, the more deliberate it looks" is itself the tell.

So the trick: **embed that post's unique title text into the cover.** Title differs per post → cover pixels differ per post → pHash naturally differs. That turns the "change the hash" dead-end into "regenerate a genuinely different image from the source every time" — no post-hoc variation needed.

**In one line**: "unique copy + unique cover" as double insurance cuts off the most fatal duplication signal at the source. That's why the design insists on "local HTML template + title embedding" rather than "fixed template + post-edit the image."

## 6. Reverse-Engineering Core (the hard roads)

### 6.1 DMs: Rwp protocol WebSocket reverse (lifeline)

Xiaohongshu DMs don't go over HTTP — they use a **custom long-lived TCP connection**, so pure-HTTP reverse isn't practical. The DM engine is a **genuine Rwp-protocol WebSocket reverse**:

- Endpoint: `wss://apppush-rws.xiaohongshu.com/rwp`
- Flow: `get_login_token` → `AUTH(t=2)` → `BIND im(t=2)` → `sendMessage(t=3, ChatOneMessage protobuf)`
- Hand-rolled **varint / protobuf encoding** + message_id parsing
- The DM WebSocket natively supports `proxy_host` (`http_proxy_host`), so it plugs straight into the account × IP exit

**Send-direction gotcha** (verified PASS): websocket-client 1.9.0 natively supports socks5/socks5h (`proxy_type` param, depends on python_socks), so the send-direction WS can go straight through the existing socks5 tunnel — no HTTP conversion needed.

### 6.2 Signature engine: Falcon risk screening (foundation)

The signature engine computes Xiaohongshu's full signature set locally over pure HTTP, no browser:

- Signature chain: `a1 / web_id / b1 / websectiga / sec_poison_id / gid / x-s / x-t / x-s-common / x-b3-traceid / x-rap-param`
- Stack: Python 3.10 + **node** (runs the JS signature algorithm) + curl_cffi
- Three login methods: cookie / QR / SMS code (QR fully rendered locally + scanned in-app)

**Why pure HTTP instead of a browser**: headless browsers get flagged (`isRiskReason: HeadlessUA` → note page error_code=300031), so the signature route (`generate_request_params`) is the correct one. Don't go the packet-capture route.

### 6.3 Content write-API reverse (like / favorite / follow / comment)

The read layer ships ready-made; **every write API was newly reverse-engineered** (the read layer doesn't have them). Key interfaces:

| Op | Endpoint | body | Gotcha |
|---|---|---|---|
| Like | `POST /api/sns/web/v1/note/like` | `{"note_oid":id}` | param is `note_oid`, **not** `note_id` |
| Favorite | `POST /api/sns/web/v1/note/collect` | `{"note_id":id}` | |
| Follow | `POST /api/sns/web/v1/user/follow` | `{"target_user_id":uid}` | |
| Comment | `POST /api/sns/web/v1/comment/post` | `{"note_id","content"}` | **needs x-rap-param header**; replies add `parent_comment_id` |

There's also a rate limit ("commenting too fast").

### 6.4 Stranger-message API reverse

For conversations with strangers you haven't followed back, the old `get_recent_chats` `user_list` doesn't show them — not a bug, the platform filters out non-mutual conversations (the messages do arrive). The fix is **`/api/im/web/v3/chats`** (the endpoint the web message page actually uses), returning `data.chats[]` including strangers, with fields `chat_user_id` / `info.nickname` / `info.avatar` / `last_msg_content` / `info.follow_status` (NONE = not mutual / BOTH = mutual).

**Nobody on GitHub has published this reverse** (kept behind paid walls). Got it by packet capture — inject the cookie via playwright, navigate to the message page, and grab the XHR.

### 6.5 Old-account cookies: DPAPI app-bound → CDP

Three walls stand between you and a login-state cookie; CDP is the answer:

1. `document.cookie` can't grab `web_session` / `id_token` (**HttpOnly**)
2. Reading the disk DB + DPAPI decryption all fail: Edge uses **app-bound encryption**, plain `win32crypt.CryptUnprotectData` can't open it
3. **The fix = CDP**: start Edge with `--remote-debugging-port=9222 --remote-allow-origins=*`, connect via CDP, send `Network.getAllCookies` — the browser returns the decrypted values (including HttpOnly)

⚠️ You must add `--remote-allow-origins=*`, otherwise the WebSocket handshake 403s.

### 6.6 SOCKS5 tunnel + account × IP exit (unique)

`_socks_tunnel.py` (paramiko) starts a local SOCKS5 listening on `127.0.0.1:1080`, egressing through jumpbox `<jumpbox-ip>`, with auto-reconnect. The link:

```
local → 127.0.0.1:1080 → jumpbox <jumpbox-ip> → target
```

- Account proxy uses `socks5h://` (**not** socks5) = remote DNS resolution, avoiding DNS leaks
- Cloud exits use an authenticated http proxy `http://user:pass@host:port`; ws_client must split `[user:pass@]` + `http_proxy_auth`
- Exit mapping: N cloud exits (`<cloud-exit-1>` … `<cloud-exit-N>`) → jumpbox `<port>~<port>` ports
- The tunnel supports SSH auto-reconnect (exponential backoff 3s→60s), so a drop doesn't hammer the jumpbox on an empty loop

## 7. DeepSeek web reverse + token pool

> Using the DeepSeek web app (chat.deepseek.com) as a **free, effectively unlimited** compute pool: copy generation. Fully automated pure HTTP, zero browser.

### 7.1 The pure-HTTP link (core secret)

```
token(64-char base64, biz_data.user.token) → POST /api/v0/chat_session/create for session_id
→ POST /api/v0/chat/create_pow_challenge for challenge
→ solve PoW in Node WASM (pure Python gets rejected INVALID_POW_RESPONSE)
→ POST /api/v0/chat/completion (x-ds-pow-response header + x-client-version: 2.3.0)
```

- The token is 64-char base64; the iOS App Bearer token works against the web API, `Authorization: Bearer <token>`
- Session reuse: `parent_message_id` chain, rebuilt after 5 reuses (`_ensure_session`)
- curl_cffi `impersonate="chrome120"`

### 7.2 PoW solved in Node WASM

DeepSeek's PoW challenge must be solved with Node WASM (`pow_solver.js` + `sha3_wasm_bg.wasm`); pure Python gets rejected. Add `CREATE_NO_WINDOW` before running so a `--windowed` exe doesn't flash a black box when subprocess calls node.

### 7.3 DEEP_SEARCH trigger

Multi-step web search is triggered by **`x-client-version: 2.3.0`** — **not** a body param, and no `x-hif-*` signature needed. One header version flips it into deep-search mode.

### 7.4 SSE stream parsing (`parse_deep`)

The response is line-by-line SSE JSON; `parse_deep` collects all content (including `v` fragments without `p`):

- `p == "response/conversation_mode"` → mode
- `p == "response/fragments/-1/content"` → append content
- `p == ""` with `v` → append
- `p == "response/fragments"` and list → iterate, take `type=="RESPONSE"` content

**Key: it only collects content fragments and filters out the thinking chain**, so you get clean text — the fundamental reason production uses `ds_client.ask` rather than the MCP tool (MCP's `deepseek_search` muddles the thinking chain and the body together).

### 7.5 Token pool + three-sword scheduling

Token pool: multiple accounts (stored in `<ds_tokens.json>`, storing email+password+token; password kept for re-login if the token expires).

Three-sword scheduling (anti-limit / anti-short-circuit):
1. **Two accounts staggered 1s apart** (not simultaneous, lowering time-correlation flags)
2. **Barrier**: wait for this whole round to land before the next batch (no fill-as-you-go)
3. **Status detection**: HTTP 401/403 or mute keywords → drop the account; `fut.result(timeout=300)` as a guard against hangs; if all are dropped, terminate

### 7.6 Account-level mute (lifeline)

- The whole account gets muted (**not token-level**), response `{"biz_code":5,"is_muted":1,"mute_until":...}`, roughly 24h to lift
- **What triggers it = tool-burst volume within a single request** (63 TOOL_SEARCH/29s megaburst), not request concurrency — a human can't send 60+ in one go
- **Production rule**: rotate multiple accounts + never run one account concurrently (ms-level double-fire = automation fingerprint) + random sleep between batches

### 7.7 Structured output (cover copy)

Have DeepSeek return two structured lines, zero parsing cost on the backend:

```
标题：<12~20字封面钩子>
内容：<正文60~150字>
```

`parse_ds` extracts with regex `标题\s*[:：]\s*(.+)` / `内容\s*[:：]\s*([\s\S]+)` — the colon anchor ignores DeepSeek's verbatim prompt-recall preamble; the title line's `.+` without DOTALL prevents it running into the body line.

## 8. Cover generation (DeepSeek compute pool + local template)

Core principle: **HTML cover template locked locally; DeepSeek only acts as the copy machine.** Because auto-recoloring needs to "locate the color characters in the html and swap them," the color characters must be 100% consistent — DeepSeek's HTML color writing varies every time and can't be reliably located.

Three pieces (`<cover-dir>`):
- `cover_template.html` — colors as CSS variables `--bg/--text/--accent`, bold-italic (800+italic), outer double-line patterned frame + four-corner L flourishes + scattered dots, font-size 7vw
- `recolor.py` — locate the three CSS variables, swap color, inject the title, screenshot with Playwright (1080×1440 = 3:4). Five palettes: white_red / white_black / black_red / white_green / white_blue
- `gen_post.py` — manual pipeline: `ds_client.ask()` → `parse_deep()` → `parse_ds()` → recolor to image + write post.txt for the record

## 9. Pitfalls & Lessons (high-frequency)

1. **Dependency upgrades overwrite patches**: the socks5h + http proxy auth added to the DM engine's underlying ws_client.py live inside the dependency — re-apply the patch after an upgrade.
2. **Privacy default**: `creator.publish`'s `privacy_type` defaults to 1 = private; you must explicitly pass 0 to make it public.
3. **xsec_token required**: the comment API returns `data={}` empty without it.
4. **Inconsistent field names**: search items are `item.id`, details are `note_card.desc`; likes are `note_oid`, not `note_id`.
5. **Anti-hotlink**: images just need `referrerpolicy="no-referrer"` (referer check only, no token).
6. **Synchronous blocking**: `/api/login` QR can take up to 5min; must run it in a thread pool via `asyncio.to_thread`, or the WS event loop gets stuck on playwright.
7. **Windows GBK**: `print` of Chinese crashes; set `PYTHONIOENCODING=utf-8` before running.

## 10. Todo

- Video publishing
- One-copy-many-accounts + DeepSeek rewrite dedup
- Scheduled batch posting
- Comment outreach (note comment → auto-DM)
- Account health management (lifecycle)

---

## ⚠️ Friendly Reminder

This tool is for operating **your own** accounts. Use it on other people's accounts, spam, or cross platform lines — and you're on your own.

The accounts are yours; the risk is theirs. You're an adult — you handle the fallout.

---

## 💝 Sponsor

If this project helped you, leave the author a **star** — or buy them a coffee.

Ways to support: WeChat / Alipay payment QR — scan one and buy the author a coffee.

<p>
<img src="assets/wechat.jpg" alt="WeChat QR" width="200">
<img src="assets/alipay.jpg" alt="Alipay QR" width="200">
</p>

---

## 🤝 Contact & Contributing

- **Report bugs / suggest features**: open a [GitHub Issue](https://github.com/Liangqingkui8/xhs-dispatch-relay/issues)
- **Contribute code**: Fork → change → open a PR. Any improvement is welcome.
- **Contact the author**: via GitHub Issues, or liangqingkui8@gmail.com

### FAQ

**Q: What environment is needed?**
Python 3.10 + Windows, plus the xhs-api SDK (point the `XHS_SDK_DIR` env var at its install dir). No extra frontend dependencies.

**Q: Are account cookies safe?**
Stored only in local `data/`, never in version control. Cloud server / account / exit credentials are all injected via environment variables, never hardcoded.

**Q: Does it support Docker / server deployment?**
Currently a Windows-local web service. The scheduling skeleton is platform-agnostic; moving it to a server needs your own adaptation.

**Q: Login failed / API errors?**
Check the "Pitfalls & Lessons" section and the runtime logs first; if it persists, open an Issue with the error message and reproduction steps.

---

## 📜 License

[GPL-3.0](LICENSE) — free software. Redistribution must retain the author's attribution and the repository link.

Copyright (C) 2026 **Liangqingkui8** · [github.com/Liangqingkui8](https://github.com/Liangqingkui8)
