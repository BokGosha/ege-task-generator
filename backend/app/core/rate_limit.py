"""
Общий экземпляр slowapi.Limiter для всего приложения.

Ключ ограничения — IP клиента (get_remote_address). Хранилище —
память процесса: при нескольких воркерах uvicorn реальный лимит равен
rate_limit_per_minute × число воркеров.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
