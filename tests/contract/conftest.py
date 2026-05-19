"""
Контрактные тесты используют те же фикстуры, что и интеграционные:
реальная PostgreSQL + ASGI-клиент + mock-провайдеры LLM.
"""

from tests.integration.conftest import (
    _reset_rate_limiter,
    client,
    db_session,
    test_engine,
)
