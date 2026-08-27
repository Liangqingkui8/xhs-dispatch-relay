// xhs-dispatch-relay — 前端：账号卡片 + 右键菜单 + 私信弹窗 + WS 实时推流
let accounts = [];
const grid = document.getElementById('grid');
const ctxMenu = document.getElementById('ctx-menu');
const dmModal = document.getElementById('dm-modal');

const STATUS_TEXT = { online: '在线', offline: '离线', rate_limited: '限流', banned: '封号' };

// ---------- 账号卡片 ----------
async function loadAccounts() {
  try {
    const res = await fetch('/api/accounts');
    accounts = await res.json();
    accounts.forEach(a => { unreadCache[a.name] = a.unread || 0; });
    render();
  } catch (e) {
    grid.innerHTML = '<div class="empty">后端未启动或账号为空</div>';
  }
}

function render() {
  grid.innerHTML = '';
  if (!accounts.length) {
    grid.innerHTML = '<div class="empty">暂无账号，请在 data/accounts.json 配置</div>';
    return;
  }
  accounts.forEach(a => grid.appendChild(makeCard(a)));
}

function makeCard(a) {
  const card = document.createElement('div');
  card.className = 'card ' + (a.status || 'offline');
  card.dataset.name = a.name;
  const unread = unreadCache[a.name] || 0;
  card.innerHTML = `
    <div class="card-header">
      <span class="status-dot ${a.status || 'offline'}"></span>
      <span class="name">${esc(a.nickname || a.name)}</span>
    </div>
    <div class="card-info">
      <div class="row"><span>IP</span><b>${esc(a.proxy || '直连')}</b></div>
      <div class="row"><span>状态</span><b id="status-${esc(a.name)}">${STATUS_TEXT[a.status] || a.status}</b></div>
      <div class="row"><span>未读</span><b class="unread-badge" id="unread-${esc(a.name)}">${unread}</b></div>
      <div class="row"><span>自动回复</span><b class="${a.reply_text ? 'reply-on' : 'reply-off'}">${a.reply_text ? '开' : '关'}</b></div>
    </div>
  `;
  card.addEventListener('contextmenu', (e) => showCtxMenu(e, a.name));
  return card;
}

// ---------- 右键菜单 ----------
let ctxTarget = null;

function showCtxMenu(e, name) {
  e.preventDefault();
  ctxTarget = name;
  ctxMenu.style.display = 'block';
  ctxMenu.style.left = e.clientX + 'px';
  ctxMenu.style.top = e.clientY + 'px';
}

function hideCtxMenu() { ctxMenu.style.display = 'none'; }

ctxMenu.addEventListener('click', (e) => {
  const item = e.target.closest('.ctx-item');
  if (!item || item.classList.contains('disabled')) return;
  const action = item.dataset.action;
  const name = ctxTarget;
  hideCtxMenu();
  if (action === 'dm') openDm(name);
  if (action === 'explore') openExplore(name);
  if (action === 'publish') openPublish(name);
  if (action === 'mine') openMine(name);
  if (action === 'reply') setAutoReply(name);
});
document.addEventListener('click', hideCtxMenu);
document.addEventListener('contextmenu', (e) => {
  if (!e.target.closest('.card')) hideCtxMenu();
});

// ---------- 私信弹窗 ----------
let dmName = null;    // 当前账号
let dmUserId = null;  // 当前账号的 user_id（判左右气泡）
let dmUid = null;     // 当前会话 uid
let convAvatar = {};  // 会话对方头像缓存 uid → avatar
let convNick = {};    // 会话对方昵称缓存 uid → nickname
let myAvatar = '';    // 当前账号头像

function openDm(name) {
  dmName = name;
  const acc = accounts.find(a => a.name === name);
  dmUserId = acc ? acc.user_id : null;
  myAvatar = acc ? (acc.avatar || '') : '';
  dmUid = null;
  document.getElementById('dm-title').textContent = '消息 · ' + name;
  document.getElementById('dm-chat').innerHTML = '<div class="chat-tip">左侧选会话，或直接输入 uid 开聊</div>';
  document.getElementById('dm-msg').value = '';
  dmModal.classList.add('show');
  switchMsgTab('dm');
  loadConvs(name);
}

function closeDm() {
  dmModal.classList.remove('show');
  dmName = null; dmUid = null;
}
document.getElementById('dm-close').onclick = closeDm;
dmModal.addEventListener('click', (e) => { if (e.target === dmModal) closeDm(); });

// ---------- 消息中心 tab 切换 ----------
document.querySelectorAll('.msg-tab').forEach(t => {
  t.onclick = () => switchMsgTab(t.dataset.tab);
});

