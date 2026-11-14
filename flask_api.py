"""Минимальный Flask-сервер для API привилегий.

Эндпоинты:
  POST /api/privilege  — установить/снять привилегию
  GET  /api/stats      — общая статистика

Запуск:
  pip install flask
  python flask_api.py
"""

import os

from dotenv import load_dotenv
from flask import Flask, request, jsonify

from db import DB

load_dotenv()

app = Flask(__name__)

# Секретный ключ для API — из .env
API_KEY = os.getenv("API_KEY", "")
API_SECRET = os.getenv("API_SECRET", "")

PRIVILEGE_NAMES = {"starvision", "viaglobal", "gectoring", "none"}


def _check_auth() -> bool:
    """Проверка авторизации по заголовку X-API-Key."""
    key = request.headers.get("X-API-Key", "")
    return key == API_KEY and API_KEY != ""


@app.route("/api/privilege", methods=["POST"])
def api_privilege():
    """
    Установить/снять привилегию.

    JSON body:
      {
        "user_id": 123456789,
        "privilege": "starvision" | "viaglobal" | "gectoring" | "none",
        "action": "set" | "remove"
      }

    Response:
      {"ok": true, "privilege": "starvision"}
      {"ok": false, "error": "message"}
    """
    if not _check_auth():
        return jsonify({"ok": False, "error": "Не авторизован"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "Нет JSON body"}), 400

    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "user_id обязателен"}), 400

    action = data.get("action", "set")
    priv = data.get("privilege", "none").lower()

    if priv not in PRIVILEGE_NAMES:
        return jsonify({
            "ok": False,
            "error": f"Недопустимая привилегия: {priv}. "
                     f"Доступно: {', '.join(PRIVILEGE_NAMES)}",
        }), 400

    if action == "set":
        with DB() as db:
            db.execute(
                "INSERT INTO dc_users(id, privilege) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE privilege = VALUES(privilege)",
                (int(user_id), priv),
            )
        return jsonify({"ok": True, "privilege": priv})

    elif action == "remove":
        with DB() as db:
            db.execute(
                "UPDATE dc_users SET privilege = 'none' WHERE id = %s",
                (int(user_id),),
            )
        return jsonify({"ok": True, "privilege": "none"})

    return jsonify({"ok": False, "error": "Неизвестное действие"}), 400


@app.route("/api/privilege", methods=["GET"])
def api_get_privilege():
    """
    Получить привилегию пользователя.

    Query params: user_id=123456789

    Response:
      {"ok": true, "user_id": 123, "privilege": "starvision"}
    """
    if not _check_auth():
        return jsonify({"ok": False, "error": "Не авторизован"}), 401

    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "user_id обязателен"}), 400

    with DB() as db:
        row = db.fetchone(
            "SELECT privilege FROM dc_users WHERE id = %s",
            (int(user_id),),
        )
    priv = row["privilege"] if row else "none"
    return jsonify({"ok": True, "user_id": int(user_id), "privilege": priv})


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """Общая статистика."""
    if not _check_auth():
        return jsonify({"ok": False, "error": "Не авторизован"}), 401

    with DB() as db:
        users = db.fetchone("SELECT COUNT(*) AS c FROM dc_users")["c"]
        tickets = db.fetchone("SELECT COUNT(*) AS c FROM tickets")["c"]
        punishments = db.fetchone(
            "SELECT COUNT(*) AS c FROM punishments"
        )["c"]
    return jsonify({
        "ok": True,
        "users": users,
        "tickets": tickets,
        "punishments": punishments,
    })


if __name__ == "__main__":
    port = int(os.getenv("API_PORT", "5000"))
    host = os.getenv("API_HOST", "127.0.0.1")
    print(f"API запущен на http://{host}:{port}")
    app.run(host=host, port=port, debug=False)
