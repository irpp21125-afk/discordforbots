"""HTTP API панели управления (Flask).

Этот сервер — единственная точка входа для десктоп-приложения.
Приложение НЕ знает пароль от MySQL, оно общается только по HTTP
с заголовком X-API-Key.

Запуск отдельно:
    python flask_api.py

Запуск внутри бота (для FadeHost — один порт на приложение):
    bot.py вызывает start_in_thread()

Эндпоинты (все, кроме /api/ping и /api/login, требуют X-API-Key):
    GET  /api/ping
    POST /api/login                 {login, password}
    GET  /api/stats
    GET  /api/tickets?status=&limit=
    GET  /api/ticket?id=
    POST /api/ticket/answer         {ticket_id, text}
    POST /api/ticket/close          {ticket_id}
    GET  /api/users?search=&limit=
    POST /api/money                 {user_id, amount, mode}
    GET  /api/privilege?user_id=
    POST /api/privilege             {user_id, privilege}
    GET  /api/punishments?user_id=
    POST /api/punish                {user_id, type, reason}
    GET  /api/activity?limit=
    GET  /api/giveaways
    GET  /api/faq
    POST /api/faq                   {question, answer}
    DELETE /api/faq?id=
    GET  /api/settings
    POST /api/settings              {key, value}
    POST /api/broadcast             {text}
"""

import json
import logging
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime
from decimal import Decimal

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from db import DB

load_dotenv()

log = logging.getLogger("api")

API_KEY = os.getenv("API_KEY", "")
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

PRIVILEGE_NAMES = {"starvision", "viaglobal", "gectoring", "none"}
PUNISH_TYPES = {"warn", "mute", "kick", "ban"}


# ---------- вспомогательное ----------


