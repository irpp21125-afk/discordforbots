-- Схема MySQL для Support Bot (Discord + Telegram + C++ приложение)
-- Импорт: mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS support_bot
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE support_bot;

-- ---------- Пользователи Telegram ----------
CREATE TABLE IF NOT EXISTS tg_users (
  id BIGINT PRIMARY KEY,
  username VARCHAR(64) DEFAULT 'Не указан',
  name VARCHAR(128) DEFAULT 'Не указано',
  registration_date DATETIME,
  last_activity DATETIME,
  is_admin TINYINT(1) DEFAULT 0,
  is_moderator TINYINT(1) DEFAULT 0,
  notify TINYINT(1) DEFAULT 1,
  INDEX idx_tg_activity (last_activity),
  INDEX idx_tg_admin (is_admin)
) ENGINE=InnoDB;

-- ---------- Пользователи Discord ----------
CREATE TABLE IF NOT EXISTS dc_users (
  id BIGINT PRIMARY KEY,
  username VARCHAR(64),
  display_name VARCHAR(128),
  guild_id BIGINT,
  registration_date DATETIME,
  last_activity DATETIME,
  is_admin TINYINT(1) DEFAULT 0,
  is_moderator TINYINT(1) DEFAULT 0,
  notify TINYINT(1) DEFAULT 1,
  points INT DEFAULT 0,
  level INT DEFAULT 1,
  messages_count INT DEFAULT 0,
  voice_seconds INT DEFAULT 0,
  privilege VARCHAR(32) DEFAULT 'none',
  INDEX idx_dc_guild (guild_id),
  INDEX idx_dc_points (points DESC)
) ENGINE=InnoDB;

-- ---------- Веб-пользователи (личный кабинет) ----------
CREATE TABLE IF NOT EXISTS web_users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  name VARCHAR(128),
  telegram_id BIGINT,
  discord_id BIGINT,
  is_admin TINYINT(1) DEFAULT 0,
  created_at DATETIME
) ENGINE=InnoDB;

-- ---------- Тикеты (Обращения) ----------
CREATE TABLE IF NOT EXISTS tickets (
  id INT AUTO_INCREMENT PRIMARY KEY,
  author_type ENUM('tg','dc','web','guest') NOT NULL,
  author_ref VARCHAR(64) NOT NULL,
  email VARCHAR(255),
  email_code VARCHAR(32),
  category VARCHAR(64) DEFAULT 'Другое',
  priority ENUM('low','normal','high') DEFAULT 'normal',
  status ENUM('open','answered','closed') DEFAULT 'open',
  message TEXT NOT NULL,
  rating TINYINT,
  guild_id BIGINT,          -- Discord guild (если из DC)
  channel_id BIGINT,        -- канал тикета в Discord
  created_at DATETIME,
  updated_at DATETIME,
  INDEX idx_status (status),
  INDEX idx_author (author_type, author_ref),
  INDEX idx_guild (guild_id),
  INDEX idx_created (created_at DESC)
) ENGINE=InnoDB;

-- ---------- Ответы в тикетах ----------
CREATE TABLE IF NOT EXISTS replies (
  id INT AUTO_INCREMENT PRIMARY KEY,
  ticket_id INT NOT NULL,
  author_name VARCHAR(128),
  is_admin TINYINT(1) DEFAULT 0,
  text TEXT NOT NULL,
  created_at DATETIME,
  FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
  INDEX idx_ticket (ticket_id)
) ENGINE=InnoDB;

-- ---------- Наказания ----------
CREATE TABLE IF NOT EXISTS punishments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  moderator_id BIGINT,
  type ENUM('warn','mute','kick','ban') NOT NULL,
  reason TEXT,
  duration_minutes INT DEFAULT 0,
  active TINYINT(1) DEFAULT 1,
  created_at DATETIME,
  expires_at DATETIME,
  INDEX idx_user (guild_id, user_id),
  INDEX idx_active (active)
) ENGINE=InnoDB;

