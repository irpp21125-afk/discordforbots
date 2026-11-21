/* ===== Support Bot Dashboard — логика ===== */

const API_KEY_STORE = "sb_api_key";

const state = {
  key: localStorage.getItem(API_KEY_STORE) || "",
  stats: {},
};

/* ---------- HTTP ---------- */

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json" };
  if (state.key) headers["X-API-Key"] = state.key;
  const resp = await fetch(path, { ...opts, headers });
  let data = {};
  try { data = await resp.json(); } catch (e) { /* ignore */ }
  if (resp.status === 401) {
    logout();
    throw new Error(data.error || "Сессия истекла");
  }
  if (!resp.ok || data.ok === false) {
    throw new Error(data.error || "Ошибка HTTP " + resp.status);
  }
  return data;
}

const post = (path, body) => api(path, {
  method: "POST", body: JSON.stringify(body),
});

/* ---------- Утилиты ---------- */

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
));

function toast(msg, kind = "ok") {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast " + kind;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add("hidden"), 3200);
}

function openModal(title, html) {
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = html;
  $("#modal-overlay").classList.remove("hidden");
}
function closeModal() {
  $("#modal-overlay").classList.add("hidden");
}
$("#modal-overlay").addEventListener("click", (e) => {
  if (e.target.id === "modal-overlay") closeModal();
});

const pill = (status) => `<span class="pill pill-${esc(status)}">${esc(status)}</span>`;

/* ---------- Авторизация ---------- */

function showLogin() {
  $("#login-screen").classList.remove("hidden");
  $("#app").classList.add("hidden");
}

function showApp() {
  $("#login-screen").classList.add("hidden");
  $("#app").classList.remove("hidden");
  navigate("home");
}

async function doLogin() {
  const login = $("#login-user").value.trim();
  const password = $("#login-pass").value;
  const errBox = $("#login-error");
  errBox.classList.add("hidden");
  $("#login-btn").disabled = true;
  try {
    const resp = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login, password }),
    });
    const data = await resp.json();
    if (!resp.ok || !data.ok) throw new Error(data.error || "Ошибка входа");
    state.key = data.api_key;
    localStorage.setItem(API_KEY_STORE, state.key);
    showApp();
  } catch (e) {
    errBox.textContent = e.message;
    errBox.classList.remove("hidden");
  } finally {
    $("#login-btn").disabled = false;
  }
}

function logout() {
  localStorage.removeItem(API_KEY_STORE);
  state.key = "";
  showLogin();
}

$("#login-btn").addEventListener("click", doLogin);
$("#login-pass").addEventListener("keydown", (e) => {
  if (e.key === "Enter") doLogin();
});
$("#logout-btn").addEventListener("click", logout);

/* ---------- Навигация ---------- */

document.querySelectorAll(".nav-item[data-view]").forEach((el) => {
  el.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
    el.classList.add("active");
    const view = el.dataset.view;
    if (view === "stub") {
      const [title, note] = (el.dataset.stub || "").split("|");
      renderStub(title, note);
    } else {
      navigate(view);
    }
  });
});

$("#collapse-btn").addEventListener("click", () => {
  document.querySelector(".sidebar").classList.toggle("collapsed");
});

const VIEWS = {};   // реестр разделов, заполняется ниже
async function navigate(view) {
  const root = $("#view-root");
  const render = VIEWS[view] || VIEWS.home;
  root.innerHTML = `<div class="empty-state">Загрузка…</div>`;
  try {
    await render(root);
  } catch (e) {
    root.innerHTML = `<div class="empty-state">⚠️ ${esc(e.message)}</div>`;
  }
}

/* ---------- ГЛАВНАЯ ---------- */

