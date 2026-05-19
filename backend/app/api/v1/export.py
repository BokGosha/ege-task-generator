"""Эндпоинт экспорта задания в JSON/TXT/PDF."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.schemas.common import ExportFormat
from backend.app.services import export_service

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/tasks/{task_id}")
async def export_task(
        task_id: UUID,
        format: ExportFormat = Query(ExportFormat.JSON, description="Формат экспорта: json, txt, pdf"),
        session: AsyncSession = Depends(get_db),
) -> Response:
    """Экспорт задания в выбранном формате."""

    if format == ExportFormat.JSON:
        data = await export_service.export_task_json(session, task_id)
        media_type = "application/json"
        filename = f"task_{task_id}.json"
    elif format == ExportFormat.TXT:
        data = await export_service.export_task_txt(session, task_id)
        media_type = "text/plain; charset=utf-8"
        filename = f"task_{task_id}.txt"
    else:
        data = await export_service.export_task_pdf(session, task_id)
        media_type = "application/pdf"
        filename = f"task_{task_id}.pdf"

    if data is None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "TASK_NOT_FOUND", "message": f"Задание с id={task_id} не найдено."}
        })

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
