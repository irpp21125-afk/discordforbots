/*
 * Support Bot — CLI панель управления
 * Компиляция: см. CMakeLists.txt
 * Зависимости: MySQL C API (libmysql)
 */

#include <iostream>
#include <string>
#include <cstdlib>
#include <memory>
#include <map>
#include <vector>
#include <algorithm>

#ifdef _WIN32
#include <windows.h>
#include <mysql.h>
#else
#include <mysql/mysql.h>
#endif

// ---------- конфигурация (можно заменить на чтение из .env) ----------
struct Config {
    std::string host = "localhost";
    int port = 3306;
    std::string user = "root";
    std::string password;
    std::string database = "support_bot";
    std::string discord_token;
    std::string admin_login = "admin";
    std::string admin_password;
};

Config load_config() {
    Config cfg;
    auto get = [](const char* key, const char* def = "") -> std::string {
        const char* v = std::getenv(key);
        return v ? std::string(v) : std::string(def);
    };
    cfg.host = get("MYSQL_HOST", "localhost");
    cfg.port = std::atoi(get("MYSQL_PORT", "3306").c_str());
    cfg.user = get("MYSQL_USER", "root");
    cfg.password = get("MYSQL_PASSWORD");
    cfg.database = get("MYSQL_DATABASE", "support_bot");
    cfg.discord_token = get("DISCORD_TOKEN");
    cfg.admin_login = get("ADMIN_LOGIN", "admin");
    cfg.admin_password = get("ADMIN_PASSWORD");
    return cfg;
}

// ---------- упрощённая обёртка MySQL ----------
class Database {
public:
    explicit Database(const Config& cfg) {
        conn = mysql_init(nullptr);
        if (!mysql_real_connect(conn, cfg.host.c_str(), cfg.user.c_str(),
                                cfg.password.c_str(), cfg.database.c_str(),
                                cfg.port, nullptr, 0)) {
            std::cerr << "Ошибка подключения к MySQL: "
                      << mysql_error(conn) << std::endl;
            throw std::runtime_error("MySQL connection failed");
        }
        mysql_set_character_set(conn, "utf8mb4");
    }

    ~Database() {
        if (conn) mysql_close(conn);
    }

    // Невозможно копировать — только перемещать
    Database(const Database&) = delete;
    Database& operator=(const Database&) = delete;

    MYSQL_RES* query(const std::string& sql) {
        if (mysql_query(conn, sql.c_str())) {
            std::cerr << "SQL error: " << mysql_error(conn) << std::endl;
            return nullptr;
        }
        return mysql_store_result(conn);
    }

    void execute(const std::string& sql) {
        mysql_query(conn, sql.c_str());
    }

    // Простая экранировка строки (для параметров)
    std::string escape(const std::string& s) {
        std::string out;
        out.reserve(s.size() + 8);
        for (char c : s) {
            switch (c) {
                case '\'': out += "\\'"; break;
                case '"':  out += "\\\""; break;
                case '\\': out += "\\\\"; break;
                case '\0': out += "\\0"; break;
                case '\n': out += "\\n"; break;
                default:   out += c;
            }
        }
        return out;
    }

private:
    MYSQL* conn = nullptr;
};

// ---------- вывод ----------
void clear_screen() {
#ifdef _WIN32
    system("cls");
#else
    system("clear");
#endif
}

void print_header(const std::string& title) {
    std::cout << "\n" << std::string(56, '=') << std::endl;
    std::cout << "  " << title << std::endl;
    std::cout << std::string(56, '=') << std::endl;
}

void print_menu(const std::vector<std::string>& items) {
    for (size_t i = 0; i < items.size(); ++i) {
        std::cout << "  [" << i << "] " << items[i] << std::endl;
    }
    std::cout << "  [0] Назад / выход" << std::endl;
}

int read_choice() {
    int c;
    std::cout << "\nВаш выбор: ";
    std::cin >> c;
    std::cin.ignore(10000, '\n');
    return c;
}

std::string read_line(const std::string& prompt = "") {
    if (!prompt.empty()) std::cout << prompt;
    std::string s;
    std::getline(std::cin, s);
    return s;
}

