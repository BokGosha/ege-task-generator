"""
Загрузчик текстовых промпт-шаблонов из ``backend/app/resources/prompts``.

Все шаблоны хранятся как обычные .txt/.tmpl-файлы в UTF-8. Это позволяет
доменному эксперту (учителю информатики, методисту) править формулировки
и few-shot примеры без изменения Python-кода.

Подстановка переменных делается простой заменой ``{имя}`` на значение —
не Python ``str.format``: содержимое шаблонов и значений может включать
произвольные фигурные скобки, и формат-строка тогда падала бы.

Файлы читаются с диска один раз и кешируются на время жизни процесса.
Если ресурс отсутствует — возвращается пустая строка (для опциональных
блоков вроде формализма по неизвестному типу задания).
"""

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR: Path = Path(__file__).resolve().parents[1] / "resources" / "prompts"


@lru_cache(maxsize=None)
def load_prompt(relative_path: str) -> str:
    """Возвращает содержимое промпт-файла относительно prompts-корня.

    Пустая строка, если файл не найден, — это допустимо для опциональных
    блоков (например, формализм для неизвестного типа задания).
    """

    path = _PROMPTS_DIR / relative_path
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def render(template: str, **substitutions: object) -> str:
    """Подставляет ``{key}`` → ``value`` без участия Python format-парсера."""

    result = template
    for key, value in substitutions.items():
        result = result.replace("{" + key + "}", str(value))
    return result
