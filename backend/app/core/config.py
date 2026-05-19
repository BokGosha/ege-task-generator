"""
Конфигурация приложения через переменные окружения.

Использует pydantic-settings для загрузки параметров из .env-файлов
и переменных окружения. Все настройки собраны в settings.

Параметры приложения хранятся в backend/.env; корневой .env содержит
только инфраструктурные переменные для docker-compose и здесь читается лишь
как fallback (с extra="ignore" лишние ключи отбрасываются).
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_PROJECT_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    """
    Настройки приложения.

    Атрибуты:
        database_url: Строка подключения к PostgreSQL (asyncpg).
        llm_generation_provider: Провайдер LLM для генерации формулировок.
        llm_validation_provider: Провайдер LLM для семантической валидации.
        yandexgpt_api_key: API-ключ для YandexGPT.
        yandexgpt_folder_id: ID каталога (folder) в Yandex Cloud.
        gigachat_credentials: Учётные данные для GigaChat (Сбер).
        gigachat_scope: Scope авторизации GigaChat.
        max_retries: Максимальное количество повторных попыток при сбоях.
        llm_timeout_seconds: Максимальное время ожидания ответа от LLM.
        llm_max_concurrency: Максимум одновременных LLM-вызовов в одном процессе.
        llm_retry_attempts: Количество попыток при транспортных сбоях LLM.
        llm_retry_initial_delay: Начальная задержка экспоненциального бэкоффа (сек).
        db_pool_size: Размер постоянного пула соединений SQLAlchemy.
        db_max_overflow: Сколько дополнительных соединений допустимо сверх пула.
        db_pool_timeout: Секунды ожидания свободного слота в пуле, затем ошибка.
        rate_limit_per_minute: Лимит запросов к /generate на одного клиента в минуту.
        debug: Включить отладочный режим (DEBUG-уровень логирования).
    """

    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/ege_tasks"

    llm_generation_provider: Literal["yandexgpt", "gigachat", "mock"] = "mock"
    llm_validation_provider: Literal["yandexgpt", "gigachat", "mock"] = "mock"

    yandexgpt_api_key: str = ""
    yandexgpt_folder_id: str = ""
    gigachat_credentials: str = ""
    gigachat_scope: str = ""
    gigachat_generation_model: str = "GigaChat-Pro"
    gigachat_generation_temperature: float = 0.7
    gigachat_validation_model: str = "GigaChat-Max"
    gigachat_validation_temperature: float = 0.0

    yandexgpt_price_rub_per_1k_prompt: float = 0.0
    yandexgpt_price_rub_per_1k_completion: float = 0.0
    gigachat_price_rub_per_1k_prompt: float = 0.0
    gigachat_price_rub_per_1k_completion: float = 0.0

    max_retries: int = 3

    llm_timeout_seconds: float = 90.0
    llm_max_concurrency: int = 8
    llm_retry_attempts: int = 3
    llm_retry_initial_delay: float = 1.0

    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: float = 5.0

    rate_limit_per_minute: int = 5

    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=(str(_PROJECT_ROOT / ".env"), str(_BACKEND_DIR / ".env")),
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
