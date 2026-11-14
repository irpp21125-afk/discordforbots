# Support Bot Panel (C++)

CLI-панель управления ботом: тикеты, пользователи, статистика,
наказания, розыгрыши, FAQ, настройки. Работает напрямую с MySQL.

## Требования

1. **Компилятор C++17** (Visual Studio 2022 + workload «Desktop C++» или MinGW-w64)
2. **CMake** 3.16+
3. **MySQL Server 8.0** (у вас уже установлен — C:\Program Files\MySQL)
   — C API (`libmysql`) входит в поставку Server.

## Сборка (Windows, Visual Studio)

```bat
cd cpp_app
mkdir build && cd build
cmake .. -G "Visual Studio 17 2022"
cmake --build . --config Release
```

Готовый exe: `build\Release\support_bot_panel.exe`
(рядом автоматически копируется `libmysql.dll`).

## Сборка (MinGW)

```bat
cd cpp_app
mkdir build && cd build
cmake .. -G "MinGW Makefiles" -DMYSQL_ROOT="C:/Program Files/MySQL/MySQL Server 8.0"
mingw32-make
```

## Сборка (Linux)

```bash
sudo apt install libmysqlclient-dev cmake g++
cd cpp_app && mkdir build && cd build
cmake .. && make
```

## Запуск

Панель читает переменные окружения (вручную или через `.env` проекта):

```bat
set MYSQL_HOST=localhost
set MYSQL_USER=root
set MYSQL_PASSWORD=ваш_пароль
set MYSQL_DATABASE=support_bot
set DISCORD_TOKEN=...
support_bot_panel.exe
```

## Меню

- 📋 **Обращения** — просмотр, детали, ответы, закрытие тикетов
- 👥 **Пользователи** — Telegram и Discord (XP, уровни)
- 📊 **Статистика** — счётчики тикетов и пользователей
- 📈 **Активность** — журнал событий сервера
- ⚖️ **Наказания** — история и выдача (warn/mute/kick/ban)
- 🎉 **Розыгрыши** — список розыгрышей
- ❓ **FAQ** — база ответов
- ⚙️ **Настройки** — просмотр и изменение конфига
- 📣 **Рассылка** — через Discord-бот (команда)
