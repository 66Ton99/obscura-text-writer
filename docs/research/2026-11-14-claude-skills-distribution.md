# Скіли й MCP для Claude: як розповсюджувати разом зі збіркою зі Store

Дата: 14.11.2026. Статус: дослідження. Задача: R-35 у [беклозі](../superpowers/plans/2026-10-20-remediation-backlog.md), GitHub [#173](https://github.com/ysilvestrov/obscura-text-writer/issues/173).

Документ відповідає на два питання власника:

1. Як співвідносяться скіли й MCP і як провести автора від розмитого наміру («хочу написати оповідання про друзів, але не знаю, з чого почати») до викликів `create_story`, `import_plan_and_characters`, `save_draft`.
2. Як користувач збірки з Microsoft Store підключає до Obscura не лише MCP, а й скіли в Claude Desktop і Claude Code.

Факти про Claude перевірено за офіційною документацією станом на 14.11.2026, джерела наприкінці. Те, що документація прямо не підтверджує, позначено як **не перевірено**.

## 1. Скіли й MCP: розподіл ролей

| | MCP | Скіл |
|---|---|---|
| Що це | Інструменти з типізованими параметрами | Markdown-інструкція (`SKILL.md`), за потреби з довідковими файлами |
| Відповідає на питання | «Що можна зробити?» | «Як зробити добре, у якому порядку, що спитати в автора?» |
| Контекст | Інструкції сервера й описи інструментів доступні завжди | Постійно в контексті лише `description`; повний текст завантажується, коли запит відповідає опису |
| Стан | На сервері (твори, версії, revision) | Немає; це процес і знання про жанр |

Інструкції сервера Obscura й `next_steps` уже містять правила протоколу (порядок викликів, revision, fingerprint, конфлікт 409, режими «chat» і «obscura»). Вони вчать модель не ламати API, але не вчать ремесла: розпитати автора, запропонувати задуми, не завалити питаннями, не створювати твір до погодження задуму.

Розподіл:

- **Інструкції MCP-сервера** — лише інваріанти протоколу, коротко, бо їх отримує кожен клієнт.
- **Скіли** — сценарії, що починаються з наміру автора, а не з інструмента. Перший набір:
  - `start-story`: автор хоче писати, але плану немає. Питання по одному (для кого текст, обсяг, тон, реальні деталі), 2–3 задуми на вибір, вибір шаблону через `get_templates`, показ плану й персонажів автору і лише після згоди `create_story` + `import_plan_and_characters`; перевірка `writing_mode`, наступний крок.
  - `draft-scene`: прочитати контекст і чернетку → написати → зберегти без втрати правок автора.
  - `revise`: «смішніше», «коротше», «цей персонаж не такий» — вибрати, що міняти (план, картку персонажа чи текст) і яким інструментом.
  - `publish`: обкладинка, метадані, експорт.
- **Довідкові файли скіла** — питальник інтерв’ю, приклади задумів за жанрами, правила письма про реальних людей. Модель читає їх лише за потреби.

`description` скіла пишеться мовою наміру користувача, бо саме за ним модель вирішує, чи завантажувати скіл. Наприклад: «Use when the author wants to write a story but has no plan yet, is unsure where to start, or describes an idea vaguely». Опис «Creates a story via MCP» на запит «не знаю, з чого почати» не спрацює.

Скіл може поєднувати кілька MCP-серверів, які нічого не знають один про одного. Наприклад, якщо в автора підключено ще й сервіс із даними друзів, скіл може запропонувати взяти звідти деталі для персонажів — лише з явної згоди автора.

Перевірка скілів — сценаріями: набір розмитих запитів і перевірка, що скіл завантажився, `create_story` не викликано до погодження, питання йшли по одному, план відповідає відповідям. Інструмент — `skill-creator` з evals.

## 2. Канали доставки

### 2.1. Що доходить разом із самим MCP

Працює в будь-якому клієнті без встановлення:

- інструкції сервера (`instructions`);
- **MCP prompts** — готові сценарії; Claude Desktop показує їх у меню «+»;
- інструмент-провідник (наприклад, `get_writing_guide(topic)`), що віддає текст методики на вимогу.

Плюс — версія методики збігається з версією сервера. Мінус — усе це займає контекст, тож тексти мають бути стислими.

### 2.2. Claude Code: плагін

Плагін Claude Code містить скіли, MCP-сервер (`.mcp.json` або пакет MCPB), slash-команди й хуки. Ставиться з маркетплейсу — git-репозиторію або локальної теки з `.claude-plugin/marketplace.json`:

```bash
claude plugin marketplace add owner/repo
claude plugin marketplace add ./obscura-plugin
claude plugin install obscura@obscura
```

Перевірені властивості:

- Локальну теку треба вказувати з `./`, `../` або абсолютним шляхом, інакше `name/name` читається як GitHub.
- **Локальний маркетплейс використовується з місця, без копіювання.** Зміни файлів діють з наступної сесії або після `/reload-plugins`, зміна версії не потрібна. Маркетплейси з git клонуються, а плагіни копіюються в кеш за версією.
- Автооновлення за замовчуванням вимкнене для сторонніх і локальних маркетплейсів.
- Скіли з `~/.claude/skills/<name>/SKILL.md` Claude Code підхоплює автоматично. Скіл плагіна викликається як `/<plugin>:<skill>`.
- Що станеться, якщо зареєстрована локальна тека зникне або переїде, — **не перевірено**.

### 2.3. Claude Desktop і claude.ai

- **Плагіни є** в Chat, Cowork і Claude Code. Додаються через *Customize → Plugins → Add*:
  - *Add marketplace* — git-репозиторій (`owner/repo` або URL; GitHub, публічні GitLab і Bitbucket);
  - *Upload plugin* — ZIP або `.plugin` з одним `.claude-plugin/plugin.json`.
  Локальна тека як маркетплейс підтримується лише в Claude Code. Плагін прив’язаний до акаунта.
- **Обмеження для локального MCP:** Chat ігнорує локальний MCP-сервер усередині плагіна (зокрема MCPB); Cowork запускає його лише тоді, коли сесія йде на комп’ютері користувача; Claude Code — завжди. Віддалений MCP (http із фіксованою адресою) працює скрізь. Скіли з плагіна працюють у всіх трьох.
- Плагіни доступні на платних планах (Pro, Max, Ultra, Team, Enterprise). Доступ на Free — **не перевірено**.
- **Скіли окремо:** ZIP із текою, що містить `SKILL.md`, завантажується через *Customize → Skills → + → Upload a skill*. Потрібно ввімкнути створення файлів і виконання коду. Доступно й на Free. Увімкнені скіли односторонньо синхронізуються в Claude Code, якщо користувач увійшов тим самим акаунтом (не для входу через API-ключ).
- Cowork і хмарні сесії **не читають** `~/.claude/skills` з комп’ютера; вони беруть скіли, увімкнені в акаунті.
- Встановлення в один клік чи програмного встановлення скілів і плагінів у Desktop немає — лише через інтерфейс.

### 2.4. Desktop Extensions (MCPB)

- Офіційна назва — MCP Bundles, файл `.mcpb` (ZIP). Старий `.dxt` працює. Пакувальник — `@anthropic-ai/mcpb` (`mcpb init`, `mcpb pack`).
- Встановлення: *Settings → Extensions*, перетягнути файл, переглянути, Install; або *Advanced settings → Extension Developer → Install Extension…*.
- **Скіли в `.mcpb` покласти не можна** — маніфест описує лише сервер. Навпаки працює: плагін може містити MCPB-сервер.
- Розширення, поширені поза каталогом, оновлюються вручну повторним встановленням файлу.
- Доступність на Free і Pro — **не перевірено**.

### 2.5. Обмеження MSIX

За документацією Microsoft (flexible virtualization):

- Нові файли й теки, які пакетний застосунок створює в `%USERPROFILE%\AppData`, потрапляють у приватну копію пакета. **Інші програми, зокрема Claude Code й Claude Desktop, їх не бачать.** Зміни вже наявних файлів у `AppData` йдуть у справжні файли.
- Поза `AppData` (наприклад, `%USERPROFILE%\.obscura\`, `%USERPROFILE%\.claude\skills\`) застосунок пише в справжню файлову систему.
- Вийти з віртуалізації окремих тек `AppData` можна через `virtualization:ExcludedDirectories` (Windows 11) із restricted capability `unvirtualizedResources`; Store вимагає обґрунтування такої capability.
- Шлях пакета `C:\Program Files\WindowsApps\…_<версія>_…` лише для читання й змінюється з кожним оновленням. Реєструвати його як маркетплейс чи шлях MCP-сервера не можна. Для запуску сервера варто використати app execution alias (`%LOCALAPPDATA%\Microsoft\WindowsApps\<alias>.exe`) — це знання з практики, у цьому дослідженні окремо не перевірене.
- Поведінку запису в `%USERPROFILE%` на реальній збірці зі Store треба перевірити — **не перевірено**.

### 2.6. Передумова: MCP-міст у пакеті

Зараз у пакет MSIX MCP-міст **не входить** ([packaging.md](../packaging.md), розділ «Звідки береться вміст пакета»); сторінка сайту «Чат-клієнти (MCP)» описує підключення з робочої копії (`.venv\Scripts\storygen-mcp.exe`). До кнопки «Підключити до Claude» міст треба додати в збірку й дати йому сталий шлях запуску.

## 3. Рекомендована схема

| Клієнт | MCP | Скіли |
|---|---|---|
| Claude Code | Плагін з `.mcp.json` | У тому самому плагіні |
| Desktop: Chat | `.mcpb` (*Settings → Extensions*) | Плагін із GitHub або ZIP-скіли |
| Desktop: Cowork (локально) | Плагін або `.mcpb` | Плагін |

1. **Основа — методика в самому MCP** (prompts і інструмент-провідник), щоб будь-який клієнт не губився навіть без скілів.
2. **Один плагін** (скіли + конфігурація MCP) як єдине джерело. Публічний GitHub-репозиторій — для Desktop і для тих, хто хоче оновлень окремо від Store.
3. **Кнопка в застосунку «Підключити до Claude»:**
   - копіює плагін у сталу теку поза `AppData`, наприклад `%USERPROFILE%\.obscura\claude-plugin`, і перезаписує її під час кожного оновлення застосунку — Claude Code читає теку з місця, тож версії скілів і сервера залишаються узгодженими;
   - для Claude Code виконує або показує `claude plugin marketplace add "<тека>"` і `claude plugin install obscura@obscura`;
   - для Claude Desktop готує `.mcpb` і ZIP скілів і відкриває теку з покроковою інструкцією.
4. **Сайт інструкцій** (`docs/site/{uk,en}/mcp.md`) — шляхи для Free і платних планів, Chat і Cowork.

Скіли додають якості поверх MCP: без них продукт працює, з ними працює краще.

## 4. Відкриті питання

- Чи доступні плагіни й розширення `.mcpb` на Free.
- Поведінка Claude Code, коли зареєстрована локальна тека маркетплейсу зникла.
- Запис у `%USERPROFILE%` і запуск через execution alias на реальній збірці зі Store.
- Чи публікувати плагін у публічному репозиторії (ліцензія FSL, розділ R-33) і як узгоджувати його версію зі збірками Store.
- Чи потрібен віддалений MCP для Chat (зараз поза межами: без хмарного розгортання, див. R-32).

## Джерела

- [Plugins overview](https://claude.com/docs/plugins/overview.md)
- [Plugin platform support](https://claude.com/docs/plugins/platform-support.md)
- [Cowork: plugins](https://claude.com/docs/cowork/guide/plugins.md)
- [Use plugins in Claude](https://support.claude.com/en/articles/13837440-use-plugins-in-claude)
- [Use skills in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude)
- [Getting started with local MCP servers on Claude Desktop](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)
- [Add unlisted connectors](https://claude.com/docs/connectors/custom/add-unlisted.md)
- [MCPB](https://github.com/modelcontextprotocol/mcpb)
- [Claude Code: install plugins](https://code.claude.com/docs/en/plugins/install.md)
- [Claude Code: create a marketplace](https://code.claude.com/docs/en/plugins/create-marketplace.md)
- [Claude Code: plugin loading](https://code.claude.com/docs/en/plugins/loading.md)
- [Claude Code: plugin components](https://code.claude.com/docs/en/plugins/components.md)
- [Claude Code: skills](https://code.claude.com/docs/en/skills.md)
- [MSIX flexible virtualization](https://learn.microsoft.com/en-us/windows/msix/desktop/flexible-virtualization)