// ---------- просмотр тикетов ----------
void show_tickets(Database& db) {
    print_header("📋 Обращения");
    MYSQL_RES* res = db.query(
        "SELECT id, author_type, author_ref, category, priority, status,"
        " LEFT(message, 50), created_at FROM tickets ORDER BY created_at DESC LIMIT 20"
    );
    if (!res) return;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        std::cout << "  #" << row[0] << " [" << row[4] << "] " << row[3]
                  << " | " << row[5] << " | " << row[6] << "..."
                  << " | " << row[7] << std::endl;
    }
    mysql_free_result(res);
}

void ticket_detail(Database& db) {
    std::cout << "Номер тикета: ";
    int id;
    std::cin >> id;
    MYSQL_RES* res = db.query(
        "SELECT id, author_type, author_ref, category, priority, status,"
        " message, created_at FROM tickets WHERE id = " + std::to_string(id)
    );
    if (!res) return;
    MYSQL_ROW row = mysql_fetch_row(res);
    if (!row) {
        std::cout << "Тикет не найден." << std::endl;
        mysql_free_result(res);
        return;
    }
    std::cout << "\n--- Обращение #" << row[0] << " ---\n"
              << "Автор: " << row[1] << " " << row[2] << "\n"
              << "Категория: " << row[3] << "\n"
              << "Приоритет: " << row[4] << "\n"
              << "Статус: " << row[5] << "\n"
              << "Создан: " << row[7] << "\n\n"
              << "Сообщение:\n" << row[6] << "\n" << std::endl;
    mysql_free_result(res);

    // Ответы
    MYSQL_RES* reps = db.query(
        "SELECT author_name, is_admin, text, created_at FROM replies"
        " WHERE ticket_id = " + std::to_string(id) + " ORDER BY id"
    );
    if (reps) {
        MYSQL_ROW r;
        while ((r = mysql_fetch_row(reps))) {
            std::cout << (std::atoi(r[1]) ? "👨‍💼 " : "👤 ") << r[0]
                      << " (" << r[3] << "):\n" << r[2] << "\n" << std::endl;
        }
        mysql_free_result(reps);
    }
}

void answer_ticket(Database& db) {
    int id;
    std::cout << "Номер тикета: ";
    std::cin >> id;
    std::cin.ignore(10000, '\n');
    std::string text = read_line("Текст ответа: ");
    if (text.empty()) {
        std::cout << "Пустой ответ не отправлен." << std::endl;
        return;
    }
    std::string safe_text = db.escape(text);
    db.execute(
        "INSERT INTO replies(ticket_id, author_name, is_admin, text, created_at)"
        " VALUES (" + std::to_string(id) + ", 'Админ (C++)', 1, '" + safe_text
        + "', NOW())"
    );
    db.execute(
        "UPDATE tickets SET status = 'answered', updated_at = NOW()"
        " WHERE id = " + std::to_string(id)
    );
    std::cout << "✅ Ответ отправлен!" << std::endl;
}

void close_ticket(Database& db) {
    int id;
    std::cout << "Номер тикета: ";
    std::cin >> id;
    db.execute(
        "UPDATE tickets SET status = 'closed', updated_at = NOW()"
        " WHERE id = " + std::to_string(id)
    );
    std::cout << "✅ Тикет закрыт." << std::endl;
}

// ---------- статистика ----------
void show_stats(Database& db) {
    print_header("📊 Статистика");
    MYSQL_RES* res = db.query(
        "SELECT status, COUNT(*) FROM tickets GROUP BY status"
    );
    if (res) {
        MYSQL_ROW row;
        while ((row = mysql_fetch_row(res))) {
            std::cout << "  " << row[0] << ": " << row[1] << std::endl;
        }
        mysql_free_result(res);
    }
    res = db.query("SELECT COUNT(*) FROM tg_users");
    if (res) {
        MYSQL_ROW row = mysql_fetch_row(res);
        if (row) std::cout << "  Telegram-пользователей: " << row[0] << std::endl;
        mysql_free_result(res);
    }
    res = db.query("SELECT COUNT(*) FROM dc_users");
    if (res) {
        MYSQL_ROW row = mysql_fetch_row(res);
        if (row) std::cout << "  Discord-пользователей: " << row[0] << std::endl;
        mysql_free_result(res);
    }
}