function switchMsgTab(tab) {
  document.querySelectorAll('.msg-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  const isDm = tab === 'dm';
  document.getElementById('dm-pane').style.display = isDm ? 'flex' : 'none';
  document.getElementById('dm-input-pane').style.display = isDm ? 'flex' : 'none';
  document.getElementById('notif-pane').style.display = isDm ? 'none' : 'block';
  if (!isDm) loadNotif(tab);
}

async function loadNotif(tab) {
  const pane = document.getElementById('notif-pane');
  pane.innerHTML = '<div class="empty">加载中…</div>';
  try {
    const res = await fetch(`/api/notifications/${encodeURIComponent(dmName)}?tab=${tab}`);
    const j = await res.json();
    if (!res.ok) throw new Error(j.detail || res.status);
    const list = (j.data && j.data.message_list) || [];
    pane.innerHTML = '';
    if (!list.length) { pane.innerHTML = '<div class="empty">暂无消息</div>'; return; }
    list.forEach(m => pane.appendChild(notifItem(m, tab)));
  } catch (e) { pane.innerHTML = `<div class="empty">消息加载失败: ${esc(e.message || e)}</div>`; }
}

function notifItem(m, tab) {
  const u = (tab === 'connections') ? (m.user || {}) : (m.user_info || {});
  const uid = u.userid || u.user_id || '';
  const nickname = u.nickname || '';
  const avatar = u.image || u.images || '';
  const title = m.title || '';
  const info = m.item_info || {};
  const content = info.content || '';
  const thumb = info.image || '';
  const el = document.createElement('div');
  el.className = 'notif-item';
  el.innerHTML = `
    <img src="${esc(imgUrl(avatar))}" referrerpolicy="no-referrer" onerror="this.style.background='#333';this.style.display='inline-block'">
    <div class="n-body">
      <div class="n-head">
        <span class="n-name">${esc(nickname)}</span>
        <span class="n-title">${esc(title)}</span>
      </div>
      ${content ? `<div class="n-content">${esc(content)}</div>` : ''}
      <div class="n-time">${fmtTime(m.time)}</div>
    </div>
    ${thumb ? `<img class="n-thumb" src="${esc(imgUrl(thumb))}" referrerpolicy="no-referrer" onerror="this.style.display='none'">` : ''}`;
  const goUser = () => { if (!uid) return; openExplore(dmName); openUser({ user_id: uid, nickname, avatar, xsec_token: u.xsec_token }); };
  el.querySelector('.n-name').onclick = goUser;
  el.querySelector('img').onclick = goUser;
  return el;
}

function fmtTime(sec) {
  if (!sec) return '';
  const d = Date.now() / 1000 - sec;
  if (d < 60) return '刚刚';
  if (d < 3600) return Math.floor(d / 60) + ' 分钟前';
  if (d < 86400) return Math.floor(d / 3600) + ' 小时前';
  if (d < 86400 * 30) return Math.floor(d / 86400) + ' 天前';
  return new Date(sec * 1000).toLocaleDateString();
}

async function loadConvs(name) {
  const box = document.getElementById('dm-convs');
  box.innerHTML = '';
  try {
    const res = await fetch(`/api/conversations/${encodeURIComponent(name)}`);
    const convs = await res.json();
    convs.forEach(c => {
      const uid = c.user_id || c.id;
      const nick = c.nickname || '未知';
      const avatar = c.image || '';
      const preview = c.last_msg_content || '';
      const unread = c.unread || 0;
      convAvatar[uid] = avatar;
      convNick[uid] = nick;
      const item = document.createElement('div');
      item.className = 'dm-conv-item';
      item.dataset.maxStoreId = c.max_store_id || '';
      const avHtml = avatar
        ? `<img class="c-avatar" src="${esc(imgUrl(avatar))}" referrerpolicy="no-referrer" onerror="this.style.visibility='hidden'">`
        : `<span class="c-avatar"></span>`;
      item.innerHTML = `
        ${avHtml}
        <div class="c-main">
          <div class="cn">${esc(nick)}</div>
          ${preview ? `<div class="cp">${esc(preview)}</div>` : ''}
        </div>
        ${unread > 0 ? `<span class="c-badge">${unread > 99 ? '99+' : unread}</span>` : ''}
      `;
      item.onclick = () => selectConv(uid, item);
      box.appendChild(item);
    });
  } catch (e) { box.innerHTML = '<div class="chat-tip">会话拉取失败</div>'; }
}

function selectConv(uid, item) {
  dmUid = uid;
  document.querySelectorAll('.dm-conv-item').forEach(el => el.classList.remove('active'));
  if (item) {
    item.classList.add('active');
    // 清掉未读红字
    const badge = item.querySelector('.c-badge');
    if (badge) badge.remove();
    // 后端标记已读（last_store_id 取会话最新消息）
    const maxStoreId = item.dataset.maxStoreId;
    if (maxStoreId) markRead(uid, maxStoreId);
  }
  loadHistory(uid);
}

function markRead(uid, lastStoreId) {
  fetch('/api/mark_read', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: dmName, user_id: uid, last_store_id: Number(lastStoreId) })
  }).catch(() => {});
}

async function loadHistory(uid) {
  const box = document.getElementById('dm-chat');
  box.innerHTML = '<div class="chat-tip">加载中…</div>';
  try {
    const res = await fetch(`/api/history/${encodeURIComponent(dmName)}/${encodeURIComponent(uid)}`);
    const msgs = await res.json();
    renderChat(msgs);
  } catch (e) { box.innerHTML = '<div class="chat-tip">历史拉取失败</div>'; }
}