def _jsonable(value):
    """DATETIME / Decimal -> то, что понимает jsonify."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, Decimal):
        return float(value)
    return value


def _rows(rows):
    return [{k: _jsonable(v) for k, v in row.items()} for row in rows]


def _ok(**kwargs):
    payload = {"ok": True}
    payload.update(kwargs)
    return jsonify(payload)


def _err(message, code=400):
    return jsonify({"ok": False, "error": message}), code


def _auth_ok() -> bool:
    """Ключ берётся из заголовка или query (для простых клиентов)."""
    if not API_KEY:
        return False
    key = request.headers.get("X-API-Key") or request.args.get(
        "api_key", ""
    )
    return key == API_KEY


def _body() -> dict:
    return request.get_json(silent=True) or {}


def create_app() -> Flask:
    app = Flask(__name__)

    @app.before_request
    def guard():
        """Все /api/* кроме ping и login требуют ключ."""
        if request.path in ("/api/ping", "/api/login"):
            return None
        if not request.path.startswith("/api/"):
            return _err("Неизвестный путь", 404)
        if not _auth_ok():
            return _err("Не авторизован: проверьте API-ключ", 401)
        return None

    @app.errorhandler(Exception)
    def on_error(exc):
        log.exception("API error")
        return _err(f"Внутренняя ошибка: {exc}", 500)

    # ---------- служебное ----------

    @app.route("/api/ping")
    def ping():
        return _ok(service="support-bot-api")

    @app.route("/api/login", methods=["POST"])
    def login():
        data = _body()
        login_ok = str(data.get("login", "")) == ADMIN_LOGIN
        pass_ok = str(data.get("password", "")) == ADMIN_PASSWORD
        if not ADMIN_PASSWORD:
            return _err("ADMIN_PASSWORD не задан на сервере", 500)
        if login_ok and pass_ok:
            return _ok(api_key=API_KEY)
        return _err("Неверный логин или пароль", 401)

    # ---------- статистика ----------

    @app.route("/api/stats")
    def stats():
        with DB() as db:
            out = {}
            for table in (
                "dc_users", "tg_users", "tickets", "punishments",
                "giveaways", "suggestions",
            ):
                try:
                    row = db.fetchone(f"SELECT COUNT(*) AS c FROM `{table}`")
                    out[table] = int(row["c"]) if row else 0
                except Exception:
                    out[table] = 0
            try:
                by_status = db.fetchall(
                    "SELECT status, COUNT(*) AS c FROM tickets "
                    "GROUP BY status"
                )
                out["tickets_by_status"] = {
                    r["status"]: int(r["c"]) for r in by_status
                }
            except Exception:
                out["tickets_by_status"] = {}
        return _ok(**out)

    # ---------- обращения ----------

    @app.route("/api/tickets")
    def tickets_list():
        status = request.args.get("status", "")
        limit = min(int(request.args.get("limit", 50)), 200)
        sql = (
            "SELECT id, author_type, author_ref, category, priority, "
            "status, LEFT(message, 60) AS preview, created_at "
            "FROM tickets "
        )
        params = []
        if status in ("open", "answered", "closed"):
            sql += "WHERE status = %s "
            params.append(status)
        sql += "ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        with DB() as db:
            rows = db.fetchall(sql, tuple(params))
        return _ok(tickets=_rows(rows))

    @app.route("/api/ticket")
    def ticket_detail():
        tid = request.args.get("id")
        if not tid:
            return _err("Нужен id")
        with DB() as db:
            ticket = db.fetchone(
                "SELECT * FROM tickets WHERE id = %s", (int(tid),)
            )
            replies = db.fetchall(
                "SELECT author_name, is_admin, text, created_at "
                "FROM replies WHERE ticket_id = %s ORDER BY id",
                (int(tid),),
            ) if ticket else []
        if not ticket:
            return _err("Обращение не найдено", 404)
        return _ok(ticket=_rows([ticket])[0], replies=_rows(replies))

    @app.route("/api/ticket/answer", methods=["POST"])
    def ticket_answer():
        data = _body()
        tid = data.get("ticket_id")
        text = str(data.get("text", "")).strip()
        if not tid or not text:
            return _err("Нужны ticket_id и text")
        author = str(data.get("author", "Админ (панель)"))[:64]
        with DB() as db:
            db.execute(
                "INSERT INTO replies(ticket_id, author_name, is_admin, text, "
                "created_at) VALUES (%s, %s, 1, %s, NOW())",
                (int(tid), author, text[:4000]),
            )
            db.execute(
                "UPDATE tickets SET status = 'answered', updated_at = NOW() "
                "WHERE id = %s", (int(tid),),
            )
        return _ok()

    @app.route("/api/ticket/close", methods=["POST"])
    def ticket_close():
        tid = _body().get("ticket_id")
        if not tid:
            return _err("Нужен ticket_id")
        with DB() as db:
            db.execute(
                "UPDATE tickets SET status='closed', updated_at=NOW() "
                "WHERE id = %s", (int(tid),),
            )
        return _ok()

    # ---------- пользователи ----------

    @app.route("/api/users")
    def users():
        search = request.args.get("search", "").strip()
        limit = min(int(request.args.get("limit", 50)), 200)
        sql = (
            "SELECT id, username, display_name, points, level, "
            "messages_count, privilege, last_activity FROM dc_users "
        )
        params = []
        if search:
            sql += (
                "WHERE id LIKE %s OR username LIKE %s "
                "OR display_name LIKE %s "
            )
            like = f"%{search}%"
            params += [like, like, like]
        sql += "ORDER BY points DESC LIMIT %s"
        params.append(limit)
        with DB() as db:
            rows = db.fetchall(sql, tuple(params))
        return _ok(users=_rows(rows))

    @app.route("/api/money", methods=["POST"])
    def money():
        data = _body()
        uid = data.get("user_id")
        mode = data.get("mode", "add")
        try:
            amount = int(data.get("amount", 0))
        except (TypeError, ValueError):
            return _err("amount должен быть числом")
        if not uid:
            return _err("Нужен user_id")
        if mode not in ("add", "remove", "set"):
            return _err("mode: add | remove | set")
        if amount < 0:
            return _err("amount не может быть отрицательным")
        with DB() as db:
            if mode == "set":
                db.execute(
                    "INSERT INTO dc_users(id, points, registration_date, "
                    "last_activity) VALUES (%s, %s, NOW(), NOW()) "
                    "ON DUPLICATE KEY UPDATE points = VALUES(points)",
                    (int(uid), amount),
                )
            elif mode == "add":
                db.execute(
                    "INSERT INTO dc_users(id, points, registration_date, "
                    "last_activity) VALUES (%s, %s, NOW(), NOW()) "
                    "ON DUPLICATE KEY UPDATE points = points + VALUES(points)",
                    (int(uid), amount),
                )
            else:
                db.execute(
                    "UPDATE dc_users SET points = GREATEST(0, points - %s) "
                    "WHERE id = %s", (amount, int(uid)),
                )
        return _ok()

    # ---------- привилегии ----------

    @app.route("/api/privilege", methods=["GET"])
    def privilege_get():
        uid = request.args.get("user_id")
        if not uid:
            return _err("Нужен user_id")
        with DB() as db:
            row = db.fetchone(
                "SELECT privilege FROM dc_users WHERE id = %s", (int(uid),)
            )
        return _ok(user_id=int(uid),
                   privilege=row["privilege"] if row else "none")

    @app.route("/api/privilege", methods=["POST"])
    def privilege_set():
        data = _body()
        uid = data.get("user_id")
        priv = str(data.get("privilege", "none")).lower()
        if not uid:
            return _err("Нужен user_id")
        if priv not in PRIVILEGE_NAMES:
            return _err(
                f"Недопустимая привилегия. Доступно: "
                f"{', '.join(sorted(PRIVILEGE_NAMES))}"
            )
        with DB() as db:
            db.execute(
                "INSERT INTO dc_users(id, privilege) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE privilege = VALUES(privilege)",
                (int(uid), priv),
            )
        return _ok(privilege=priv)

    @app.route("/api/privileges")
    def privileges_list():
        with DB() as db:
            rows = db.fetchall(
                "SELECT name, price, color, icon FROM privileges "
                "ORDER BY price"
            )
        return _ok(privileges=_rows(rows))

    # ---------- наказания ----------

    @app.route("/api/punishments")
    def punishments():
        uid = request.args.get("user_id")
        limit = min(int(request.args.get("limit", 50)), 200)
        sql = (
            "SELECT id, guild_id, user_id, moderator_id, type, reason, "
            "duration_minutes, active, created_at FROM punishments "
        )
        params = []
        if uid:
            sql += "WHERE user_id = %s "
            params.append(int(uid))
        sql += "ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        with DB() as db:
            rows = db.fetchall(sql, tuple(params))
        return _ok(punishments=_rows(rows))

    @app.route("/api/punish", methods=["POST"])
    def punish():
        """Запись наказания в БД. Kick/ban в Discord делает бот."""
        data = _body()
        uid = data.get("user_id")
        ptype = str(data.get("type", "warn")).lower()
        reason = str(data.get("reason", "без причины"))[:500]
        guild_id = data.get("guild_id")
        if not uid:
            return _err("Нужен user_id")
        if ptype not in PUNISH_TYPES:
            return _err(f"type: {' | '.join(sorted(PUNISH_TYPES))}")
        if not guild_id:
            return _err("Нужен guild_id")
        with DB() as db:
            db.execute(
                "INSERT INTO punishments(guild_id, user_id, type, reason, "
                "created_at) VALUES (%s, %s, %s, %s, NOW())",
                (int(guild_id), int(uid), ptype, reason),
            )
            db.execute(
                "INSERT INTO activity_log(guild_id, user_id, event, "
                "created_at) VALUES (%s, %s, %s, NOW())",
                (int(guild_id), int(uid), f"panel_{ptype}"),
            )
        return _ok()

    # ---------- активность ----------

    @app.route("/api/activity")
    def activity():
        limit = min(int(request.args.get("limit", 30)), 200)
        with DB() as db:
            rows = db.fetchall(
                "SELECT guild_id, user_id, event, created_at "
                "FROM activity_log ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
        return _ok(events=_rows(rows))

    # ---------- розыгрыши ----------

    @app.route("/api/giveaways")
    def giveaways():
        with DB() as db:
            rows = db.fetchall(
                "SELECT id, prize, winners_count, ends_at, ended, "
                "winner_ids FROM giveaways ORDER BY ends_at DESC LIMIT 50"
            )
        return _ok(giveaways=_rows(rows))

    # ---------- FAQ ----------

    @app.route("/api/faq")
    def faq_list():
        with DB() as db:
            rows = db.fetchall(
                "SELECT id, question, answer, sort FROM faq "
                "ORDER BY sort, id"
            )
        return _ok(faq=_rows(rows))

    @app.route("/api/faq", methods=["POST"])
    def faq_add():
        data = _body()
        q = str(data.get("question", "")).strip()
        a = str(data.get("answer", "")).strip()
        if not q or not a:
            return _err("Нужны question и answer")
        with DB() as db:
            db.execute(
                "INSERT INTO faq(question, answer, sort) VALUES (%s, %s, %s)",
                (q[:512], a[:4000], int(data.get("sort", 0))),
            )
        return _ok()

    @app.route("/api/faq", methods=["DELETE"])
    def faq_delete():
        fid = request.args.get("id")
        if not fid:
            return _err("Нужен id")
        with DB() as db:
            cur = db.execute("DELETE FROM faq WHERE id = %s", (int(fid),))
            deleted = cur.rowcount
        return _ok(deleted=deleted)

    # ---------- настройки ----------

    @app.route("/api/settings")
    def settings_get():
        with DB() as db:
            rows = db.fetchall(
                "SELECT `key`, `value` FROM settings"
            )
        return _ok(
            settings={r["key"]: r["value"] for r in rows}
        )

    @app.route("/api/settings", methods=["POST"])
    def settings_set():
        data = _body()
        key = str(data.get("key", "")).strip()
        value = str(data.get("value", ""))
        if not key:
            return _err("Нужен key")
        with DB() as db:
            db.execute(
                "INSERT INTO settings(`key`, `value`) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE `value` = VALUES(`value`)",
                (key, value),
            )
        return _ok()

    # ---------- рассылка ----------

    @app.route("/api/broadcast", methods=["POST"])
    def broadcast():
        text = str(_body().get("text", "")).strip()
        if not text:
            return _err("Пустой текст")
        if not WEBHOOK_URL:
            return _err(
                "DISCORD_WEBHOOK_URL не задан на сервере", 500
            )
        payload = json.dumps({"content": text[:1900]}).encode()
        req = urllib.request.Request(
            WEBHOOK_URL, data=payload, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                good = resp.status < 300
        except urllib.error.URLError as e:
            return _err(f"Вебхук недоступен: {e}", 502)
        if not good:
            return _err("Discord отклонил сообщение", 502)
        return _ok()

    return app


def start_in_thread(host: str = None, port: int = None):
    """Поднять API в фоновом потоке (используется ботом на FadeHost)."""
    host = host or os.getenv("API_HOST", "0.0.0.0")
    # FadeHost выдаёт порт в PORT — наружу открывается именно он
    port = port or int(os.getenv("API_PORT") or os.getenv("PORT") or "5000")
    app = create_app()
    thread = threading.Thread(
        target=lambda: app.run(
            host=host, port=port, debug=False, use_reloader=False
        ),
        name="flask-api",
        daemon=True,
    )
    thread.start()
    log.info("API поднят на http://%s:%s", host, port)
    return thread


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not API_KEY:
        print(
            "API_KEY пуст в .env — все запросы будут отклонены (401)"
        )
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(
        os.getenv("API_PORT") or os.getenv("PORT") or "5000"
    )
    print(f"API запущен на http://{host}:{port}")
    create_app().run(host=host, port=port, debug=False)

