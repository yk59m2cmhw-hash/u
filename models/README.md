# Калькулятор юнит-экономики

Код: [unit_economics.py](unit_economics.py) (только стандартная библиотека Python). Входные цифры:
[scenarios.csv](scenarios.csv) — у каждой есть источник с датой или пометка `assumption`. Чтобы пересчитать
под себя, поменяйте значения в CSV и запустите:

```bash
python3 models/unit_economics.py        # таблицы ниже
python3 models/test_unit_economics.py   # тесты
```

Запуск 12.11.2026: тесты — 13 из 13 прошли; таблицы ниже — вывод этого запуска.

## Главное

1. **Продажа токенов не сходится.** Узел 8×H100 с моделью класса gpt-oss-120b при ценах уровня Together и Groq
   приносит около $51K в месяц при 100 % загрузке и около $15K при 30 %. Сам узел стоит $64.6K в месяц на
   Google Cloud и $40.2K на AWS. Окупается на AWS только при загрузке от 79 %, на Google Cloud — никогда. При
   самых низких рыночных ценах (DeepInfra) не окупается ни на одном облаке; на маркетплейсах — только при 92 %.
2. **Агент сходится с запасом.** Разговор с клиентом стоит от $0.0016 (Gemini 2.5 Flash-Lite) до $0.034
   (Claude Sonnet 5.5); смесь «90 % Haiku 5.5 + 10 % Sonnet 5.5» — около $0.005. На клиента с 600 разговорами
   модели обходятся в ~$3 в месяц. Главные затраты — ваше время на поддержку, хостинг и сообщения. При цене
   $250 в месяц валовая маржа ~80 %, затраты на привлечение окупаются за ~2 месяца.
3. **Своя модель выгодна только при высокой загрузке или ради приватности.** 8B-модель на одном L4 при 30 %
   загрузке дороже API ($0.0035 против $0.0017 за разговор), при 80 % — чуть дешевле ($0.0013). Начинать с
   API, оплаченных кредитами; свой GPU — когда клиентов достаточно, чтобы загрузить его, или когда клиент
   требует, чтобы данные не уходили во внешний API.
4. **Кредитный обрыв не страшен этой модели.** $14K кредитов фазы P1 покрывают всю инфраструктуру первого
   года; в 12-м месяце инфраструктура — около 12 % MRR.
5. **Голос — отдельный тариф.** 300 минут в месяц добавляют ~$45 затрат и снижают маржу до ~62 % при той же
   цене.

## Допущения, которые сильнее всего меняют результат

| Допущение | Значение | Что будет, если ошибаемся |
|---|---|---|
| Пропускная способность GPU | 3,000 ток/с на H100 для MoE 120B; 800 ток/с на L4 для 8B | в 2 раза больше — продажа токенов на AWS окупается от ~40 % загрузки, но на Google Cloud всё равно нет; проверить бенчмарком vLLM |
| Новых клиентов в месяц | 5, начиная со 2-го месяца | при 2 в месяц к 12-му месяцу ~20 клиентов и MRR ~$5K |
| Цена для клиента | $250 в месяц + $500 за подключение | проверяется интервью (`gtm/`) |
| Время поддержки | 2 часа на клиента в месяц по $15 | главная статья затрат; шаблоны и самообслуживание её снижают |
| Отток | 3 % в месяц | малый бизнес часто уходит быстрее; 6 % снижает MRR 12-го месяца примерно на 15 % (оценка) |

## Результаты запуска

### (a) Selling tokens: revenue and cost per GPU-hour

