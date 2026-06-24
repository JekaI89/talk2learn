/* ══════════════════════════════════════
   ui.js — переиспользуемые UI-хелперы
   ══════════════════════════════════════ */

/* ── Toast ── */
const UI = {
  toast(msg, type = 'success') {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    document.getElementById('toast-container').appendChild(el);
    setTimeout(() => el.remove(), 2800);
  },

  loading(html = '') {
    return `<div class="loading-center"><div class="spinner"></div></div>`;
  },

  empty(icon, msg) {
    return `<div class="empty-state"><div class="icon">${icon}</div><p>${msg}</p></div>`;
  },

  /* ── Clickable words (tap for translation) ── */
  makeClickable(text) {
    return text.replace(/([A-Za-zÀ-ÿА-яёЁ]{2,})/g,
      w => `<span class="cw" data-word="${w.replace(/&/g, '&amp;').replace(/</g, '&lt;')}">${w}</span>`
    );
  },

  /* ── Word popup ── */
  showWordPopup() {
    document.getElementById('word-popup-overlay').classList.add('open');
    document.getElementById('word-popup').classList.add('open');
  },
  hideWordPopup() {
    document.getElementById('word-popup-overlay').classList.remove('open');
    document.getElementById('word-popup').classList.remove('open');
  },

  /* ── Sidebar / mobile header user info ── */
  updateUserInfo(name, streak, xp, level) {
    const initial = (name || '?')[0].toUpperCase();
    _setAll('.sidebar-avatar', initial);
    _setAll('.sidebar-user-name', name || 'Ученик');
    _setAll('.sidebar-user-meta', `🔥 ${streak}  ·  ⭐ ${xp} XP`);
    _setAll('#mobile-header-xp', `⭐ ${xp} XP`);
    _setAll('#mobile-avatar-letter', initial);
    // Daily goal bar (hardcoded 75% until real data)
    document.querySelectorAll('.sidebar-goal-fill').forEach(el => el.style.width = '75%');
  },

  /* ── CEFR level badge ── */
  levelBadge(lvl) {
    return `<span class="badge badge-primary">${lvl}</span>`;
  },

  /* ── Spinner inside element ── */
  setLoading(el) {
    if (typeof el === 'string') el = document.getElementById(el);
    if (el) el.innerHTML = UI.loading();
  },

  /* ── Progress bar HTML ── */
  progressBar(pct, label, sub, color = 'blue') {
    return `
      <div class="progress-wrap">
        ${label || sub ? `<div class="progress-meta"><span>${label || ''}</span><span>${sub || ''}</span></div>` : ''}
        <div class="progress-track"><div class="progress-fill ${color}" style="width:${pct}%"></div></div>
      </div>`;
  },
};

function _setAll(sel, text) {
  document.querySelectorAll(sel).forEach(el => el.textContent = text);
}

/* ── Global word-tap handler ── */
document.addEventListener('click', e => {
  const span = e.target.closest('.cw');
  if (!span) return;
  APP.handleWordTap(span.dataset.word, span.closest('div')?.textContent || '');
});
