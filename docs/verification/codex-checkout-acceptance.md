# B1: приймання Codex206 в окремому Windows-акаунті

Дата: 18.11.2026. Обсяг: checkout PR206. Виконує власник після входу в окремий локальний акаунт Windows. Ця процедура ще не є доказом проходження B1.

## 1. Підготувати окреме середовище

Створіть окремого локального користувача засобами Windows, увійдіть саме в нього. Установіть для нього офіційний Python3.12, Git, Codex CLI та застосунок Codex. Увійдіть у Codex самостійно. Облікові дані нікому передавати не потрібно.

Відкрийте PowerShell у цьому акаунті:

~~~powershell
$B1Profile = [Environment]::GetFolderPath('UserProfile')
if ($B1Profile -ieq 'C:\Users\yuriy') { throw 'Це основний профіль власника. Зупиніться й увійдіть в окремий акаунт.' }
if ($env:USERPROFILE -ine $B1Profile) { throw 'USERPROFILE не збігається із системним профілем; не продовжуйте із підміною HOME.' }
$B1Profile
whoami
~~~

Якщо CODEX_HOME уже заданий, він має вказувати на теку цього тестового акаунта. За іншого шляху зупиніться й уточніть середовище; не запускайте клієнти з посиланням на конфігурацію основного автора. Не використовуйте основну .venv: її базовий інтерпретатор може лежати в профілі автора.

Створіть свіжу робочу теку та власний checkout:

