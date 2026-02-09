(function() {
  const API = '';
  const TOKEN_KEY = 'jarvis_token';
  const USER_KEY = 'jarvis_user';

  function getToken() { return localStorage.getItem(TOKEN_KEY); }
  function setToken(t) { if (t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY); }
  function getUser() { try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; } }
  function setUser(u) { if (u) localStorage.setItem(USER_KEY, JSON.stringify(u)); else localStorage.removeItem(USER_KEY); }

  function headers() {
    const t = getToken();
    return { 'Content-Type': 'application/json', ...(t ? { 'Authorization': 'Bearer ' + t } : {}) };
  }

  function getErrorMessage(data, fallback) {
    if (!data || typeof data !== 'object') return fallback;
    if (data.message) return data.message;
    if (Array.isArray(data.details) && data.details.length > 0 && data.details[0].message)
      return data.details[0].message;
    if (data.detail) {
      if (typeof data.detail === 'string') return data.detail;
      if (Array.isArray(data.detail) && data.detail.length > 0 && data.detail[0].msg)
        return data.detail[0].msg;
    }
    return fallback;
  }

  function showAuth() {
    document.getElementById('auth').style.display = 'block';
    document.getElementById('dashboard').classList.remove('visible');
    document.getElementById('chatFab').classList.remove('visible');
    document.getElementById('chatPopup').classList.remove('visible');
  }

  function showApp() {
    document.getElementById('auth').style.display = 'none';
    document.getElementById('dashboard').classList.add('visible');
    document.getElementById('chatFab').classList.add('visible');
    document.getElementById('chatPopup').classList.remove('visible');
    var user = getUser();
    document.getElementById('userEmail').textContent = (user && user.email) || '';
    startLiveTime();
    startStatusStripClock();
    updateNetworkStatus();
    setGreeting();
    setOrbState('idle');
    setStripMode('Waiting (General)');
    startIdleQuotes();
    initPanelToggles();
    initDevOverlay();
    loadDashboardStatus();
    loadSessions();
    loadCurrentSession();
    maybeShowProactiveSuggestion();
  }

  function setOrbState(state) {
    var orb = document.getElementById('jarvisOrb');
    var dot = document.getElementById('stripDot');
    if (!orb || !dot) return;
    orb.className = 'jarvis-orb state-' + state;
    dot.className = 'strip-dot ' + (state === 'listening' ? 'listening' : state === 'processing' ? 'processing' : state === 'error' ? 'error' : '');
  }

  function setStripMode(text) {
    var el = document.getElementById('stripMode');
    if (el) el.textContent = text;
  }

  function setStripLatency(ms) {
    var el = document.getElementById('stripLatency');
    if (el) el.textContent = (ms == null ? '—' : ms) + (ms != null ? ' ms' : '');
  }

  function startStatusStripClock() {
    function tick() {
      var el = document.getElementById('stripDateTime');
      if (el) {
        var d = new Date();
        el.textContent = d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }) + ' · ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      }
    }
    tick();
    if (window._stripClockInterval) clearInterval(window._stripClockInterval);
    window._stripClockInterval = setInterval(tick, 1000);
  }

  function updateNetworkStatus() {
    var el = document.getElementById('stripNetwork');
    if (el) el.textContent = navigator.onLine ? 'Online' : 'Offline';
  }
  window.addEventListener('online', updateNetworkStatus);
  window.addEventListener('offline', updateNetworkStatus);

  var IDLE_QUOTES = [
    'At your service.',
    'Analyzing background processes…',
    'Systems nominal.',
    'Ready when you are.',
    'Listening.'
  ];
  function startIdleQuotes() {
    var el = document.getElementById('orbIdleQuote');
    if (!el) return;
    var idx = 0;
    setInterval(function() {
      if (!document.getElementById('jarvisOrb') || document.getElementById('jarvisOrb').className.indexOf('state-idle') === -1) return;
      idx = (idx + 1) % IDLE_QUOTES.length;
      el.textContent = IDLE_QUOTES[idx];
    }, 8000);
  }

  function initPanelToggles() {
    document.querySelectorAll('.jarvis-panel-head').forEach(function(head) {
      head.addEventListener('click', function() {
        var panel = this.getAttribute('data-panel');
        var cap = (panel && panel.charAt(0).toUpperCase() + panel.slice(1)) || '';
        var body = document.getElementById('panel' + cap);
        if (body) body.classList.toggle('collapsed');
      });
    });
  }

  function initDevOverlay() {
    var overlay = document.getElementById('jarvisDevOverlay');
    var closeBtn = document.getElementById('devOverlayClose');
    if (closeBtn) closeBtn.addEventListener('click', function() { if (overlay) overlay.classList.remove('visible'); });
    document.addEventListener('keydown', function(e) {
      if (e.ctrlKey && e.shiftKey && (e.key === 'D' || e.key === 'd')) {
        e.preventDefault();
        if (overlay) overlay.classList.toggle('visible');
      }
    });
  }

  function maybeShowProactiveSuggestion() {
    var box = document.getElementById('jarvisSuggestion');
    var text = document.getElementById('jarvisSuggestionText');
    if (!box || !text) return;
    var shown = sessionStorage.getItem('jarvis_suggestion_shown');
    if (shown) return;
    text.textContent = 'You can ask for your daily brief or schedule a meeting.';
    box.classList.add('visible');
    sessionStorage.setItem('jarvis_suggestion_shown', '1');
    setTimeout(function() { box.classList.remove('visible'); }, 6000);
  }

  function startLiveTime() {
    function tick() {
      var el = document.getElementById('liveTime');
      if (el) {
        var d = new Date();
        el.textContent = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      }
    }
    tick();
    if (window._liveTimeInterval) clearInterval(window._liveTimeInterval);
    window._liveTimeInterval = setInterval(tick, 1000);
  }

  function setGreeting() {
    var hour = new Date().getHours();
    var name = (getUser() && getUser().name) || (getUser() && getUser().email && getUser().email.split('@')[0]) || '';
    var greeting = 'At your service.';
    if (hour >= 5 && hour < 12) greeting = name ? 'Good morning, ' + name + '.' : 'Good morning.';
    else if (hour >= 12 && hour < 17) greeting = name ? 'Good afternoon, ' + name + '.' : 'Good afternoon.';
    else if (hour >= 17 && hour < 21) greeting = name ? 'Good evening, ' + name + '.' : 'Good evening.';
    else greeting = name ? 'Good to see you, ' + name + '.' : 'At your service.';
    var el = document.getElementById('greeting');
    if (el) el.textContent = greeting;
  }

  function loadDashboardStatus() {
    if (!getToken()) return;
    fetch(API + '/brief', { headers: headers() })
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        var card = document.getElementById('cardBrief');
        var preview = document.getElementById('briefPreview');
        if (!card || !preview) return;
        if (data && data.text) {
          preview.textContent = data.text.length > 120 ? data.text.slice(0, 120) + '…' : data.text;
          card.style.display = 'block';
        } else { card.style.display = 'none'; }
      })
      .catch(function() { document.getElementById('cardBrief').style.display = 'none'; });

    fetch(API + '/reminders', { headers: headers() })
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        var card = document.getElementById('cardReminder');
        var preview = document.getElementById('reminderPreview');
        if (!card || !preview) return;
        var items = (data && data.items) || [];
        var next = items.find(function(r) { return r.status === 'pending' && r.run_at; });
        if (next && next.run_at) {
          var runAt = new Date(next.run_at);
          if (runAt > new Date()) {
            preview.textContent = (next.message || '').slice(0, 60) + (next.message && next.message.length > 60 ? '…' : '') + ' — ' + runAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            card.style.display = 'block';
          } else { card.style.display = 'none'; }
        } else { card.style.display = 'none'; }
      })
      .catch(function() { document.getElementById('cardReminder').style.display = 'none'; });
  }

  function openChatPopup() {
    document.getElementById('chatPopup').classList.add('visible');
    document.getElementById('chatFab').classList.remove('visible');
  }
  function closeChatPopup() {
    document.getElementById('chatPopup').classList.remove('visible');
    document.getElementById('chatFab').classList.add('visible');
  }
  function toggleChatPopup() {
    var popup = document.getElementById('chatPopup');
    if (popup.classList.contains('visible')) closeChatPopup();
    else openChatPopup();
  }

  document.getElementById('chatFab').addEventListener('click', function() { openChatPopup(); });
  document.getElementById('popupMinimize').addEventListener('click', function() { closeChatPopup(); });
  document.getElementById('btnOpenBrief').addEventListener('click', function() {
    openChatPopup();
    var input = document.getElementById('input');
    if (input) { input.placeholder = 'e.g. Give me my daily brief'; input.focus(); }
  });

  var sessionsListOpen = false;
  document.getElementById('popupSessionsToggle').addEventListener('click', function() {
    sessionsListOpen = !sessionsListOpen;
    document.getElementById('popupSessionsList').classList.toggle('open', sessionsListOpen);
  });

  let isRegister = false;
  const authError = document.getElementById('authError');
  const authBtn = document.getElementById('authBtn');
  const authToggle = document.getElementById('authToggle');
  const nameInput = document.getElementById('name');

  function setAuthMode(register) {
    isRegister = register;
    authBtn.textContent = register ? 'Create account' : 'Login';
    authToggle.textContent = register ? 'Already have an account? Login' : 'Create account';
    nameInput.style.display = register ? 'block' : 'none';
    authError.textContent = '';
    authError.style.color = '';
  }
  authToggle.addEventListener('click', function() { setAuthMode(!isRegister); });

  authBtn.addEventListener('click', async function() {
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    authError.textContent = '';
    authError.style.color = '';
    if (!email || !password) { authError.textContent = 'Email and password required'; return; }
    if (isRegister && password.length < 6) { authError.textContent = 'Password must be at least 6 characters'; return; }
    const url = isRegister ? API + '/auth/register' : API + '/auth/login';
    const body = { email, password, name: document.getElementById('name').value.trim() };
    try {
      const r = await fetch(url, { method: 'POST', headers: headers(), body: JSON.stringify(body) });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { authError.textContent = getErrorMessage(data, r.statusText || 'Failed'); return; }
      if (isRegister) {
        setToken(null); setUser(null); setAuthMode(false);
        document.getElementById('password').value = '';
        authError.textContent = 'Account created. Please log in.';
        authError.style.color = 'var(--green)';
      } else {
        setToken(data.access_token); setUser(data.user);
        showApp();
      }
    } catch (e) { authError.textContent = e.message || 'Network error'; }
  });

  document.getElementById('logout').addEventListener('click', function() {
    setToken(null); setUser(null);
    showAuth();
  });

  let currentSessionId = null;
  let mode = 'general';

  document.getElementById('modeGeneral').addEventListener('click', function() {
    mode = 'general';
    document.getElementById('modeGeneral').classList.add('active');
    document.getElementById('modeRealtime').classList.remove('active');
    if (document.getElementById('stripMode').textContent.indexOf('Waiting') === 0) setStripMode('Waiting (General)');
  });
  document.getElementById('modeRealtime').addEventListener('click', function() {
    mode = 'realtime';
    document.getElementById('modeRealtime').classList.add('active');
    document.getElementById('modeGeneral').classList.remove('active');
    if (document.getElementById('stripMode').textContent.indexOf('Waiting') === 0) setStripMode('Waiting (Realtime)');
  });

  function getSessionsEl() { return document.getElementById('popupSessionsList'); }
  function getMessagesEl() { return document.getElementById('messages'); }
  function getInputEl() { return document.getElementById('input'); }
  function getSendBtn() { return document.getElementById('send'); }

  async function loadSessions() {
    const el = getSessionsEl();
    if (!el) return;
    try {
      const r = await fetch(API + '/chats/sessions', { headers: headers() });
      if (!r.ok) { el.innerHTML = '<div style="padding:0.75rem;color:var(--muted);font-size:0.85rem">No chats yet</div>'; return; }
      const data = await r.json();
      const list = data.items || [];
      if (!list.length) { el.innerHTML = '<div style="padding:0.75rem;color:var(--muted);font-size:0.85rem">No chats yet</div>'; return; }
      el.innerHTML = list.map(function(s) {
        var preview = (s.preview || 'New chat').substring(0, 35) + ((s.preview && s.preview.length > 35) ? '…' : '');
        var active = s.session_id === currentSessionId ? ' active' : '';
        return '<div class="session-item' + active + '" data-id="' + (s.session_id || '') + '">' + preview + '</div>';
      }).join('');
      el.querySelectorAll('.session-item[data-id]').forEach(function(node) {
        node.addEventListener('click', function() {
          currentSessionId = this.getAttribute('data-id');
          loadCurrentSession();
          loadSessions();
          sessionsListOpen = false;
          document.getElementById('popupSessionsList').classList.remove('open');
        });
      });
    } catch (e) {
      el.innerHTML = '<div style="padding:0.75rem;color:var(--muted)">Could not load chats</div>';
    }
  }

  async function loadCurrentSession() {
    const el = getMessagesEl();
    if (!el) return;
    if (!currentSessionId) {
      el.innerHTML = '<div class="empty-state">Start a new conversation or choose one from history.</div>';
      return;
    }
    try {
      const r = await fetch(API + '/chats/sessions/' + encodeURIComponent(currentSessionId), { headers: headers() });
      if (!r.ok) { el.innerHTML = '<div class="empty-state">Could not load chat.</div>'; return; }
      const data = await r.json();
      el.innerHTML = (data.messages || []).map(function(m) {
        var role = m.role === 'user' ? 'You' : 'Jarvis';
        var content = (m.content || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        var confidence = m.role === 'assistant' ? '<div class="confidence high">Confidence: HIGH</div>' : '';
        return '<div class="msg ' + m.role + '"><div class="role">' + role + '</div><div class="content">' + content + '</div>' + confidence + '</div>';
      }).join('') || '<div class="empty-state">No messages yet.</div>';
      el.scrollTop = el.scrollHeight;
    } catch (e) {
      el.innerHTML = '<div class="empty-state">Could not load chat.</div>';
    }
  }

  function escapeHtml(s) {
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function typeIntoElement(contentEl, rawText, options) {
    var msPerChar = (options && options.msPerChar) || 18;
    var byWord = options && options.byWord !== false;
    var scrollContainer = options && options.scrollContainer || null;
    var text = String(rawText || '');
    if (!text) return Promise.resolve();
    contentEl.textContent = '';
    return new Promise(function(resolve) {
      var index = 0;
      function tick() {
        if (index >= text.length) {
          if (scrollContainer) scrollContainer.scrollTop = scrollContainer.scrollHeight;
          resolve();
          return;
        }
        if (byWord) {
          var nextSpace = text.indexOf(' ', index + 1);
          var nextNewline = text.indexOf('\n', index);
          var end = text.length;
          if (nextSpace !== -1) end = Math.min(end, nextSpace + 1);
          if (nextNewline !== -1 && nextNewline < end) end = nextNewline + 1;
          var chunkLen = end - index;
          contentEl.textContent = text.slice(0, end);
          index = end;
          setTimeout(tick, Math.min(msPerChar * chunkLen, 120));
        } else {
          contentEl.textContent = text.slice(0, index + 1);
          index++;
          setTimeout(tick, msPerChar);
        }
        if (scrollContainer) scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
      tick();
    });
  }

  document.getElementById('popupNewChat').addEventListener('click', function() {
    currentSessionId = null;
    loadCurrentSession();
    loadSessions();
    sessionsListOpen = false;
    document.getElementById('popupSessionsList').classList.remove('open');
  });

  var inputEl = getInputEl();
  var sendBtn = getSendBtn();

  function addErrorBubble(messagesEl, errText, retryPayload) {
    var div = document.createElement('div');
    div.className = 'msg assistant msg-error';
    div.innerHTML = '<div class="role">Jarvis</div><div class="content"></div>';
    var content = div.querySelector('.content');
    content.textContent = errText;
    if (retryPayload) {
      var retryBtn = document.createElement('button');
      retryBtn.type = 'button';
      retryBtn.className = 'retry-btn';
      retryBtn.textContent = 'Retry';
      retryBtn.setAttribute('aria-label', 'Retry');
      retryBtn.addEventListener('click', function() {
        div.remove();
        sendMessageWithPayload(retryPayload);
      });
      content.appendChild(document.createElement('br'));
      content.appendChild(retryBtn);
    }
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function sendMessageWithPayload(payload) {
    var text = payload.message;
    var messagesEl = getMessagesEl();
    if (!messagesEl) return;
    messagesEl.querySelector('.empty-state') && messagesEl.querySelector('.empty-state').remove();
    messagesEl.insertAdjacentHTML('beforeend', '<div class="msg user"><div class="role">You</div><div class="content">' + escapeHtml(text) + '</div></div>');
    inputEl.value = '';
    messagesEl.scrollTop = messagesEl.scrollHeight;
    sendBtn.disabled = true;

    setOrbState('processing');
    setStripMode('Executing');
    var startTime = Date.now();

    var loadingDiv = document.createElement('div');
    loadingDiv.className = 'msg assistant msg-loading';
    loadingDiv.setAttribute('aria-live', 'polite');
    loadingDiv.innerHTML = '<div class="role">Jarvis</div><div class="content"><span class="typing-dots">…</span> At your service…</div>';
    messagesEl.appendChild(loadingDiv);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    updateIntentPanel(text, null);
    addTaskItem('API call…', 'pending');

    var endpoint = mode === 'realtime' ? '/chat/realtime' : '/chat/general';
    var body = { message: text, session_id: payload.session_id || currentSessionId || undefined };
    if (mode === 'realtime' && payload.search_query !== undefined) body.search_query = payload.search_query;

    fetch(API + endpoint, { method: 'POST', headers: headers(), body: JSON.stringify(body) })
      .then(function(r) { return r.json().catch(function() { return {}; }).then(function(data) { return { r: r, data: data }; }); })
      .then(function(_) {
        var r = _.r, data = _.data;
        var latency = Math.round(Date.now() - startTime);
        loadingDiv.remove();
        setTaskItemDone('API call…', 'Response received');
        if (!r.ok) {
          setOrbState('error');
          setStripMode('Error');
          setStripLatency(latency);
          addErrorBubble(messagesEl, 'Error: ' + getErrorMessage(data, r.statusText), { message: text, session_id: currentSessionId || undefined });
          sendBtn.disabled = false;
          setTimeout(function() { setOrbState('idle'); setStripMode('Waiting (' + (mode === 'realtime' ? 'Realtime' : 'General') + ')'); }, 2000);
          return;
        }
        if (!currentSessionId) currentSessionId = data.session_id;
        var reply = data.reply || '';
        setStripLatency(latency);
        setOrbState('speaking');
        var assistantDiv = document.createElement('div');
        assistantDiv.className = 'msg assistant';
        assistantDiv.innerHTML = '<div class="role">Jarvis</div><div class="content"></div><div class="confidence high">Confidence: HIGH</div>';
        messagesEl.appendChild(assistantDiv);
        var contentEl = assistantDiv.querySelector('.content');
        typeIntoElement(contentEl, reply, { msPerChar: 16, byWord: true, scrollContainer: messagesEl })
          .then(function() { loadSessions(); loadDashboardStatus(); })
          .finally(function() { setOrbState('idle'); setStripMode('Waiting (' + (mode === 'realtime' ? 'Realtime' : 'General') + ')'); sendBtn.disabled = false; });
        if (data.intent) updateIntentPanel(text, data);
      })
      .catch(function(e) {
        loadingDiv.remove();
        setTaskItemDone('API call…', 'Failed');
        setOrbState('error');
        setStripMode('Error');
        setStripLatency(Math.round(Date.now() - startTime));
        addErrorBubble(messagesEl, 'Error: ' + (e.message || 'Network error'), { message: text, session_id: currentSessionId || undefined });
        sendBtn.disabled = false;
        setTimeout(function() { setOrbState('idle'); setStripMode('Waiting (' + (mode === 'realtime' ? 'Realtime' : 'General') + ')'); }, 2000);
      });
  }

  function addTaskItem(label, state) {
    var list = document.getElementById('taskList');
    if (!list) return;
    var div = document.createElement('div');
    div.className = 'task-item';
    div.setAttribute('data-task', label);
    div.innerHTML = '<span class="icon ' + (state === 'pending' ? 'pending' : '') + '">' + (state === 'pending' ? '⏳' : '✓') + '</span> ' + label;
    list.appendChild(div);
  }
  function setTaskItemDone(label, doneLabel) {
    var list = document.getElementById('taskList');
    if (!list) return;
    var item = list.querySelector('.task-item[data-task="' + label.replace(/"/g, '\\"') + '"]');
    if (item) {
      item.querySelector('.icon').className = 'icon';
      item.querySelector('.icon').textContent = '✓';
      item.childNodes[1].textContent = doneLabel || label;
    }
  }

  function updateIntentPanel(userText, responseData) {
    var intentEl = document.getElementById('intentDetected');
    var entitiesEl = document.getElementById('intentEntities');
    if (!intentEl) return;
    if (responseData && responseData.intent) {
      intentEl.textContent = 'Detected Intent: ' + (responseData.intent.name || responseData.intent);
      if (entitiesEl && responseData.intent.entities) {
        entitiesEl.innerHTML = 'Entities: ' + (responseData.intent.entities.map(function(e) { return e.name + ': ' + e.value; }).join(', ') || '—');
      }
    } else if (userText) {
      intentEl.textContent = 'Detected Intent: General query';
      if (entitiesEl) entitiesEl.textContent = 'Entities: (extracted when supported)';
    }
  }

  function sendMessage() {
    var text = (inputEl && inputEl.value.trim()) || '';
    if (!text) return;
    sendMessageWithPayload({ message: text });
  }

  sendBtn && sendBtn.addEventListener('click', sendMessage);
  inputEl && inputEl.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });

  (function voiceModule() {
    var voiceBtn = document.getElementById('voiceBtn');
    var voiceLabel = document.getElementById('voiceLabel');
    if (!voiceBtn) return;
    var voiceActive = false;
    var voicePhase = 'wake';
    var voiceStream = null;
    var voiceRecorder = null;
    var wakeChunkMs = 2500;
    var queryChunkMs = 5500;

    function setVoiceUI(listening, phase) {
      voiceBtn.classList.toggle('listening', listening);
      if (voiceLabel) voiceLabel.textContent = phase === 'query' ? 'Listening…' : (listening ? 'Say "Hey Jarvis"' : 'Voice');
      if (typeof setOrbState === 'function') setOrbState(listening ? 'listening' : 'idle');
    }

    function sendAudioToTranscribe(blob) {
      var formData = new FormData();
      formData.append('audio', blob, 'chunk.webm');
      var h = headers();
      delete h['Content-Type'];
      return fetch(API + '/voice/transcribe', { method: 'POST', headers: h, body: formData })
        .then(function(r) { return r.json(); });
    }

    function startWakeLoop() {
      if (!voiceStream || voiceActive === false) return;
      var opts = { mimeType: 'audio/webm;codecs=opus', audioBitsPerSecond: 128000 };
      if (!MediaRecorder.isTypeSupported(opts.mimeType)) opts = { audioBitsPerSecond: 128000 };
      voiceRecorder = new MediaRecorder(voiceStream, opts);
      var wakeChunks = [];
      voiceRecorder.ondataavailable = function(ev) {
        if (ev.data && ev.data.size > 0) wakeChunks.push(ev.data);
      };
      voiceRecorder.onstop = function() {
        if (!voiceActive) return;
        if (voicePhase === 'wake' && wakeChunks.length > 0) {
          var blob = new Blob(wakeChunks, { type: opts.mimeType || 'audio/webm' });
          sendAudioToTranscribe(blob).then(function(data) {
            if (!voiceActive || voicePhase !== 'wake') return;
            if (data && data.woke) {
              voicePhase = 'query';
              setVoiceUI(true, 'query');
              recordQueryOnce();
            } else {
              startWakeLoop();
            }
          }).catch(function() { startWakeLoop(); });
        } else if (voicePhase === 'wake') {
          startWakeLoop();
        } else if (voicePhase === 'query') {
          recordQueryOnce();
        }
      };
      voiceRecorder.start();
      setTimeout(function() {
        if (voiceRecorder && voiceRecorder.state === 'recording' && voicePhase === 'wake') voiceRecorder.stop();
      }, wakeChunkMs);
    }

    function recordQueryOnce() {
      if (!voiceStream || !voiceActive || voicePhase !== 'query') return;
      var opts = { mimeType: 'audio/webm;codecs=opus', audioBitsPerSecond: 128000 };
      if (!MediaRecorder.isTypeSupported(opts.mimeType)) opts = { audioBitsPerSecond: 128000 };
      voiceRecorder = new MediaRecorder(voiceStream, opts);
      var queryChunks = [];
      voiceRecorder.ondataavailable = function(ev) {
        if (ev.data && ev.data.size > 0) queryChunks.push(ev.data);
      };
      voiceRecorder.onstop = function() {
        if (!voiceActive || voicePhase !== 'query') return;
        voicePhase = 'wake';
        setVoiceUI(voiceActive, 'wake');
        if (queryChunks.length > 0) {
          var blob = new Blob(queryChunks, { type: opts.mimeType || 'audio/webm' });
          sendAudioToTranscribe(blob).then(function(data) {
            var text = (data && data.text) ? data.text.trim() : '';
            if (text && typeof sendMessageWithPayload === 'function') sendMessageWithPayload({ message: text });
            if (voiceActive) startWakeLoop();
          }).catch(function() {
            if (voiceActive) startWakeLoop();
          });
        } else {
          if (voiceActive) startWakeLoop();
        }
      };
      voiceRecorder.start();
      setTimeout(function() {
        if (voiceRecorder && voiceRecorder.state === 'recording' && voicePhase === 'query') voiceRecorder.stop();
      }, queryChunkMs);
    }

    function startVoiceMode() {
      voiceActive = true;
      voicePhase = 'wake';
      setVoiceUI(true, 'wake');
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function(stream) {
        voiceStream = stream;
        startWakeLoop();
      }).catch(function(err) {
        voiceActive = false;
        setVoiceUI(false);
        alert('Microphone access needed for voice. Please allow and try again.');
      });
    }

    function stopVoiceMode() {
      voiceActive = false;
      if (voiceRecorder && voiceRecorder.state !== 'inactive') voiceRecorder.stop();
      voiceRecorder = null;
      if (voiceStream) {
        voiceStream.getTracks().forEach(function(t) { t.stop(); });
        voiceStream = null;
      }
      setVoiceUI(false);
    }

    voiceBtn.addEventListener('click', function() {
      if (voiceActive) stopVoiceMode();
      else startVoiceMode();
    });
  })();

  var REMINDER_PLAYED_KEY = 'jarvis_reminder_played';
  function getPlayedNotificationIds() {
    try { return JSON.parse(sessionStorage.getItem(REMINDER_PLAYED_KEY) || '[]'); } catch (e) { return []; }
  }
  function markNotificationPlayed(id) {
    var ids = getPlayedNotificationIds();
    if (ids.indexOf(id) === -1) ids.push(id);
    sessionStorage.setItem(REMINDER_PLAYED_KEY, JSON.stringify(ids.slice(-50)));
  }

  function showReminderToast(notification, blob) {
    var hasAudio = blob && blob.size > 0;
    var url = hasAudio ? URL.createObjectURL(blob) : null;
    var toast = document.getElementById('reminderToast');
    var toastBody = document.getElementById('reminderToastBody');
    var toastPlay = document.getElementById('reminderToastPlay');
    var toastDismiss = document.getElementById('reminderToastDismiss');
    if (!toast || !toastBody) return;
    toastBody.textContent = (notification.title ? notification.title + ': ' : '') + (notification.body || 'Reminder');
    if (toastPlay) {
      toastPlay.style.display = hasAudio ? '' : 'none';
      toastPlay.onclick = hasAudio ? function() {
        var a = new Audio(url);
        a.play().catch(function() {});
        a.onended = function() { try { if (url) URL.revokeObjectURL(url); } catch (e) {} };
      } : null;
    }
    toast.classList.add('visible');
    if (toastDismiss) {
      toastDismiss.onclick = function() {
        toast.classList.remove('visible');
        try { if (url) URL.revokeObjectURL(url); } catch (e) {}
      };
    }
  }

  function pollAndPlayReminders() {
    if (!getToken() || !document.getElementById('dashboard').classList.contains('visible')) return;
    fetch(API + '/notifications', { headers: headers(), method: 'GET' })
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        if (!data || !data.items) return;
        var played = getPlayedNotificationIds();
        for (var i = 0; i < data.items.length; i++) {
          var n = data.items[i];
          if (n.audio_url && played.indexOf(n.id) === -1) {
            markNotificationPlayed(n.id);
            fetch(API + n.audio_url, { headers: headers() })
              .then(function(res) { return res.ok ? res.blob() : null; })
              .then(function(blob) {
                if (!blob) return;
                var url = URL.createObjectURL(blob);
                var audio = new Audio(url);
                audio.onended = function() { URL.revokeObjectURL(url); };
                audio.play().then(function() {
                  if (document.getElementById('jarvisOrb')) setOrbState('listening');
                  audio.onended = function() {
                    URL.revokeObjectURL(url);
                    if (document.getElementById('jarvisOrb')) setOrbState('idle');
                  };
                }).catch(function() {
                  URL.revokeObjectURL(url);
                  showReminderToast(n, blob);
                });
            }).catch(function() {
              showReminderToast(n, null);
            });
            return;
          }
        }
      })
      .catch(function() {});
  }

  if (getToken()) {
    fetch(API + '/me', { headers: headers() })
      .then(function(r) { return r.ok ? showApp() : showAuth(); })
      .catch(function() { showAuth(); });
  } else {
    showAuth();
  }
  setInterval(pollAndPlayReminders, 15000);
  setTimeout(pollAndPlayReminders, 2000);
  document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'visible') pollAndPlayReminders();
  });
})();
