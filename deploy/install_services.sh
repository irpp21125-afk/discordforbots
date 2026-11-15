#!/usr/bin/env bash
# Установка systemd-сервисов для 24/7 работы (Ubuntu/Debian VPS).
#
#   sudo bash deploy/install_services.sh
#
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/supportbot}
APP_USER=${APP_USER:-supportbot}

echo "== Проверка прав =="
if [ "$EUID" -ne 0 ]; then
    echo "Запустите через sudo"
    exit 1
fi

echo "== Создание пользователя и каталога =="
id -u "$APP_USER" &>/dev/null || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR"

if [ ! -d "$APP_DIR/venv" ]; then
    echo "== Python-окружение =="
    apt-get update -y
    apt-get install -y python3-venv python3-pip
    python3 -m venv "$APP_DIR/venv"
fi

"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r requirements.txt

chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "== Установка сервисов =="
for unit in supportbot supportbot-notify supportbot-api; do
    sed -e "s|/opt/supportbot|$APP_DIR|g" \
        -e "s|User=supportbot|User=$APP_USER|" \
        -e "s|Group=supportbot|Group=$APP_USER|" \
        "deploy/$unit.service" > "/etc/systemd/system/$unit.service"
    systemctl enable --now "$unit"
    echo "  включён: $unit"
done

systemctl daemon-reload
echo
echo "Готово. Проверка:"
echo "  systemctl status supportbot"
echo "  journalctl -u supportbot -f"