VIEWS.home = async (root) => {
  const [stats, activity] = await Promise.all([
    api("/api/stats"),
    api("/api/activity?limit=8").catch(() => ({ events: [] })),
  ]);
  state.stats = stats;
  $("#badge-tickets").textContent = stats.tickets || 0;
  $("#badge-pun").textContent = stats.punishments || 0;
  $("#badge-gw").textContent = stats.giveaways || 0;

  const byStatus = stats.tickets_by_status || {};
  const changes = (activity.events || []).map((e) => `
    <div class="change-item">
      <span class="change-icon">⚡</span>
      <div>
        <div class="change-title">${esc(e.event)}</div>
        <div class="change-time">user ${esc(e.user_id)} · ${esc(e.created_at)}</div>
      </div>
    </div>`).join("") || `<div class="empty-state">Событий пока нет</div>`;

  root.innerHTML = `
  <div class="grid-2">
    <div>
      <div class="section-title">Недавно посещённые</div>
      <div class="toolbar">
        <button class="btn btn-sm" onclick="navigate('tickets')">🎫 Обращения</button>
        <button class="btn btn-sm" onclick="navigate('users')">👥 Пользователи</button>
        <button class="btn btn-sm" onclick="navigate('punishments')">👮 Наказания</button>
        <button class="btn btn-sm" onclick="navigate('giveaways')">🎉 Розыгрыши</button>
        <button class="btn btn-sm" onclick="navigate('commands')">⌨️ Команды</button>
      </div>

      <div class="section-title">Популярные модули</div>
      <div class="grid-cards">
        ${tile("🎫", "Обращения", `${stats.tickets || 0} всего, ${byStatus.open || 0} открытых`, "tickets")}
        ${tile("🛡️", "Модерация", "Наказания, фильтры, санкции", "moderation")}
        ${tile("🏆", "Рейтинг", "Уровни участников", "users")}
        ${tile("💰", "Экономика", "Баланс и внутренние награды", "economy")}
      </div>

      <div class="section-title" style="margin-top:20px">Статистика</div>
      <div class="grid-cards">
        ${stat("👥", stats.dc_users || 0, "Пользователей Discord")}
        ${stat("🎫", stats.tickets || 0, "Обращений")}
        ${stat("👮", stats.punishments || 0, "Наказаний")}
        ${stat("🎉", stats.giveaways || 0, "Розыгрышей")}
        ${stat("💡", stats.suggestions || 0, "Предложений")}
      </div>
    </div>

    <div class="card">
      <div class="card-title">Последние изменения</div>
      ${changes}
    </div>
  </div>`;
};

const tile = (icon, name, desc, view) => `
  <div class="module-tile" onclick="navigate('${view}')">
    <div class="module-icon">${icon}</div>
    <div>
      <div class="module-name">${name}</div>
      <div class="module-desc">${esc(desc)}</div>
    </div>
  </div>`;

const stat = (icon, value, label) => `
  <div class="card stat-card">
    <div class="stat-value">${icon} ${value}</div>
    <div class="stat-label">${label}</div>
  </div>`;

/* ---------- ОБРАЩЕНИЯ ---------- */

VIEWS.tickets = async (root, status = "") => {
  const data = await api("/api/tickets?limit=100" + (status ? `&status=${status}` : ""));
  const rows = (data.tickets || []).map((t) => `
    <tr class="clickable" onclick="openTicket(${t.id})">
      <td>#${t.id}</td>
      <td>${esc(t.author_type)}:${esc(t.author_ref)}</td>
      <td>${esc(t.category)}</td>
      <td>${esc(t.priority)}</td>
      <td>${pill(t.status)}</td>
      <td>${esc(t.preview)}</td>
      <td>${esc(t.created_at)}</td>
    </tr>`).join("");

  root.innerHTML = `
    <div class="section-title">🎫 Обращения</div>
    <div class="toolbar">
      <button class="btn btn-sm ${!status ? "btn-primary" : ""}" onclick="VIEWS.tickets($('#view-root'),'')">Все</button>
      <button class="btn btn-sm ${status === "open" ? "btn-primary" : ""}" onclick="VIEWS.tickets($('#view-root'),'open')">Открытые</button>
      <button class="btn btn-sm ${status === "answered" ? "btn-primary" : ""}" onclick="VIEWS.tickets($('#view-root'),'answered')">Отвеченные</button>
      <button class="btn btn-sm ${status === "closed" ? "btn-primary" : ""}" onclick="VIEWS.tickets($('#view-root'),'closed')">Закрытые</button>
    </div>
    ${rows ? `<table class="data">
      <tr><th>№</th><th>Автор</th><th>Категория</th><th>Приоритет</th><th>Статус</th><th>Сообщение</th><th>Дата</th></tr>
      ${rows}</table>` : `<div class="empty-state">Обращений нет</div>`}`;
};