function renderChat(msgs) {
  const box = document.getElementById('dm-chat');
  box.innerHTML = '';
  // 历史返回最新在前 → 反转成时间正序
  msgs.slice().reverse().forEach(m => appendMsg(m));
  box.scrollTop = box.scrollHeight;
}

function appendMsg(m) {
  const box = document.getElementById('dm-chat');
  const me = m.sender_id === null || m.sender_id === dmUserId;
  const div = document.createElement('div');
  div.className = 'msg ' + (me ? 'me' : 'other');
  const avatar = me ? myAvatar : (convAvatar[dmUid] || '');
  const avHtml = avatar
    ? `<img class="m-avatar" src="${esc(imgUrl(avatar))}" referrerpolicy="no-referrer" onerror="this.style.visibility='hidden'">`
    : `<span class="m-avatar"></span>`;
  div.innerHTML = `${avHtml}<div class="bubble">${esc(m.content || '')}</div>`;
  // 对方头像可点 → 跳对方主页（复用发现里的 openUser）
  if (!me) {
    const avEl = div.querySelector('.m-avatar');
    avEl.style.cursor = 'pointer';
    avEl.title = '查看主页';
    avEl.onclick = () => {
      openExplore(dmName);
      openUser({ user_id: dmUid, nickname: convNick[dmUid] || '', avatar: avatar, xsec_token: '' });
    };
  }
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

async function sendDm() {
  if (!dmName) return;
  const content = document.getElementById('dm-msg').value.trim();
  const receiver = dmUid || document.getElementById('dm-msg').dataset.uid;
  if (!content) return;
  // 没选会话时，把输入框当 uid 用（临时开聊）
  const target = dmUid;
  if (!target) return alert('先选一个会话');
  try {
    const res = await fetch('/api/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: dmName, receiver: target, content })
    });
    const r = await res.json();
    if (r.ok) {
      document.getElementById('dm-msg').value = '';
      appendMsg({ sender_id: dmUserId, content });
    } else {
      alert('发送失败: ' + (r.detail || ''));
    }
  } catch (e) { alert('发送异常: ' + e); }
}
document.getElementById('dm-send').onclick = sendDm;
document.getElementById('dm-msg').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') sendDm();
});

// ---------- WS 实时推流 ----------
const unreadCache = {};

function connectWs() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => console.log('[ws] 已连接');
  ws.onmessage = (e) => {
    let ev;
    try { ev = JSON.parse(e.data); } catch { return; }
    if (ev.type === 'message') {
      const uid = ev.data.conversation;
      const count = ev.data.unread;
      unreadCache[ev.account] = count;
      const unreadEl = document.getElementById('unread-' + ev.account);
      if (unreadEl) unreadEl.textContent = count;
      // 弹窗开着且正在看这个会话 → 实时追加
      if (dmName === ev.account && dmUid === uid && ev.data.latest) {
        appendMsg(ev.data.latest);
      }
    } else if (ev.type === 'status') {
      const card = document.querySelector(`.card[data-name="${ev.account}"]`);
      if (card) {
        const st = ev.data.status || 'offline';
        card.className = 'card ' + st;
        const dot = card.querySelector('.status-dot');
        if (dot) dot.className = 'status-dot ' + st;
        const statusEl = document.getElementById('status-' + ev.account);
        if (statusEl) statusEl.textContent = STATUS_TEXT[st] || st;
      }
    }
  };
  ws.onclose = () => { setTimeout(connectWs, 3000); };
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

// ============================================================
//  发现（搜索 → 详情 → 评论 → 作者主页 → 关注/私信）
// ============================================================
const exploreModal = document.getElementById('explore-modal');
const exBody = document.getElementById('ex-body');
const exCrumb = document.getElementById('ex-crumb');

let exName = null;           // 当前账号
let exSearchQ = '', exSearchType = 'notes';
let exNote = null;           // 当前详情 note_card
let exNoteId = null, exNoteXsec = null;
let exUser = null;           // 当前查看的用户 {user_id,nickname,avatar,xsec_token}

