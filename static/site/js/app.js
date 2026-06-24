/* ══════════════════════════════════════
   app.js — роутер, состояние, auth
   ══════════════════════════════════════ */

/* ── Глобальное состояние ── */
const STATE = {
  userId: 0,
  userEmail: '',
  userName: '',
  nativeLang: 'ru',
  targetLang: 'en',
  level: 'A1',
  currentCategory: 'lessons',
  popupWord: '',
  popupCtx: '',

  // flashcard
  vfCards: [], vfIdx: 0, vfKnown: [], vfLearning: [], vfFlipped: false, vfCard: null,
  // sentence builder
  sbSelected: [], sbCorrect: '', sbQId: null,
  // practice
  practiceQId: null, practiceCorrect: null,
  // chat
  clubMediaRec: null, clubChunks: [], clubStream: null,
  sitMediaRec: null, sitChunks: [], sitStream: null,
  currentSit: '',
};

/* ── Константы ── */
const LEVELS = ['A1','A2','B1','B2','C1','C2'];
const LEVEL_GRAD = { A1:'lvl-A1', A2:'lvl-A2', B1:'lvl-B1', B2:'lvl-B2', C1:'lvl-C1', C2:'lvl-C2' };
const TOPIC_ICONS = { Animals:'🐾', Food:'🍽️', Transport:'🚀', Home:'🏠', Nature:'🌿', Emotions:'😊', Sports:'⚽', Technology:'💻' };
const AI_GREET = { en:'Hello! Feel free to type or use the microphone 🎤', de:'Hallo! Wie kann ich helfen?', fr:'Bonjour ! Comment puis-je vous aider ?', es:'¡Hola! ¿En qué puedo ayudarte?', it:'Ciao!', zh:'你好！', ru:'Привет!' };
const SIT_GREET = { shop:{en:'Welcome! How can I help you today?'}, restaurant:{en:'Good evening! Do you have a reservation?'}, airport:{en:'Good morning! May I see your passport?'}, hotel:{en:"Welcome! Do you have a reservation?"}, doctor:{en:"Hello! What brings you in today?"}, emergency:{en:"Emergency services, what's your emergency?"} };
const SIT_HINTS = { shop:'🛒 Вы покупатель', restaurant:'🍽️ Вы гость', airport:'✈️ Вы пассажир', hotel:'🏨 Вы гость', doctor:'🏥 Вы пациент', emergency:'🚨 Опишите ситуацию' };

/* ═══════════════════════════════════════
   ROUTER
═══════════════════════════════════════ */

const ROUTES = {
  home:           '/pages/home.html',
  lessons:        '/pages/lessons.html',
  'lesson-view':  '/pages/lesson-view.html',
  dictionary:     '/pages/dictionary.html',
  club:           '/pages/club.html',
  situations:     '/pages/situations.html',
  'sit-chat':     '/pages/sit-chat.html',
  notebook:       '/pages/notebook.html',
  profile:        '/pages/profile.html',
  onboarding:     '/pages/onboarding.html',
  'practice':     '/pages/practice.html',
};

const _pageCache = {};

const NAV_TITLES = {
  home:'Главная', lessons:'Уроки', dictionary:'Словарь',
  club:'Разговорный клуб', notebook:'Блокнот', profile:'Профиль',
  situations:'Ситуации', onboarding:'Добро пожаловать',
  'lesson-view':'Урок', practice:'Практика', 'sit-chat':'Ситуация',
};