async function openTicket(id) {
  try {
    const d = await api("/api/ticket?id=" + id);
    const t = d.ticket;
    const replies = (d.replies || []).map((r) => `
      <div class="reply-block">
        <div class="reply-author">${r.is_admin ? "🛡️" : "👤"} ${esc(r.author_name)}
          <span class="reply-time">${esc(r.created_at)}</span></div>
        <div>${esc(r.text)}</div>
      </div>`).join("") || `<div class="empty-state">Ответов пока нет</div>`;

    openModal(`Обращение #${id}`, `
      <div class="form-row">${pill(t.status)} <b>${esc(t.category)}</b> · приоритет ${esc(t.priority)} · ${esc(t.created_at)}</div>
      <div class="reply-block"><b>${esc(t.author_type)}:${esc(t.author_ref)}</b><br>${esc(t.message)}</div>
      <div class="section-title" style="margin-top:14px">Ответы</div>
      ${replies}
      <div class="form-row" style="margin-top:14px">
        <textarea id="ticket-answer" rows="3" placeholder="Текст ответа..." style="flex:1"></textarea>
      </div>
      <div class="form-row">
        <button class="btn btn-primary" onclick="sendAnswer(${id})">✉️ Ответить</button>
        <button class="btn btn-danger" onclick="closeTicket(${id})">🔒 Закрыть</button>
      </div>`);
  } catch (e) { toast(e.message, "err"); }
}

async function sendAnswer(id) {
  const text = $("#ticket-answer").value.trim();
  if (!text) return;
  try {
    await post("/api/ticket/answer", { ticket_id: id, text });
    toast("Ответ отправлен");
    closeModal();
    navigate("tickets");
  } catch (e) { toast(e.message, "err"); }
}

async function closeTicket(id) {
  try {
    await post("/api/ticket/close", { ticket_id: id });
    toast("Обращение закрыто");
    closeModal();
    navigate("tickets");
  } catch (e) { toast(e.message, "err"); }
}

/* ---------- ПОЛЬЗОВАТЕЛИ / РЕЙТИНГ ---------- */

VIEWS.users = async (root, search = "") => {
  const data = await api("/api/users?limit=100" + (search ? `&search=${encodeURIComponent(search)}` : ""));
  const rows = (data.users || []).map((u) => `
    <tr class="clickable" onclick='openUser(${JSON.stringify(u)})'>
      <td>${esc(u.id)}</td>
      <td>${esc(u.display_name || u.username || "—")}</td>
      <td>${esc(u.points)}</td>
      <td>${esc(u.level)}</td>
      <td>${privPill(u.privilege)}</td>
      <td>${esc(u.messages_count)}</td>
      <td>${esc(u.last_activity || "—")}</td>
    </tr>`).join("");

  root.innerHTML = `
    <div class="section-title">👥 Пользователи и рейтинг</div>
    <div class="form-row">
      <input id="user-search" placeholder="Поиск по ID или имени..." value="${esc(search)}" style="width:280px">
      <button class="btn btn-primary btn-sm" onclick="VIEWS.users($('#view-root'), $('#user-search').value)">Найти</button>
    </div>
    ${rows ? `<table class="data">
      <tr><th>ID</th><th>Имя</th><th>XP</th><th>Уровень</th><th>Привилегия</th><th>Сообщений</th><th>Активность</th></tr>
      ${rows}</table>` : `<div class="empty-state">Никого не найдено</div>`}`;

  $("#user-search").addEventListener("keydown", (e) => {
    if (e.key === "Enter") VIEWS.users(root, e.target.value);
  });
};

const PRIVS = ["none", "starvision", "viaglobal", "gectoring"];
const privPill = (p) => {
  const icons = { starvision: "⭐", viaglobal: "🌍", gectoring: "🏆" };
  return p && p !== "none"
    ? `<span class="pill pill-warn">${icons[p] || ""} ${esc(p)}</span>`
    : `<span class="pill pill-closed">—</span>`;
};

