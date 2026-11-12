# Подключение каналов: Telegram и WhatsApp

Код: [okno/channels/](../okno/channels/). Решение о WhatsApp — D-020 в [plan/DECISIONS.md](../plan/DECISIONS.md).
Сервер должен быть доступен по HTTPS: [deploy.md](deploy.md).

## Telegram (бесплатно, быстрее всего для пилота)

1. Создайте бота у @BotFather → получите токен. Для каждой компании — свой бот с её названием.
2. Задайте переменные: `TELEGRAM_CUSTOMER_BOT_TOKEN` (бот для клиентов) и `TELEGRAM_WEBHOOK_SECRET` (любая
   длинная случайная строка).
3. Зарегистрируйте вебхук (один раз):

```bash
python3 -c "from okno.channels.telegram import TelegramClient as T; import os; print(T().set_webhook('https://ВАШ_ДОМЕН/webhooks/telegram', os.environ['TELEGRAM_WEBHOOK_SECRET']))"
```

4. Карточки заявок сотрудникам: отдельный бот или тот же; `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` чата
   сотрудников ([okno/README.md](../okno/README.md)).

Ссылку на бота компания ставит в 2GIS, Instagram и на сайт: «Напишите нам — ответим за минуту».

## WhatsApp (официальный WhatsApp Business Platform, Meta Cloud API)

Нужно: аккаунт Meta Business компании, приложение в Meta for Developers с продуктом WhatsApp, номер телефона,
подключённый к платформе.

1. В Meta for Developers: приложение → WhatsApp → добавить номер компании → получить `WHATSAPP_PHONE_NUMBER_ID`.
2. Создать постоянный токен системного пользователя с доступом к WhatsApp → `WHATSAPP_TOKEN`.
3. Секрет приложения (App Secret) → `WHATSAPP_APP_SECRET` — им проверяется подпись каждого вебхука.
4. Вебхук: URL `https://ВАШ_ДОМЕН/webhooks/whatsapp`, токен проверки — любая строка, та же в
   `WHATSAPP_VERIFY_TOKEN`; подписаться на поле `messages`.
5. Версия Graph API — `WHATSAPP_GRAPH_VERSION` (по умолчанию `v23.0`; сверить с журналом изменений Meta).

Что важно:

- **Номер.** Номер, подключённый к платформе, обычно нельзя одновременно использовать в обычном приложении
  WhatsApp Business. У Meta есть режим совместного использования (coexistence) — проверить, доступен ли он в
  Казахстане, до подключения номера компании.
- **Деньги.** С 01.10.2026 в Казахстане оплачиваются и ответы в 24-часовом окне (~$0.02 за сообщение по данным
  посредника; сверить с официальной таблицей Meta). Это заложено в тариф «WhatsApp» (D-015, D-019).
- **Мы только отвечаем.** Агент пишет клиенту лишь в ответ на его сообщение, в пределах 24 часов. Шаблоны для
  сообщений по инициативе компании (напоминания) — не в этом сценарии.
- **Неофициальные API не используем**: они нарушают правила WhatsApp, номер компании могут заблокировать.

## Что видит компания

Карточки заявок — в Telegram-чате сотрудников и в кабинете `/admin?token=...` (переменная `OKNO_ADMIN_TOKEN`):
список заявок, выгрузка в CSV, редактирование базы знаний.
