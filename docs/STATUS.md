# Стан перевірки проєкту

**ПЕРЕВІРКА НЕ ПРОЙШЛА** — свідчення конкретного запуску, не поточного довільного стану.

- Початок (UTC): 2026-11-15T15:21:10.291253+00:00
- Завершення (UTC): 2026-11-15T15:30:01.754525+00:00
- Базовий commit: `d9ff0b43af08e294dcfeb6d634def7ace2ac0b42`
- Незакомічені зміни під час перевірки: `true`
- SHA-256 вихідного знімка: `42be8480ff5410f6c1a32504881a6f6b32ea1ab93f09ff9b9cea02886d7e4b4d`
- Зміна знімка під час прогону: `false`
- Exit code: `1`
- Фактичні testcase результати JUnit: passed: 3345 · failed: 4 · errors: 0 · skipped: 3
- Тривалість: 531.46 с

Точний argv (JSON, не shell-команда):

```json
["/tmp/claude-0/-home-user-obscura-text-writer/19ae2e98-73e4-5122-8d9b-851ca810b91d/scratchpad/venv/bin/python", "-m", "pytest", "-q", "--junitxml=/home/user/obscura-text-writer/artifacts/verification-sv0tl4cy/junit.xml", "--basetemp=/home/user/obscura-text-writer/artifacts/verification-sv0tl4cy/test-tmp"]
```

Результат стосується лише наведеної команди й вихідного знімка. Якщо в argv зазначено окремі файли або фільтри, це часткова перевірка. Збір (collection) не є виконанням; skipped не зараховано до passed. Відсутній або непридатний XML позначається непідтвердженим. Після зміни вихідних файлів звіт історичний. Власний STATUS і artifacts виключено зі знімка; початкова ревізія може мати dirty=true, оскільки звіт створюється до коміту.

Цей прогін не є доказом літературної якості, реальної поведінки моделей або виконання ручних процедур. Коди виходу та лічильники не замінюють аналізу тестів.

Архітектура: [SPEC.MD](../SPEC.MD). Способи перевірки: [інструкція та матриця](verification/README.md). Мотиви рішень: [ADR](adr/README.md). Подальша робота: [беклог](superpowers/plans/2026-10-20-remediation-backlog.md).
