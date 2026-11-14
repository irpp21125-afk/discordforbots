"""Отправка уведомлений в Discord через webhook (для C++ панели и скриптов).

C++-панель пишет в MySQL, а пользователи получают уведомления в Discord —
это делает данный модуль (запускается как: python notify.py).
"""

import json
import os
import urllib.error
import urllib.request

import mysql.connector
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def db_config() -> dict:
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "support_bot"),
        "charset": "utf8mb4",
        "autocommit": True,
    }


def send_webhook(webhook_url: str, content: str) -> bool:
    """Отправить сообщение в Discord-вебхук."""
    data = json.dumps({"content": content[:1900]}).encode()
    req = urllib.request.Request(
        webhook_url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status < 300
    except urllib.error.URLError:
        return False


def notify_new_ticket_via_webhook(webhook_url: str, ticket_id: int,
                                  author: str, message: str):
    send_webhook(
        webhook_url,
        f"🎫 **Новое обращение #{ticket_id}**\n"
        f"👤 {author}\n📝 {message[:300]}",
    )


def main():
    """Цикл: новые тикеты и ответы из MySQL → уведомления в Discord.

    Запускается вместе с ботом (или из C++ панели).
    """
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
    if not webhook:
        print("DISCORD_WEBHOOK_URL не задан — уведомления отключены.")
        return

    conn = mysql.connector.connect(**db_config())
    cur = conn.cursor(dictionary=True)
    print("Notify-цикл запущен (опрос каждые 15 сек)...")

    cur.execute("SELECT COALESCE(MAX(id), 0) AS m FROM replies")
    last_reply = int(cur.fetchone()["m"])
    cur.execute("SELECT COALESCE(MAX(id), 0) AS m FROM tickets")
    last_ticket = int(cur.fetchone()["m"])

    import time
    while True:
        try:
            cur.execute(
                "SELECT id, author_type, author_ref, category, message"
                " FROM tickets WHERE id > %s",
                (last_ticket,),
            )
            for row in cur.fetchall():
                last_ticket = int(row["id"])
                notify_new_ticket_via_webhook(
                    webhook, row["id"],
                    f"{row['author_type']}:{row['author_ref']}",
                    row["message"],
                )

            cur.execute(
                "SELECT r.id, r.ticket_id, r.author_name, r.text"
                " FROM replies r WHERE r.id > %s AND r.is_admin = 1",
                (last_reply,),
            )
            for row in cur.fetchall():
                last_reply = int(row["id"])
                send_webhook(
                    webhook,
                    f"📨 **Ответ на #{row['ticket_id']}** от "
                    f"{row['author_name']}:\n{row['text'][:300]}",
                )
        except Exception as e:
            print(f"notify error: {e}")
        time.sleep(15)


if __name__ == "__main__":
    main()
