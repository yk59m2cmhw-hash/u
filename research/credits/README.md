# База стартап-кредитов

83 программы: гиперскейлеры, GPU-облака, AI-API, инструменты, бесплатные тарифы, региональные программы.
Источник правды — [`programs.csv`](programs.csv); [`programs.json`](programs.json) выгружается из него командой
`python3 tools/credits.py export-json`. Состояние на 11.11.2026.

## Как проверялись данные

- Цифры собраны 11.11.2026 через веб-поиск по официальным страницам и агрегаторам. Открыть официальные
  страницы напрямую из облачной сессии не удалось: сетевые правила окружения не пускают на `aws.amazon.com`,
  `learn.microsoft.com`, `nvidia.com`, `cloudflare.com`; `oracle.com` отвечает 403, а страница Google
  отдаётся без содержимого.
- Поэтому у каждой строки есть `confidence`:
  - `high` — цифра из официального источника, процитированного в поиске;
  - `medium` — несколько согласных источников или официальный источник с оговорками;
  - `low` — один источник, старые данные или проверить не удалось.
- Перед подачей заявки откройте `application_url` и сверьте сумму и условия. Если цифра изменилась, исправьте
  CSV, выполните `python3 tools/credits.py validate` и `export-json`.

## Поля

| Поле | Значение |
|---|---|
| `phase` | когда программа становится доступной: **P0** — сейчас, без компании; **P1** — после юрлица, сайта и почты на домене; **P2** — после MVP и первых пользователей; **P3** — после инвестора или акселератора |
| `priority` | 1 — подавать в первую очередь, 5 — по остаточному принципу |
| `max_credits_usd` | потолок «до» в долларах; `0` — сумма не денежная или неизвестна |
| `self_serve`, `requires_*`, `gpu_eligible`, `covers_ai_apis` | `yes` / `no` / `partial` / `unknown` |
| `prohibited_uses`, `prior_credits_rule`, `excluded_countries` | ограничения программы |
| `verified_on`, `source_url` | когда и по какому источнику проверено |

## Сколько можно получить по фазам

Только вычислительные кредиты (облака, GPU, AI-API), без перков SaaS — `python3 tools/credits.py summary --compute`:

| Фаза | Программ с кредитами | Провайдеров | Сумма потолков | Лучшая программа у каждого провайдера |
|---|---|---|---|---|
| P0 | 0 | 0 | — | — |
| P1 | 8 | 8 | $59,000 | $59,000 |
| P2 | 16 | 14 | $663,000 | $650,000 |
| P3 | 25 | 14 | $2,281,000 | $1,877,000 |

Потолки — это «до», а не обещание. Реалистичная оценка (моя, с учётом одобрений и того, что у части
программ `confidence: low`):

| Фаза | Реалистично | Почему меньше потолка |
|---|---|---|
| P0 | $0 кредитов, но бесплатные тарифы: Gemini API, пробные $200–300 у облаков | без юрлица программы недоступны |
| P1 | **$5–25K** | крупные цифры P1 — Modal, OVHcloud, Oracle — дискреционные или неподтверждённые; гарантированнее всего Google Start, AWS Founders и Microsoft — около $8K вместе |
| P2 | **$25–80K** | Nebius, Oracle, Together, Anthropic одобряют выборочно; Anthropic сейчас закрыт для новых заявок |
| P3 | **$300K–1M** | у каждого провайдера получите один крупный тир; Google AI ($350K) и AWS Portfolio ($100–200K) — основа |

Это согласуется с вердиктом этапа 0: сейчас около $0, после юрлица $5–25K, после инвестора или акселератора
$300K–1M+.

## Топ-25 по фазам

