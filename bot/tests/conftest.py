import os
import sys
from pathlib import Path

# Делает пакеты бота (includes/database/...) импортируемыми в тестах,
# повторяя запуск из каталога сервиса.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Обязательные для env.py переменные: тесты не трогают ни сеть, ни БД,
# но конфиг собирается на импорте модулей.
os.environ.setdefault("TG_API_TOKEN", "test-token")
os.environ.setdefault("DEBUG", "True")
