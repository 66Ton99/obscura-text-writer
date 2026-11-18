# Стан перевірки проєкту

**ПЕРЕВІРКА ПРОЙШЛА** — свідчення конкретного запуску, не поточного довільного стану.

- Початок (UTC): 2026-11-18T09:47:07.459212+00:00
- Завершення (UTC): 2026-11-18T10:02:08.504925+00:00
- Базовий commit: `1fbca9e5d0fbec32e94b084f321974bbd3b09bac`
- Незакомічені зміни під час перевірки: `false`
- SHA-256 вихідного знімка: `bdee439452c9d3968794af6400d2d7cdedba2cb94b7fe612264864778b56e867`
- Зміна знімка під час прогону: `false`
- Exit code: `0`
- Фактичні testcase результати JUnit: passed: 3673 · failed: 0 · errors: 0 · skipped: 20
- Тривалість: 901.05 с

Точний argv (JSON, не shell-команда):

```json
["C:\\Projects\\text-generator\\.venv\\Scripts\\python.exe", "-m", "pytest", "-q", "--junitxml=C:\\tmp\\obscura-codex-design\\artifacts\\verification-5z1fzvnj\\junit.xml", "--basetemp=C:\\tmp\\obscura-codex-design\\artifacts\\verification-5z1fzvnj\\test-tmp"]
```

Результат стосується лише наведеної команди й вихідного знімка. Якщо в argv зазначено окремі файли або фільтри, це часткова перевірка. Збір (collection) не є виконанням; skipped не зараховано до passed. Відсутній або непридатний XML позначається непідтвердженим. Після зміни вихідних файлів звіт історичний. Власний STATUS і artifacts виключено зі знімка; початкова ревізія може мати dirty=true, оскільки звіт створюється до коміту.

Цей прогін не є доказом літературної якості, реальної поведінки моделей або виконання ручних процедур. Коди виходу та лічильники не замінюють аналізу тестів.

Архітектура: [SPEC.MD](../SPEC.MD). Способи перевірки: [інструкція та матриця](verification/README.md). Мотиви рішень: [ADR](adr/README.md). Подальша робота: [беклог](superpowers/plans/2026-10-20-remediation-backlog.md).


## Додатковий фактичний прогін POSIX hook

Через Git Bash: python -X utf8 scripts/verify.py tests/test_pre_push_hook.py -q.
Ревізія та snapshot збігаються з повним прогоном вище: 1fbca9e; source_changed_during_run=false.
18 passed, 0 failed/errors/skipped. Результат: artifacts/verification-9g_cdcdu/result.json; JUnit: artifacts/verification-9g_cdcdu/junit.xml (локальні артефакти verify.py, не відстежуються git).
Це саме 18 перевірок, пропущених повним PowerShell-прогоном через відсутній sh у PATH.
Разом виконано 3691 унікальний тест; два symlink-тести лишаються skipped через дозволи Windows. Звіт не підтверджує GUI або Store runtime.