function imgUrl(u) { return u ? String(u).replace(/^http:\/\//, 'https://') : ''; }

async function exFetch(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.status);
  return res.json();
}

function openExplore(name) {
  exName = name;
  exNote = null; exNoteId = null; exNoteXsec = null; exUser = null;
  document.getElementById('explore-title').textContent = '发现 · ' + name;
  document.getElementById('ex-q').value = '';
  exBody.innerHTML = '<div class="empty">输入关键词开始搜索</div>';
  exCrumb.innerHTML = '';
  exploreModal.classList.add('show');
  document.getElementById('ex-q').focus();
}
document.getElementById('explore-close').onclick = () => exploreModal.classList.remove('show');
exploreModal.addEventListener('click', (e) => { if (e.target === exploreModal) exploreModal.classList.remove('show'); });

function renderSearchResults() { doSearch(); }

function renderCrumb() {
  // 状态机：exNote → 详情；exUser → 用户主页；否则 → 搜索结果
  const back = document.createElement('span');
  back.className = 'bc-link';
  let html = '';
  if (exNote) {
    html = `搜索「${esc(exSearchQ)}」`;
    back.textContent = '‹ 返回';
    back.onclick = () => { exNote = null; exNoteId = null; exUser = null; renderCrumb(); renderSearchResults(); };
  } else if (exUser) {
    html = exNote ? `搜索「${esc(exSearchQ)}」 › 笔记` : `搜索「${esc(exSearchQ)}」`;
    back.textContent = '‹ 返回';
    back.onclick = () => { exUser = null; renderCrumb(); if (exNote) { renderDetail(); } else { renderSearchResults(); } };
  }
  exCrumb.innerHTML = '';
  if (back.textContent) exCrumb.appendChild(back);
  if (html) {
    const lbl = document.createElement('span');
    lbl.style.cssText = 'color:#888;margin-left:6px';
    lbl.textContent = html;
    exCrumb.appendChild(lbl);
  }
}

async function doSearch() {
  const q = document.getElementById('ex-q').value.trim();
  if (!q) return;
  exSearchQ = q;
  exSearchType = document.getElementById('ex-type').value;
  exNote = null; exNoteId = null; exNoteXsec = null; exUser = null;
  exBody.innerHTML = '<div class="empty">搜索中…</div>';
  renderCrumb();
  try {
    const j = await exFetch(`/api/search/${encodeURIComponent(exName)}?q=${encodeURIComponent(q)}&type=${exSearchType}`);
    if (exSearchType === 'users') {
      renderUsers((j.data && j.data.users) || []);
    } else {
      renderNotes((j.data && j.data.items) || []);
    }
  } catch (e) { exBody.innerHTML = `<div class="empty">搜索失败: ${esc(e.message || e)}</div>`; }
}
document.getElementById('ex-search').onclick = doSearch;
document.getElementById('ex-q').addEventListener('keydown', (e) => { if (e.key === 'Enter') doSearch(); });

function noteCard(item) {
  const nc = item.note_card || item;
  const u = nc.user || {};
  const it = nc.interact_info || {};
  const cover = (nc.cover && (nc.cover.url_default || nc.cover.url_pre)) || '';
  const el = document.createElement('div');
  el.className = 'note-card';
  el.innerHTML = `
    <img class="thumb" src="${esc(imgUrl(cover))}" referrerpolicy="no-referrer" loading="lazy" onerror="this.style.opacity=0.2">
    <div class="nc-title">${esc(nc.display_title || nc.title || '')}</div>
    <div class="nc-meta">
      <img src="${esc(imgUrl(u.avatar || ''))}" referrerpolicy="no-referrer" onerror="this.style.display='none'">
      <span class="nc-author">${esc(u.nickname || u.nick_name || '')}</span>
      <span class="nc-likes">❤ ${esc(it.liked_count || 0)}</span>
    </div>`;
  el.onclick = () => openNote(item.id, item.xsec_token || '', u);
  return el;
}

function renderNotes(items) {
  if (!items.length) { exBody.innerHTML = '<div class="empty">没有结果</div>'; return; }
  const grid = document.createElement('div');
  grid.className = 'note-grid';
  items.forEach(it => grid.appendChild(noteCard(it)));
  exBody.innerHTML = '';
  exBody.appendChild(grid);
}

function userItem(u) {
  const el = document.createElement('div');
  el.className = 'user-item';
  el.innerHTML = `
    <img src="${esc(imgUrl(u.avatar || u.image || ''))}" referrerpolicy="no-referrer" onerror="this.src='';this.style.background='#333'">
    <div>
      <div class="u-name">${esc(u.name || u.nickname || '')}</div>
      <div class="u-sub">${esc(u.sub_title || '')}</div>
    </div>
    <div class="u-right">${esc((u.fans != null ? u.fans : '') + '')}${u.note_count != null ? '<br>' + esc(u.note_count) + ' 笔记' : ''}</div>`;
  el.onclick = () => openUser({ user_id: u.id, nickname: u.name, avatar: u.avatar || u.image || '', xsec_token: u.xsec_token });
  return el;
}

function renderUsers(users) {
  if (!users.length) { exBody.innerHTML = '<div class="empty">没有结果</div>'; return; }
  const list = document.createElement('div');
  list.className = 'user-list';
  users.forEach(u => list.appendChild(userItem(u)));
  exBody.innerHTML = '';
  exBody.appendChild(list);
}

function noteImages(nc) {
  const il = nc.image_list || [];
  return il.map(im => {
    if (im.url_default) return im.url_default;
    const info = im.info_list || [];
    const dft = info.find(x => x.image_scene === 'WB_DFT') || info[0];
    return dft ? dft.url : (im.url || '');
  }).filter(Boolean);
}
function noteVideo(nc) {
  const v = nc.video;
  if (!v || !v.media || !v.media.stream || !v.media.stream.h264) return '';
  return v.media.stream.h264[0].master_url || '';
}

async function openNote(noteId, xsec, user) {
  exNoteId = noteId; exNoteXsec = xsec || '';
  exBody.innerHTML = '<div class="empty">加载笔记…</div>';
  try {
    const url = `https://www.xiaohongshu.com/explore/${noteId}?xsec_token=${encodeURIComponent(exNoteXsec)}&xsec_source=pc_search`;
    const j = await exFetch(`/api/note/${encodeURIComponent(exName)}?url=${encodeURIComponent(url)}`);
    const items = (j.data && j.data.items) || [];
    if (!items.length) { exBody.innerHTML = '<div class="empty">笔记已失效</div>'; return; }
    exNote = items[0].note_card;
    exUser = null;
    renderCrumb();
    renderDetail();
  } catch (e) { exBody.innerHTML = `<div class="empty">加载失败: ${esc(e.message || e)}</div>`; }
}

function renderDetail() {
  const nc = exNote;
  const u = nc.user || {};
  const it = nc.interact_info || {};
  const imgs = noteImages(nc);
  const vid = noteVideo(nc);
  const tags = (nc.tag_list || []).map(t => t.name || t.tag || t).filter(Boolean);
  exBody.innerHTML = '';
  const box = document.createElement('div');
  box.className = 'note-detail';
  let mediaHtml = '';
  if (vid) mediaHtml = `<div class="nd-media"><video controls src="${esc(imgUrl(vid))}" referrerpolicy="no-referrer"></video></div>`;
  else if (imgs.length) mediaHtml = `<div class="nd-media">${imgs.map(u2 => `<img src="${esc(imgUrl(u2))}" referrerpolicy="no-referrer" onerror="this.style.display='none'">`).join('')}</div>`;
  box.innerHTML = `
    <div class="nd-author">
      <img src="${esc(imgUrl(u.avatar || ''))}" referrerpolicy="no-referrer" onerror="this.style.display='none'">
      <div>
        <div class="nd-name">${esc(u.nickname || u.nick_name || '')}</div>
        <div class="nd-ip">${esc(nc.ip_location || '')}</div>
      </div>
    </div>
    ${mediaHtml}
    <div class="nd-desc">${esc(nc.desc || nc.title || '')}</div>
    ${tags.length ? `<div class="nd-tags">${tags.map(t => `<span>#${esc(t)}</span>`).join('')}</div>` : ''}
    <div class="nd-actions">
      <button id="nd-like" class="${it.liked ? 'on' : ''}">❤ 点赞 ${esc(it.liked_count || '')}</button>
      <button id="nd-collect" class="${it.collected ? 'on' : ''}">⭐ 收藏 ${esc(it.collected_count || '')}</button>
      <button id="nd-cm">💬 评论 ${esc(it.comment_count || '')}</button>
    </div>
    <div class="cm-input">
      <input id="cm-text" placeholder="写评论…">
      <button id="cm-send">发布</button>
    </div>
    <div class="cm-title">评论</div>
    <div id="cm-list"><div class="empty">加载评论…</div></div>`;
  exBody.appendChild(box);

  box.querySelector('.nd-author').onclick = () => openUser({ user_id: u.user_id, nickname: u.nickname || u.nick_name, avatar: u.avatar, xsec_token: u.xsec_token });
  box.querySelector('#nd-like').onclick = () => likeNote();
  box.querySelector('#nd-collect').onclick = () => collectNote();
  box.querySelector('#nd-cm').onclick = () => box.querySelector('#cm-text').focus();
  box.querySelector('#cm-send').onclick = () => postComment();
  box.querySelector('#cm-text').addEventListener('keydown', (e) => { if (e.key === 'Enter') postComment(); });
  loadComments();
}

async function likeNote() {
  try {
    const res = await fetch('/api/like', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: exName, note_id: exNoteId })
    });
    const r = await res.json();
    if (r.ok) {
      const btn = document.getElementById('nd-like');
      btn.classList.toggle('on');
      toast('已点赞');
    } else toast('点赞失败: ' + (r.detail || ''));
  } catch (e) { toast('点赞异常: ' + e); }
}