const APP = {
  /* ── navigate to a page ── */
  async go(page, params = {}) {
    const pathBase = window.location.pathname.replace(/\/[^/]*$/, '/');
    const route = ROUTES[page];
    if (!route) return console.error('Unknown page:', page);

    const container = document.getElementById('page-container');
    container.innerHTML = UI.loading();

    // Update active nav
    document.querySelectorAll('.nav-item, .mob-nav-btn').forEach(el => {
      el.classList.toggle('active', el.dataset.page === page);
    });
    document.getElementById('mobile-header-title').textContent = NAV_TITLES[page] || 'Talk2Learn';

    // Load HTML fragment (cache it)
    if (!_pageCache[page]) {
      try {
        const res = await fetch('/site' + route);
        if (!res.ok) throw new Error(res.status);
        _pageCache[page] = await res.text();
      } catch (e) {
        container.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>Не удалось загрузить страницу</p></div>`;
        return;
      }
    }

    container.innerHTML = _pageCache[page];

    // Call page-specific init
    const init = PAGE_INITS[page];
    if (init) await init(params);
  },

  /* ── Auth flow ── */
  showAuth() {
    document.getElementById('shell').classList.add('hidden');
    document.getElementById('auth-screen').classList.add('visible');
  },
  showApp() {
    document.getElementById('auth-screen').classList.remove('visible');
    document.getElementById('shell').classList.remove('hidden');
  },

  async initApp() {
    APP.showApp();
    try {
      const langs = await API.languages(STATE.userId);
      STATE.nativeLang = langs.native || 'ru';
      STATE.targetLang = langs.target || 'en';
    } catch (e) {}

    try {
      const data = await API.dashboard(STATE.userId);
      const p = data.user || data;
      STATE.userName = p.name || STATE.userEmail.split('@')[0] || 'Ученик';
      STATE.level = p.level || 'A1';
      UI.updateUserInfo(STATE.userName, p.streak ?? 0, p.xp ?? 0, STATE.level);
    } catch (e) {}

    try {
      const ob = await API.onboardingStatus(STATE.userId);
      if (!ob.onboarding_done) { await APP.go('onboarding'); return; }
    } catch (e) {}

    await APP.go('home');
  },

  /* ── Word tap (translate popup) ── */
  async handleWordTap(word, ctx) {
    STATE.popupWord = word;
    STATE.popupCtx = ctx;
    const popup = document.getElementById('word-popup');
    popup.querySelector('#pw-word').textContent = word;
    popup.querySelector('#pw-trans').textContent = '⏳ Перевод...';
    popup.querySelector('#pw-transcription').textContent = '';
    popup.querySelector('#pw-example').textContent = '';
    popup.querySelector('#pw-status').textContent = '';
    const addBtn = popup.querySelector('#pw-add-btn');
    addBtn.disabled = false;
    addBtn.textContent = '+ В мой словарь';
    UI.showWordPopup();

    try {
      const d = await API.translateWord(STATE.userId, word, ctx, STATE.nativeLang, STATE.targetLang);
      if (d.status === 'success') {
        popup.querySelector('#pw-transcription').textContent = d.transcription || '';
        popup.querySelector('#pw-trans').textContent = d.translation || '—';
        popup.querySelector('#pw-example').textContent = d.context_example ? `"${d.context_example}"` : '';
      } else {
        popup.querySelector('#pw-trans').textContent = d.message || 'Ошибка';
      }
    } catch (e) {
      popup.querySelector('#pw-trans').textContent = 'Ошибка соединения';
    }
  },
};

/* ═══════════════════════════════════════
   PAGE INITS (called after HTML injected)
═══════════════════════════════════════ */

const PAGE_INITS = {};

/* ── home ── */
PAGE_INITS.home = async () => {
  // filled by home.html inline script
};

/* ── lessons ── */
PAGE_INITS.lessons = async () => {
  renderLevelsGrid();
};

/* ── lesson-view ── */
PAGE_INITS['lesson-view'] = async (params) => {
  STATE.currentCategory = params.category || STATE.currentCategory;
  if (params.level) STATE.level = params.level;
  await loadNextLesson();
};

/* ── dictionary ── */
PAGE_INITS.dictionary = async () => {
  loadVocabTopics(null);
};

/* ── practice ── */
PAGE_INITS.practice = async (params) => {
  if (params.mode === 'sentence_builder') loadSentenceBuilder();
  else loadPractice();
};

/* ── club ── */
PAGE_INITS.club = async () => {
  const box = document.getElementById('chat-box');
  if (box && box.children.length === 0) initClubGreeting();
};

/* ── sit-chat ── */
PAGE_INITS['sit-chat'] = async (params) => {
  if (params.sit) {
    STATE.currentSit = params.sit;
    document.getElementById('sit-title').textContent = params.title || '';
    document.getElementById('sit-hint').textContent = SIT_HINTS[params.sit] || '';
    const box = document.getElementById('sit-chat-box');
    box.innerHTML = '';
    const greet = (SIT_GREET[params.sit] || {})[STATE.targetLang] || (SIT_GREET[params.sit] || {}).en || 'Hello!';
    addMsg(box, 'ai', greet);
  }
};

/* ── notebook ── */
PAGE_INITS.notebook = async () => { await loadNotebook(); };

/* ── profile ── */
PAGE_INITS.profile = async () => { await loadProfile(); };

/* ── onboarding ── */
PAGE_INITS.onboarding = async () => {
  // handled inline in onboarding.html
};

/* ═══════════════════════════════════════
   LESSONS
═══════════════════════════════════════ */

function renderLevelsGrid() {
  const grid = document.getElementById('levels-grid');
  if (!grid) return;
  grid.innerHTML = LEVELS.map(lvl => `
    <button class="card card-pad card-hover ${LEVEL_GRAD[lvl]} text-white cursor-pointer"
      onclick="APP.go('lesson-view', {level:'${lvl}', category:STATE.currentCategory})">
      <div style="font-size:11px;opacity:.75">Уровень</div>
      <div style="font-size:28px;font-weight:800">${lvl}</div>
    </button>`).join('');
}

async function loadNextLesson() {
  const el = document.getElementById('lesson-content');
  if (!el) return;
  UI.setLoading(el);
  const typeMap = { lessons:'lesson', grammar:'grammar', vocabulary:'vocabulary' };
  const ct = typeMap[STATE.currentCategory] || 'lesson';
  try {
    const lesson = await API.nextLesson(STATE.userId, STATE.level, ct);
    if (lesson.completed) { renderLevelComplete(el); return; }
    renderLesson(el, lesson);
  } catch (e) { el.innerHTML = `<p style="color:var(--clr-rose);text-align:center;padding:32px">Ошибка загрузки</p>`; }
}

function renderLesson(el, lesson) {
  const p = lesson.progress || {};
  const total = p.total || 0, num = p.next_num || 1;
  const pct = total > 0 ? Math.round(((num - 1) / total) * 100) : 0;
  el.innerHTML = `
    ${total > 0 ? UI.progressBar(pct, `Урок ${num} из ${total}`, `${pct}%`) : ''}
    <div class="mt-16">
      <div class="text-muted mb-8 text-sm">${(lesson.type || 'урок').toUpperCase()} · ${STATE.level}</div>
      <h1 style="font-size:22px;font-weight:800;margin-bottom:16px;line-height:1.3">${lesson.title}</h1>
      <p class="text-muted mb-12">💡 Нажмите на слово для перевода</p>
      <div class="card card-pad mb-16" style="line-height:1.9;font-size:15px">${UI.makeClickable(lesson.lesson_text || '')}</div>
      <button id="complete-btn" class="btn btn-accent btn-full btn-lg"
        onclick="completeLesson('${lesson.type || 'lesson'}', ${lesson.id})">
        ✅ Просмотрено · +5 XP
      </button>
    </div>`;
}

function renderLevelComplete(el) {
  const idx = LEVELS.indexOf(STATE.level);
  const hasNext = idx < LEVELS.length - 1;
  el.innerHTML = `
    <div class="empty-state" style="padding-top:64px">
      <div class="icon">🎉</div>
      <h2 style="font-size:22px;font-weight:800;margin-bottom:8px">Уровень ${STATE.level} пройден!</h2>
      <p class="mb-24">Все материалы пройдены. Отличная работа!</p>
      ${hasNext ? `<button class="btn btn-primary" onclick="STATE.level='${LEVELS[idx+1]}';loadNextLesson()">Следующий: ${LEVELS[idx + 1]} →</button>` : '<p style="font-weight:700">🏆 Вы прошли все уровни!</p>'}
      <br><button class="btn btn-ghost mt-12" onclick="APP.go('lessons')">← К выбору уровня</button>
    </div>`;
}

async function completeLesson(type, id) {
  const btn = document.getElementById('complete-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Сохранение...'; }
  try {
    const d = await API.completeContent(STATE.userId, type, id);
    if (d.xp_earned > 0) UI.toast(`🎉 +${d.xp_earned} XP!`);
    await loadNextLesson();
  } catch (e) {
    UI.toast('Ошибка', 'error');
    if (btn) { btn.disabled = false; btn.textContent = '✅ Просмотрено · +5 XP'; }
  }
}

/* ═══════════════════════════════════════
   PRACTICE — multiple choice
═══════════════════════════════════════ */

async function loadPractice() {
  const el = document.getElementById('practice-content');
  if (!el) return;
  UI.setLoading(el);
  try {
    const q = await API.randomQuestion(STATE.userId, STATE.level, 'multiple_choice');
    if (q.error === 'no_more_questions') { el.innerHTML = UI.empty('🎉', 'Все вопросы уровня пройдены!'); return; }
    STATE.practiceQId = q.question_id;
    STATE.practiceCorrect = q.correct_option;
    el.innerHTML = `
      <div class="card card-pad mb-16">
        <div class="text-muted mb-8 text-sm">ВОПРОС</div>
        <p style="font-size:15px">${q.question}</p>
      </div>
      <div id="practice-options" class="flex-col gap-8">
        ${q.options.map((opt, i) => `
          <button onclick="checkAnswer(${i + 1}, this)"
            class="card card-pad" style="text-align:left;transition:border-color .15s;border-width:2px;cursor:pointer">
            <span style="color:var(--clr-txt-3);margin-right:8px;font-weight:700">${String.fromCharCode(65 + i)}.</span>${opt}
          </button>`).join('')}
      </div>
      <div id="practice-feedback" class="hidden card card-pad mt-16 text-center fw-700"></div>`;
  } catch (e) { el.innerHTML = `<p style="color:var(--clr-rose);text-align:center;padding:32px">Ошибка</p>`; }
}

async function checkAnswer(selected, btn) {
  document.querySelectorAll('#practice-options button').forEach(b => b.disabled = true);
  const fb = document.getElementById('practice-feedback');
  fb.classList.remove('hidden');
  if (selected === STATE.practiceCorrect) {
    btn.style.cssText = 'background:var(--clr-accent-lt);border-color:var(--clr-accent);color:var(--clr-accent-dk)';
    fb.style.cssText = 'background:var(--clr-accent-lt);color:var(--clr-accent-dk)';
    fb.textContent = '✅ Правильно!';
    try { await API.completeContent(STATE.userId, 'practice', STATE.practiceQId); } catch(e) {}
  } else {
    btn.style.cssText = 'background:var(--clr-rose-lt);border-color:var(--clr-rose);color:var(--clr-rose)';
    fb.style.cssText = 'background:var(--clr-rose-lt);color:var(--clr-rose)';
    fb.textContent = '❌ Неверно';
  }
  setTimeout(loadPractice, 2000);
}

/* ═══════════════════════════════════════
   SENTENCE BUILDER
═══════════════════════════════════════ */

async function loadSentenceBuilder() {
  const el = document.getElementById('practice-content');
  if (!el) return;
  STATE.sbSelected = [];
  UI.setLoading(el);
  try {
    const q = await API.randomQuestion(STATE.userId, STATE.level, 'sentence_builder');
    if (q.error === 'no_more_questions') { el.innerHTML = UI.empty('🎉', 'Все задания пройдены!'); return; }
    STATE.sbCorrect = q.correct_sentence;
    STATE.sbQId = q.question_id;
    el.innerHTML = `
      <div class="card card-pad mb-16">
        <div class="text-muted mb-8 text-sm">ПЕРЕВЕДИТЕ</div>
        <p style="font-size:15px">${q.question}</p>
      </div>
      <div id="sb-zone" style="min-height:52px;border:2px dashed var(--clr-border);border-radius:12px;padding:10px;display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px;align-items:flex-start">
        <span id="sb-hint" style="color:var(--clr-txt-3);font-size:13px;width:100%;text-align:center">Нажимайте слова ниже</span>
      </div>
      <div id="sb-bank" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px">
        ${q.word_bank.map((w, i) => `<button class="badge badge-primary" style="font-size:13px;padding:6px 12px;cursor:pointer" data-word="${w.replace(/"/g,'&quot;')}" data-idx="${i}" onclick="sbPick(this)">${w}</button>`).join('')}
      </div>
      <div id="sb-feedback" class="hidden card card-pad text-center fw-700 mb-16"></div>
      <button id="sb-check" onclick="checkSb()" disabled class="btn btn-ghost btn-full" style="cursor:not-allowed">Проверить</button>`;
  } catch(e) { el.innerHTML = `<p style="color:var(--clr-rose);text-align:center">Ошибка</p>`; }
}

function sbPick(btn) {
  const { word, idx } = btn.dataset;
  btn.style.visibility = 'hidden';
  btn.disabled = true;
  const hint = document.getElementById('sb-hint');
  if (hint) hint.remove();
  STATE.sbSelected.push({ word, idx });
  const zone = document.getElementById('sb-zone');
  const chip = document.createElement('button');
  chip.className = 'badge badge-primary';
  chip.style.cssText = 'font-size:13px;padding:6px 12px;cursor:pointer;background:var(--clr-primary);color:#fff';
  chip.textContent = word;
  chip.dataset.idx = idx;
  chip.onclick = () => sbReturn(chip, idx);
  zone.appendChild(chip);
  updateSbBtn();
}

function sbReturn(chip, idx) {
  chip.remove();
  STATE.sbSelected = STATE.sbSelected.filter(w => w.idx !== idx);
  const b = document.querySelector(`#sb-bank button[data-idx="${idx}"]`);
  if (b) { b.style.visibility = ''; b.disabled = false; }
  if (STATE.sbSelected.length === 0) {
    const zone = document.getElementById('sb-zone');
    const hint = document.createElement('span');
    hint.id = 'sb-hint';
    hint.style.cssText = 'color:var(--clr-txt-3);font-size:13px;width:100%;text-align:center';
    hint.textContent = 'Нажимайте слова ниже';
    zone.appendChild(hint);
  }
  updateSbBtn();
}

function updateSbBtn() {
  const btn = document.getElementById('sb-check');
  if (!btn) return;
  const ok = STATE.sbSelected.length > 0;
  btn.disabled = !ok;
  btn.className = ok ? 'btn btn-primary btn-full' : 'btn btn-ghost btn-full';
  btn.style.cursor = ok ? 'pointer' : 'not-allowed';
}

async function checkSb() {
  const user = STATE.sbSelected.map(w => w.word).join(' ');
  const norm = s => s.toLowerCase().replace(/[.!?,]/g,'').trim().replace(/\s+/g,' ');
  const ok = norm(user) === norm(STATE.sbCorrect);
  const fb = document.getElementById('sb-feedback');
  fb.classList.remove('hidden');
  document.querySelectorAll('#sb-zone button, #sb-bank button, #sb-check').forEach(b => b.disabled = true);
  if (ok) {
    fb.style.cssText = 'background:var(--clr-accent-lt);color:var(--clr-accent-dk)';
    fb.textContent = '✅ Правильно!';
    try { await API.completeContent(STATE.userId, 'practice', STATE.sbQId); } catch(e) {}
    setTimeout(loadSentenceBuilder, 2000);
  } else {
    fb.style.cssText = 'background:var(--clr-rose-lt);color:var(--clr-rose)';
    fb.textContent = `❌ Правильно: «${STATE.sbCorrect}»`;
    setTimeout(loadSentenceBuilder, 3000);
  }
}

/* ═══════════════════════════════════════
   VOCABULARY / FLASHCARDS
═══════════════════════════════════════ */

async function loadVocabTopics(level) {
  const grid = document.getElementById('vocab-grid');
  if (!grid) return;
  // Update filter buttons
  document.querySelectorAll('.vocab-lvl-btn').forEach(b => {
    const active = level === null ? b.dataset.lvl === 'all' : b.dataset.lvl === level;
    b.className = `badge ${active ? 'badge-primary' : 'badge-accent'} cursor-pointer`;
    b.style.fontSize = '13px'; b.style.padding = '6px 14px';
  });
  UI.setLoading(grid);
  try {
    const topics = await API.vocabTopics(level);
    if (!topics.length) { grid.innerHTML = UI.empty('📭', 'Темы пока не добавлены'); return; }
    const byTopic = {};
    topics.forEach(t => {
      if (!byTopic[t.topic]) byTopic[t.topic] = { count: 0, level: t.level };
      byTopic[t.topic].count += parseInt(t.card_count);
    });
    grid.innerHTML = Object.entries(byTopic).map(([topic, info]) => {
      const icon = TOPIC_ICONS[topic] || '📖';
      return `<button onclick="openVocabTopic('${topic.replace(/'/g,"\\'")}','${level||''}')"
        class="card card-pad card-hover text-white ${LEVEL_GRAD[info.level] || 'lvl-A1'} cursor-pointer" style="text-align:left">
        <div style="font-size:28px;margin-bottom:8px">${icon}</div>
        <div style="font-weight:700;font-size:14px">${topic}</div>
        <div style="font-size:12px;opacity:.8">${info.count} слов</div>
      </button>`;
    }).join('');
  } catch(e) { grid.innerHTML = UI.empty('⚠️', 'Ошибка загрузки'); }
}

async function openVocabTopic(topic, level) {
  // Inject flashcard view into page
  const container = document.getElementById('page-container');
  container.innerHTML = `
    <button class="btn btn-ghost btn-sm mb-16" onclick="APP.go('dictionary')">← К темам</button>
    <div id="flashcard-content">${UI.loading()}</div>`;
  try {
    const cards = await API.vocabCards(topic, level);
    if (!cards.length) { document.getElementById('flashcard-content').innerHTML = UI.empty('📭', 'Карточки не найдены'); return; }
    startFlashcards(cards);
  } catch(e) { document.getElementById('flashcard-content').innerHTML = UI.empty('⚠️', 'Ошибка'); }
}

function startFlashcards(cards) {
  STATE.vfCards = shuffle([...cards]); STATE.vfIdx = 0; STATE.vfKnown = []; STATE.vfLearning = []; STATE.vfFlipped = false;
  renderFlashcard();
}

function renderFlashcard() {
  const el = document.getElementById('flashcard-content');
  if (!el) return;
  if (STATE.vfIdx >= STATE.vfCards.length) { renderFCComplete(el); return; }
  STATE.vfCard = STATE.vfCards[STATE.vfIdx]; STATE.vfFlipped = false;
  const card = STATE.vfCard;
  const pct = STATE.vfCards.length > 0 ? Math.round(STATE.vfIdx / STATE.vfCards.length * 100) : 0;
  let emoji = '📖'; try { emoji = String.fromCodePoint(parseInt(card.emoji_code, 16)); } catch(e) {}
  el.innerHTML = `
    ${UI.progressBar(pct, `${STATE.vfIdx}/${STATE.vfCards.length}`, `${STATE.vfKnown.length} знаю · ${STATE.vfLearning.length} учу`)}
    <div id="fc" class="flashcard mt-16" onclick="flipFC()">
      <div class="${LEVEL_GRAD[card.level] || 'lvl-A1'}" style="width:72px;height:72px;border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:36px;margin-bottom:12px">${emoji}</div>
      <div style="font-size:24px;font-weight:800;margin-bottom:8px">${card.word}</div>
      <span class="badge badge-primary">${card.level}</span>
      <div id="fc-hint" class="text-muted mt-12 text-sm">Нажмите, чтобы открыть</div>
      <div id="fc-back" class="hidden mt-16 text-center" style="width:100%">
        <div style="font-size:18px;font-weight:700;color:var(--clr-primary);margin-bottom:6px">${card.translation || ''}</div>
        <div class="text-muted text-sm">${card.definition || ''}</div>
      </div>
    </div>
    <div id="fc-btns" class="hidden grid-2 mt-16">
      <button onclick="rateFC('learning')" class="btn btn-danger btn-full">👈 Учу</button>
      <button onclick="rateFC('known')" class="btn btn-accent btn-full">Знаю 👉</button>
    </div>
    <button onclick="speakWord()" class="btn btn-ghost btn-full mt-8 btn-sm">🔊 Произношение</button>`;
}

function flipFC() {
  if (STATE.vfFlipped) return;
  STATE.vfFlipped = true;
  document.getElementById('fc-hint').classList.add('hidden');
  document.getElementById('fc-back').classList.remove('hidden');
  document.getElementById('fc-btns').classList.remove('hidden');
  document.getElementById('fc').classList.add('flipped');
}

function rateFC(rating) {
  if (!STATE.vfFlipped) { flipFC(); return; }
  if (rating === 'known') {
    STATE.vfKnown.push(STATE.vfCard);
    API.completeContent(STATE.userId, 'vocab_card', STATE.vfCard.id).catch(() => {});
  } else {
    STATE.vfLearning.push(STATE.vfCard);
    API.quickAdd(STATE.userId, STATE.vfCard.word, STATE.vfCard.definition || '').catch(() => {});
  }
  STATE.vfIdx++;
  renderFlashcard();
}

function renderFCComplete(el) {
  el.innerHTML = `
    <div class="empty-state">
      <div class="icon">🎉</div>
      <h3 style="font-size:20px;font-weight:800;margin-bottom:8px">Тема пройдена!</h3>
      <div class="grid-2 mt-16 mb-16">
        <div class="card card-pad text-center" style="background:var(--clr-accent-lt)"><div style="font-size:28px;font-weight:800;color:var(--clr-accent-dk)">${STATE.vfKnown.length}</div><div class="text-muted text-sm">Знаю</div></div>
        <div class="card card-pad text-center" style="background:var(--clr-rose-lt)"><div style="font-size:28px;font-weight:800;color:var(--clr-rose)">${STATE.vfLearning.length}</div><div class="text-muted text-sm">Учу</div></div>
      </div>
      <button class="btn btn-primary btn-full mb-8" onclick="startFlashcards(STATE.vfCards)">Повторить все</button>
      ${STATE.vfLearning.length > 0 ? `<button class="btn btn-ghost btn-full" onclick="startFlashcards(STATE.vfLearning)">Повторить «учу»</button>` : ''}
    </div>`;
}

function speakWord() {
  if (!STATE.vfCard) return;
  new Audio(API.ttsUrl(STATE.vfCard.word)).play().catch(() => {});
}

/* ═══════════════════════════════════════
   NOTEBOOK
═══════════════════════════════════════ */

async function loadNotebook() {
  const el = document.getElementById('notebook-content');
  const cnt = document.getElementById('notebook-count');
  if (!el) return;
  UI.setLoading(el);
  try {
    const words = await API.userDictionary(STATE.userId);
    if (cnt) cnt.textContent = `${words.length} слов`;
    if (!words.length) { el.innerHTML = UI.empty('📒', 'Нажмите на слово в уроке — оно появится здесь'); return; }
    el.innerHTML = words.map(w => `
      <div class="card card-pad mb-12">
        <div class="flex items-center justify-between">
          <div>
            <div style="font-size:18px;font-weight:700">${w.word}</div>
            ${w.transcription ? `<div class="text-muted text-sm">${w.transcription}</div>` : ''}
            <div style="color:var(--clr-primary);font-weight:600;margin-top:2px">${w.translation}</div>
          </div>
          <button onclick="toggleWordStatus('${w.word.replace(/'/g,"\\'")}','${w.status}')"
            class="badge ${w.status === 'known' ? 'badge-accent' : 'badge-orange'}" style="cursor:pointer">
            ${w.status === 'known' ? '✓ Знаю' : 'Учу'}
          </button>
        </div>
        ${w.context_example ? `<div class="text-muted text-sm mt-8" style="border-top:1px solid var(--clr-border);padding-top:8px;font-style:italic">"${w.context_example}"</div>` : ''}
      </div>`).join('');
  } catch(e) { el.innerHTML = UI.empty('⚠️', 'Ошибка загрузки'); }
}

async function toggleWordStatus(word, status) {
  const newStatus = status === 'known' ? 'learning' : 'known';
  try { await API.setWordStatus(STATE.userId, word, newStatus); await loadNotebook(); } catch(e) {}
}

/* ═══════════════════════════════════════
   PROFILE
═══════════════════════════════════════ */

async function loadProfile() {
  const el = document.getElementById('profile-content');
  if (!el) return;
  UI.setLoading(el);
  try {
    const p = await API.profile(STATE.userId);
    const xpPct = Math.min(100, Math.round((p.xp % 50) / 50 * 100));
    let catHtml = '';
    try {
      const cats = await API.statsCategories(STATE.userId);
      const labels = { lesson:{icon:'📖',name:'Уроки'}, grammar:{icon:'✍️',name:'Грамматика'}, vocabulary:{icon:'💬',name:'Лексика'}, practice:{icon:'🎯',name:'Практика'}, vocab_cards:{icon:'🃏',name:'Карточки'} };
      catHtml = Object.entries(labels).map(([k, {icon, name}]) => {
        const s = cats[k] || { completed: 0, total: 0 };
        const pct = s.total > 0 ? Math.min(100, Math.round(s.completed / s.total * 100)) : 0;
        return `<div class="mb-12">
          <div class="flex items-center justify-between mb-8" style="font-size:13px">
            <span>${icon} ${name}</span>
            <span class="text-muted">${s.total === 0 ? 'нет данных' : `${s.completed}/${s.total}`}</span>
          </div>
          ${UI.progressBar(pct)}
        </div>`;
      }).join('');
    } catch(e) {}

    el.innerHTML = `
      <div style="background:linear-gradient(135deg,var(--clr-primary),var(--clr-accent));border-radius:var(--radius-xl);padding:28px;color:#fff;text-align:center;margin-bottom:20px">
        <div style="width:64px;height:64px;background:rgba(255,255,255,.2);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:28px;margin:0 auto 12px">🎓</div>
        <div style="font-size:20px;font-weight:800">${p.name || 'Ученик'}</div>
        ${p.username ? `<div style="opacity:.75;font-size:13px;margin-top:4px">@${p.username}</div>` : ''}
      </div>
      <div class="grid-4 mb-16">
        <div class="stat-card"><div class="stat-value" style="color:var(--clr-orange)">${p.streak}</div><div class="stat-label">🔥 Дней</div></div>
        <div class="stat-card"><div class="stat-value" style="color:var(--clr-primary)">${p.xp}</div><div class="stat-label">⭐ XP</div></div>
        <div class="stat-card"><div class="stat-value" style="color:var(--clr-accent)">${p.lessons_done}</div><div class="stat-label">📖 Уроков</div></div>
        <div class="stat-card"><div class="stat-value" style="color:var(--clr-purple)">${p.tasks_done}</div><div class="stat-label">🎯 Заданий</div></div>
      </div>
      <div class="card card-pad mb-16">
        ${UI.progressBar(xpPct, 'Прогресс XP', `${p.xp} XP`)}
      </div>
      ${catHtml ? `<div class="card card-pad mb-16"><div class="text-muted mb-12 text-sm" style="text-transform:uppercase;letter-spacing:.05em;font-weight:700">Прогресс по разделам</div>${catHtml}</div>` : ''}
      <button class="btn btn-ghost btn-full" onclick="showLangSettings()">⚙️ Настройки языка</button>`;
  } catch(e) { el.innerHTML = UI.empty('⚠️', 'Ошибка загрузки'); }
}

function showLangSettings() {
  const el = document.getElementById('profile-content');
  const langs = [['en','🇬🇧','Английский'],['de','🇩🇪','Немецкий'],['fr','🇫🇷','Французский'],['es','🇪🇸','Испанский'],['it','🇮🇹','Итальянский'],['zh','🇨🇳','Китайский']];
  const natives = [['ru','🇷🇺','Русский'],['en','🇬🇧','Английский'],['de','🇩🇪','Немецкий'],['fr','🇫🇷','Французский']];
  el.innerHTML = `
    <div class="card card-pad mb-16">
      <h3 style="font-weight:700;margin-bottom:12px">Язык изучения</h3>
      <div class="grid-2">
        ${langs.map(([l,f,n]) => `<button onclick="setLSTgt('${l}')" data-tgt="${l}" class="ls-tgt card card-pad text-center" style="cursor:pointer;${STATE.targetLang===l?'border-color:var(--clr-primary);background:var(--clr-primary-lt)':''}"><div style="font-size:24px">${f}</div><div style="font-size:13px;font-weight:600">${n}</div></button>`).join('')}
      </div>
    </div>
    <div class="card card-pad mb-16">
      <h3 style="font-weight:700;margin-bottom:12px">Родной язык</h3>
      <div class="grid-2">
        ${natives.map(([l,f,n]) => `<button onclick="setLSNtv('${l}')" data-ntv="${l}" class="ls-ntv card card-pad text-center" style="cursor:pointer;${STATE.nativeLang===l?'border-color:var(--clr-primary);background:var(--clr-primary-lt)':''}"><div style="font-size:24px">${f}</div><div style="font-size:13px;font-weight:600">${n}</div></button>`).join('')}
      </div>
    </div>
    <p id="ls-status" class="text-center text-muted text-sm mb-12"></p>
    <button onclick="saveLangSettings()" class="btn btn-primary btn-full mb-8">Сохранить</button>
    <button onclick="loadProfile()" class="btn btn-ghost btn-full">← Назад</button>`;
  window._lsTgt = STATE.targetLang; window._lsNtv = STATE.nativeLang;
}
function setLSTgt(l) { window._lsTgt = l; document.querySelectorAll('.ls-tgt').forEach(b => { const a = b.dataset.tgt===l; b.style.borderColor=a?'var(--clr-primary)':''; b.style.background=a?'var(--clr-primary-lt)':''; }); }
function setLSNtv(l) { window._lsNtv = l; document.querySelectorAll('.ls-ntv').forEach(b => { const a = b.dataset.ntv===l; b.style.borderColor=a?'var(--clr-primary)':''; b.style.background=a?'var(--clr-primary-lt)':''; }); }
async function saveLangSettings() {
  if (!window._lsTgt || !window._lsNtv) { document.getElementById('ls-status').textContent = 'Выберите оба языка'; return; }
  if (window._lsTgt === window._lsNtv) { document.getElementById('ls-status').textContent = '⚠️ Языки не могут совпадать'; return; }
  try {
    await API.setLanguages(STATE.userId, window._lsNtv, window._lsTgt);
    STATE.nativeLang = window._lsNtv; STATE.targetLang = window._lsTgt;
    document.getElementById('ls-status').textContent = '✅ Сохранено!';
    setTimeout(loadProfile, 1000);
  } catch(e) { document.getElementById('ls-status').textContent = 'Ошибка'; }
}

/* ═══════════════════════════════════════
   CLUB CHAT
═══════════════════════════════════════ */

function initClubGreeting() {
  const box = document.getElementById('chat-box');
  if (!box) return;
  box.innerHTML = '';
  addMsg(box, 'ai', AI_GREET[STATE.targetLang] || AI_GREET.en);
}

function addMsg(box, who, text) {
  const div = document.createElement('div');
  if (who === 'ai') { div.className = 'chat-bubble-ai'; div.innerHTML = UI.makeClickable(text); }
  else { div.className = 'chat-bubble-user'; div.textContent = text; }
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

async function sendClubMsg() {
  const inp = document.getElementById('chat-input');
  const text = inp.value.trim(); if (!text) return;
  inp.value = '';
  const box = document.getElementById('chat-box');
  addMsg(box, 'user', text);
  try {
    const fd = new FormData();
    fd.append('user_id', STATE.userId); fd.append('text', text); fd.append('level', STATE.level);
    fd.append('native_language', STATE.nativeLang); fd.append('target_language', STATE.targetLang);
    const d = await API.clubText(fd);
    addMsg(box, 'ai', d.ai_text);
    if (d.audio_url) new Audio(d.audio_url).play().catch(() => {});
  } catch(e) { addMsg(box, 'ai', 'Connection error.'); }
}

async function startMicRecording(which) {
  const chunks = []; const streamKey = which + 'Stream'; const recKey = which + 'MediaRec'; const chunksKey = which + 'Chunks';
  STATE[chunksKey] = [];
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    STATE[streamKey] = stream;
    let opts = {}; if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) opts = { mimeType: 'audio/webm;codecs=opus' };
    const rec = new MediaRecorder(stream, opts);
    STATE[recKey] = rec;
    rec.ondataavailable = ev => { if (ev.data?.size > 0) STATE[chunksKey].push(ev.data); };
    rec.onstop = () => onRecStop(which);
    rec.start();
    const btn = document.getElementById(which + '-mic-btn');
    if (btn) btn.classList.add('recording');
  } catch(e) { alert('Нужен HTTPS и разрешение на микрофон'); }
}

function stopMicRecording(which) {
  const recKey = which + 'MediaRec'; const streamKey = which + 'Stream';
  STATE[recKey]?.state !== 'inactive' && STATE[recKey]?.stop();
  STATE[streamKey]?.getTracks().forEach(t => t.stop());
  STATE[streamKey] = null;
  const btn = document.getElementById(which + '-mic-btn');
  if (btn) btn.classList.remove('recording');
}

async function onRecStop(which) {
  const chunksKey = which + 'Chunks';
  const blob = new Blob(STATE[chunksKey], { type: STATE[which + 'MediaRec']?.mimeType || 'audio/webm' });
  const isClub = which === 'club';
  const box = document.getElementById(isClub ? 'chat-box' : 'sit-chat-box');
  addMsg(box, 'user', '🎙️ ...');
  const fd = new FormData();
  fd.append('user_id', STATE.userId); fd.append('file', blob, 'voice'); fd.append('level', STATE.level);
  fd.append('native_language', STATE.nativeLang); fd.append('target_language', STATE.targetLang);
  if (!isClub) fd.append('situation', STATE.currentSit);
  try {
    const d = await (isClub ? API.clubVoice(fd) : API.clubVoice(fd));
    if (box.lastChild) box.removeChild(box.lastChild);
    addMsg(box, 'user', d.user_text || '🎤');
    addMsg(box, 'ai', d.ai_text);
    if (d.audio_url) new Audio(d.audio_url).play().catch(() => {});
  } catch(e) { addMsg(box, 'ai', 'Error.'); }
}

async function sendSitMsg() {
  const inp = document.getElementById('sit-input');
  const text = inp.value.trim(); if (!text) return;
  inp.value = '';
  const box = document.getElementById('sit-chat-box');
  addMsg(box, 'user', text);
  try {
    const fd = new FormData();
    fd.append('user_id', STATE.userId); fd.append('text', text); fd.append('level', STATE.level);
    fd.append('situation', STATE.currentSit); fd.append('native_language', STATE.nativeLang); fd.append('target_language', STATE.targetLang);
    const d = await API.clubText(fd);
    addMsg(box, 'ai', d.ai_text);
    if (d.audio_url) new Audio(d.audio_url).play().catch(() => {});
  } catch(e) { addMsg(box, 'ai', 'Error.'); }
}

/* ═══════════════════════════════════════
   ONBOARDING
═══════════════════════════════════════ */

const OB = { target: 'en', native: 'ru', level: 'A1' };

function obSelectTarget(lang) {
  OB.target = lang;
  document.querySelectorAll('.ob-lang').forEach(b => {
    const a = b.dataset.lang === lang;
    b.style.borderColor = a ? 'var(--clr-primary)' : '';
    b.style.background = a ? 'var(--clr-primary-lt)' : '';
  });
  setTimeout(() => {
    document.getElementById('ob-step-0').classList.add('hidden');
    const step1 = document.getElementById('ob-step-1');
    step1.classList.remove('hidden');
    step1.querySelectorAll('.ob-native').forEach(b => b.classList.toggle('hidden', b.dataset.lang === lang));
  }, 250);
}

function obSelectNative(lang) {
  OB.native = lang;
  setTimeout(() => {
    document.getElementById('ob-step-1').classList.add('hidden');
    document.getElementById('ob-step-2').classList.remove('hidden');
  }, 250);
}

function obSelectLevel(lvl) {
  OB.level = lvl;
  document.getElementById('ob-step-2').classList.add('hidden');
  document.getElementById('ob-ready-msg').textContent = `Язык: ${OB.target.toUpperCase()} · Уровень: ${lvl}`;
  document.getElementById('ob-step-3').classList.remove('hidden');
}

async function finishOnboarding() {
  try {
    await API.onboardingComplete(STATE.userId, OB.level, 'general', OB.native, OB.target);
    STATE.nativeLang = OB.native; STATE.targetLang = OB.target; STATE.level = OB.level;
    await APP.go('home');
  } catch(e) { await APP.go('home'); }
}

/* ═══════════════════════════════════════
   AUTH
═══════════════════════════════════════ */

async function requestCode() {
  const email = document.getElementById('auth-email').value.trim();
  const err = document.getElementById('auth-error1');
  err.classList.add('hidden');
  if (!email || !email.includes('@')) { err.textContent = 'Введите корректный email'; err.classList.remove('hidden'); return; }
  const btn = document.getElementById('auth-email-btn');
  btn.disabled = true; btn.textContent = 'Отправка...';
  try {
    await API.requestEmailCode(email);
    document.getElementById('auth-email-display').textContent = email;
    document.getElementById('auth-step1').classList.add('hidden');
    document.getElementById('auth-step2').classList.remove('hidden');
  } catch(e) {
    err.textContent = e.data?.detail || 'Ошибка отправки'; err.classList.remove('hidden');
  }
  btn.disabled = false; btn.textContent = 'Получить код →';
}

async function verifyCode() {
  const email = document.getElementById('auth-email').value.trim();
  const code = document.getElementById('auth-code').value.trim();
  const err = document.getElementById('auth-error2');
  err.classList.add('hidden');
  const btn = document.getElementById('auth-verify-btn');
  btn.disabled = true; btn.textContent = 'Проверка...';
  try {
    const d = await API.verifyEmailCode(email, code);
    STATE.userId = d.user_id; STATE.userEmail = email;
    localStorage.setItem('t2l_user_id', STATE.userId);
    localStorage.setItem('t2l_email', email);
    await APP.initApp();
  } catch(e) {
    err.textContent = e.data?.detail || 'Неверный код'; err.classList.remove('hidden');
    btn.disabled = false; btn.textContent = 'Войти ✓';
  }
}

async function onTelegramAuth(user) {
  try {
    const d = await API.verifyTelegram(user);
    STATE.userId = d.user_id;
    if (d.name) STATE.userName = d.name;
    localStorage.setItem('t2l_user_id', STATE.userId);
    localStorage.setItem('t2l_name', d.name || '');
    await APP.initApp();
  } catch(e) { alert('Ошибка авторизации Telegram'); }
}

function logout() {
  ['t2l_user_id','t2l_email','t2l_name'].forEach(k => localStorage.removeItem(k));
  STATE.userId = 0;
  APP.showAuth();
}

/* ═══════════════════════════════════════
   UTILS
═══════════════════════════════════════ */

function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

/* ── Word popup add button ── */
async function addWordToDict() {
  const btn = document.getElementById('pw-add-btn');
  btn.disabled = true; btn.textContent = 'Сохранение...';
  try {
    const d = await API.quickAdd(STATE.userId, STATE.popupWord, STATE.popupCtx);
    if (d.status === 'success') {
      document.getElementById('pw-status').textContent = '✅ Добавлено!';
      btn.textContent = '✓ В словаре';
    } else {
      document.getElementById('pw-status').textContent = d.message || 'Ошибка';
      btn.disabled = false; btn.textContent = '+ В мой словарь';
    }
  } catch(e) {
    document.getElementById('pw-status').textContent = 'Ошибка';
    btn.disabled = false; btn.textContent = '+ В мой словарь';
  }
}

/* ═══════════════════════════════════════
   BOOT
═══════════════════════════════════════ */

window.addEventListener('DOMContentLoaded', () => {
  const saved = localStorage.getItem('t2l_user_id');
  if (saved && parseInt(saved) > 0) {
    STATE.userId = parseInt(saved);
    STATE.userEmail = localStorage.getItem('t2l_email') || '';
    STATE.userName = localStorage.getItem('t2l_name') || '';
    APP.initApp();
  } else {
    APP.showAuth();
  }
});
