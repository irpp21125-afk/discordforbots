# Support Bot — Discord-бот + MySQL + Панели управления

Система поддержки: Discord-бот с модулями (Обращения, Модерация,
Наказания, Роли, Экономика, Розыгрыши, Автоматизация, Оповещения),
общая MySQL-база и две панели: CLI на C++ и GUI на Python (Windows).

## Архитектура

```
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│ Discord-бот  │   │  C++ панель  │   │  Flask API       │
│ (discord.py) │   │  (CLI, MySQL │   │ (HTTP, X-API-Key)│
│              │   │    C API)    │   │                  │
└──────┬───────┘   └──────┬───────┘   └────────┬─────────┘
       │                  │                    │
       └──────────────────┼────────────────────┘
                     ┌────▼─────┐
                     │  MySQL   │  support_bot (schema.sql)
                     └──────────┘
                              ▲
                              │ HTTP / X-API-Key
                     ┌────────┴─────────┐
                     │  Windows-панель  │
                     │  (Python GUI)    │
                     └──────────────────┘
```

## Быстрый старт

### 1. База данных (MySQL Workbench)

Откройте MySQL Workbench → подключитесь → File → Run Script → `schema.sql`.
Или из консоли:

```bat
mysql -u root -p < schema.sql
```

### 2. Настройка

```bat
copy .env.example .env
notepad .env
```

Заполните: `MYSQL_PASSWORD`, `DISCORD_TOKEN`, `ADMIN_PASSWORD`.

### 3. Миграция старых данных (опционально)

```bat
python migrate_to_mysql.py
```

### 4. Discord-бот

```bat
pip install -r requirements.txt
python discord_bot\bot.py
```

Пригласите бота с правами: Manage Channels, Manage Roles, Kick/Ban,
Moderate Members (ссылка-приглашение в Developer Portal → OAuth2).

### 5. C++ панель (CLI)

См. `cpp_app/README.md` (сборка через CMake + MySQL C API).

### 6. Windows-панель (GUI)

Графическое приложение на Python (Tkinter) — работает через HTTP API,
не требует MySQL на клиенте.

**Запуск из исходников:**
```bat
python desktop\app.py
```

**Сборка .exe:**
```bat
build_exe.bat
```
Результат: `dist\SupportBotPanel.exe` (один файл, ~15 МБ).

**Сборка установщика:**
```bat
installer\build_installer.bat
```
Результат: `installer\SupportBotPanel_Setup.exe` (раздавать пользователям).

**Подключение:**
1. В поле «Сервер» введите `http://ВАШ_ХОСТИНГ:ПОРТ`
2. В поле «API-ключ» — значение `API_KEY` из `.env` на сервере
3. Нажмите «Подключиться»

Возможности: статистика, обращения (ответы/закрытие), пользователи
(XP/привилегии), наказания, FAQ, настройки, рассылка.

### 7. Уведомления в Discord (опционально)

Задайте `DISCORD_WEBHOOK_URL` в `.env` и запустите `python notify.py`.

## Структура

```
├── schema.sql            — MySQL-схема (18 таблиц)
├── db.py                 — слой доступа к MySQL
├── flask_api.py          — HTTP API (Flask)
├── run_forever.py        — watchdog для 24/7 работы
├── main.py               — точка входа для FadeHost
├── user.py / profile.py  — пользователи и профили
├── support.py            — тикет-система
├── admin.py              — управление правами
├── notify.py             — уведомления через Discord-вебхук
├── migrate_to_mysql.py   — перенос данных из JSON
├── bot_commands.json     — справочник команд
├── discord_bot/          — Discord-бот
│   ├── bot.py            — запуск, коги, фоновые задачи
│   ├── utils.py          — права, настройки гильдий, аудит
│   └── cogs/             — модули из меню панели
│       ├── general.py    — Общие настройки, Баннер, Конфигурация
│       ├── tickets.py    — Обращения
│       ├── moderation.py — Модерация + Наказания + аудит
│       ├── roles.py      — Управление ролями
│       ├── economy.py    — Экономика, Рейтинг, Вовлечённость
│       ├── giveaway.py   — Розыгрыши
│       ├── automod.py    — Автоматизация
│       ├── alerts.py     — Оповещения
│       ├── games.py      — Развлечения
│       ├── logging_cog.py— Логи
│       └── user_info.py  — /userinfo, /help, /serverinfo
├── desktop/              — GUI-панель для Windows
│   ├── app.py            —Tkinter приложение
│   └── app.spec          — PyInstaller spec
├── installer/            — установщик Windows
│   ├── setup.iss         — скрипт Inno Setup
│   └── build_installer.bat
├── build_exe.bat         — сборка .exe через PyInstaller
├── deploy/               — systemd-юниты, автозапуск
├── Dockerfile, docker-compose.yml — Docker-развёртывание
└── cpp_app/              — CLI-панель на C++ (MySQL C API)
```

## Команды Discord-бота

