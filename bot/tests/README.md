# Tests Directory

Тесты для модуля обработки ошибок БД (PROBLEM_6: Database Error Handling)

## Файлы

- **test_error_handler.py** - Unit-тесты с mock объектами
- **test_error_handler_integration.py** - Интеграционные тесты с реальной БД SQLite
- **test_db_errors.py** - Вспомогательный скрипт для ручного тестирования

## Быстрый старт

```bash
# Unit-тесты
pytest test_error_handler.py -v

# Интеграционные тесты
python test_error_handler_integration.py

# Ручные тесты
python test_db_errors.py --help-all
```

## Полная документация

Смотрите: [TESTING_DATABASE_ERROR_HANDLER.md](../TESTING_DATABASE_ERROR_HANDLER.md)
