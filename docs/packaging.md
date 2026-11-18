# Збирання пакета для Microsoft Store

Документ для того, хто збирає пакет. Користувачам застосунку він не потрібен. Вимоги — у [SPEC.MD](../SPEC.MD), `PACKAGING-001`.

## Що потрібно

- Windows 10 версії 2004 або новіша, x64.
- Робоча копія репозиторію (git) з віртуальним середовищем і залежностями: `pip install -e ".[web,publication,local-tokens,desktop,mcp,build]"`.
- `makeappx.exe`. Він є в Windows SDK і в меншому пакеті `Microsoft.Windows.SDK.BuildTools` з nuget.org (тека `bin\<версія>\x64`). Шлях передається аргументом `--makeappx` або змінною середовища `MAKEAPPX`. Для збирання без пакета (`--skip-msix`) він не потрібен.

Скрипт нічого не завантажує й не встановлює.

## Команда

```powershell
./.venv/Scripts/python.exe scripts/build_store.py `
  --out C:\tmp\obscura-build `
  --report-url https://obscurawriter.com/report.html `
  --support-url https://<адреса подяки> `
  --waitlist-url https://obscurawriter.com/paid.html `
  --identity-name <Name з Partner Center> `
  --publisher "<Publisher з Partner Center>" `
  --publisher-display-name "<назва видавця>" `
  --display-name "<назва, зарезервована в Partner Center>" `
  --makeappx <шлях до makeappx.exe>
```

- `--out` — порожня або відсутня тека. Скрипт пише лише в неї; Python і PyInstaller можуть користуватися системною тимчасовою текою.
- `--report-url` обов’язковий для видання `store`: це сторінка сайту [Поскаржитися на результат](https://obscurawriter.com/report.html) з адресою report@obscurawriter.com (для англійського інтерфейсу є `…/en/report.html`, але в збірку передається одна адреса). Політика приватності для сторінки в Partner Center — https://obscurawriter.com/privacy.html.
- `--waitlist-url` — сторінка сайту [Платна версія](https://obscurawriter.com/paid.html) з формою списку очікування (для англійського інтерфейсу є `…/en/paid.html`, але в збірку передається одна адреса). Її відкривають посилання «Повідомте про платну версію» і підказка в чаті про межу видання. Як розгорнути форму — [docs/waitlist.md](waitlist.md). Інші адреси можна не задавати.
- Ідентичність пакета (`--identity-name`, `--publisher`, `--publisher-display-name`, `--display-name`) дає Partner Center після резервування назви застосунку. Для пробного збирання підійдуть будь-які значення.
- `--skip-msix` зупиняється після самоперевірки й не потребує ні ідентичності, ні `makeappx`.
- `--allow-vendor-runtime` — див. розділ про інтерпретатор.

У теці результату з’являються: `Obscura\` (заморожений застосунок), `self-check.json`, `pyinstaller.log`, `work\` (проміжні файли PyInstaller), а без `--skip-msix` ще `msix-layout\`, `makeappx.log` і `Obscura-<версія>.msix`.

Успішне збирання лишає `BUILD-OK.json` з підсумком (версія, розмір, перелік компонентів у ліцензійних повідомленнях). Якщо скрипт відмовив, у теці лежить `BUILD-FAILED.txt` з причиною: теку `Obscura\` з такого збирання публікувати не можна, хоч вона й виглядає повною.

## Звідки береться вміст пакета

Пакет збирається саме з тієї робочої копії, з якої запущено скрипт, а не з копії `storygen`, встановленої в середовищі:

- код заморожується з `src` робочої копії; скрипт відмовляє, якщо в середовищі збирання пакет береться з іншого місця;
- для всіх файлів даних пакета, які відстежує git, скрипт записує в збірку контрольні суми (`build_manifest.json`), а зібраний застосунок звіряє з ними кожен файл;
- невідстежуваний файл у теці пакета або метадані встановленої копії зупиняють збирання;
- версію застосунок бере з того самого маніфесту, і скрипт звіряє її з `pyproject.toml`.

Поруч з `Obscura.exe` пакет містить консольний міст MCP `obscura-mcp.exe` з власною текою `_mcp` і псевдонімом виконання `obscura-mcp.exe` (STORE-MCP-001): чат-клієнту досить вказати команду `obscura-mcp.exe`. Збирання зупиняється, якщо міст не відповідає на `--help` або `--self-check`. У пакет не входять тести й інструменти розробки.

## Що перевіряє збирання

Після заморожування скрипт запускає `Obscura.exe --self-check` і вважає збірку придатною лише за повним зеленим звітом із сімома перевірками:

| Перевірка | Що доводить |
|---|---|
| `tls_context` | застосунок може створити захищений контекст з’єднання, без якого не працює жоден хмарний провайдер (мережевого запиту немає) |
| `edition_marker` | позначка видання читається; скрипт окремо звіряє, що видання саме те, яке збирали |
| `package_data` | кожен файл даних пакета на місці й збігається з робочою копією |
| `key_store` | доступне сховище облікових даних Windows (нічого не читає й не пише) |
| `tray` | Windows API значка доступний, значок із PNG створюється й знищується (у трей не додається) |
| `database` | у тимчасовій теці створюється база чинної схеми |
| `licenses` | поруч із виконуваним файлом є `THIRD-PARTY-NOTICES.txt` |

## Інтерпретатор Python

Скрипт працює на будь-якому CPython 3.12. Якщо стандартна бібліотека інтерпретатора потребує додаткових файлів, яких PyInstaller не бере (так поводиться Python із комплекту Codex: його `ssl.py` читає `codex-rejected-cas.pem`), скрипт попереджає про це, кладе їх у збірку, а перевірка `tls_context` підтверджує результат.

Пакет MSIX на такому інтерпретаторі збирається лише з `--allow-vendor-runtime`: пакет для публікації слід збирати на офіційному CPython з python.org, бо умови розповсюдження доданого файла не з’ясовано.

Для збирання тримайте постійне середовище `.venv-store` у корені робочої копії на офіційному CPython 3.12 з python.org, не чіпаючи робоче `.venv`:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv-store
.venv-store\Scripts\python.exe -c "import sys; print(sys.base_prefix)"
.venv-store\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv-store\Scripts\python.exe -m pip install -e ".[web,publication,local-tokens,desktop,mcp,build]"
.venv-store\Scripts\python.exe scripts/build_store.py --out C:\tmp\obscura-build ...
```

