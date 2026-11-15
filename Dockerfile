FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Зависимости отдельно — для кэширования слоёв
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Бот должен жить вечно: watchdog перезапускает при падении
CMD ["python", "run_forever.py", "discord_bot/bot.py"]