| Команда | Кто | Описание |
|---|---|---|
| `/ticket` | все | Создать обращение |
| `/ticket_close` | все | Закрыть своё обращение |
| `/ticket_answer` | персонал | Ответить на обращение |
| `/ticket_close_id` | персонал | Закрыть по номеру |
| `/tickets` | персонал | Список открытых |
| `/ticket_stats` | персонал | Статистика обращений |
| `/warn` `/mute` `/kick` `/ban` `/unban` | персонал | Наказания |
| `/clear` `/slowmode` `/say` `/embed` | персонал/админ | Канал и сообщения |
| `/punishments` | персонал | История наказаний |
| `/audit` | персонал | Журнал событий |
| `/unban_request` | все | Заявка на разбан |
| `/autorole_set` `/levelrole` `/giverole` | админ | Роли |
| `/top` `/balance` `/daily` `/transfer` | все | Экономика |
| `/shop` `/buy` `/inventory` | все | Магазин |
| `/shop_add` `/shop_remove` | админ | Товары магазина |
| `/addmoney` `/removemoney` `/setmoney` | админ | Балансы |
| `/premium` | админ | Привилегии (starvision/viaglobal/gectoring) |
| `/addword` `/removeword` `/filterlist` `/filtertoggle` | админ | Фильтр слов |
| `/antispam` `/antiflood` `/automod` | админ | Безопасность |
| `/blackjack` `/dice` `/slots` `/card` `/gamestats` | все | Игры |
| `/monopoly` `/monopoly_roll` `/urbanplay` `/urbanjoin` | все | Игры |
| `/logchannel` `/logtoggle` `/logstatus` | админ | Логи |
| `/welcomemsg` `/welcomechannel` `/welcometoggle` `/welcomeautorole` | админ | Приветствия |
| `/ping` `/reminder` `/suggest` `/avatar` `/roll` | все | Утилиты |
| `/userinfo` `/serverinfo` `/help` | все | Справка |
| `/giveaway` | персонал | Розыгрыш |
| `/alert_add` `/alert_remove` | персонал | Оповещения |
| `/config` `/config_set` | админ | Настройки сервера |
| `/server_banner` `/botinfo` | все | Инфо |

Полный список с аргументами — в `bot_commands.json`.

## Работа 24/7

Бот не может работать, когда ваш ПК выключен. Чтобы он жил постоянно,
нужен запуск на сервере, который не выключается (VPS). Ниже три варианта.

### Вариант 1 — Docker (рекомендуется)

Поднимает MySQL, бота, уведомления и API одной командой; всё
перезапускается автоматически после падения и после перезагрузки сервера.

```bash
# на сервере (Ubuntu 22.04 / Debian 12)
sudo apt-get update && sudo apt-get install -y git docker.io docker-compose-plugin

git clone <ваш-репозиторий> /opt/supportbot && cd /opt/supportbot
cp .env.example .env && nano .env        # токен, пароли, API_KEY

docker compose up -d --build
docker compose logs -f bot
```

Данные MySQL лежат в volume `mysql_data` — при `docker compose down`
они сохраняются.

### Вариант 2 — systemd без Docker

```bash
sudo bash deploy/install_services.sh
systemctl status supportbot
journalctl -u supportbot -f
```

Сервисы: `supportbot` (бот), `supportbot-notify`, `supportbot-api`.
Все с `Restart=always`, включаются при загрузке системы.
Путь по умолчанию `/opt/supportbot`, пользователь `supportbot`
(переопределяется через `APP_DIR` / `APP_USER`).

### Вариант 3 — Windows (ваш ПК остаётся основным)

Бот будет стартовать при загрузке Windows, до входа в систему.
Питание при этом должно быть включено.

```powershell
# PowerShell от администратора
powershell -ExecutionPolicy Bypass -File deploy\autostart_windows.ps1
```

### Watchdog (используют все варианты)

`run_forever.py` перезапускает процесс, если он упал:

```bash
python run_forever.py discord_bot/bot.py
```

После 5 быстрых падений подряд делает паузу 5 минут (чтобы не долбить
Discord API при неверном токене). Лог — `watchdog.log`.

### Про `mysqlclient`

Python-код использует `mysql-connector-python`, который ставится без
компиляции. Пакет `mysqlclient` ставить **не нужно** — он требует
системные заголовки MySQL и падает с ошибкой
«Could not find suitable pkg-config». Он нужен только для сборки
C++ панели, и там зависимости ставятся так:

```bash
sudo apt install libmysqlclient-dev cmake g++
```

## Что важно знать про «вечно работает»

| Ситуация | Работает? |
|---|---|
| Бот упал с ошибкой в коде | Да — watchdog поднимет через 3 сек |
| Перезагрузка сервера | Да — systemd / docker restart-политика |
| Пропал интернет на минуту | Да — discord.py переподключается сам |
| MySQL стартует дольше бота | Да — бот ждёт базу 10 попыток по 5 сек |
| **Ваш домашний ПК выключен** | **Нет** — нужен VPS или включённый ПК |
| Домашний интернет отключили | Нет — нужен сервер у провайдера |

Дешёвый VPS на 1 ядре и 1 ГБ ОЗУ (Hetzner, Timeweb, Selectel,
Beget — от 200–400 ₽/мес) полностью покрывает эту систему.