| # | Фаза | Программа | До | Зачем вам | Уверенность |
|---|---|---|---|---|---|
| 1 | P0 | Gemini API, бесплатный тариф | — | прототип первого агента без компании; без клиентских данных | medium |
| 2 | P0 | Пробные периоды Google Cloud ($300), AWS ($200), Oracle ($300) | $800 | научиться разворачивать vLLM и Terraform | medium |
| 3 | P0 | GroqCloud, бесплатный тариф | — | быстрые open-weight модели для прототипа | low |
| 4 | P1 | **NVIDIA Inception** | — | бесплатно; открывает партнёрские кредиты (Nebius AI Lift, AWS) | medium |
| 5 | P1 | **Google for Startups — Start** | $2,000 | вход в Google; дальше — Scale/AI | medium |
| 6 | P1 | **AWS Activate — Founders** | $1,000 | вход в AWS; дальше — Portfolio | high |
| 7 | P1 | **Microsoft for Startups (без инвестора)** | $5,000 | Azure OpenAI и GPU с ограничениями | medium |
| 8 | P1 | Modal for Startups | $25,000 | serverless GPU для инференса и дообучения | medium |
| 9 | P1 | DigitalOcean Startups — Direct | $1,000 | дешёвый хостинг; не подавать как «сервисная компания» | medium |
| 10 | P1 | RunPod — Starter | $1,000 | дешёвые GPU для экспериментов | medium |
| 11 | P1 | OVHcloud — Start | $12,000 | инфраструктура в EU | low |
| 12 | P1 | MongoDB for Startups | $20,000 | база и эмбеддинги Voyage AI | medium |
| 13 | P2 | Cloudflare for Startups — Tier 3 | $10,000 | Workers AI, сайт, R2 | medium |
| 14 | P2 | Together AI Startup Accelerator | $50,000 | API open-weight моделей и fine-tune | medium |
| 15 | P2 | Nebius AI Lift (через Inception) | $160,000 | GPU H100/H200 | low |
| 16 | P2 | ElevenLabs Startup Grants | ~33M кредитов | голосовые агенты | medium |
| 17 | P2 | Claude for Startups | $100,000 | сильная модель для агентов; сейчас набор закрыт | medium |
| 18 | P2 | Oracle for Startups | $100,000 | GPU OCI; дискреционно | low |
| 19 | P3 | **Google for Startups — AI** | $350,000 | главный приз: GPU, TPU, Gemini | high |
| 20 | P3 | **AWS Activate — Portfolio** | $200,000 | GPU и Bedrock; нужен Org ID провайдера | medium |
| 21 | P3 | Microsoft — Investor Offer | $150,000 | Azure; нужен код инвестора | medium |
| 22 | P3 | Cloudflare — Tier 1 / Tier 2 | $350,000 / $100,000 | инфраструктура на edge | medium |
| 23 | P3 | DigitalOcean Startups — Partner / AI | $100,000 | GPU Droplets | medium |
| 24 | P3 | OVHcloud — Scale | $108,000 | EU-инфраструктура | medium |
| 25 | P3 | Vercel for Startups | $30,000 | хостинг фронтенда | medium |

Полный список с фильтрами: `python3 tools/credits.py list --phase P2 --sort amount`.

## Что кредиты покрывают и что нет

