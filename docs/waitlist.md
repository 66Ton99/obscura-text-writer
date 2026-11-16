# Список очікування платної версії: розгортання

Розробницький документ для власника проєкту (WAITLIST-001 у [SPEC.MD](../SPEC.MD#waitlist-001)). Форма на сторінці сайту «Платна версія» надсилає адресу Cloudflare Worker'у `workers/waitlist/`, той перевіряє Turnstile і пише рядок у базу D1. Розгортає Worker власник у своєму акаунті Cloudflare. Автодеплою з GitHub немає.

## Що потрібно

- Акаунт Cloudflare, у якому є зона `obscurawriter.com`, і Node.js (команди нижче запускають `npx wrangler`).
- Усе вкладається в тариф Free: Workers (100 000 запитів на день), D1, Turnstile, один Cron Trigger. Якщо панель Cloudflare на будь-якому кроці просить оплату чи перехід на платний тариф, зупиніться й напишіть у PR (див. «Якщо власний домен попросить оплату»).

## Кроки власника

Усі команди — з теки `workers/waitlist`.

1. `npx wrangler login` — вхід у браузері.
2. `npx wrangler d1 create obscura-waitlist --jurisdiction=eu`. У відповіді буде `database_id`. Юрисдикцію пізніше змінити не можна, лише створити нову базу.
3. Впишіть цей `database_id` у `wrangler.toml` (замість `REPLACE_WITH_DATABASE_ID`): wrangler бере id бази звідти, і з заглушкою наступна команда падає з `Invalid uuid`. Потім `npx wrangler d1 execute obscura-waitlist --remote --file schema.sql` — таблиця `waitlist`.
4. Панель Cloudflare → Turnstile → **Add widget**: режим **Managed**, хости `obscurawriter.com` і `localhost`. Панель покаже публічний ключ (Site Key, починається з `0x`) і секрет (Secret Key).
5. `database_id` і публічний ключ — не секрети: напишіть їх у PR або закомітьте в `wrangler.toml` (`database_id`) і `docs/site/site.json` (`waitlist.sitekey`). Секрет нікуди не пишіть, крім наступного кроку.
6. `npx wrangler secret put TURNSTILE_SECRET` і вставте секрет у запит wrangler.
7. `npx wrangler deploy` з гілки PR, а не з `main`: `PRIVACY_EDITION` у `wrangler.toml` має збігатися з редакцією «Приватності», яку покаже сайт. Розгортання саме прив'язує піддомен `waitlist.obscurawriter.com` (із сертифікатом) і щоденне видалення старих записів.

Поки ключ віджета чи `database_id` у репозиторії — заглушки, workflow сайту не публікує сайт після злиття (`check_site.py --publish`), тож мертвої форми на `obscurawriter.com` не буде.

## Перевірка наживо до злиття

Процедура — [перевірка наживо](verification/manual.md#waitlist-live): тимчасовий `localhost` у Worker, локальна збірка сайту, записи й рядок у D1, потім повернення `wrangler.toml` і повторне розгортання.

## Після злиття

- Ту саму перевірку повторіть на `https://obscurawriter.com/paid.html` і `https://obscurawriter.com/en/paid.html`, видаліть тестові рядки.
- Приберіть хост `localhost` з віджета Turnstile.

## SQL

Запити — у консолі D1 (панель → D1 → `obscura-waitlist` → Console) або `npx wrangler d1 execute obscura-waitlist --remote --command "<запит>"`.

- Скільки записів від дати (поріг «50 за 90 днів»): `SELECT COUNT(*) FROM waitlist WHERE created_at >= '2026-12-01T00:00:00Z';`
- Вивантаження для листа: `SELECT email, lang FROM waitlist ORDER BY created_at;`
- Видалення на запит (адреса в нижньому регістрі): `DELETE FROM waitlist WHERE email = 'name@example.com';`
- Після листа про вихід платної версії: `DELETE FROM waitlist;`

Лист про вихід надсилає власник сам, один раз: прихованою копією зі своєї пошти або через сервіс розсилки на свій вибір, з поясненням, як відписатися.

## Якщо власний домен попросить оплату

Приберіть розділ `[[routes]]` з `wrangler.toml` і розгорніть Worker: він буде на `https://obscura-waitlist.<ваш піддомен>.workers.dev/`. Цю адресу треба вписати в `waitlist.action` маніфесту сайту, а правило `check_site.py --publish` про власний домен — змінити окремою зміною репозиторію. Напишіть про це в PR, і зміну зробить розробник.