function openUser(u) {
  const name = esc(u.display_name || u.username || u.id);
  openModal(`Пользователь ${name}`, `
    <div class="form-row">
      <span>ID: <b>${esc(u.id)}</b></span> ·
      <span>XP: <b id="u-xp">${esc(u.points)}</b></span> ·
      <span>Уровень: <b>${esc(u.level)}</b></span>
    </div>
    <div class="section-title">Экономика</div>
    <div class="form-row">
      <input id="xp-amount" type="number" min="0" placeholder="Кол-во XP" style="width:140px">
      <button class="btn btn-success btn-sm" onclick="changeMoney(${u.id},'add')">+ Выдать</button>
      <button class="btn btn-danger btn-sm" onclick="changeMoney(${u.id},'remove')">− Снять</button>
      <button class="btn btn-sm" onclick="changeMoney(${u.id},'set')">= Установить</button>
    </div>
    <div class="section-title">Привилегия</div>
    <div class="form-row">
      <select id="u-priv">${PRIVS.map((p) =>
        `<option value="${p}" ${p === u.privilege ? "selected" : ""}>${p}</option>`).join("")}</select>
      <button class="btn btn-primary btn-sm" onclick="setPrivilege(${u.id})">Применить</button>
    </div>
    <div class="section-title">Наказания</div>
    <div class="form-row">
      <input id="pun-guild" type="number" placeholder="ID сервера" style="width:170px">
      <select id="pun-type">
        <option value="warn">warn</option><option value="mute">mute</option>
        <option value="kick">kick</option><option value="ban">ban</option>
      </select>
      <input id="pun-reason" placeholder="Причина" style="flex:1">
      <button class="btn btn-danger btn-sm" onclick="punishUser(${u.id})">Наказать</button>
    </div>`);
}

async function changeMoney(uid, mode) {
  const amount = parseInt($("#xp-amount").value, 10);
  if (!Number.isFinite(amount) || amount < 0) return toast("Введите количество XP", "err");
  try {
    await post("/api/money", { user_id: uid, amount, mode });
    toast("Баланс обновлён");
    closeModal();
    navigate("users");
  } catch (e) { toast(e.message, "err"); }
}

async function setPrivilege(uid) {
  try {
    await post("/api/privilege", { user_id: uid, privilege: $("#u-priv").value });
    toast("Привилегия обновлена");
    closeModal();
    navigate("users");
  } catch (e) { toast(e.message, "err"); }
}

async function punishUser(uid) {
  const guild_id = parseInt($("#pun-guild").value, 10);
  if (!Number.isFinite(guild_id)) return toast("Укажите ID сервера", "err");
  try {
    await post("/api/punish", {
      user_id: uid, type: $("#pun-type").value,
      reason: $("#pun-reason").value || "без причины", guild_id,
    });
    toast("Наказание записано");
    closeModal();
  } catch (e) { toast(e.message, "err"); }
}

/* ---------- ЭКОНОМИКА (тот же список, с акцентом на XP) ---------- */

VIEWS.economy = async (root) => {
  await VIEWS.users(root);
  const title = root.querySelector(".section-title");
  if (title) title.textContent = "💰 Экономика — балансы участников";
};

/* ---------- НАКАЗАНИЯ ---------- */

VIEWS.punishments = async (root) => {
  const data = await api("/api/punishments?limit=100");
  const rows = (data.punishments || []).map((p) => `
    <tr>
      <td>#${p.id}</td>
      <td>${pill(p.type)}</td>
      <td>${esc(p.user_id)}</td>
      <td>${esc(p.guild_id)}</td>
      <td>${esc((p.reason || "").slice(0, 60))}</td>
      <td>${p.active ? "✅" : "—"}</td>
      <td>${esc(p.created_at)}</td>
    </tr>`).join("");

  root.innerHTML = `
    <div class="section-title">👮 Наказания</div>
    ${rows ? `<table class="data">
      <tr><th>№</th><th>Тип</th><th>Пользователь</th><th>Сервер</th><th>Причина</th><th>Активно</th><th>Дата</th></tr>
      ${rows}</table>` : `<div class="empty-state">Наказаний нет</div>`}`;
};

/* ---------- МОДЕРАЦИЯ (быстрые действия) ---------- */

VIEWS.moderation = async (root) => {
  root.innerHTML = `
    <div class="section-title">🛡️ Быстрая модерация</div>
    <div class="card" style="max-width:640px">
      <p style="color:var(--text-dim);margin-bottom:14px">
        Записать наказание можно и здесь, но kick/ban/mute в Discord
        выполняет бот командами <b>/kick</b>, <b>/ban</b>, <b>/mute</b> —
        они действуют сразу.
      </p>
      <div class="form-row">
        <input id="m-user" type="number" placeholder="ID пользователя" style="width:190px">
        <input id="m-guild" type="number" placeholder="ID сервера" style="width:170px">
        <select id="m-type">
          <option value="warn">warn</option><option value="mute">mute</option>
          <option value="kick">kick</option><option value="ban">ban</option>
        </select>
      </div>
      <div class="form-row">
        <input id="m-reason" placeholder="Причина" style="flex:1">
        <button class="btn btn-danger" onclick="quickPunish()">Записать</button>
      </div>
    </div>
    <div class="section-title" style="margin-top:18px">Последние наказания</div>
    <div id="mod-recent"><div class="empty-state">Загрузка…</div></div>`;

  try {
    const data = await api("/api/punishments?limit=10");
    $("#mod-recent").innerHTML = (data.punishments || []).length
      ? `<table class="data"><tr><th>Тип</th><th>Пользователь</th><th>Причина</th><th>Дата</th></tr>
         ${data.punishments.map((p) => `<tr><td>${pill(p.type)}</td><td>${esc(p.user_id)}</td><td>${esc((p.reason || "").slice(0, 60))}</td><td>${esc(p.created_at)}</td></tr>`).join("")}</table>`
      : `<div class="empty-state">Пусто</div>`;
  } catch (e) {
    $("#mod-recent").innerHTML = `<div class="empty-state">${esc(e.message)}</div>`;
  }
};