Друга команда має показати теку python.org (`...\Programs\Python\Python312`), а не Python із комплекту іншого застосунку. Extra `build` закріплює перевірені версії PyInstaller (див. «Ліцензії компонентів»). На машині з увімкненим Smart App Control локальна самоперевірка свіжої збірки відмовить; тоді збирайте в CI (розділ нижче).

Так перевірено 11.11.2026 на CPython 3.12.10: попереджень про інтерпретатор немає, додаткові файли не потрібні, пакет збирається без `--allow-vendor-runtime`.

## Значки пакета

`store_build/msix/Assets` містить `StoreLogo.png` (50 px), `Square44x44Logo.png` (44 px) і `Square150x150Logo.png` (150 px), намальовані з емблеми вебінтерфейсу `src/storygen/web/static/favicon.svg`. Після зміни емблеми їх перемальовує:

```powershell
./.venv/Scripts/python.exe -m playwright install chromium
./.venv/Scripts/python.exe scripts/make_store_assets.py
```

## Збирання в CI

Робочий процес `.github/workflows/store-build.yml` збирає пакет на чистому образі `windows-latest` з офіційним CPython 3.12 тими самими командами, що й вище. Він запускається для кожного PR у `main`, що зачіпає збирання, і вручну з вкладки Actions. Якщо в образі є `makeappx`, збирається непідписаний `.msix` з тестовою ідентичністю `Obscura.CI` — лише щоб перевірити склад пакета; інакше збирання йде з `--skip-msix` і попередженням. Звіти, журнали, повідомлення, `.msix` і тека `Obscura` лишаються артефактами запуску на 7 днів. Секретів, підпису й публікації в CI немає.

Це потрібно, бо на машині з увімкненим Smart App Control свіжозібраний непідписаний `obscura-mcp.exe` чи `Obscura.exe` не запускається, і самоперевірка локального збирання відмовляє з цієї причини, а не через код.

## Ліцензії компонентів

`THIRD-PARTY-NOTICES.txt` складається за фактичним вмістом збірки: скрипт читає записи PyInstaller про всі зібрані файли й бере ліцензійні тексти дистрибутивів, яким вони належать, а також ліцензію самого інтерпретатора й PyInstaller. Компонент без тексту ліцензії зупиняє збирання.

Wheel `tokenizers` не має ліцензійного файла, тому його текст разом із ліцензіями 121 бібліотеки Rust, вкомпільованої в нього, лежить у `store_build/licenses/tokenizers-<версія>.txt`. Після оновлення `tokenizers` збирання зупиниться («Немає тексту ліцензії для: tokenizers <версія>»), доки файл не перегенерувати:

```powershell
./.venv/Scripts/python.exe -I scripts/tokenizers_notices.py --out store_build/licenses/tokenizers-<версія>.txt
```

Скрипт бере перелік crate зі SBOM встановленого wheel, завантажує архіви з static.crates.io (звіряючи SHA-256 зі SBOM) і текст Apache-2.0 з GitHub. Crate без ліцензійних файлів зупиняє скрипт, доки його не додано в таблицю `MANUAL` із текстом і причиною; старий файл видаліть.

Значок у треї — власний код на Windows API (`storygen/win_tray.py`), сторонньої бібліотеки трея в збірці немає. Якщо в збірку потрапить бібліотека з ліцензією родини GPL (GPL, LGPL, AGPL), збирання зупиняється з її назвою (`copyleft_distributions`), і рішення ухвалює власник. Винятки — лише PyInstaller і `pyinstaller-hooks-contrib` (`COPYLEFT_EXCEPTIONS`): загрузчик PyInstaller має Bootloader Exception, а runtime hooks, що потрапляють у збірку, — під Apache-2.0. Виняток діє, лише поки заявлена ліцензія точно збігається з записаною; тому extra `build` закріплює перевірені версії, а оновлення PyInstaller потребує звірки таблиці.

## Перевірка встановлення

Пакет зі Store підписує Microsoft. Щоб встановити власноруч зібраний пакет, його треба підписати сертифікатом, якому довіряє система, а якщо ввімкнено Smart App Control — перевіряти через приватний тестовий випуск у Partner Center; процедура — у [ручних перевірках](verification/manual.md#store-package-install). Це зміна системних налаштувань безпеки, тому її виконує власник машини. На момент написання її не виконано.

## Чого тут немає

Подання в Store, підпис і публікація з CI. Перед першим поданням варто звірити з Partner Center правила щодо версії пакета й набору значків.
