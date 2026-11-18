# Стан перевірки проєкту

**ПЕРЕВІРКА ПРОЙШЛА** — свідчення конкретного запуску, не поточного довільного стану.

- Початок (UTC): 2026-11-18T14:59:11.864192+00:00
- Завершення (UTC): 2026-11-18T14:59:12.801142+00:00
- Базовий commit: `027434b3406d1d5390ee67550e929015cc17a7dc`
- Незакомічені зміни під час перевірки: `true`
- SHA-256 вихідного знімка: `e273efeceea653562bfd732fe8079170b754a87ee937f6eb9ec0b6e948e7a976`
- Зміна знімка під час прогону: `false`
- Exit code: `0`
- Фактичні testcase результати JUnit: passed: 4 · failed: 0 · errors: 0 · skipped: 0
- Тривалість: 0.94 с

Точний argv (JSON, не shell-команда):

```json
["C:\\Projects\\text-generator\\.venv\\Scripts\\python.exe", "-m", "pytest", "docs/verification/b1-kit/test_driver.py", "-q", "--basetemp=C:/tmp/obscura-b1-helper-verify", "--junitxml=C:\\tmp\\obscura-codex-design\\artifacts\\verification-zjcdghg9\\junit.xml", "--basetemp=C:\\tmp\\obscura-codex-design\\artifacts\\verification-zjcdghg9\\test-tmp"]
```

Результат стосується лише наведеної команди й вихідного знімка. Якщо в argv зазначено окремі файли або фільтри, це часткова перевірка. Збір (collection) не є виконанням; skipped не зараховано до passed. Відсутній або непридатний XML позначається непідтвердженим. Після зміни вихідних файлів звіт історичний. Власний STATUS і artifacts виключено зі знімка; початкова ревізія може мати dirty=true, оскільки звіт створюється до коміту.

Цей прогін не є доказом літературної якості, реальної поведінки моделей або виконання ручних процедур. Коди виходу та лічильники не замінюють аналізу тестів.

Архітектура: [SPEC.MD](../SPEC.MD). Способи перевірки: [інструкція та матриця](verification/README.md). Мотиви рішень: [ADR](adr/README.md). Подальша робота: [беклог](superpowers/plans/2026-10-20-remediation-backlog.md).


## Повний прогін продуктового коду перед допоміжною процедурою B1

18.11.2026, commit027434b3406d1d5390ee67550e929015cc17a7dc: verify.py без фільтра виконав 3744passed,0failed/errors,2OSsymlinkskip. source_changed_during_run=false, dirty=false. Початок13:40:18UTC, завершення13:55:33UTC, exit0, SHA-2569664b6321a572d04655c2a5ea418c1e39f50321c853a7d0cf413cb1221e9dafe. Файли artifacts/verification-dv4sjrq6/result.json,junit.xml,pytest.log. Цей повний прогін стосується продуктового safety fix; наступні зміни — уточнення документації та допоміжні файли B1. Чотири тести допоміжної процедури виконано окремим verify-прогоном вище; це не повторний повний suite.

Підготовлений комплект C:/tmp/Obscura-Codex-B1 пройшов окрему живу діагностику двох backend без моделей:5user-scope скілів через тимчасовий CODEX_HOME/skills,27MCPtools,list_stories=[]; PREPARATION-CHECK.json,b1_passed=false. Це НЕ приймання справжньої Test/.agents/skills/GUI. Це був стан до фактичного B1; його наступний результат наведено нижче. Попередній службовий виклик verify.py --help не запускав testcase і мав unconfirmed; для нього немає твердження про проходження.


## Ручне приймання B1 — PASS

B1 виконано 18.11.2026, запуск 20261118-164659-b6b2f8 (15:46:59–15:49:25 UTC, 16:46–16:49 Europe/Warsaw), checkout027434b. Штатний установник встановив усі п’ять скілів у C:/Users/Test/.agents/skills; MCP configured у Test/.codex/config.toml зі штатною копією. CLI0.166.0 та app backend0.169.0-alpha.11.1 підтвердили ті самі п’ять user-scope шляхів, discovery_errors=0,27tools incl get_guide, list_stories=[] без помилки; model_turns=0. Власник підтвердив у GUI всі п’ять скілів і enabled obscura. Загальний automatic/status=PASS. Доказ: docs/verification/evidence/2026-11-18-codex-b1.json (копія без Windows SID, SHA-256 оригіналу збережено). Це закриває checkout B1, але не доводить Store runtime/license чи літературну якість. Тестову Obscura після перевірки зупинено; її збережений у Test MCP URL належить цьому завершеному тестовому запуску.

Після027434b продуктовий код не змінювався: git diff підтвердив лише SPEC.MD та docs/. Наявний повний verify-звіт вище стосується саме цього продуктового коду; повторний повний прогін заради запису результату не виконувався. Ручний GUI-доказ є свідченням власника, а не автоматизованим GUI-тестом.