async function quickPunish() {
  const user_id = parseInt($("#m-user").value, 10);
  const guild_id = parseInt($("#m-guild").value, 10);
  if (!user_id || !guild_id) return toast("Заполните ID пользователя и сервера", "err");
  try {
    await post("/api/punish", {
      user_id, guild_id, type: $("#m-type").value,
      reason: $("#m-reason").value || "без причины",
    });
    toast("Записано");
    VIEWS.moderation($("#view-root"));
  } catch (e) { toast(e.message, "err"); }
}

/* ---------- АУДИТ ---------- */

VIEWS.audit = async (root) => {
  const data = await api("/api/activity?limit=100");
  const rows = (data.events || []).map((e) => `
    <tr>
      <td>${esc(e.event)}</td>
      <td>${esc(e.user_id)}</td>
      <td>${esc(e.guild_id || "—")}</td>
      <td>${esc(e.created_at)}</td>
    </tr>`).join("");
  root.innerHTML = `
    <div class="section-title">📋 Журнал аудита</div>
    ${rows ? `<table class="data">
      <tr><th>Событие</th><th>Пользователь</th><th>Сервер</th><th>Время</th></tr>
      ${rows}</table>` : `<div class="empty-state">Событий нет</div>`}`;
};

/* ---------- КОМАНДЫ ---------- */

VIEWS.commands = async (root) => {
  const data = await api("/api/commands");
  const rows = (data.commands || []).map((c) => `
    <tr>
      <td><b>/${esc(c.name)}</b></td>
      <td>${esc(c.desc)}</td>
      <td><code style="color:var(--text-dim)">${esc(c.usage || "")}</code></td>
      <td>${pill(c.perms === "all" ? "open" : c.perms === "staff" ? "answered" : "ban")}</td>
    </tr>`).join("");
  root.innerHTML = `
    <div class="section-title">⌨️ Команды бота (${(data.commands || []).length})</div>
    <table class="data">
      <tr><th>Команда</th><th>Описание</th><th>Использование</th><th>Доступ</th></tr>
      ${rows}</table>`;
};

/* ---------- FAQ ---------- */

VIEWS.faq = async (root) => {
  const data = await api("/api/faq");
  const rows = (data.faq || []).map((f) => `
    <tr>
      <td>#${f.id}</td>
      <td><b>${esc(f.question)}</b><br><span style="color:var(--text-dim)">${esc(f.answer)}</span></td>
      <td><button class="btn btn-danger btn-sm" onclick="delFaq(${f.id})">Удалить</button></td>
    </tr>`).join("");

  root.innerHTML = `
    <div class="section-title">💬 Сообщения / FAQ</div>
    <div class="card" style="margin-bottom:16px">
      <div class="form-row">
        <input id="faq-q" placeholder="Вопрос" style="flex:1">
      </div>
      <div class="form-row">
        <textarea id="faq-a" rows="2" placeholder="Ответ" style="flex:1"></textarea>
        <button class="btn btn-primary" onclick="addFaq()">Добавить</button>
      </div>
    </div>
    ${rows ? `<table class="data"><tr><th>№</th><th>Вопрос — ответ</th><th></th></tr>${rows}</table>`
           : `<div class="empty-state">FAQ пуст</div>`}`;
};

async function addFaq() {
  const question = $("#faq-q").value.trim();
  const answer = $("#faq-a").value.trim();
  if (!question || !answer) return toast("Заполните вопрос и ответ", "err");
  try {
    await post("/api/faq", { question, answer });
    toast("Добавлено");
    navigate("faq");
  } catch (e) { toast(e.message, "err"); }
}

