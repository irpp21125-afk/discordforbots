"""Слой доступа к MySQL.

Настройка через .env:
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

Все модули (Discord-бот, Telegram-бот, C++ приложение) используют этот файл.
"""

import os

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
        "autocommit": False,
        "use_pure": True,
    }


def get_conn():
    """Новое соединение. MySQL-коннектор не потокобезопасен —
    соединения создаются на задачу, а не хранятся глобально."""
    return mysql.connector.connect(**db_config())


class DB:
    """Контекстный менеджер: фикс/откат + закрытие соединения."""

    def __enter__(self):
        self.conn = get_conn()
        self.cur = self.conn.cursor(dictionary=True)
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.cur.close()
        self.conn.close()
        return False

    def execute(self, sql, params=None):
        self.cur.execute(sql, params or ())
        return self.cur

    def fetchone(self, sql, params=None):
        self.cur.execute(sql, params or ())
        return self.cur.fetchone()

    def fetchall(self, sql, params=None):
        self.cur.execute(sql, params or ())
        return self.cur.fetchall()

    def lastrowid(self):
        return self.cur.lastrowid


# Миграции для существующих баз: колонки, которых не было в ранней схеме.
# (таблица, колонка, определение)
COLUMN_MIGRATIONS = [
    ("dc_users", "privilege", "VARCHAR(32) DEFAULT 'none'"),
    ("guild_settings", "welcome_enabled", "TINYINT(1) DEFAULT 1"),
    ("guild_settings", "welcome_autorole", "BIGINT"),
    ("guild_settings", "log_channel", "BIGINT"),
    ("guild_settings", "log_enabled", "TINYINT(1) DEFAULT 0"),
    ("guild_settings", "filter_enabled", "TINYINT(1) DEFAULT 1"),
    ("guild_settings", "antispam_enabled", "TINYINT(1) DEFAULT 0"),
    ("guild_settings", "antispam_limit", "INT DEFAULT 5"),
    ("guild_settings", "antiflood_enabled", "TINYINT(1) DEFAULT 0"),
    ("guild_settings", "antiflood_seconds", "INT DEFAULT 5"),
]

# Новые таблицы, появляющиеся поверх ранней схемы.
MIGRATION_TABLES = [
    """CREATE TABLE IF NOT EXISTS privileges (
         id INT AUTO_INCREMENT PRIMARY KEY,
         name VARCHAR(64) UNIQUE NOT NULL,
         price DECIMAL(10,2) NOT NULL,
         color VARCHAR(16) DEFAULT '#5865F2',
         icon VARCHAR(32) DEFAULT '',
         created_at DATETIME DEFAULT NOW()
       ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS shop_items (
         id INT AUTO_INCREMENT PRIMARY KEY,
         guild_id BIGINT NOT NULL,
         name VARCHAR(128) NOT NULL,
         price INT NOT NULL DEFAULT 0,
         description TEXT,
         INDEX idx_shop_guild (guild_id)
       ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS inventory (
         id INT AUTO_INCREMENT PRIMARY KEY,
         guild_id BIGINT NOT NULL,
         user_id BIGINT NOT NULL,
         item_name VARCHAR(128) NOT NULL,
         purchased_at DATETIME DEFAULT NOW(),
         INDEX idx_inv_user (guild_id, user_id)
       ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS filter_words (
         id INT AUTO_INCREMENT PRIMARY KEY,
         guild_id BIGINT NOT NULL,
         word VARCHAR(128) NOT NULL,
         INDEX idx_filter_guild (guild_id)
       ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS moderation_log (
         id INT AUTO_INCREMENT PRIMARY KEY,
         guild_id BIGINT NOT NULL,
         user_id BIGINT NOT NULL,
         moderator_id BIGINT,
         action VARCHAR(32) NOT NULL,
         reason TEXT,
         created_at DATETIME,
         INDEX idx_modlog (guild_id, user_id)
       ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS reminders (
         id INT AUTO_INCREMENT PRIMARY KEY,
         guild_id BIGINT,
         user_id BIGINT NOT NULL,
         channel_id BIGINT,
         message TEXT,
         remind_at DATETIME NOT NULL,
         delivered TINYINT(1) DEFAULT 0,
         created_at DATETIME DEFAULT NOW(),
         INDEX idx_remind (remind_at, delivered)
       ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS suggestions (
         id INT AUTO_INCREMENT PRIMARY KEY,
         guild_id BIGINT NOT NULL,
         user_id BIGINT NOT NULL,
         channel_id BIGINT,
         message_id BIGINT,
         text TEXT NOT NULL,
         upvotes INT DEFAULT 0,
         downvotes INT DEFAULT 0,
         status ENUM('pending','approved','rejected') DEFAULT 'pending',
         created_at DATETIME DEFAULT NOW(),
         INDEX idx_sugg (guild_id, status)
       ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS game_stats (
         id INT AUTO_INCREMENT PRIMARY KEY,
         guild_id BIGINT NOT NULL,
         user_id BIGINT NOT NULL,
         game VARCHAR(32) NOT NULL,
         wins INT DEFAULT 0,
         losses INT DEFAULT 0,
         draws INT DEFAULT 0,
         last_played DATETIME,
         INDEX idx_game (guild_id, user_id, game)
       ) ENGINE=InnoDB""",
]

