# Этап 1 из 5 — Деньги: кредиты, акселераторы, юрисдикции, гранты

Старт: ср 11.11.2026, сразу после этапа 0 (около 20:50 UTC). Проект: AI-стартап на облачных кредитах,
репозиторий `github.com/yk59m2cmhw-hash/u`, ветка `main`.

Это запланированный запуск: основатели не следят в реальном времени. Не задавай вопросов — принимай разумные
решения сам, а решения и допущения записывай в репозиторий.

## Подготовка

1. Если `/home/user/u` нет или это не git-репозиторий: подключи репозиторий (`add_repo`: owner `yk59m2cmhw-hash`,
   repo `u`, access `push`) и клонируй: `git clone --depth 1 https://github.com/yk59m2cmhw-hash/u /home/user/u`.
   Затем `git -C /home/user/u pull`.
2. Прочитай `AGENTS.md` и `STATUS.md`. Если у прошлых этапов есть незакрытые пункты — сначала закрой их.
3. Правила: коммит и push после КАЖДОГО пункта; личных данных основателей в репозитории нет; каждая цифра — со
   ссылкой и датой проверки; оценки помечены; никаких советов по обходу правил программ, KYC или санкций.

## Цель этапа

Полная и проверенная карта бесплатных ресурсов — кредитов, акселераторов, грантов — с приоритетами и
календарём заявок на 8 недель.

## Пункты

1.1 **База кредитов** → `research/credits/programs.csv` и тот же набор в `research/credits/programs.json`.
    80–120 программ:
    - гиперскейлеры: Google Cloud, AWS, Microsoft Azure, Oracle OCI, IBM, Alibaba, Tencent, Huawei;
    - GPU-облака: Nebius, Lambda, CoreWeave, Crusoe, RunPod, Vast.ai, Modal, Together AI, Fireworks, Baseten,
      Replicate, DigitalOcean, Vultr, Akamai/Linode, OVHcloud, Scaleway и другие;
    - Cloudflare; AI-API: Anthropic, OpenAI, Google Gemini, Mistral, Cohere, ElevenLabs, Deepgram, AssemblyAI и другие;
    - инструменты и SaaS-перки: MongoDB, Supabase, Vercel, Datadog, Sentry, PostHog, Notion, HubSpot, Stripe Atlas и другие.

    Поля: `id, provider, program, category, tier, max_credits_usd, validity_months, self_serve, requires_entity,
    requires_funding, requires_partner_code, company_age_limit, gpu_eligible, covers_ai_apis, prohibited_uses,
    prior_credits_rule, excluded_countries, application_url, source_url, verified_on, confidence, phase,
    priority, notes`. `confidence` — high, medium или low. `phase` — P0 сейчас, P1 после юрлица, P2 после MVP,
    P3 после инвестора или акселератора. `priority` — от 1 до 5. Главные 25 программ проверь на официальных
    страницах (WebFetch); остальным честно поставь confidence.

1.2 **`research/credits/README.md`**: как читать базу; топ-25 по фазам; реалистичная сумма кредитов по фазам;
    что кредиты покрывают и не покрывают (GPU, Gemini на Vertex AI, Bedrock, сторонние модели, поддержка,
    marketplace) — с цитатами и ссылками; запреты (перепродажа, майнинг, аккаунты ради кредитов); как получить
    квоты GPU у каждого гиперскейлера.

1.3 **Акселераторы** → `research/accelerators.csv` и `research/accelerators.md`: Google for Startups
    Accelerator (AI-треки), AWS Generative AI Accelerator, Microsoft, NVIDIA Inception, Y Combinator, Antler,
    Techstars, Entrepreneur First, Plug and Play, Alchemist, региональные. Что дают (кредиты, деньги, доля),
    ближайшие наборы на 6 месяцев, требования, реальные шансы для команды «только идея», ссылка.

1.4 **Юрисдикции** → `research/jurisdictions.md`: Индия, Казахстан, Узбекистан, Грузия, Армения, ОАЭ, Эстония
    (e-Residency), Великобритания, США (Delaware), Россия. Для каждой: доступны ли программы Google, AWS,
    Microsoft и Oracle; стоимость и срок регистрации; требования к директорам-резидентам; налоги в двух строках;
    локальные гранты, субсидированные GPU и местные облака со стартап-программами. Только законные пути. Явное
    предупреждение: компания регистрируется там, где основатели законно являются гражданами или резидентами
    или имеют реальное присутствие; скрывать местонахождение и обходить санкции нельзя. Пометка: это ориентир,
    а не юридическая консультация.

1.5 **Гранты без доли** → `research/grants.md`: государственные и частные гранты на AI и технологии по тем же
    странам плюс международные; суммы, сроки, требования, ссылки.

1.6 **Календарь заявок на 8 недель** → `research/credits/calendar.md`: неделя за неделей — что подавать, что
    должно быть готово (юрлицо, сайт, MVP, дек), ожидаемая сумма, ссылки на действия Мандалы (2.x, 3.x).

1.7 **Скрипт** `tools/credits.py` (только stdlib): фильтры по фазе, GPU, self-serve, сумме; суммы по фазам;
    вывод Markdown-таблицы. Тест `tools/test_credits.py`. Запусти оба и вставь вывод в
    `research/credits/README.md`.

Бонус, если остаётся лимит: чек-листы требований для топ-10 программ (`research/credits/checklists/`);
обнови цифры в `00-verdict/VERDICT.md`, если они изменились, с пометкой «обновлено на этапе 1»; в
`mandala/mandala.json` поставь `ready` для 2.1 и 2.7 и пересобери `python3 mandala/build.py`.

## Завершение

- Обнови `STATUS.md` (что сделано, что не успел и почему, что запускал и с каким результатом) и строку этапа
  в `README.md`, push.
- Последнее сообщение — короткий отчёт по-русски: что сделано (ссылки на файлы), три главных вывода, что
  основателям решить до следующего этапа.
- Если лимит на исходе — сначала закоммить и запушь то, что есть, и запиши в `STATUS.md`, на каком пункте
  остановился.