void show_activity(Database& db) {
    print_header("📈 Активность (последние события)");
    MYSQL_RES* res = db.query(
        "SELECT event, user_id, created_at FROM activity_log"
        " ORDER BY created_at DESC LIMIT 20"
    );
    if (!res) return;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        std::cout << "  " << row[2] << " | " << row[0]
                  << " | user " << row[1] << std::endl;
    }
    mysql_free_result(res);
}

// ---------- пользователи ----------
void show_users(Database& db) {
    print_header("👥 Пользователи");
    std::cout << "\n--- Telegram ---\n";
    MYSQL_RES* res = db.query(
        "SELECT id, username, name, is_admin, last_activity"
        " FROM tg_users ORDER BY last_activity DESC LIMIT 20"
    );
    if (res) {
        MYSQL_ROW row;
        while ((row = mysql_fetch_row(res))) {
            std::cout << "  " << row[0] << " | " << row[1] << " | " << row[2]
                      << (std::atoi(row[3]) ? " | ADMIN" : "") << " | " << row[4]
                      << std::endl;
        }
        mysql_free_result(res);
    }
    std::cout << "\n--- Discord ---\n";
    res = db.query(
        "SELECT id, username, display_name, points, level, last_activity"
        " FROM dc_users ORDER BY points DESC LIMIT 20"
    );
    if (res) {
        MYSQL_ROW row;
        while ((row = mysql_fetch_row(res))) {
            std::cout << "  " << row[0] << " | " << row[1] << " | " << row[2]
                      << " | " << row[3] << " XP | ур. " << row[4] << " | "
                      << row[5] << std::endl;
        }
        mysql_free_result(res);
    }
}

// ---------- наказания ----------
void show_punishments(Database& db) {
    print_header("⚖️ Наказания");
    MYSQL_RES* res = db.query(
        "SELECT user_id, type, reason, created_at, expires_at"
        " FROM punishments ORDER BY created_at DESC LIMIT 20"
    );
    if (!res) return;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        std::cout << "  " << row[3] << " | user " << row[0] << " | " << row[1]
                  << " | " << row[2] << std::endl;
    }
    mysql_free_result(res);
}

void add_punishment(Database& db) {
    std::cout << "\n--- Новое наказание ---" << std::endl;
    std::string uid = read_line("ID пользователя: ");
    std::string type = read_line("Тип (warn/mute/kick/ban): ");
    std::string reason = read_line("Причина: ");
    if (uid.empty() || type.empty()) {
        std::cout << "Пустые поля." << std::endl;
        return;
    }
    db.execute(
        "INSERT INTO punishments(guild_id, user_id, moderator_id, type, reason,"
        " created_at) VALUES (0, " + uid + ", 0, '" + type + "', '" + db.escape(reason) + "',"
        " NOW())"
    );
    std::cout << "✅ Наказание добавлено." << std::endl;
}

// ---------- настройки ----------
void show_settings(Database& db) {
    print_header("⚙️ Настройки");
    MYSQL_RES* res = db.query("SELECT `key`, `value` FROM settings");
    if (!res) return;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        std::cout << "  " << row[0] << " = " << row[1] << std::endl;
    }
    mysql_free_result(res);
}

void set_setting(Database& db) {
    std::string key = read_line("Ключ: ");
    std::string val = read_line("Значение: ");
    db.execute(
        "INSERT INTO settings(`key`, `value`) VALUES ('" + key + "', '" + db.escape(val) + "')"
        " ON DUPLICATE KEY UPDATE `value` = '" + db.escape(val) + "'"
    );
    std::cout << "✅ Сохранено." << std::endl;
}

// ---------- розыгрыши ----------
void show_giveaways(Database& db) {
    print_header("🎉 Розыгрыши");
    MYSQL_RES* res = db.query(
        "SELECT prize, winners_count, ends_at, ended FROM giveaways"
        " ORDER BY ends_at DESC LIMIT 10"
    );
    if (!res) return;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        std::cout << "  " << row[0] << " | " << row[1] << " поб. | "
                  << row[2] << (std::atoi(row[3]) ? " [ЗАВЕРШЁН]" : " [активен]")
                  << std::endl;
    }
    mysql_free_result(res);
}