~~~powershell
$B1Work = Join-Path $B1Profile ('ObscuraCodex206-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $B1Work | Out-Null
git clone --branch codex/obscura-codex-integration --single-branch https://github.com/ysilvestrov/obscura-text-writer.git (Join-Path $B1Work 'checkout')
Set-Location (Join-Path $B1Work 'checkout')
git rev-parse HEAD
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[web,mcp]"
New-Item -ItemType Directory -Path (Join-Path $B1Work 'evidence') | Out-Null
~~~

Якщо репозиторій вимагає автентифікації, виконайте її самостійно під цим акаунтом. Запишіть надруковані шлях робочої теки та SHA.

## 2. Установити user-скіли штатним CLI

~~~powershell
.\.venv\Scripts\python.exe .\scripts\install_codex_skills.py --install
Get-ChildItem (Join-Path $B1Profile '.agents\skills') -Directory -Filter 'obscura-*' | Select-Object Name,FullName
~~~

Очікується installed або unchanged і рівно п’ять потрібних тек:

- obscura-start-story;
- obscura-draft-scene;
- obscura-publish;
- obscura-series-bible;
- obscura-setup-models.

Не копіюйте їх у checkout/.agents чи CODEX_HOME/skills: B1 перевіряє саме домашню .agents/skills. За conflict або partial зупиніться, збережіть JSON; не видаляйте чужих файлів і не примушуйте установку.

## 3. Запустити нейтральну Obscura

У цій самій консолі, із теки checkout, перевірте порт і приберіть ключі лише з поточного процесного середовища:

~~~powershell
if (Get-NetTCPConnection -State Listen -LocalPort 18761 -ErrorAction SilentlyContinue) { throw 'Порт18761 зайнятий; не підключайтеся до невідомого сервера.' }
Get-ChildItem Env: | Where-Object { $_.Name -like '*_API_KEY' } | ForEach-Object { Remove-Item -LiteralPath ('Env:' + $_.Name) }
$env:PYTHON_KEYRING_BACKEND = 'keyring.backends.fail.Keyring'
.\.venv\Scripts\python.exe -m storygen.server --data-dir (Join-Path $B1Work 'data') --env-file (Join-Path $B1Work 'absent.env') --port 18761
~~~

Консоль лишається зайнятою сервером. У браузері цього акаунта відкрийте http://127.0.0.1:18761. Це нова порожня бібліотека. Не додавайте реальні твори, ключі чи модельні налаштування.

Розгорніть блок Codex і натисніть «Підключити до Codex». Збережіть шлях config.toml, результат і названу копію, якщо її створено. Це перевірка запису файла, а не живого MCP. Відкрийте нову сесію або перезапустіть Codex у тестовому акаунті. Сервер Obscura лишіть запущеним.

## 4. Зафіксувати версії й схеми обох backend

Відкрийте другу PowerShell-консоль цього акаунта; перейдіть у створений checkout, відновіть B1Work зі шляху кроку1. В обох консолях системний профіль має бути тим самим окремим акаунтом.

~~~powershell
codex --version
codex mcp get obscura --json
$B1App = Get-AppxPackage -Name OpenAI.Codex
if (-not $B1App) { throw 'Застосунок Codex не зареєстровано для цього акаунта; зафіксуйте невиконаний крок.' }
$B1AppExe = Join-Path $B1App.InstallLocation 'app\resources\codex.exe'
& $B1AppExe --version
codex app-server generate-json-schema --out (Join-Path $B1Work 'evidence\cli-schema')
& $B1AppExe app-server generate-json-schema --out (Join-Path $B1Work 'evidence\app-schema')
~~~

Якщо Codex установлено іншим способом, використайте фактичний resources/codex.exe того застосунку, а не підміну CLI-файлом. Якщо app-пакета чи RPC нижче немає, запишіть це як невиконане приймання. Не вгадуйте інший RPC і не замінюйте його модельним ходом.

JSON mcp get має вказувати на checkout цього акаунта, stdio міст і URL http://127.0.0.1:18761. Не публікуйте повний config.toml, auth.json чи дані входу. Потрібні лише назва obscura, enabled, команда, argv і версії.

## 5. Діагностичні RPC без моделі — повторити для CLI й app backend

Використано протокол, уже перевірений на CLI0.166.0 та app backend0.169.0-alpha.11.1. Для інших установлених версій спершу звірте exported schema: initialize, skills/list, thread/start(ephemeral), mcpServerStatus/list та mcpServer/tool/call. Не надсилайте turn/start.

Запустіть перший backend інтерактивно:

~~~powershell
codex app-server
~~~

Вводьте по одному наведеному JSON-рядку в його stdin; після кожного запиту дочекайтеся відповіді з відповідним id. Збережіть лише потрібні відповіді в evidence/cli-rpc.jsonl. Сповіщення між відповідями можливі. У полях cwd/cwds замініть приклад на справжній checkout окремого акаунта; у JSON Windows-шлях можна записувати зі звичайними прямими слешами.

~~~json
{"id":1,"method":"initialize","params":{"clientInfo":{"name":"obscura_b1_acceptance","version":"1"}}}
{"method":"initialized","params":{}}
{"id":2,"method":"skills/list","params":{"cwds":["C:/Users/TEST_ACCOUNT/ObscuraCodex206-ID/checkout"],"forceReload":true}}
~~~

У відповіді1 codexHome має належати цьому тестовому профілю. У відповіді2 потрібні всі п’ять obscura-* із scope=user та path під системним профілем/.agents/skills; errors має бути порожнім. У доказ не включайте вміст чи назви інших особистих скілів.

~~~json
{"id":3,"method":"thread/start","params":{"cwd":"C:/Users/TEST_ACCOUNT/ObscuraCodex206-ID/checkout","ephemeral":true,"approvalPolicy":"never","sandbox":"read-only"}}
~~~

Візьміть thread.id з відповіді3. Замініть THREAD_ID у двох наступних рядках; це не текст повідомлення моделі:

~~~json
{"id":4,"method":"mcpServerStatus/list","params":{"threadId":"THREAD_ID","serverName":"obscura","detail":"toolsAndAuthOnly"}}
{"id":5,"method":"mcpServer/tool/call","params":{"threadId":"THREAD_ID","server":"obscura","tool":"list_stories","arguments":{}}}
~~~

Очікується obscura із27 інструментами, зокрема get_guide, та успішний list_stories з порожнім списком: isError=false. get_guide є в загальному мосту, але не має згадуватися в установлених Codex-скілах. Не викликайте інші інструменти; не створюйте модельний хід.

Завершіть backend через Ctrl+C. Повторіть ті самі запити для backend застосунку:

~~~powershell
& $B1AppExe app-server
~~~

Збережіть потрібні відповіді в evidence/app-rpc.jsonl. Успіх CLI не замінює успіху другого executable.

## 6. Перевірити GUI та повернути результат

У застосунку Codex під тим самим акаунтом після нової сесії/перезапуску перевірте доступність усіх п’яти obscura-* скілів і MCP-сервера obscura. Лише відкрийте відповідні списки/налаштування; не відправляйте промпт, не запускайте codex exec чи модель.

Збережіть нейтральні знімки цих списків у evidence, приховавши адресу облікового запису й будь-які дані входу. Поверніть Codex підсумок:

~~~text
B1 checkout SHA:
Windows test profile:
Codex CLI version/path:
Codex app/backend version/path:
CLI: 5 user skills з <profile>/.agents/skills, errors=0: так/ні
App backend: те саме: так/ні
MCP catalog:27 tools, obscura, обидва backend: так/ні
list_stories: isError=false, result=[], обидва backend: так/ні
GUI: усі5skills видимі, obscura доступний: так/ні
Модельні ходи:0
Шляхи нейтральних доказів:
Невиконані кроки/помилки:
~~~

За відсутнього пункту його не зараховувати. Після перевірки закрийте Codex у тестовому акаунті й зупиніть сервер Obscura. Автоматичного видалення скілів, акаунта або робочої теки ця процедура не передбачає.

Store freeze/license (B2/B3) належать R-39 PR2 і не є частиною цього приймання.
