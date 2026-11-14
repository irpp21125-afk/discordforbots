"""Менеджер тикет-системы (MySQL).

Старый API для Telegram-бота сохранён. Добавлены Discord-интеграции:
создание тикет-канала, поиск по guild_id, пагинация.
"""

import secrets

from db import DB, init_db

STATUS_EMOJI = {"open": "🟢", "answered": "🟡", "closed": "🔴"}


class SupportManager:
    """Менеджер системы поддержки (тикетов)."""

    def __init__(self, filepath: str | None = None):
        init_db()

    def create_ticket(self, user_id: int, message: str,
                      category: str = "Вопрос по боту",
                      priority: str = "normal") -> int:
        with DB() as db:
            db.execute(
                "INSERT INTO tickets(author_type, author_ref, category, priority,"
                " status, message, created_at, updated_at)"
                " VALUES ('tg', %s, %s, %s, 'open', %s, NOW(), NOW())",
                (str(int(user_id)), category, priority, message),
            )
            return int(db.lastrowid())

    def create_ticket_web(self, author_type: str, author_ref: str, message: str,
                          email: str | None = None, category: str = "Другое",
                          priority: str = "normal") -> dict:
        email_code = secrets.token_hex(4).upper() if author_type == "guest" else None
        with DB() as db:
            db.execute(
                "INSERT INTO tickets(author_type, author_ref, email, email_code,"
                " category, priority, status, message, created_at, updated_at)"
                " VALUES (%s, %s, %s, %s, %s, %s, 'open', %s, NOW(), NOW())",
                (author_type, str(author_ref), email, email_code, category,
                 priority, message),
            )
            return {"id": int(db.lastrowid()), "email_code": email_code}

    def create_ticket_dc(self, guild_id: int, user_id: int, message: str,
                         category: str = "Обращение",
                         priority: str = "normal",
                         channel_id: int | None = None) -> int:
        with DB() as db:
            db.execute(
                "INSERT INTO tickets(author_type, author_ref, category, priority,"
                " status, message, guild_id, channel_id, created_at, updated_at)"
                " VALUES ('dc', %s, %s, %s, 'open', %s, %s, %s, NOW(), NOW())",
                (str(user_id), category, priority, message,
                 int(guild_id), int(channel_id) if channel_id else None),
            )
            return int(db.lastrowid())

    def get_ticket_by_id(self, ticket_id: int) -> dict | None:
        with DB() as db:
            row = db.fetchone(
                "SELECT * FROM tickets WHERE id = %s", (int(ticket_id),)
            )
        if not row:
            return None
        with DB() as db:
            replies = db.fetchall(
                "SELECT author_name, is_admin, text, created_at FROM replies "
                "WHERE ticket_id = %s ORDER BY created_at, id",
                (int(ticket_id),),
            )
        return {
            "id": row["id"],
            "user_id": row["author_ref"],
            "author_type": row["author_type"],
            "email": row.get("email"),
            "email_code": row.get("email_code"),
            "category": row["category"],
            "priority": row["priority"],
            "status": row["status"],
            "message": row["message"],
            "rating": row.get("rating"),
            "guild_id": row.get("guild_id"),
            "channel_id": row.get("channel_id"),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "replies": [
                {
                    "author_name": r["author_name"],
                    "is_admin": bool(r["is_admin"]),
                    "text": r["text"],
                    "created_at": str(r["created_at"]),
                }
                for r in replies
            ],
        }

    def get_user_tickets(self, user_id: int) -> str:
        with DB() as db:
            rows = db.fetchall(
                "SELECT id, status, created_at, message FROM tickets "
                "WHERE author_type = 'tg' AND author_ref = %s "
                "ORDER BY created_at DESC LIMIT 20",
                (str(int(user_id)),),
            )
        if not rows:
            return ""
        lines = ["📋 Ваши обращения:\n"]
        for row in rows:
            emoji = STATUS_EMOJI.get(row["status"], "⚪")
            try:
                date = str(row["created_at"]).split(".")[0].split(" ")[1][:5]
            except Exception:
                date = "?"
            text = row["message"][:60]
            suffix = "..." if len(row["message"]) > 60 else ""
            lines.append(
                f"{emoji} #{row['id']} — {row['status']} ({date})\n"
                f"   {text}{suffix}"
            )
        return "\n\n".join(lines)

    def get_open_tickets(self) -> list:
        with DB() as db:
            return db.fetchall(
                "SELECT * FROM tickets WHERE status = 'open' "
                "ORDER BY created_at DESC"
            )

    def get_all_tickets(self) -> list:
        with DB() as db:
            return db.fetchall(
                "SELECT * FROM tickets ORDER BY created_at DESC"
            )

    def get_tickets_for_author(self, author_type: str, author_ref: str) -> list:
        with DB() as db:
            return db.fetchall(
                "SELECT * FROM tickets WHERE author_type = %s AND author_ref = %s "
                "ORDER BY created_at DESC",
                (author_type, str(author_ref)),
            )

    def find_guest_ticket(self, ticket_id: int, email: str, code: str) -> dict | None:
        with DB() as db:
            row = db.fetchone(
                "SELECT id, email_code FROM tickets WHERE id = %s",
                (int(ticket_id),),
            )
        if not row:
            return None
        stored = (row.get("email_code") or "").lower()
        if stored != (code or "").strip().lower():
            return None
        return self.get_ticket_by_id(ticket_id)

    def search_tickets(self, query: str) -> list:
        q = f"%{query.strip()}%"
        with DB() as db:
            return db.fetchall(
                "SELECT * FROM tickets WHERE CAST(id AS CHAR) LIKE %s "
                "OR message LIKE %s OR email LIKE %s OR author_ref LIKE %s "
                "ORDER BY created_at DESC LIMIT 200",
                (q, q, q, q),
            )

    def list_tickets(self, status: str | None = None, page: int = 1,
                     per_page: int = 20) -> tuple:
        with DB() as db:
            if status:
                total_row = db.fetchone(
                    "SELECT COUNT(*) AS c FROM tickets WHERE status = %s",
                    (status,),
                )
                total = int(total_row["c"])
                offset = (page - 1) * per_page
                rows = db.fetchall(
                    "SELECT * FROM tickets WHERE status = %s "
                    "ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (status, per_page, offset),
                )
            else:
                total_row = db.fetchone("SELECT COUNT(*) AS c FROM tickets")
                total = int(total_row["c"])
                offset = (page - 1) * per_page
                rows = db.fetchall(
                    "SELECT * FROM tickets ORDER BY created_at DESC "
                    "LIMIT %s OFFSET %s",
                    (per_page, offset),
                )
        pages = max(1, -(-total // per_page))
        return list(rows), pages, total

    def close_ticket(self, ticket_id: int) -> bool:
        with DB() as db:
            cur = db.execute(
                "UPDATE tickets SET status = 'closed', updated_at = NOW() "
                "WHERE id = %s AND status != 'closed'",
                (int(ticket_id),),
            )
        return cur.rowcount > 0

    def reopen_ticket(self, ticket_id: int) -> bool:
        with DB() as db:
            cur = db.execute(
                "UPDATE tickets SET status = 'open', updated_at = NOW() WHERE id = %s",
                (int(ticket_id),),
            )
        return cur.rowcount > 0

    def set_priority(self, ticket_id: int, priority: str) -> bool:
        if priority not in {"low", "normal", "high"}:
            return False
        with DB() as db:
            cur = db.execute(
                "UPDATE tickets SET priority = %s, updated_at = NOW() "
                "WHERE id = %s",
                (priority, int(ticket_id)),
            )
        return cur.rowcount > 0

    def set_rating(self, ticket_id: int, rating: int) -> bool:
        if not 1 <= int(rating) <= 5:
            return False
        with DB() as db:
            cur = db.execute(
                "UPDATE tickets SET rating = %s WHERE id = %s",
                (int(rating), int(ticket_id)),
            )
        return cur.rowcount > 0

    def add_reply(self, ticket_id: int, text: str, is_admin: bool = True,
                  author_name: str = "Администратор") -> bool:
        with DB() as db:
            row = db.fetchone(
                "SELECT status FROM tickets WHERE id = %s",
                (int(ticket_id),),
            )
        if not row:
            return False
        new_status = "answered" if is_admin else row["status"]
        with DB() as db:
            db.execute(
                "INSERT INTO replies(ticket_id, author_name, is_admin, text, "
                "created_at) VALUES (%s, %s, %s, %s, NOW())",
                (int(ticket_id), author_name, 1 if is_admin else 0, text),
            )
            db.execute(
                "UPDATE tickets SET status = %s, updated_at = NOW() WHERE id = %s",
                (new_status, int(ticket_id)),
            )
        return True

    def get_counts_by_status(self) -> dict:
        with DB() as db:
            rows = db.fetchall(
                "SELECT status, COUNT(*) AS c FROM tickets GROUP BY status"
            )
        counts = {"open": 0, "answered": 0, "closed": 0}
        for row in rows:
            counts[row["status"]] = int(row["c"])
        counts["total"] = sum(counts.values())
        return counts

    def get_daily_stats(self, days: int = 14) -> list:
        result = []
        for offset in range(days - 1, -1, -1):
            with DB() as db:
                created_row = db.fetchone(
                    "SELECT COUNT(*) AS c FROM tickets "
                    "WHERE DATE(created_at) = DATE_SUB(CURDATE(), INTERVAL %s DAY)",
                    (offset,),
                )
                closed_row = db.fetchone(
                    "SELECT COUNT(*) AS c FROM tickets "
                    "WHERE status = 'closed' AND DATE(updated_at) = "
                    "DATE_SUB(CURDATE(), INTERVAL %s DAY)",
                    (offset,),
                )
            from datetime import date, timedelta
            day_str = (date.today() - timedelta(days=offset)).isoformat()
            result.append({
                "day": day_str,
                "created": int(created_row["c"]) if created_row else 0,
                "closed": int(closed_row["c"]) if closed_row else 0,
            })
        return result

    def get_avg_response_hours(self) -> float | None:
        with DB() as db:
            rows = db.fetchall(
                "SELECT t.created_at AS t_created, "
                "MIN(r.created_at) AS r_created "
                "FROM tickets t JOIN replies r "
                "ON r.ticket_id = t.id AND r.is_admin = 1 "
                "GROUP BY t.id"
            )
        deltas = []
        for r in rows:
            try:
                diff = (r["r_created"] - r["t_created"]).total_seconds() / 3600
                deltas.append(diff)
            except (TypeError, ValueError):
                continue
        if not deltas:
            return None
        return round(sum(deltas) / len(deltas), 1)

    def get_avg_rating(self) -> float | None:
        with DB() as db:
            row = db.fetchone(
                "SELECT AVG(rating) AS a FROM tickets WHERE rating IS NOT NULL"
            )
        return round(row["a"], 2) if row and row["a"] is not None else None
