import sys
from pathlib import Path

# Делает пакеты сервиса (parsing/sheets/...) импортируемыми в тестах,
# повторяя поведение prepend_sys_path=. при запуске из каталога сервиса.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
