# Развёртывание Okno для пилота

Цель — поднять сервер для первых компаний за час. Решение о хостинге и персональных данных — D-022 в
[plan/DECISIONS.md](../plan/DECISIONS.md); тексты для клиентов — [privacy-notice.md](privacy-notice.md).

## 1. Сервер

- **Где:** в Казахстане — данные заявок (имя, телефон) хранятся на территории страны (D-022, проверить у юриста).
  Подойдёт VPS с 1–2 vCPU, 1–2 ГБ памяти и 20 ГБ диска; на пилоте один сервер обслуживает несколько компаний.
- **ОС:** Ubuntu 24.04 LTS или новее.
- **Домен:** запись A на IP сервера, например `okno.ваш-домен.kz`.

## 2. Установка

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
```

```bash
sudo git clone https://github.com/yk59m2cmhw-hash/u /opt/okno && cd /opt/okno
```

```bash
sudo cp .env.example .env && sudo nano .env
```

В `.env` заполните минимум: `OKNO_DOMAIN`, `OKNO_ADMIN_TOKEN` (длинная случайная строка), ключ модели
(`ANTHROPIC_API_KEY` или `GEMINI_API_KEY`; без ключа работает офлайн-режим), `TELEGRAM_BOT_TOKEN` и
`TELEGRAM_CHAT_ID` для карточек сотрудникам. Остальное — по [channels.md](channels.md) и [crm.md](crm.md).

```bash
sudo docker compose up -d --build
```

Caddy сам получит HTTPS-сертификат. Проверка: `https://ВАШ_ДОМЕН/` — демо, `https://ВАШ_ДОМЕН/admin?token=...` —
кабинет.

## 3. База знаний компании

При первом запуске создаётся `data/company.json` из демо-компании. Замените правила на правила компании в
кабинете `/admin` (раздел «База знаний») — по записям со встречи ([gtm/pilots/onboarding.md](../gtm/pilots/onboarding.md)).
Добавьте поле `privacy_notice` — короткое уведомление о данных, оно покажется клиенту в первом ответе.

## 4. Каналы

Telegram-бот и вебхук WhatsApp — по [channels.md](channels.md). Адреса вебхуков:
`https://ВАШ_ДОМЕН/webhooks/telegram` и `https://ВАШ_ДОМЕН/webhooks/whatsapp`.

## 5. Резервные копии

```bash
echo "15 3 * * * cd /opt/okno && OKNO_BACKUP_PASSPHRASE=... ./deploy/backup.sh >> backups/backup.log 2>&1" | sudo crontab -
```

Архивы содержат персональные данные: шифруются (gpg) и хранятся в той же стране.

## 6. Обновление и наблюдение

```bash
cd /opt/okno && sudo git pull && sudo docker compose up -d --build
```

- Логи: `sudo docker compose logs -f okno`.
- Доступность: бесплатный внешний монитор на `https://ВАШ_ДОМЕН/api/info` раз в 5 минут.
- Расходы на модель: смотрите в консоли провайдера; лимит расходов задайте там же.

## Что не сделано и почему

- Образ Docker не собирался в облачной сессии: там нет Docker. Код и тесты проверены без контейнера.
- Одна база знаний на сервер: для нескольких компаний на пилоте — несколько копий сервиса (разные папки и порты)
  или сервер на компанию. Мультиарендность — в бэклоге, когда компаний станет больше трёх (D-021).