- **Google Cloud.** Кредиты программы можно тратить на Gemini и open-модели Vertex AI; стартапы AI-тира
  получают ещё $10,000 на партнёрские LLM в Model Garden ([AI-программа Google](https://cloud.google.com/startup/ai)).
  Для Scale/AI нужно equity-финансирование pre-seed–Series A, компания моложе 10 лет и не более $5,000
  прошлых кредитов Google Cloud ([FAQ](https://cloud.google.com/startup/faq)).
- **AWS.** Кредиты Activate покрывают больше 200 сервисов AWS. Покрытие сторонних моделей в Bedrock нужно
  проверить в условиях конкретной заявки.
- **Microsoft.** Кредиты Azure не покрывают продукты, которые продаются отдельно; например, Claude в Azure AI
  Foundry ([разбор случая](https://www.pulse.bot/saas/news/azure-startup-credits-dont-apply-to-claude-via-azure-ai-foundry-reader-finds-after-1600-charge-de0d295f-2400-486a-a87d-cffd537b1392)).
  Кредиты Investor Offer действуют 2 года и не продлеваются ([Microsoft Learn](https://learn.microsoft.com/en-us/startups/benefits/azure-credits/azure-usage-and-billing)).
- **Cloudflare.** Workers AI ограничен потолком по тиру (по трекерам — около $2,500, $10,000 и $50,000),
  R2 — до $10,000. AI Gateway, регистрация доменов и премиальные сетевые сервисы не покрываются.
- **DigitalOcean.** Сервисные и консалтинговые компании не допускаются. Если вы начинаете как студия
  автоматизации, описывайте себя через продукт: платформа агентов для ниши.
- **NVIDIA Inception.** Не дает GPU и не дает деньги: это членство со скидками и доступом к партнёрским
  кредитам. Крипто-компании исключены; по части источников исключены облачные провайдеры и реселлеры. Ещё
  одна причина не позиционироваться как «облако» или «продавец токенов».
- **Типичные исключения, которые надо проверять в каждой программе:** планы поддержки, покупки в
  marketplace, предоплата Reserved Instances и Savings Plans, регистрация доменов, сторонние лицензии.

## Красные линии из условий

- AWS: Promotional Credit нельзя «sell, license, rent, or otherwise transfer»; кредит применяется только к
  вашему аккаунту и аннулируется, если продан за деньги или иное встречное предоставление. При нарушении
  AWS вправе потребовать возместить использованные кредиты. Кредиты аннулируются для аккаунта, созданного
  только ради кредитов ([AWS Promotional Credit](https://aws.amazon.com/awscredits/),
  [AWS Activate terms](https://aws.amazon.com/activate/terms)).
- Майнинг криптовалюты исключён у AWS ([условия кредитов](https://aws.amazon.com/awscredits/)) и у других
  провайдеров.
- Одна компания — одна заявка в каждую программу. Фиктивные компании и аккаунты ради повторных кредитов —
  нарушение условий с риском бана и возврата денег.

## Как получить квоты GPU

У новых аккаунтов квоты на GPU обычно нулевые или минимальные; кредиты не дают квоту автоматически. Это общий
порядок по документации провайдеров; названия пунктов меню проверяйте на месте.

| Облако | Где | Что просить сначала | Советы |
|---|---|---|---|
| Google Cloud | IAM & Admin → Quotas | `GPUS_ALL_REGIONS` и `NVIDIA_L4_GPUS` в одном регионе, 1–4 шт. | на пробном аккаунте GPU нет: нужен платный billing-аккаунт; начать с L4, потом A100/H100; Spot дешевле |
| AWS | Service Quotas → EC2 | «Running On-Demand G and VT instances» (vCPU) для g6/g5; потом «P instances» | квота считается в vCPU; для коротких задач на H100 — Capacity Blocks for ML |
| Azure | Quotas → Compute | семейство VM с T4, A10 или A100 в одном регионе | на спонсорских подписках часть GPU-семейств бывает закрыта; запрос через тикет поддержки |
| Oracle OCI | Limits, Quotas and Usage | шейп `VM.GPU.A10.1` | для `BM.GPU.H100.8` нужен отдельный запрос и обоснование |

В каждом запросе: что за продукт, какая модель, сколько GPU и на сколько, когда начнёте, что уже сделано.
Просите мало и растите по мере использования: так одобряют быстрее.

## Инструмент

```bash
python3 tools/credits.py validate                 # проверка схемы
python3 tools/credits.py summary --compute        # суммы по фазам, только вычисления
python3 tools/credits.py list --phase P1 --gpu    # что доступно после юрлица и годится для GPU
python3 tools/credits.py list --max-priority 2    # главное
python3 tools/test_credits.py                     # тесты
```

Результат запуска 11.11.2026: `validate` — «OK: 83 programs, schema valid»; тесты — 10 из 10 прошли.

`python3 tools/credits.py list --phase P1 --category hyperscaler,cloud,gpu-cloud,ai-api --sort amount`:

| # | Provider | Program | Phase | Up to | GPU | Self-serve | Confidence |
|---|---|---|---|---|---|---|---|
| 1 | Modal | Modal for Startups | P1 | $25,000 | yes | yes | medium |
| 2 | OVHcloud | OVHcloud Startup Program — Start | P1 | $12,000 | partial | yes | low |
| 3 | Oracle | Oracle AI SMB bundle | P1 | $12,000 | unknown | no | low |
| 4 | Microsoft | Microsoft for Startups — No-investor offer | P1 | $5,000 | partial | yes | medium |
| 5 | Google Cloud | Google for Startups Cloud Program — Start | P1 | $2,000 | yes | yes | medium |
| 6 | AWS | AWS Activate — Founders | P1 | $1,000 | yes | yes | high |
| 7 | DigitalOcean | DigitalOcean Startups (ex-Hatch) — Direct | P1 | $1,000 | partial | yes | medium |
| 8 | RunPod | RunPod startup program — Starter | P1 | $1,000 | yes | yes | medium |
| 9 | NVIDIA | NVIDIA Inception — Membership | P1 | — | partial | yes | medium |

## Источники, кроме ссылок в CSV

- [Google for Startups: AI-программа](https://cloud.google.com/startup/ai), [FAQ](https://cloud.google.com/startup/faq), [Start tier](https://cloud.google.com/startup/pre-funded?hl=en)
- [AWS: всё о кредитах Activate](https://aws.amazon.com/aws-startups/learn/everything-you-need-to-know-about-aws-activate-credits/), [гайд по заявке](https://aws.amazon.com/aws-startups/learn/applying-for-aws-activate-credits-a-step-by-step-guide/)
- [Better Stack: обзор программ 2026](https://betterstack.com/community/comparisons/best-startup-cloud-credit-programs/)
- [Perkstack: бесплатные GPU-кредиты](https://perkstack.co/blog/free-gpu-credits-startups), [Spheron: GPU-кредиты 2026](https://www.spheron.network/blog/free-gpu-cloud-credits-2026/)
- [Claude for Startups 2026](https://hub.causo.ai/guides/how-to-apply-to-claude-for-startups-2026), [AI-кредиты 2026](https://fin.ai/learn/ai-credits-for-startups)
- [NVIDIA Inception 2026](https://hub.causo.ai/guides/how-to-apply-to-nvidia-inception-2026)