| Model on H100 | Prices | GPU | GPU $/h | Revenue $/h at 100% | at 30% | Margin at 30% | Break-even load |
|---|---|---|---|---|---|---|---|
| MoE 120B (gpt-oss class) | Together/Groq level | gcp | $11.06 | $8.72 | $2.62 | -323% | never |
| MoE 120B (gpt-oss class) | Together/Groq level | aws | $6.88 | $8.72 | $2.62 | -163% | 79% |
| MoE 120B (gpt-oss class) | Together/Groq level | neocloud | $3.99 | $8.72 | $2.62 | -52% | 46% |
| MoE 120B (gpt-oss class) | Together/Groq level | marketplace | $2.14 | $8.72 | $2.62 | 18% | 25% |
| MoE 120B (gpt-oss class) | cheapest market | gcp | $11.06 | $2.33 | $0.70 | -1479% | never |
| MoE 120B (gpt-oss class) | cheapest market | aws | $6.88 | $2.33 | $0.70 | -882% | never |
| MoE 120B (gpt-oss class) | cheapest market | neocloud | $3.99 | $2.33 | $0.70 | -470% | never |
| MoE 120B (gpt-oss class) | cheapest market | marketplace | $2.14 | $2.33 | $0.70 | -206% | 92% |
| Dense 70B | median $0.48 | gcp | $11.06 | $5.32 | $1.60 | -593% | never |
| Dense 70B | median $0.48 | aws | $6.88 | $5.32 | $1.60 | -331% | never |
| Dense 70B | median $0.48 | neocloud | $3.99 | $5.32 | $1.60 | -150% | 75% |
| Dense 70B | median $0.48 | marketplace | $2.14 | $5.32 | $1.60 | -34% | 40% |

One 8xH100 node with a gpt-oss-class model at Together-level prices: $50,943 per month at 100% load, $15,283 at 30%; the node costs $64,590 on Google Cloud and $40,179 on AWS per month.

### (b) Selling an agent: cost of one conversation

| Option | $ per conversation | $ per 1,000 conversations |
|---|---|---|
| Gemini 2.5 Flash-Lite | $0.0016 | $1.58 |
| Claude Haiku 5.5 | $0.0017 | $1.70 |
| Gemini 3.5 Flash-Lite | $0.0063 | $6.31 |
| Claude Sonnet 5.5 | $0.0341 | $34.08 |
| Routed: 90% Haiku 5.5 + 10% Sonnet 5.5 | $0.0049 | $4.94 |
| Self-hosted 8B on one L4 (GCP), 30% load | $0.0035 | $3.54 |
| Self-hosted 8B on one L4 (GCP), 80% load | $0.0013 | $1.33 |

#### One client per month (routed model mix)

| Item | $ per month |
|---|---|
| price | $250.00 |
| llm | $2.96 |
| messaging | $8.00 |
| voice | $0.00 |
| hosting | $10.00 |
| support | $30.00 |
| cost | $50.96 |
| gross profit | $199.04 |
| gross margin | 80% |
| payback of CAC $400 | 2.0 months |

With 300 voice minutes a month at $0.15/min the cost rises to $95.96 and the margin falls to 62% at the same price: voice needs a higher tier.

### (c) 12-month plan and the credit cliff

| Month | Clients | MRR | Revenue | Infra cost | Paid by credits | Paid in cash |
|---|---|---|---|---|---|---|
| 1 | 0.0 | $0 | $0 | $770 | $770 | $0 |
| 2 | 5.0 | $1,250 | $3,750 | $835 | $835 | $0 |
| 3 | 9.8 | $2,462 | $4,962 | $898 | $898 | $0 |
| 4 | 14.6 | $3,639 | $6,139 | $959 | $959 | $0 |
| 5 | 19.1 | $4,779 | $7,279 | $1,018 | $1,018 | $0 |
| 6 | 23.5 | $5,886 | $8,386 | $1,076 | $1,076 | $0 |
| 7 | 27.8 | $6,959 | $9,459 | $1,131 | $1,131 | $0 |
| 8 | 32.0 | $8,001 | $10,501 | $1,185 | $1,185 | $0 |
| 9 | 36.0 | $9,011 | $11,511 | $1,238 | $1,238 | $0 |
| 10 | 40.0 | $9,990 | $12,490 | $1,289 | $1,289 | $0 |
| 11 | 43.8 | $10,941 | $13,441 | $1,338 | $1,338 | $0 |
| 12 | 47.4 | $11,862 | $14,362 | $1,386 | $1,386 | $0 |

Credits $14,000, valid 12 months: they cover infrastructure for the whole plan. Revenue over 12 months: $102,281. Month 12: MRR $11,862, infra $1,386 (12% of MRR).
The cliff is survivable: infrastructure is a small share of revenue.

