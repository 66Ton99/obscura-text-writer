# Стан перевірки проєкту

**ПЕРЕВІРКА ПРОЙШЛА** — свідчення конкретного запуску, не поточного довільного стану.

- Початок (UTC): 2026-11-18T15:55:49.010302+00:00
- Завершення (UTC): 2026-11-18T16:08:13.769085+00:00
- Базовий commit: `67fdc0b1975d897b7d83dfe9d8bbe9ecd25cbcde`
- Незакомічені зміни під час перевірки: `false`
- SHA-256 вихідного знімка: `a84c8fbddd9c9421e5414bc2d70659a9a76bac97f817c688b2d8820f76830e8b`
- Зміна знімка під час прогону: `false`
- Exit code: `0`
- Фактичні testcase результати JUnit: passed: 3753 · failed: 0 · errors: 0 · skipped: 20
- Тривалість: 744.75 с

Точний argv (JSON, не shell-команда):

```json
["C:\\Projects\\text-generator\\.venv\\Scripts\\python.exe", "-m", "pytest", "-q", "--junitxml=C:\\tmp\\obscura-codex-design\\artifacts\\verification-eor0jsy6\\junit.xml", "--basetemp=C:\\tmp\\obscura-codex-design\\artifacts\\verification-eor0jsy6\\test-tmp"]
```

Результат стосується лише наведеної команди й вихідного знімка. Якщо в argv зазначено окремі файли або фільтри, це часткова перевірка. Збір (collection) не є виконанням; skipped не зараховано до passed. Відсутній або непридатний XML позначається непідтвердженим. Після зміни вихідних файлів звіт історичний. Власний STATUS і artifacts виключено зі знімка; початкова ревізія може мати dirty=true, оскільки звіт створюється до коміту.

Цей прогін не є доказом літературної якості, реальної поведінки моделей або виконання ручних процедур. Коди виходу та лічильники не замінюють аналізу тестів.

Архітектура: [SPEC.MD](../SPEC.MD). Способи перевірки: [інструкція та матриця](verification/README.md). Мотиви рішень: [ADR](adr/README.md). Подальша робота: [беклог](superpowers/plans/2026-10-20-remediation-backlog.md).


## Ручне B1 та завершення checkout206

Після інтеграції main d12c8a7 (#208), merge67fdc0b: повний verify.py3753passed,0failed/errors,20skip (18POSIX sh unavailable,2Windows symlink permissions),source_changed=false; artifacts/verification-eor0jsy6. 24browser Codex+Claude desktop/mobile PASS. CI store-build44341453142 і site44341453297 SUCCESS. Захищені Claude/Store-файли відносно нового main не змінені. Codex core/routes/installer/generator та джерела SKILL.md/references/shared не змінилися від027434b; B1 докази залишаються для цієї поведінки. B1 PASS — штатна Test/.agents/skills, обидва backend,27tools,list_stories=[],model_turns0, GUI підтвердив власник. Злиття PR206 не виконано.

B1run20261118-164659-b6b2f8,18.11.2026 15:46:59–15:49:25UTC. CLI0.166.0, app backend0.169.0-alpha.11.1;5user-scope paths C:/Users/Test/.agents/skills,discovery_errors0. Доказ і SHA-256 оригіналу: docs/verification/evidence/2026-11-18-codex-b1.json. GUI-поля є свідченням власника, не автоматичним GUI-тестом. Store B2/B3 належать R-39 PR2. Пропуски вище не зараховано до passed.
