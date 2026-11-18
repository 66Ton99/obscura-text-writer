# Стан перевірки проєкту

**ПЕРЕВІРКА ПРОЙШЛА** — свідчення конкретного запуску, не поточного довільного стану.

- Початок (UTC): 2026-11-18T09:59:51.972735+00:00
- Завершення (UTC): 2026-11-18T10:13:16.258274+00:00
- Базовий commit: `319ead0b0b4f5c35dd676074b3470f65840e8a48`
- Незакомічені зміни під час перевірки: `false`
- SHA-256 вихідного знімка: `7be163092b8bda10170248a27392e6cabc3fc4828afdab979c3fedeec9cb1859`
- Зміна знімка під час прогону: `false`
- Exit code: `0`
- Фактичні testcase результати JUnit: passed: 3647 · failed: 0 · errors: 0 · skipped: 1
- Тривалість: 804.28 с

Точний argv (JSON, не shell-команда):

```json
["C:\\Projects\\text-generator\\.venv\\Scripts\\python.exe", "-m", "pytest", "-q", "--junitxml=C:\\tmp\\store-verify\\artifacts\\verification-jmk70yn4\\junit.xml", "--basetemp=C:\\tmp\\store-verify\\artifacts\\verification-jmk70yn4\\test-tmp"]
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
