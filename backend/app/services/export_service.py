"""
Сервис экспорта задания в форматах JSON, TXT, PDF.
"""

import io
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.history_service import get_task_by_id


async def export_task_json(session: AsyncSession, task_id: UUID) -> bytes | None:
    """Экспорт задания в JSON."""

    task_resp = await get_task_by_id(session, task_id)
    if task_resp is None:
        return None
    return task_resp.model_dump_json(indent=2, by_alias=True).encode("utf-8")


async def export_task_txt(session: AsyncSession, task_id: UUID) -> bytes | None:
    """Экспорт задания в TXT (UTF-8 fixed template)."""

    task_resp = await get_task_by_id(session, task_id)
    if task_resp is None:
        return None

    lines = [
        f"Задание ЕГЭ по информатике",
        f"Тип: {task_resp.task_type}",
        f"Подтип: {task_resp.subtype}",
        f"Статус: {task_resp.status}",
        f"ID: {task_resp.task_id}",
        f"Создано: {task_resp.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "=" * 50,
        "",
    ]

    if task_resp.final_wording:
        lines.append("УСЛОВИЕ ЗАДАЧИ:")
        lines.append(task_resp.final_wording)
        lines.append("")

    lines.append(f"ПРАВИЛЬНЫЙ ОТВЕТ: {task_resp.reference_answer}")
    lines.append("")

    if task_resp.quality_profile:
        qp = task_resp.quality_profile
        lines.append("ПРОФИЛЬ КАЧЕСТВА:")
        lines.append(f"  Вердикт: {qp.verdict}")
        criteria = [
            ("Ясность", qp.clarity),
            ("Однозначность", qp.unambiguity),
            ("Непротиворечивость", qp.consistency),
            ("Формат ответа", qp.answer_format),
            ("Языковая корректность", qp.language_correctness),
        ]
        for name, c in criteria:
            status = "PASS" if c.pass_ else "FAIL"
            msg = f" — {c.message}" if c.message else ""
            lines.append(f"  {name}: {status}{msg}")
        lines.append("")

    if task_resp.iterations:
        lines.append("ИТЕРАЦИИ:")
        for it in task_resp.iterations:
            verdict = f", вердикт: {it.quality_verdict}" if it.quality_verdict else ""
            reason = f", причина: {it.failure_reason}" if it.failure_reason else ""
            lines.append(f"  #{it.attempt_no}: {it.status}{verdict}{reason}")
        lines.append("")

    return "\n".join(lines).encode("utf-8")


async def export_task_pdf(session: AsyncSession, task_id: UUID) -> bytes | None:
    """Экспорт задания в PDF (чистый лист задания)."""

    task_resp = await get_task_by_id(session, task_id)
    if task_resp is None:
        return None

    try:
        from pathlib import Path
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        fonts_dir = Path(__file__).resolve().parent.parent / "resources" / "fonts"
        pdfmetrics.registerFont(TTFont("DejaVuSans", str(fonts_dir / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(fonts_dir / "DejaVuSans-Bold.ttf")))

        FONT = "DejaVuSans"
        FONT_BOLD = "DejaVuSans-Bold"

        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        p.setFont(FONT_BOLD, 16)
        p.drawString(2 * cm, height - 3 * cm, f"Задание ЕГЭ. Тип {task_resp.task_type}")

        p.setFont(FONT, 11)
        y = height - 4.5 * cm
        p.drawString(2 * cm, y, f"Подтип: {task_resp.subtype}")
        y -= 0.7 * cm

        if task_resp.final_wording:
            y -= 0.5 * cm
            p.setFont(FONT_BOLD, 12)
            p.drawString(2 * cm, y, "Условие:")
            y -= 0.8 * cm
            p.setFont(FONT, 11)

            for line in task_resp.final_wording.split("\n"):
                words = line.split()
                current = []
                for word in words:
                    test = " ".join(current + [word])
                    if p.stringWidth(test, FONT, 11) < 16 * cm:
                        current.append(word)
                    else:
                        p.drawString(2 * cm, y, " ".join(current))
                        y -= 0.5 * cm
                        current = [word]
                        if y < 3 * cm:
                            p.showPage()
                            p.setFont(FONT, 11)
                            y = height - 2 * cm
                if current:
                    p.drawString(2 * cm, y, " ".join(current))
                    y -= 0.5 * cm

        y -= 1 * cm
        p.setFont(FONT_BOLD, 12)
        p.drawString(2 * cm, y, f"Ответ: {task_resp.reference_answer}")

        p.save()
        buffer.seek(0)
        return buffer.getvalue()

    except ImportError:
        return await export_task_txt(session, task_id)