// ---------- FAQ ----------
void show_faq(Database& db) {
    print_header("❓ FAQ");
    MYSQL_RES* res = db.query(
        "SELECT question, answer FROM faq ORDER BY sort, id"
    );
    if (!res) return;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        std::cout << "  Q: " << row[0] << "\n  A: " << row[1] << "\n\n";
    }
    mysql_free_result(res);
}

// ---------- рассылка ----------
void broadcast(Database& db, const Config& cfg) {
    if (cfg.discord_token.empty()) {
        std::cout
            << "⚠️ DISCORD_TOKEN не задан — рассылка невозможна." << std::endl;
        return;
    }
    std::string text = read_line("Текст рассылки: ");
    if (text.empty()) return;
    std::cout << "📣 Рассылка доступна только через Discord-бота (команда !broadcast)."
              << std::endl;
}

// ---------- главное меню ----------
void main_menu(Database& db, const Config& cfg) {
    while (true) {
        clear_screen();
        print_header("🤖 Support Bot — Панель управления");
        std::vector<std::string> items = {
            "📋 Обращения (тикеты)",
            "👥 Пользователи",
            "📊 Статистика",
            "📈 Активность",
            "⚖️ Наказания",
            "🎉 Розыгрыши",
            "❓ FAQ",
            "⚙️ Настройки",
            "📣 Рассылка",
            "🚪 Выход",
        };
        print_menu(items);
        int choice = read_choice();
        if (choice == 0) break;

        switch (choice) {
            case 1: {
                while (true) {
                    clear_screen();
                    print_header("📋 Обращения");
                    std::cout << "  [1] Все тикеты\n"
                              << "  [2] Детали тикета\n"
                              << "  [3] Ответить\n"
                              << "  [4] Закрыть\n"
                              << "  [0] Назад\n";
                    int c = read_choice();
                    if (c == 0) break;
                    if (c == 1) show_tickets(db);
                    else if (c == 2) ticket_detail(db);
                    else if (c == 3) answer_ticket(db);
                    else if (c == 4) close_ticket(db);
                    if (c != 0) { read_line("\nНажмите Enter..."); }
                }
                break;
            }
            case 2: show_users(db); read_line("\nНажмите Enter..."); break;
            case 3: show_stats(db); read_line("\nНажмите Enter..."); break;
            case 4: show_activity(db); read_line("\nНажмите Enter..."); break;
            case 5: {
                while (true) {
                    clear_screen();
                    print_header("⚖️ Наказания");
                    std::cout << "  [1] История\n"
                              << "  [2] Добавить\n"
                              << "  [0] Назад\n";
                    int c = read_choice();
                    if (c == 0) break;
                    if (c == 1) show_punishments(db);
                    else if (c == 2) add_punishment(db);
                    if (c != 0) read_line("\nНажмите Enter...");
                }
                break;
            }
            case 6: show_giveaways(db); read_line("\nНажмите Enter..."); break;
            case 7: show_faq(db); read_line("\nНажмите Enter..."); break;
            case 8: {
                while (true) {
                    clear_screen();
                    print_header("⚙️ Настройки");
                    std::cout << "  [1] Просмотр\n"
                              << "  [2] Изменить\n"
                              << "  [0] Назад\n";
                    int c = read_choice();
                    if (c == 0) break;
                    if (c == 1) show_settings(db);
                    else if (c == 2) set_setting(db);
                    if (c != 0) read_line("\nНажмите Enter...");
                }
                break;
            }
            case 9: broadcast(db, cfg); read_line("\nНажмите Enter..."); break;
            case 10: return;
            default: break;
        }
    }
}

int main() {
    Config cfg = load_config();
    if (cfg.password.empty()) {
        std::cerr << "⚠️ MYSQL_PASSWORD не задан. Укажите переменные окружения:"
                  << std::endl
                  << "   MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE"
                  << std::endl;
        return 1;
    }

    std::cout << "Подключение к MySQL..." << std::endl;
    try {
        Database db(cfg);
        std::cout << "✅ Подключено к " << cfg.database << std::endl;
        main_menu(db, cfg);
    } catch (const std::exception& e) {
        std::cerr << "❌ " << e.what() << std::endl;
        return 1;
    }
    return 0;
}