async function collectNote() {
  try {
    const res = await fetch('/api/collect', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: exName, note_id: exNoteId })
    });
    const r = await res.json();
    if (r.ok) {
      const btn = document.getElementById('nd-collect');
      btn.classList.toggle('on');
      toast('已收藏');
    } else toast('收藏失败: ' + (r.detail || ''));
  } catch (e) { toast('收藏异常: ' + e); }
}

async function postComment() {
  const input = document.getElementById('cm-text');
  const content = input.value.trim();
  if (!content) return;
  try {
    const res = await fetch('/api/comment', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: exName, note_id: exNoteId, content })
    });
    const r = await res.json();
    if (r.ok) { input.value = ''; toast('评论已发'); loadComments(); }
    else toast('评论失败: ' + (r.detail || ''));
  } catch (e) { toast('评论异常: ' + e); }
}

async function loadComments() {
  const list = document.getElementById('cm-list');
  if (!list) return;
  try {
    const j = await exFetch(`/api/comments/${encodeURIComponent(exName)}?note_id=${encodeURIComponent(exNoteId)}&xsec_token=${encodeURIComponent(exNoteXsec || '')}`);
    const cms = (j.data && j.data.comments) || [];
    list.innerHTML = '';
    if (!cms.length) { list.innerHTML = '<div class="empty">暂无评论</div>'; return; }
    cms.forEach(c => list.appendChild(commentItem(c)));
  } catch (e) { list.innerHTML = `<div class="empty">评论加载失败</div>`; }
}

