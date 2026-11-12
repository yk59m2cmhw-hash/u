# Рынок и конкуренты

Состояние на 12.11.2026. Таблица со ссылками: [competitors.csv](competitors.csv). Цены — из открытых
источников (многие — блоги вендоров и агрегаторы, уверенность указана в CSV); перед решениями проверяйте
у самих компаний.

## Коротко

| Слой | Чем платят | Цена | Вывод для вас |
|---|---|---|---|
| Инференс open-weight моделей | за токены | $0.04–0.90 за 1M; медиана ≈ $0.48 | товар без отличий: цены задают DeepInfra, Groq, Together с огромными объёмами |
| Горизонтальные платформы агентов | подписка + usage | $20–150 в месяц | малый бизнес должен собрать агента сам; большинство не будет |
| Вертикальные AI-администраторы | подписка за точку | $29–1,500 в месяц | спрос доказан, но рынок США переполнен и ориентирован на телефон и английский |
| Студии AI-автоматизации | настройка + абонплата | $1,500–8,000 + $500–4,000 в месяц | высокие чеки, но это услуги и ручной труд |

**Пустое место между слоями:** «сделано за вас» за $150–500 в месяц, для одной ниши, на местном языке и в
мессенджерах, с запуском за день. Дешевле студий, проще платформ, локальнее американских вертикальных
продуктов.

## 1. Инференс: токены

- Один и тот же gpt-oss-120b стоит от $0.037 / $0.17 (DeepInfra) до $0.15 / $0.60 (Groq, Together, Fireworks)
  за 1M входных и выходных токенов. DeepSeek V3.2 — $0.28 / $0.42; DeepSeek V4 Flash — $0.14 / $0.28.
- Медианная смешанная цена open-weight моделей — около $0.48 за 1M, примерно на 82 % ниже медианы закрытых.
- Закрытые дешёвые модели стоят столько же: Gemini 2.5 Flash-Lite — $0.10 / $0.40, Claude Haiku 5.5 —
  $0.10 / $0.50. Для агентов малого бизнеса своя модель не даёт выигрыша в цене, пока нет масштаба
  (расчёт — в [models/README.md](../models/README.md)).
- Вывод: продажа токенов — гонка цен с компаниями, у которых в тысячи раз больше объёма и свои GPU. Не
  входить.

## 2. Горизонтальные платформы агентов

Lindy ($20–50), Relevance AI (от $29 + usage), Voiceflow ($60–150 за место), Botpress (от $89), n8n (€20 или
бесплатно у себя). Это инструменты для тех, кто готов собирать сам. Владелец клиники или автосервиса собирать
не будет: ему нужен результат. Платформы — не конкуренты, а возможные инструменты для вас (n8n у себя) и
источник клиентов, которые «попробовали и не осилили».

## 3. Вертикальные AI-администраторы

- Общие AI-телефонные администраторы: $25–300 в месяц (Trillet $49 за 150 минут, Dialzara $29, Aibrify $149
  за 400 минут, Synthflow $450 без лимита).
- Стоматологические, с записью в расписание клиники: $299–1,500 в месяц за точку (Dentina $299–399).
- Почти все ориентированы на США, английский язык и телефон. В странах, где клиенты пишут в WhatsApp и
  Telegram и говорят не по-английски, предложение гораздо слабее (оценка по выдаче поиска; проверить
  интервью).

## 4. Студии AI-автоматизации

Типичный чек для малого бизнеса: настройка $1,500–8,000 и $500–4,000 в месяц. Примеры: автоответ на
пропущенный звонок — $1,500–3,000 + $497–997 в месяц; запись на приём — $1,500–3,500 + $400–800; голосовой
агент — $3,000–8,000 + $1,000–3,000. Это подтверждает, что бизнес платит за результат, но модель плохо
масштабируется: каждый клиент — ручная работа.

## Сигналы спроса