-- ---------- Наказания (отдельно для логов) ----------
CREATE TABLE IF NOT EXISTS moderation_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  moderator_id BIGINT,
  action VARCHAR(32) NOT NULL,
  reason TEXT,
  created_at DATETIME,
  INDEX idx_guild_user (guild_id, user_id),
  INDEX idx_created (created_at DESC)
) ENGINE=InnoDB;

-- ---------- Привилегии ----------
CREATE TABLE IF NOT EXISTS privileges (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(64) UNIQUE NOT NULL,
  price DECIMAL(10,2) NOT NULL,
  color VARCHAR(16) DEFAULT '#5865F2',
  icon VARCHAR(32) DEFAULT '',
  created_at DATETIME DEFAULT NOW()
) ENGINE=InnoDB;

INSERT IGNORE INTO privileges(name, price, color, icon) VALUES
  ('starvision', 99.00, '#E91E63', '⭐'),
  ('viaglobal', 199.00, '#9C27B0', '🌍'),
  ('gectoring', 499.00, '#FF9800', '🏆');

-- ---------- Магазин ----------
CREATE TABLE IF NOT EXISTS shop_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  name VARCHAR(128) NOT NULL,
  price INT NOT NULL DEFAULT 0,
  description TEXT,
  INDEX idx_guild (guild_id)
) ENGINE=InnoDB;

-- ---------- Инвентарь ----------
CREATE TABLE IF NOT EXISTS inventory (
  id INT AUTO_INCREMENT PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  item_name VARCHAR(128) NOT NULL,
  purchased_at DATETIME DEFAULT NOW(),
  INDEX idx_user (guild_id, user_id)
) ENGINE=InnoDB;

-- ---------- Фильтр слов ----------
CREATE TABLE IF NOT EXISTS filter_words (
  id INT AUTO_INCREMENT PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  word VARCHAR(128) NOT NULL,
  INDEX idx_guild (guild_id)
) ENGINE=InnoDB;

-- ---------- Наказания (отдельно для логов) ----------

-- ---------- Модерация (заявки на разбан) ----------
CREATE TABLE IF NOT EXISTS unban_requests (
  id INT AUTO_INCREMENT PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  username VARCHAR(64),
  reason TEXT,
  status ENUM('pending','approved','rejected') DEFAULT 'pending',
  created_at DATETIME,
  reviewed_by BIGINT,
  reviewed_at DATETIME,
  INDEX idx_guild_status (guild_id, status)
) ENGINE=InnoDB;

-- ---------- Роли (автовыдача по уровням) ----------
CREATE TABLE IF NOT EXISTS level_roles (
  id INT AUTO_INCREMENT PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  role_id BIGINT NOT NULL,
  level_required INT NOT NULL,
  UNIQUE KEY uq_guild_role (guild_id, role_id),
  INDEX idx_guild_level (guild_id, level_required)
) ENGINE=InnoDB;

-- ---------- Настройки гильдий ----------
CREATE TABLE IF NOT EXISTS guild_settings (
  guild_id BIGINT PRIMARY KEY,
  prefix VARCHAR(8) DEFAULT '!',
  mod_log_channel BIGINT,
  ticket_category BIGINT,
  ticket_support_role BIGINT,
  welcome_channel BIGINT,
  welcome_text VARCHAR(512),
  welcome_enabled TINYINT(1) DEFAULT 1,
  welcome_autorole BIGINT,
  levelup_channel BIGINT,
  economy_enabled TINYINT(1) DEFAULT 1,
  autorole_enabled TINYINT(1) DEFAULT 0,
  autorole_id BIGINT,
  anti_raid TINYINT(1) DEFAULT 0,
  -- логи
  log_channel BIGINT,
  log_enabled TINYINT(1) DEFAULT 0,
  -- безопасность
  filter_enabled TINYINT(1) DEFAULT 1,
  antispam_enabled TINYINT(1) DEFAULT 0,
  antispam_limit INT DEFAULT 5,
  antiflood_enabled TINYINT(1) DEFAULT 0,
  antiflood_seconds INT DEFAULT 5,
  updated_at DATETIME
) ENGINE=InnoDB;