function commentItem(c) {
  const u = c.user_info || {};
  const cid = c.id || '';
  const el = document.createElement('div');
  el.className = 'cm-item';
  el.innerHTML = `
    <img src="${esc(imgUrl(u.image || u.avatar || ''))}" referrerpolicy="no-referrer" onerror="this.style.display='none'">
    <div class="cm-body">
      <span class="cm-user">${esc(u.nickname || '')}</span>
      <div class="cm-text">${esc(c.content || '')}</div>
      <div class="cm-sub">${c.like_count ? '👍 ' + c.like_count + ' · ' : ''}${c.sub_comment_count ? '回复 ' + c.sub_comment_count + ' · ' : ''}<button class="cm-reply">回复</button></div>
      <div class="cm-reply-box">
        <input placeholder="回复 @${esc(u.nickname || '')}">
        <button>发送</button>
      </div>
    </div>`;
  el.querySelector('.cm-user').onclick = () => openUser({ user_id: u.user_id, nickname: u.nickname, avatar: u.image || u.avatar, xsec_token: u.xsec_token });
  el.querySelector('img').onclick = () => openUser({ user_id: u.user_id, nickname: u.nickname, avatar: u.image || u.avatar, xsec_token: u.xsec_token });
  const replyBtn = el.querySelector('.cm-reply');
  const replyBox = el.querySelector('.cm-reply-box');
  const replyInput = replyBox.querySelector('input');
  replyBtn.onclick = () => {
    replyBox.classList.toggle('show');
    if (replyBox.classList.contains('show')) replyInput.focus();
  };
  const sendReply = () => replyComment(cid, replyInput.value);
  replyBox.querySelector('button').onclick = sendReply;
  replyInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendReply(); });
  return el;
}

async function replyComment(parentId, content) {
  content = (content || '').trim();
  if (!content) return;
  if (!parentId) return toast('评论 id 缺失');
  try {
    const res = await fetch('/api/comment', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: exName, note_id: exNoteId, content, parent_comment_id: parentId })
    });
    const r = await res.json();
    if (r.ok) { toast('回复已发'); loadComments(); }
    else toast('回复失败: ' + (r.detail || ''));
  } catch (e) { toast('回复异常: ' + e); }
}

async function openUser(user) {
  exUser = user;
  exBody.innerHTML = '<div class="empty">加载主页…</div>';
  renderCrumb();
  try {
    const j = await exFetch(`/api/user_notes/${encodeURIComponent(exName)}?user_id=${encodeURIComponent(user.user_id)}&xsec_token=${encodeURIComponent(user.xsec_token || '')}`);
    const notes = (j.data && j.data.notes) || [];
    // 拉资料（粉丝数，尽力而为）
    let profile = null;
    try {
      const p = await exFetch(`/api/user/${encodeURIComponent(exName)}?user_id=${encodeURIComponent(user.user_id)}`);
      profile = p.data || null;
    } catch (e) { profile = null; }
    renderUserHome(user, notes, profile);
  } catch (e) { exBody.innerHTML = `<div class="empty">主页加载失败: ${esc(e.message || e)}</div>`; }
}

function renderUserHome(user, notes, profile) {
  let stats = '';
  if (profile && profile.interactions) {
    stats = profile.interactions.map(i => `${i.name} ${i.count}`).join(' · ');
  }
  const desc = profile && profile.basic_info ? profile.basic_info.desc : '';
  exBody.innerHTML = '';
  const box = document.createElement('div');
  box.className = 'user-home';
  box.innerHTML = `
    <div class="uh-header">
      <img src="${esc(imgUrl(user.avatar || ''))}" referrerpolicy="no-referrer" onerror="this.style.background='#333'">
      <div>
        <div class="uh-name">${esc(user.nickname || '')}</div>
        <div class="uh-stats">${esc(stats)}</div>
        ${desc ? `<div class="uh-stats" style="white-space:pre-wrap">${esc(desc)}</div>` : ''}
      </div>
      <div class="uh-actions">
        <button id="uh-follow" class="">+ 关注</button>
        <button id="uh-dm">💬 私信</button>
      </div>
    </div>
    <div class="dm-inline" id="dm-inline">
      <input id="dm-inline-text" placeholder="输入私信内容，回车发送">
      <button id="dm-inline-send">发送</button>
    </div>
    <div class="cm-title">TA 的笔记</div>
    <div class="note-grid" id="uh-notes"></div>`;
  exBody.appendChild(box);

  const grid = box.querySelector('#uh-notes');
  if (!notes.length) grid.innerHTML = '<div class="empty">暂无笔记</div>';
  else notes.forEach(n => grid.appendChild(noteCard({ id: n.note_id, xsec_token: n.xsec_token, note_card: n })));

  const followBtn = box.querySelector('#uh-follow');
  followBtn.onclick = async () => {
    try {
      const res = await fetch('/api/follow', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: exName, user_id: user.user_id })
      });
      const r = await res.json();
      if (r.ok) { followBtn.textContent = '已关注'; followBtn.classList.add('following'); toast('已关注'); }
      else toast('关注失败: ' + (r.detail || ''));
    } catch (e) { toast('关注异常: ' + e); }
  };

  box.querySelector('#uh-dm').onclick = () => {
    const inline = box.querySelector('#dm-inline');
    inline.classList.toggle('show');
    inline.querySelector('input').focus();
  };
  const sendDmInline = async () => {
    const inp = box.querySelector('#dm-inline-text');
    const content = inp.value.trim();
    if (!content) return;
    try {
      const res = await fetch('/api/send', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: exName, receiver: user.user_id, content })
      });
      const r = await res.json();
      if (r.ok) { inp.value = ''; toast('私信已发'); }
      else toast('私信失败: ' + (r.detail || ''));
    } catch (e) { toast('私信异常: ' + e); }
  };
  box.querySelector('#dm-inline-send').onclick = sendDmInline;
  box.querySelector('#dm-inline-text').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendDmInline(); });
}

