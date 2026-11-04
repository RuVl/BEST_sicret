import os
import sys
from pathlib import Path

# Делает пакеты сервиса (parsing/sheets/...) импортируемыми в тестах,
# повторяя поведение prepend_sys_path=. при запуске из каталога сервиса.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Обязательная для env.py переменная: тесты не ходят в Google, но конфиг собирается на импорте.
os.environ.setdefault("SPREADSHEET_KEY", "test-key")