-- ---------- Экономика (транзакции) ----------
CREATE TABLE IF NOT EXISTS economy_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  amount INT NOT NULL,
  reason VARCHAR(128),
  created_at DATETIME,
  INDEX idx_guild_user (guild_id, user_id)
) ENGINE=InnoDB;

-- ---------- Розыгрыши ----------
CREATE TABLE IF NOT EXISTS giveaways (
  id INT AUTO_INCREMENT PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  channel_id BIGINT NOT NULL,
  message_id BIGINT,
  prize VARCHAR(256) NOT NULL,
  winners_count INT DEFAULT 1,
  ends_at DATETIME NOT NULL,
  ended TINYINT(1) DEFAULT 0,
  winner_ids TEXT,
  created_at DATETIME,
  INDEX idx_active (ended, ends_at)
) ENGINE=InnoDB;

-- ---------- Оповещения (подписки на роли) ----------
CREATE TABLE IF NOT EXISTS alert_subscriptions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  channel_id BIGINT NOT NULL,
  keyword VARCHAR(128) NOT NULL,
  role_id BIGINT NOT NULL,
  UNIQUE KEY uq_alert (guild_id, channel_id, keyword, role_id)
) ENGINE=InnoDB;

-- ---------- История активности (для статистики) ----------
CREATE TABLE IF NOT EXISTS activity_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  guild_id BIGINT,
  user_id BIGINT,
  event VARCHAR(32),
  created_at DATETIME,
  INDEX idx_day (created_at)
) ENGINE=InnoDB;

-- ---------- Общие настройки ----------
CREATE TABLE IF NOT EXISTS settings (
  `key` VARCHAR(64) PRIMARY KEY,
  `value` TEXT
) ENGINE=InnoDB;

INSERT IGNORE INTO settings(`key`, `value`) VALUES
  ('site_title', 'Support Bot'),
  ('bot_username', ''),
  ('discord_guild_id', ''),
  ('welcome_text', 'Добро пожаловать! Мы отвечаем в течение 24 часов.'),
  ('ticket_categories', 'Вопрос по боту|Техническая проблема|Предложение|Другое'),
  ('maintenance_mode', '0');

-- ---------- Напоминания ----------
CREATE TABLE IF NOT EXISTS reminders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  guild_id BIGINT,
  user_id BIGINT NOT NULL,
  channel_id BIGINT,
  message TEXT,
  remind_at DATETIME NOT NULL,
  delivered TINYINT(1) DEFAULT 0,
  created_at DATETIME DEFAULT NOW(),
  INDEX idx_remind (remind_at, delivered)
) ENGINE=InnoDB;

-- ---------- Предложения ----------
CREATE TABLE IF NOT EXISTS suggestions (
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
  INDEX idx_guild_status (guild_id, status)
) ENGINE=InnoDB;

-- ---------- Статистика игр ----------
CREATE TABLE IF NOT EXISTS game_stats (
  id INT AUTO_INCREMENT PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  game VARCHAR(32) NOT NULL,
  wins INT DEFAULT 0,
  losses INT DEFAULT 0,
  draws INT DEFAULT 0,
  last_played DATETIME,
  INDEX idx_guild_user (guild_id, user_id, game)
) ENGINE=InnoDB;

-- ---------- Заблокированные слова (чёрный список) ----------
CREATE TABLE IF NOT EXISTS blacklist_words (
  id INT AUTO_INCREMENT PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  word VARCHAR(128) NOT NULL,
  created_at DATETIME DEFAULT NOW(),
  INDEX idx_guild (guild_id)
) ENGINE=InnoDB;

-- ---------- FAQ ----------
CREATE TABLE IF NOT EXISTS faq (
  id INT AUTO_INCREMENT PRIMARY KEY,
  question VARCHAR(512) NOT NULL,
  answer TEXT NOT NULL,
  sort INT DEFAULT 0
) ENGINE=InnoDB;