function toast(msg) {
  let t = document.getElementById('toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'toast';
    t.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#ff2442;color:#fff;padding:10px 20px;border-radius:8px;z-index:2000;font-size:13px;box-shadow:0 4px 16px rgba(0,0,0,.18)';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.textContent = ''; }, 2000);
}

loadAccounts();
connectWs();

// ---------- 发布笔记 ----------
let pubName = null;
let pubImages = [];  // 选中的 File 列表

function openPublish(name) {
  pubName = name;
  pubImages = [];
  document.getElementById('pub-title').value = '';
  document.getElementById('pub-desc').value = '';
  document.getElementById('pub-topics').value = '';
  document.getElementById('pub-location').value = '';
  renderPubImgs();
  document.getElementById('publish-modal').classList.add('show');
}

function closePublish() {
  document.getElementById('publish-modal').classList.remove('show');
  pubName = null;
}

function renderPubImgs() {
  const box = document.getElementById('pub-imgs');
  box.innerHTML = '';
  pubImages.forEach((f, i) => {
    const div = document.createElement('div');
    div.className = 'pub-img';
    div.innerHTML = `<img src="${URL.createObjectURL(f)}"><span class="del">×</span>`;
    div.querySelector('.del').onclick = () => { pubImages.splice(i, 1); renderPubImgs(); };
    box.appendChild(div);
  });
}

async function publishNote() {
  const title = document.getElementById('pub-title').value.trim();
  if (!title) return toast('标题不能为空');
  if (!pubImages.length) return toast('至少选一张图片');
  const fd = new FormData();
  fd.append('name', pubName);
  fd.append('title', title);
  fd.append('desc', document.getElementById('pub-desc').value);
  fd.append('topics', document.getElementById('pub-topics').value);
  fd.append('location', document.getElementById('pub-location').value);
  pubImages.forEach(f => fd.append('images', f));
  const btn = document.getElementById('pub-submit');
  btn.disabled = true; btn.textContent = '发布中…';
  try {
    const res = await fetch('/api/publish', { method: 'POST', body: fd });
    const r = await res.json();
    if (r.ok) { toast('发布成功'); closePublish(); }
    else toast('发布失败: ' + (r.detail || ''));
  } catch (e) { toast('发布异常: ' + e); }
  btn.disabled = false; btn.textContent = '发布';
}

document.getElementById('publish-close').onclick = closePublish;
document.getElementById('pub-submit').onclick = publishNote;
document.getElementById('pub-addimg').onclick = () => document.getElementById('pub-file').click();
document.getElementById('pub-file').onchange = (e) => {
  const files = Array.from(e.target.files || []);
  const remain = 15 - pubImages.length;
  pubImages.push(...files.slice(0, remain));
  if (files.length > remain) toast('最多 15 张，已截断');
  e.target.value = '';
  renderPubImgs();
};
document.getElementById('publish-modal').addEventListener('click', (e) => {
  if (e.target === e.currentTarget) closePublish();
});

// ---------- 我的主页 ----------
function openMine(name) {
  const acc = accounts.find(a => a.name === name);
  if (!acc || !acc.user_id) return toast('该账号未登录');
  openExplore(name);
  openUser({ user_id: acc.user_id, nickname: acc.nickname || name, avatar: acc.avatar || '', xsec_token: '' });
}

// ---------- 数据总览 ----------
function switchView(view) {
  document.getElementById('view-accounts').style.display = view === 'accounts' ? '' : 'none';
  document.getElementById('view-data').style.display = view === 'data' ? '' : 'none';
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.dataset.view === view));
  if (view === 'data') loadDataAll();
}
document.querySelectorAll('.nav-tab').forEach(t => { t.onclick = () => switchView(t.dataset.view); });

