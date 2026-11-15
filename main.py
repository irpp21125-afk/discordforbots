"""Точка входа для панелей хостинга (FadeHost, Pterodactyl и т.п.).

Команда запуска на хостинге:

    python main.py

Запускает Discord-бот через watchdog: если бот упадёт, он будет поднят
заново, и панель не зафиксирует «3 падения подряд».
"""

import os
import runpy
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def main():
    watchdog = os.path.join(ROOT, "run_forever.py")
    bot = os.path.join(ROOT, "discord_bot", "bot.py")

    if os.path.exists(watchdog) and os.path.exists(bot):
        sys.argv = [watchdog, bot]
        runpy.run_path(watchdog, run_name="__main__")
        return

    # запасной вариант — запуск бота напрямую в этом процессе
    runpy.run_path(bot, run_name="__main__")


if __name__ == "__main__":
    main()