- Стоматологии пропускают 20–38 % входящих звонков (оценки вендоров; первичных исследований мало).
- Home services пропускают 14 % звонков (бенчмарк CallRail, январь 2025).
- По данным Invoca за 2026 год только 56 % звонков в компании доходят до человека, а 45 % телефонных лидов в
  home services конвертируются прямо на звонке.
- Intercom Fin берёт $0.99 за решённое обращение — рынок уже привык платить за результат, а не за токены.

## Где место для команды из двух человек

1. **Одна ниша, «сделано за вас», $150–500 в месяц.** Между DIY-платформами и студиями.
2. **Мессенджеры раньше телефона.** WhatsApp и Telegram дешевле в разработке и дешевле на звонок, чем голос;
   голос — второй шаг.
3. **Местный язык и местные интеграции.** Американские вертикальные продукты здесь слабы.
4. **Приватность как аргумент.** В медицине и юриспруденции «данные не уходят в американский API» — довод
   за свои open-source модели (то, с чего вы начинали).
5. **Оплата за результат.** Запись, квалифицированный лид, решённое обращение — понятно владельцу бизнеса.

## Чего избегать

- Конкуренции по цене токенов.
- Горизонтальной платформы «для всех».
- Рынка США в стоматологии на старте: переполнен, HIPAA, разница во времени.

## Источники

- [Infrabase: самые дешёвые провайдеры](https://infrabase.ai/blog/cheapest-inference-providers), [DigitalOcean: сравнение стоимости инференса](https://www.digitalocean.com/community/tutorials/llm-inference-cost-comparison), [CostBench 2026](https://costbench.com/stats/llm-api-pricing-benchmarks-2026/), [BenchLM](https://benchlm.ai/stats/llm-pricing), [Tokencost](https://tokencost.app/blog/llm-api-pricing-spectrum-april-2026)
- [Gemini 3.5 Flash-Lite](https://anotherwrapper.com/tools/llm-pricing/gemini-3.5-flash-lite); цены Claude — справочник Claude API (кэш 2026-11-03)
- [Lindy-альтернативы](https://tinycommand.com/ai-agents/lindy-ai-alternatives), [Relevance AI](https://wf.lindy.ai/blog/relevance-ai-pricing), [Botpress](https://www.lindy.ai/blog/botpress-pricing), [разбор цен платформ](https://dev.to/diego_falciola_02ab709202/i-researched-ai-agent-pricing-so-you-dont-have-to-heres-what-every-platform-actually-charges-in-3gj4), [no-code агенты 2026](https://www.nocode.mba/articles/best-ai-agent-builders-2026)
- [JustCall: AI-администраторы для стоматологий](https://justcall.io/blog/best-ai-receptionists-dental.html), [Trillet](https://www.trillet.ai/blogs/best-ai-phone-system-for-dental-office), [Dentina](https://www.cloudtalk.io/blog/dentina-ai-pricing/), [Aibrify](https://aibrify.com/en/blog/clinic-missed-calls-after-hours), [Dentalbase](https://www.dentalbase.ai/blogs/ai-dental-receptionist-cost-2026-pricing-breakdown)
- [Vapi vs Retell](https://dupple.com/learn/vapi-vs-retell-ai), [Retell 2026](https://ainora.lt/blog/retell-ai-pricing-2026)
- [Intercom Fin](https://www.featurebase.app/blog/fin-ai-pricing), [Fini](https://www.usefini.com/compare/intercom-fin-vs-fini)
- [Ciela: цены студий](https://ciela.ai/blogs/ai-agency-pricing-guide-retainers-projects)
- [Пропущенные звонки: статистика](https://getaira.io/blog/missed-business-calls-statistics), [StealthAgents: home services](https://stealthagents.com/research/home-services-missed-call-revenue-statistics-2026), [Dentalbase: 38 % звонков](https://www.dentalbase.ai/blogs/38-percent-calls-go-unanswered-lost-revenue)