async function loadDataAll() {
  const kpiRow = document.getElementById('kpi-row');
  const table = document.getElementById('data-table');
  kpiRow.innerHTML = '<div class="empty" style="grid-column:1/-1">加载中…</div>';
  try {
    const res = await fetch('/api/note_analysis_all');
    const rows = await res.json();
    if (!rows || !rows.length) {
      kpiRow.innerHTML = '<div class="empty" style="grid-column:1/-1">暂无笔记数据</div>';
      table.innerHTML = '';
      return;
    }
    rows.sort((a, b) => (b.read_count || 0) - (a.read_count || 0));
    const sum = (k) => rows.reduce((s, r) => s + (Number(r[k]) || 0), 0);
    const accountCnt = new Set(rows.map(r => r.account)).size;
    const kpis = [
      { label: '运营账号', value: accountCnt },
      { label: '笔记总数', value: rows.length },
      { label: '总观看', value: sum('read_count') },
      { label: '总点赞', value: sum('like_count') },
      { label: '总收藏', value: sum('fav_count') },
      { label: '总评论', value: sum('comment_count') },
      { label: '总分享', value: sum('share_count') },
    ];
    kpiRow.innerHTML = kpis.map((k, i) => `
      <div class="kpi-card ${i < 2 ? 'primary' : ''}">
        <div class="kpi-label">${k.label}</div>
        <div class="kpi-value">${k.value.toLocaleString()}</div>
      </div>`).join('');
    table.innerHTML = `<table class="data-table">
      <thead><tr><th>账号</th><th>笔记</th><th class="num">观看</th><th class="num">赞</th><th class="num">藏</th><th class="num">评论</th><th class="num">分享</th><th>发布时间</th></tr></thead>
      <tbody>${rows.map(r => `
        <tr>
          <td>${esc(r.account || '')}</td>
          <td><div class="data-note">${r.cover_url ? `<img class="data-cover" src="${esc(imgUrl(r.cover_url))}" referrerpolicy="no-referrer" onerror="this.style.display='none'">` : ''}<span>${esc(r.title || '(无标题)')}</span></div></td>
          <td class="num">${(r.read_count ?? 0).toLocaleString()}</td>
          <td class="num">${(r.like_count ?? 0).toLocaleString()}</td>
          <td class="num">${(r.fav_count ?? 0).toLocaleString()}</td>
          <td class="num">${(r.comment_count ?? 0).toLocaleString()}</td>
          <td class="num">${(r.share_count ?? 0).toLocaleString()}</td>
          <td>${fmtTime(r.post_time / 1000)}</td>
        </tr>`).join('')}
      </tbody></table>`;
  } catch (e) {
    kpiRow.innerHTML = '<div class="empty" style="grid-column:1/-1">数据拉取失败</div>';
  }
}

// ---------- 私信自动回复 ----------
async function setAutoReply(name) {
  const acc = accounts.find(a => a.name === name);
  const cur = acc ? (acc.reply_text || '') : '';
  const text = prompt('自动回复话术（收到私信后延迟 10~30s 自动回，留空=关闭）：', cur);
  if (text === null) return;
  try {
    const res = await fetch('/api/set_reply', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, reply_text: text })
    });
    const r = await res.json();
    if (r.ok) { toast('已保存'); loadAccounts(); }
    else toast('保存失败: ' + (r.detail || ''));
  } catch (e) { toast('异常: ' + e); }
}

// ---------- 添加账号（扫码登录） ----------
let addExit = null;  // 选中的出口名（云1~云5），null = 直连

async function openAddModal() {
  document.getElementById('add-name').value = '';
  addExit = null;
  document.getElementById('add-status').textContent = '';
  document.getElementById('add-modal').classList.add('show');
  const box = document.getElementById('add-exits');
  box.innerHTML = '<div class="empty">加载出口…</div>';
  try {
    const res = await fetch('/api/exits');
    const exits = await res.json();
    box.innerHTML = '';
    box.appendChild(exitOption({ name: null, label: '直连（本机 IP）', free: true }));
    exits.forEach(e => box.appendChild(exitOption({
      name: e.name, label: `${e.name} · ${e.cloud_ip}`, free: e.free
    })));
  } catch (e) { box.innerHTML = '<div class="empty">出口加载失败</div>'; }
}

function exitOption(opt) {
  const div = document.createElement('div');
  div.className = 'exit-option' + (opt.free ? '' : ' disabled');
  div.innerHTML = `<span class="eo-dot"></span><span>${esc(opt.label)}</span>`
    + (opt.free ? '' : '<span class="eo-used">已占用</span>');
  if (opt.free) {
    div.onclick = () => {
      document.querySelectorAll('.exit-option').forEach(x => x.classList.remove('active'));
      div.classList.add('active');
      addExit = opt.name;
    };
  }
  return div;
}

async function startLogin() {
  const name = document.getElementById('add-name').value.trim();
  if (!name) return toast('先填账号名');
  if (addExit === null) return toast('选一个登录出口');
  const status = document.getElementById('add-status');
  const btn = document.getElementById('add-start');
  status.textContent = '已打开浏览器，请扫码登录…';
  btn.disabled = true;
  try {
    const res = await fetch('/api/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, exit_name: addExit || '' })
    });
    const r = await res.json();
    if (r.ok) {
      toast('账号 ' + (r.nickname || r.name) + ' 已登录');
      document.getElementById('add-modal').classList.remove('show');
      loadAccounts();
    } else {
      status.textContent = '登录失败: ' + (r.detail || '');
    }
  } catch (e) { status.textContent = '登录异常: ' + e; }
  btn.disabled = false;
}

document.getElementById('add-account-btn').onclick = openAddModal;
document.getElementById('add-close').onclick = () => document.getElementById('add-modal').classList.remove('show');
document.getElementById('add-start').onclick = startLogin;
document.getElementById('add-modal').addEventListener('click', (e) => {
  if (e.target === e.currentTarget) document.getElementById('add-modal').classList.remove('show');
});
