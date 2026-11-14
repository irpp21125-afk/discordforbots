-- Создать отдельного пользователя MySQL для бота/панели.
-- Выполнить в MySQL Workbench (вкладка Query) под account, у которого
-- есть права на создание пользователей (root или Admin).

CREATE DATABASE IF NOT EXISTS support_bot
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

-- Придумайте свой пароль вместо BotPass2026!
CREATE USER IF NOT EXISTS 'support_bot'@'localhost'
  IDENTIFIED BY 'BotPass2026!';

ALTER USER 'support_bot'@'localhost' IDENTIFIED BY 'BotPass2026!';

GRANT ALL PRIVILEGES ON support_bot.* TO 'support_bot'@'localhost';

FLUSH PRIVILEGES;

-- Проверка: должно вернуть 1 строку
SELECT user, host FROM mysql.user WHERE user = 'support_bot';
