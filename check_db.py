"""Проверка подключения к MySQL из .env.

Запуск:  python check_db.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mysql.connector

from db import db_config

cfg = db_config()
print(f"host={cfg['host']}  port={cfg['port']}  "
      f"user={cfg['user']}  db={cfg['database']}")
print(f"password: {'(пусто!)' if not cfg['password'] else '***задан***'}")

if not cfg["password"]:
    print("\n❌ Пароль пуст. Откройте .env и заполните MYSQL_PASSWORD.")
    sys.exit(1)

try:
    conn = mysql.connector.connect(
        host=cfg["host"], port=cfg["port"], user=cfg["user"],
        password=cfg["password"], charset="utf8mb4",
    )
    cur = conn.cursor()
    cur.execute("SELECT VERSION()")
    print(f"\n✅ Подключение успешно. MySQL {cur.fetchone()[0]}")
    cur.execute("SHOW DATABASES LIKE 'support_bot'")
    if cur.fetchone():
        print("✅ База support_bot существует.")
    else:
        print("ℹ️  Базы support_bot ещё нет — создастся при запуске бота "
              "(или выполните schema.sql).")
    cur.close()
    conn.close()
except mysql.connector.Error as e:
    if e.errno == 1045:
        print(f"\n❌ Ошибка 1045: неверный пользователь/пароль ({cfg['user']}).")
        print("   Проверьте MYSQL_USER и MYSQL_PASSWORD в .env.")
        print("   Подсказка: в Workbench вы входите тем же паролем.")
    else:
        print(f"\n❌ Ошибка MySQL {e.errno}: {e.msg}")
    sys.exit(1)
