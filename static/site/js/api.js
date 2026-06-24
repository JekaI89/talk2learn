/* ══════════════════════════════════════
   api.js — все вызовы к бэкенду
   ══════════════════════════════════════ */

const API = {

  // ── Auth ──
  async requestEmailCode(email) {
    return _post('/api/auth/email/request-code', { email });
  },
  async verifyEmailCode(email, code) {
    return _post('/api/auth/email/verify', { email, code });
  },
  async verifyTelegram(user) {
    return _post('/api/auth/telegram/verify', user);
  },

  // ── User ──
  async dashboard(userId) {
    return _get(`/api/dashboard/${userId}`);
  },
  async profile(userId) {
    return _get(`/api/profile/${userId}`);
  },
  async languages(userId) {
    return _get(`/api/user/languages/${userId}`);
  },
  async setLanguages(userId, native, target) {
    return _post('/api/user/languages', { user_id: +userId, native_language: native, target_language: target });
  },
  async statsCategories(userId) {
    return _get(`/api/stats/categories/${userId}`);
  },

  // ── Onboarding ──
  async onboardingStatus(userId) {
    return _get(`/api/onboarding/${userId}`);
  },
  async onboardingComplete(userId, level, goal, native, target) {
    return _post('/api/onboarding/complete', { user_id: +userId, level, goal, native_language: native, target_language: target });
  },

  // ── Lessons ──
  async nextLesson(userId, level, contentType) {
    return _get(`/api/lessons/next/${level}?user_id=${userId}&content_type=${contentType}`);
  },
  async completeContent(userId, contentType, contentId) {
    return _post('/api/progress/complete', { user_id: +userId, content_type: contentType, content_id: +contentId });
  },

  // ── Practice ──
  async randomQuestion(userId, level, type) {
    return _get(`/api/random_question?user_id=${userId}&level=${level}&type=${type}`);
  },

  // ── Vocabulary ──
  async vocabTopics(level) {
    const qs = level ? `?level=${level}` : '';
    return _get(`/api/vocab/topics${qs}`);
  },
  async vocabCards(topic, level) {
    const qs = level ? `&level=${level}` : '';
    return _get(`/api/vocab/cards?topic=${encodeURIComponent(topic)}${qs}`);
  },

  // ── Dictionary / Notebook ──
  async userDictionary(userId) {
    return _get(`/api/dictionary/${userId}`);
  },
  async translateWord(userId, word, ctx, native, target) {
    return _post('/api/dictionary/translate', { user_id: +userId, word, context_sentence: ctx.substring(0, 300), native_language: native, target_language: target });
  },
  async quickAdd(userId, word, ctx) {
    return _post('/api/dictionary/quick_add', { user_id: +userId, word, context_sentence: ctx.substring(0, 300) });
  },
  async setWordStatus(userId, word, status) {
    return _post('/api/dictionary/status', { user_id: +userId, word, status });
  },

  // ── Club / Chat ──
  async clubText(fd) {
    const res = await fetch('/api/web-club/text', { method: 'POST', body: fd });
    return res.json();
  },
  async clubVoice(fd) {
    const res = await fetch('/api/web-club/voice', { method: 'POST', body: fd });
    return res.json();
  },

  // ── TTS ──
  ttsUrl(word) {
    return `/api/tts/word?word=${encodeURIComponent(word)}`;
  },
};

/* ── Internal helpers ── */
async function _get(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} → ${res.status}`);
  return res.json();
}

async function _post(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw Object.assign(new Error(data.detail || 'API error'), { data, status: res.status });
  return data;
}