async function delFaq(id) {
  try {
    await api("/api/faq?id=" + id, { method: "DELETE" });
    toast("Удалено");
    navigate("faq");
  } catch (e) { toast(e.message, "err"); }
}

/* ---------- НАСТРОЙКИ ---------- */

VIEWS.settings = async (root) => {
  const data = await api("/api/settings");
  const entries = Object.entries(data.settings || {});
  const rows = entries.map(([k, v]) => `
    <tr>
      <td><b>${esc(k)}</b></td>
      <td>${esc(v)}</td>
      <td><button class="btn btn-sm" onclick='editSetting(${JSON.stringify(k)}, ${JSON.stringify(v ?? "")})'>Изменить</button></td>
    </tr>`).join("");

  root.innerHTML = `
    <div class="section-title">⚙️ Общие настройки</div>
    <div class="card" style="margin-bottom:16px;max-width:760px">
      <div class="card-title">Рассылка в Discord</div>
      <div class="form-row">
        <input id="bc-text" placeholder="Текст объявления..." style="flex:1">
        <button class="btn btn-primary" onclick="sendBroadcast()">Отправить</button>
      </div>
    </div>
    ${rows ? `<table class="data" style="max-width:760px">
      <tr><th>Ключ</th><th>Значение</th><th></th></tr>${rows}</table>`
           : `<div class="empty-state">Настроек нет</div>`}`;
};

function editSetting(key, value) {
  openModal(`Настройка ${key}`, `
    <div class="form-row"><textarea id="set-value" rows="3" style="flex:1">${esc(value)}</textarea></div>
    <button class="btn btn-primary" onclick="saveSetting('${esc(key)}')">Сохранить</button>`);
}

async function saveSetting(key) {
  try {
    await post("/api/settings", { key, value: $("#set-value").value });
    toast("Сохранено");
    closeModal();
    navigate("settings");
  } catch (e) { toast(e.message, "err"); }
}

async function sendBroadcast() {
  const text = $("#bc-text").value.trim();
  if (!text) return;
  try {
    await post("/api/broadcast", { text });
    $("#bc-text").value = "";
    toast("Отправлено в Discord");
  } catch (e) { toast(e.message, "err"); }
}

/* ---------- РОЗЫГРЫШИ ---------- */

VIEWS.giveaways = async (root) => {
  const data = await api("/api/giveaways");
  const rows = (data.giveaways || []).map((g) => `
    <tr>
      <td>#${g.id}</td>
      <td><b>${esc(g.prize)}</b></td>
      <td>${esc(g.winners_count)}</td>
      <td>${esc(g.ends_at)}</td>
      <td>${g.ended ? pill("closed") : pill("open")}</td>
      <td>${esc(g.winner_ids || "—")}</td>
    </tr>`).join("");
  root.innerHTML = `
    <div class="section-title">🎉 Розыгрыши</div>
    ${rows ? `<table class="data">
      <tr><th>№</th><th>Приз</th><th>Победителей</th><th>До</th><th>Статус</th><th>Победители</th></tr>
      ${rows}</table>` : `<div class="empty-state">Розыгрышей нет</div>`}`;
};

/* ---------- ГЛУШКИ (только Discord) ---------- */

function renderStub(title, note) {
  $("#view-root").innerHTML = `
    <div class="section-title">${esc(title)}</div>
    <div class="stub-note">
      🛠 Этот модуль настраивается через Discord-бота.<br><br>
      ${esc(note || "")}
    </div>`;
}

/* ---------- ПОИСК В ВЕРХНЕЙ ПАНЕЛИ ---------- */

$("#global-search").addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  const q = e.target.value.trim();
  if (!q) return;
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
  VIEWS.users($("#view-root"), q);
});

/* ---------- СТАРТ ---------- */

(async function boot() {
  if (!state.key) return showLogin();
  try {
    await api("/api/stats");     // проверка ключа
    showApp();
  } catch (e) {
    showLogin();
  }
})();

window.navigate = navigate;
window.VIEWS = VIEWS;
window.openTicket = openTicket;
window.sendAnswer = sendAnswer;
window.closeTicket = closeTicket;
window.openUser = openUser;
window.changeMoney = changeMoney;
window.setPrivilege = setPrivilege;
window.punishUser = punishUser;
window.quickPunish = quickPunish;
window.addFaq = addFaq;
window.delFaq = delFaq;
window.editSetting = editSetting;
window.saveSetting = saveSetting;
window.sendBroadcast = sendBroadcast;
window.closeModal = closeModal;