PRIVILEGE_PRESETS = [
    ("starvision", 99.00, "#E91E63", "⭐"),
    ("viaglobal", 199.00, "#9C27B0", "🌍"),
    ("gectoring", 499.00, "#FF9800", "🏆"),
]


def _column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
        "AND COLUMN_NAME = %s",
        (table, column),
    )
    return cur.fetchone()[0] > 0


def run_migrations(conn):
    """Идемпотентная миграция: новые таблицы + недостающие колонки."""
    cur = conn.cursor()
    try:
        for ddl in MIGRATION_TABLES:
            try:
                cur.execute(ddl)
            except mysql.connector.Error as e:
                print(f"[db] migration table: {e}")

        for table, column, definition in COLUMN_MIGRATIONS:
            try:
                if not _column_exists(cur, table, column):
                    cur.execute(
                        f"ALTER TABLE `{table}` ADD COLUMN `{column}` "
                        f"{definition}"
                    )
                    print(f"[db] migration: {table}.{column} added")
            except mysql.connector.Error as e:
                print(f"[db] migration {table}.{column}: {e}")

        for name, price, color, icon in PRIVILEGE_PRESETS:
            cur.execute(
                "INSERT IGNORE INTO privileges(name, price, color, icon) "
                "VALUES (%s, %s, %s, %s)",
                (name, price, color, icon),
            )
        conn.commit()
    finally:
        cur.close()


def init_db():
    """Создание БД и таблиц (идемпотентно) + миграции.

    Для полного импорта используйте: mysql -u root -p < schema.sql
    """
    cfg = db_config()
    if not cfg["password"]:
        raise RuntimeError(
            "❌ MYSQL_PASSWORD не задан в .env.\n"
            "Откройте .env в этой папке, впишите пароль root (из MySQL "
            "Workbench) и сохраните.\n\n"
            "После этого запустите заново."
        )
    conn = mysql.connector.connect(
        host=cfg["host"], port=cfg["port"], user=cfg["user"],
        password=cfg["password"], charset="utf8mb4", autocommit=True,
    )
    cur = conn.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS `%s` "
                "DEFAULT CHARACTER SET utf8mb4" % cfg["database"])
    cur.close()
    conn.close()

    schema_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "schema.sql"
    )
    conn = get_conn()
    try:
        if os.path.exists(schema_path):
            cur = conn.cursor()
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    sql = f.read()
                for statement in sql.split(";"):
                    statement = _strip_comments(statement)
                    if statement:
                        try:
                            cur.execute(statement)
                        except mysql.connector.Error:
                            pass  # таблица/колонка уже существует
                conn.commit()
            finally:
                cur.close()
        run_migrations(conn)
    finally:
        conn.close()


def _strip_comments(statement: str) -> str:
    lines = [
        line for line in statement.splitlines()
        if not line.strip().startswith("--")
    ]
    return "\n".join(lines).strip()


def get_setting(key: str, default: str = "") -> str:
    with DB() as db:
        row = db.fetchone(
            "SELECT `value` FROM settings WHERE `key` = %s", (key,)
        )
    return row["value"] if row else default


def set_setting(key: str, value: str):
    with DB() as db:
        db.execute(
            "INSERT INTO settings(`key`, `value`) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE `value` = VALUES(`value`)",
            (key, value),
        )
