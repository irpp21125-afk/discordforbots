"""Watchdog: бесконечно перезапускает скрипт, если он упал.

Использование:
    python run_forever.py discord_bot/bot.py
    python run_forever.py notify.py
    python run_forever.py flask_api.py

Логи пишутся в watchdog.log рядом с этим файлом.
"""

import os
import subprocess
import sys
import time
from datetime import datetime

# Если процесс умирает быстрее — ждём дольше, чтобы не долбить базу/токен
FAST_FAIL_SECONDS = 10
FAST_FAIL_LIMIT = 5
SLEEP_NORMAL = 3
SLEEP_AFTER_LIMIT = 300

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "watchdog.log")


def log(msg: str):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    script = sys.argv[1]
    extra = sys.argv[2:]

    # относительный путь ищем относительно каталога проекта, а не cwd
    if not os.path.isabs(script):
        candidate = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), script
        )
        if os.path.exists(candidate):
            script = candidate

    if not os.path.exists(script):
        log(f"Файл не найден: {script} (cwd={os.getcwd()})")
        sys.exit(1)

    log(f"Watchdog старт: {script} {' '.join(extra)}")
    fast_fails = 0

    while True:
        started = time.time()
        try:
            proc = subprocess.run([sys.executable, script, *extra])
            code = proc.returncode
        except KeyboardInterrupt:
            log("Остановлено вручную (Ctrl+C)")
            return
        except Exception as e:
            log(f"Не удалось запустить процесс: {e}")
            code = -1

        ran = time.time() - started
        log(f"Процесс завершился (код {code}) за {ran:.1f} сек")

        # 0 обычно означает штатный выход — всё равно перезапускаем,
        # бот должен жить всегда
        if ran < FAST_FAIL_SECONDS:
            fast_fails += 1
        else:
            fast_fails = 0

        if fast_fails >= FAST_FAIL_LIMIT:
            log(f"Слишком много быстрых падений подряд — "
                f"пауза {SLEEP_AFTER_LIMIT} сек")
            time.sleep(SLEEP_AFTER_LIMIT)
            fast_fails = 0
        else:
            time.sleep(SLEEP_NORMAL)


if __name__ == "__main__":
    main()
