/**
 * nav.js — Shared navigation bar for all pages.
 *
 * Usage in each HTML page:
 *   1. Place a bare <nav> tag:
 *        <nav id="app-nav" class="navbar app-navbar navbar-expand-lg" data-active="chat|stats|docs"></nav>
 *   2. After building API_URL, call:
 *        initNav(API_URL);
 *
 * Provides:
 *   - Rendered navbar HTML (brand, links, usage-pill, user dropdown)
 *   - window.updateUsageStats()   — pages can call after events (e.g. post-send)
 *   - window.getCurrentUser()     — returns current user object {id,username,display_name,role_id,...}
 *   - window.getCurrentUserRole() — returns role_id string (or "customer" as fallback)
 *   - Auto-refresh of the pill every 15 s
 */
(function () {
  const PAGES = [
    { key: 'chat',     href: 'index.html',    icon: '&#x1F4AC;', label: 'Chat' },
    { key: 'messages', href: 'messages.html', icon: '&#x1F4DD;', label: 'Messages' },
    { key: 'stats',    href: 'stats.html',    icon: '&#x1F4CA;', label: 'Thống kê' },
    { key: 'docs',     href: 'docs.html',     icon: '&#x1F4D6;', label: 'API Docs' },
    { key: 'admin',    href: 'admin.html',    icon: '&#x1F4C1;', label: 'Admin' },
    { key: 'settings', href: 'settings.html', icon: '&#x2699;&#xFE0F;', label: 'Settings' },
  ];

  // ── State ────────────────────────────────────────────────────────────
  let _users = [];        // cached user list
  let _currentUser = null;

    const COOKIE_NAME = 'currentUserId';
    const COOKIE_DAYS = 30;

    function _setCookie(name, value, days) {
      const expires = new Date(Date.now() + days * 864e5).toUTCString();
      document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/`;
    }
    function _deleteCookie(name) {
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
    }
    function _getCookie(name) {
      const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
      return match ? decodeURIComponent(match[1]) : null;
    }

    function _saveUser(user) {
      _currentUser = user;
      if (user) {
        _setCookie(COOKIE_NAME, user.id, COOKIE_DAYS);
      } else {
        _deleteCookie(COOKIE_NAME);
      }
      // Dispatch event so pages can react (e.g. index.html refreshes role)
      window.dispatchEvent(new CustomEvent('navUserChanged', { detail: user }));
    }

  window.getCurrentUser     = () => _currentUser;
  window.getCurrentUserRole = () => (_currentUser && _currentUser.role_id) || 'customer';

  // ── initNav ──────────────────────────────────────────────────────────
  window.initNav = function (apiUrl) {
    const nav = document.getElementById('app-nav');
    if (!nav) return;

    const active = nav.dataset.active || '';
    const links = PAGES.map(p =>
      `<li class="nav-item"><a class="nav-link${p.key === active ? ' active' : ''}" href="${p.href}">${p.icon} ${p.label}</a></li>`
    ).join('');

    nav.innerHTML = `
      <a class="navbar-brand" href="index.html">&#x1F916; Bot MVP</a>
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMain"
              aria-controls="navMain" aria-expanded="false">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="navMain">
        <ul class="navbar-nav mx-auto gap-1">${links}</ul>
        <div class="d-flex align-items-center gap-2">
          <select id="navUserSelect" class="form-select form-select-sm" style="max-width:180px;font-size:.82rem;"
                  title="Chọn user đang đăng nhập">
            <option value="">👤 Chọn user...</option>
          </select>
          <div class="usage-pill">
            <div class="stat-item"><span class="stat-label">Requests:</span><span class="stat-value" id="statRequests">&mdash;</span></div>
            <span class="stat-sep">|</span>
            <div class="stat-item"><span class="stat-label">Tokens:</span><span class="stat-value" id="statTokens">&mdash;</span></div>
            <span class="stat-sep">|</span>
            <div class="stat-item"><span class="stat-label">Cost:</span><span class="stat-value" id="statCost">&mdash;</span></div>
          </div>
        </div>
      </div>`;

    // ── Load users ──────────────────────────────────────────────────
    const sel = document.getElementById('navUserSelect');

    async function loadUsers() {
      try {
        const res = await fetch(`${apiUrl}/users`);
        if (!res.ok) return;
        _users = await res.json();

        // Rebuild options
        sel.innerHTML = '<option value="">👤 Chọn user...</option>';
        _users.forEach(u => {
          const opt = document.createElement('option');
          opt.value = u.id;
          opt.textContent = `${u.display_name} (${u.role_id})`;
          if (!u.is_active) opt.textContent += ' [inactive]';
          sel.appendChild(opt);
        });

        // Restore from cookie (u.id is integer from DB, cookie is string → use ==)
        const saved = _getCookie(COOKIE_NAME);
        if (saved) {
          // eslint-disable-next-line eqeqeq
          const found = _users.find(u => u.id == saved);
          if (found) {
            sel.value = found.id;
            _currentUser = found;
          }
        }
      } catch (e) { /* ignore */ }
    }

    sel.addEventListener('change', () => {
      // sel.value is always a string; u.id is an integer from JSON — use == for comparison
      const user = _users.find(u => u.id == sel.value) || null;
      _saveUser(user);
    });

    loadUsers();

    // Expose so pages can reload user list after create/delete
    window.reloadNavUsers = loadUsers;

    // ── Usage pill ──────────────────────────────────────────────────
    async function refreshStats() {
      try {
        const res = await fetch(`${apiUrl}/stats`);
        if (!res.ok) return;
        const d = await res.json();
        const totalTokens = (d.total_input_tokens || 0) + (d.total_output_tokens || 0);
        document.getElementById('statRequests').textContent = (d.total_requests || 0).toLocaleString();
        document.getElementById('statTokens').textContent =
          totalTokens >= 1000 ? (totalTokens / 1000).toFixed(1) + 'K' : totalTokens.toLocaleString();
        const usd = d.total_cost_usd || 0;
        const vndK = (usd * 25000 / 1000).toFixed(1).replace('.', ',');
        document.getElementById('statCost').textContent = '$' + usd.toFixed(4) + ' (~' + vndK + 'K đ)';
      } catch (e) { /* silently ignore network errors */ }
    }

    window.updateUsageStats = refreshStats;
    refreshStats();
    setInterval(refreshStats, 15000);
  };
}());
