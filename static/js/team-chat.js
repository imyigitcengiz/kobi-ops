(function () {
    const cfg = window.GY_TEAM_CHAT;
    if (!cfg) return;

    const panel = document.getElementById('teamChatPanel');
    const toggle = document.getElementById('teamChatToggle');
    const closeBtn = document.getElementById('teamChatClose');
    const badge = document.getElementById('teamChatBadge');
    const threadList = document.getElementById('teamChatThreadList');
    const userList = document.getElementById('teamChatUserList');
    const messagesEl = document.getElementById('teamChatMessages');
    const form = document.getElementById('teamChatForm');
    const input = document.getElementById('teamChatInput');
    const subtitle = document.getElementById('teamChatSubtitle');
    const sendBtn = form?.querySelector('button[type="submit"]');
    const chatRoot = document.getElementById('teamChatRoot');

    function refreshChatIcons() {
        if (!window.lucide || !chatRoot) return;
        try {
            lucide.createIcons({ root: chatRoot });
        } catch (e) {
            lucide.createIcons();
        }
    }

    let open = false;
    let activeThreadId = null;
    let lastMessageId = 0;
    let threads = [];
    let users = [];
    let pollTimer = null;
    let socket = null;
    let reconnectDelay = 1000;
    let initDone = false;

    function csrf() {
        const hidden = document.querySelector('#teamChatRoot [name=csrfmiddlewaretoken]');
        if (hidden?.value) return hidden.value;
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }

    function escapeHtml(s) {
        return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function formatTime(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        const now = new Date();
        const sameDay = d.toDateString() === now.toDateString();
        return sameDay
            ? d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })
            : d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
    }

    function setBadge(n) {
        if (!badge) return;
        if (n > 0) {
            badge.textContent = n > 99 ? '99+' : String(n);
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }

    function showError(msg) {
        if (threadList) {
            threadList.innerHTML = `<p class="text-xs text-red-600 p-2 leading-snug">${escapeHtml(msg)}</p>`;
        }
        if (messagesEl) {
            messagesEl.innerHTML = `<p class="text-sm text-red-600 p-4">${escapeHtml(msg)}</p>`;
        }
    }

    function updateSendState() {
        const ready = !!(open && activeThreadId);
        if (input) input.disabled = !ready;
        if (sendBtn) sendBtn.disabled = !ready;
    }

    async function fetchJson(url, options = {}) {
        const opts = {
            credentials: 'same-origin',
            headers: {
                Accept: 'application/json',
                ...(options.headers || {}),
            },
            ...options,
        };
        const res = await fetch(url, opts);
        const ct = (res.headers.get('content-type') || '').toLowerCase();
        if (!ct.includes('application/json')) {
            const text = await res.text();
            throw new Error(
                res.status === 401
                    ? 'Oturum süresi dolmuş; sayfayı yenileyip tekrar giriş yapın.'
                    : `Sunucu yanıtı beklenmiyor (${res.status}). ${text.slice(0, 80)}`
            );
        }
        const data = await res.json();
        if (!res.ok && !data.ok) {
            throw new Error(data.error || data.detail || `İstek başarısız (${res.status})`);
        }
        return data;
    }

    async function apiPost(url, body) {
        return fetchJson(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
            body: JSON.stringify(body || {}),
        });
    }

    async function ensureReady() {
        await apiPost(cfg.api.joinTeam, {});
        const data = await fetchJson(cfg.api.summary);
        threads = data.threads || [];
        setBadge(data.unread_total || 0);
        renderThreadList();

        const pick =
            data.team_thread ||
            threads.find((t) => t.kind === 'team') ||
            threads[0];
        if (pick && !activeThreadId) {
            await openThread(pick.id, { skipSummary: true });
        } else if (!pick) {
            showError('Genel sohbet bulunamadı. Yönetici: python manage.py ensure_chat');
        }
        updateSendState();
        return data;
    }

    async function loadSummary() {
        try {
            const data = await fetchJson(cfg.api.summary);
            threads = data.threads || [];
            setBadge(data.unread_total || 0);
            renderThreadList();
            return data;
        } catch (err) {
            showError(err.message || 'Sohbet yüklenemedi');
            return null;
        }
    }

    async function loadUsers() {
        try {
            const data = await fetchJson(cfg.api.users);
            users = data.users || [];
            renderUserList();
        } catch (err) {
            if (userList) userList.innerHTML = `<p class="text-xs text-red-500 p-1">${escapeHtml(err.message)}</p>`;
        }
    }

    function renderThreadList() {
        if (!threadList) return;
        if (!threads.length) {
            threadList.innerHTML = '<p class="text-xs text-slate-400 p-2">Sohbet yok</p>';
            return;
        }
        threadList.innerHTML = threads
            .map((t) => {
                const active = t.id === activeThreadId;
                const unread =
                    t.unread > 0
                        ? `<span class="ml-auto text-[10px] font-bold bg-violet-600 text-white px-1.5 rounded-full">${t.unread}</span>`
                        : '';
                const preview = t.last_message
                    ? escapeHtml(t.last_message.body.slice(0, 40))
                    : 'Mesaj yok';
                return `<button type="button" data-thread-id="${t.id}" class="w-full text-left px-2 py-2 rounded-lg flex items-start gap-2 ${active ? 'bg-white shadow-sm border border-slate-200' : 'hover:bg-white/80'}">
                <span class="w-7 h-7 rounded-lg bg-violet-100 text-violet-700 flex items-center justify-center shrink-0 text-[10px] font-bold">${t.kind === 'team' ? '#' : escapeHtml(t.peer?.initials || t.title?.slice(0, 2) || '?')}</span>
                <span class="min-w-0 flex-1">
                    <span class="flex items-center gap-1"><span class="font-semibold text-slate-800 truncate text-xs">${escapeHtml(t.title)}</span>${unread}</span>
                    <span class="text-[10px] text-slate-400 truncate block">${preview}</span>
                </span>
            </button>`;
            })
            .join('');
        threadList.querySelectorAll('[data-thread-id]').forEach((btn) => {
            btn.addEventListener('click', () => openThread(Number(btn.dataset.threadId)));
        });
    }

    function renderUserList() {
        if (!userList) return;
        if (!users.length) {
            userList.innerHTML = '<p class="text-xs text-slate-400 p-1">Başka kullanıcı yok</p>';
            return;
        }
        userList.innerHTML = users
            .map(
                (u) =>
                    `<button type="button" data-user-id="${u.id}" class="w-full text-left px-2 py-1.5 rounded-lg hover:bg-white text-xs text-slate-700 flex items-center gap-2">
                <span class="w-6 h-6 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center text-[9px] font-bold">${escapeHtml(u.initials)}</span>
                <span class="truncate">${escapeHtml(u.name)}</span>
            </button>`
            )
            .join('');
        userList.querySelectorAll('[data-user-id]').forEach((btn) => {
            btn.addEventListener('click', () => startDirect(Number(btn.dataset.userId)));
        });
    }

    function renderMessages(items, append) {
        if (!messagesEl) return;
        if (!append) messagesEl.innerHTML = '';
        const meId = cfg.me.id;
        (items || []).forEach((m) => {
            const mine = m.sender.id === meId;
            const row = document.createElement('div');
            row.className = `flex ${mine ? 'justify-end' : 'justify-start'}`;
            row.dataset.msgId = m.id;
            row.innerHTML = mine
                ? `<div class="max-w-[85%]"><div class="bg-violet-600 text-white px-3 py-2 rounded-2xl rounded-br-md text-sm">${escapeHtml(m.body)}</div><p class="text-[10px] text-slate-400 text-right mt-0.5">${formatTime(m.created_at)}</p></div>`
                : `<div class="max-w-[85%]"><p class="text-[10px] font-bold text-slate-500 mb-0.5">${escapeHtml(m.sender.name)}</p><div class="bg-white border border-slate-200 px-3 py-2 rounded-2xl rounded-tl-md text-sm text-slate-800 shadow-sm">${escapeHtml(m.body)}</div><p class="text-[10px] text-slate-400 mt-0.5">${formatTime(m.created_at)}</p></div>`;
            messagesEl.appendChild(row);
            lastMessageId = Math.max(lastMessageId, m.id);
        });
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    async function openThread(threadId, opts = {}) {
        activeThreadId = threadId;
        lastMessageId = 0;
        renderThreadList();
        const t = threads.find((x) => x.id === threadId);
        if (subtitle && t) subtitle.textContent = t.title;
        if (messagesEl) messagesEl.innerHTML = '<p class="text-center text-slate-400 text-sm py-8">Yükleniyor…</p>';
        updateSendState();

        try {
            const data = await fetchJson(cfg.api.messages(threadId));
            renderMessages(data.messages || [], false);
            await apiPost(cfg.api.read(threadId), {});
            if (!opts.skipSummary) await loadSummary();
        } catch (err) {
            showError(err.message || 'Mesajlar yüklenemedi');
        }
        updateSendState();
    }

    async function startDirect(userId) {
        try {
            const data = await apiPost(cfg.api.direct, { user_id: userId });
            await loadSummary();
            await openThread(data.thread.id);
        } catch (err) {
            alert(err.message || 'Sohbet açılamadı');
        }
    }

    async function pollNewMessages() {
        if (!activeThreadId || !open) return;
        try {
            const data = await fetchJson(cfg.api.messages(activeThreadId) + '?since=' + lastMessageId);
            if (data.messages?.length) {
                renderMessages(data.messages, true);
                await apiPost(cfg.api.read(activeThreadId), {});
            }
        } catch (e) {
            /* sessiz — polling yedek */
        }
    }

    function onWsPayload(payload) {
        if (!payload || payload.event !== 'chat.message' || !payload.message) return;
        const m = payload.message;
        if (m.thread_id === activeThreadId && open) {
            if (!messagesEl.querySelector(`[data-msg-id="${m.id}"]`)) {
                renderMessages([m], true);
                apiPost(cfg.api.read(activeThreadId), {}).catch(() => {});
            }
        }
        loadSummary();
    }

    function connectWs() {
        try {
            socket = new WebSocket(cfg.wsUrl);
            socket.onopen = () => {
                reconnectDelay = 1000;
            };
            socket.onmessage = (ev) => {
                try {
                    onWsPayload(JSON.parse(ev.data));
                } catch (e) {}
            };
            socket.onclose = () => {
                setTimeout(connectWs, reconnectDelay);
                reconnectDelay = Math.min(reconnectDelay * 2, 12000);
            };
        } catch (e) {}
    }

    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text || !activeThreadId) {
            alert('Önce soldan bir sohbet seçin (Genel Sohbet).');
            return;
        }
        input.value = '';
        try {
            const data = await apiPost(cfg.api.send(activeThreadId), { body: text });
            if (!messagesEl.querySelector(`[data-msg-id="${data.message.id}"]`)) {
                renderMessages([data.message], true);
            }
            if (window.GY_MARK_LOCAL_SAVE) window.GY_MARK_LOCAL_SAVE();
            loadSummary();
        } catch (err) {
            alert(err.message || 'Gönderilemedi');
            input.value = text;
        }
    });

    async function setOpen(val) {
        open = val;
        panel?.classList.toggle('hidden', !open);
        if (open) {
            input?.focus();
            messagesEl.innerHTML = '<p class="text-center text-slate-400 text-sm py-8">Hazırlanıyor…</p>';
            try {
                if (!initDone) {
                    await ensureReady();
                    initDone = true;
                } else {
                    await loadSummary();
                    if (!activeThreadId) {
                        const team = threads.find((t) => t.kind === 'team');
                        if (team) await openThread(team.id, { skipSummary: true });
                    }
                }
                await loadUsers();
                if (!pollTimer) pollTimer = setInterval(pollNewMessages, 4000);
            } catch (err) {
                showError(err.message || 'Sohbet başlatılamadı');
            }
            updateSendState();
        }
        refreshChatIcons();
    }

    toggle?.addEventListener('click', () => setOpen(!open));
    closeBtn?.addEventListener('click', () => setOpen(false));

    connectWs();
    loadSummary().catch(() => {});
    setInterval(() => {
        if (!open) loadSummary().catch(() => {});
    }, 45000);

    updateSendState();
    refreshChatIcons();
})();
