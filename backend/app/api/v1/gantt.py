# backend/app/api/v1/gantt.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import io
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from .models import GanttTask, GanttResponse
from .schedule import _last_schedule_result

router = APIRouter(prefix="/api/v1/gantt", tags=["Диаграмма Ганта"])

@router.get("/", response_model=GanttResponse)
async def get_gantt_data():
    if not _last_schedule_result:
        raise HTTPException(status_code=404, detail="Нет данных. Сначала постройте план на вкладке 'Планирование'")

    tasks = _last_schedule_result.get("tasks", [])
    gantt_tasks = []
    equipment_set = set()
    product_set = set()

    for task in tasks:
        # 1. Безопасное извлечение данных с явным приведением к строке
        eq_name = str(task.get("equipment_name") or "")
        eq_id = str(task.get("equipment_id") or "")
        prod_name = str(task.get("product_name") or "")
        prod_id = str(task.get("product_id") or "")
        batch_name = str(task.get("batch_name") or "")
        batch_id = str(task.get("batch_id") or "")
        op_id = str(task.get("op_id") or "")

        # Используем имя, если есть, иначе первые 8 символов ID
        equipment_set.add(eq_name if eq_name else eq_id[:8])
        product_set.add(prod_name if prod_name else prod_id[:8])

        # 2. Безопасная работа с датами
        start_dt = task.get("start")
        end_dt = task.get("end")

        # Если даты пришли как строки (например, из JSON), преобразуем их
        if isinstance(start_dt, str):
            start_dt = datetime.fromisoformat(start_dt.replace('Z', '+00:00'))
        if isinstance(end_dt, str):
            end_dt = datetime.fromisoformat(end_dt.replace('Z', '+00:00'))

        # 3. Расчет длительности
        duration_mins = int(task.get("duration", 0))
        if start_dt and end_dt and isinstance(start_dt, datetime) and isinstance(end_dt, datetime):
            duration_mins = int((end_dt - start_dt).total_seconds() / 60)

        gantt_tasks.append(GanttTask(
            id=f"{batch_id}_{op_id}",
            batch_id=batch_name if batch_name else batch_id[:8],
            operation_name=str(task.get("operation_name", "Операция")),
            equipment_id=eq_name if eq_name else eq_id[:8],
            product_id=prod_name if prod_name else prod_id[:8],
            start=start_dt,
            end=end_dt,
            duration_minutes=duration_mins,
        ))

    return GanttResponse(
        tasks=gantt_tasks,
        total_tasks=len(gantt_tasks),
        makespan_hours=float(_last_schedule_result.get("makespan_minutes", 0)) / 60,
        equipment_list=sorted(list(equipment_set)),
        product_list=sorted(list(product_set)),
    )

@router.get("/export")
async def export_gantt_to_excel():
    if not _last_schedule_result:
        raise HTTPException(status_code=404, detail="Нет данных для экспорта")

    tasks = _last_schedule_result.get("tasks", [])

    def fmt_name(name, full_id):
        short_id = str(full_id)[:8] if full_id else "?"
        return f"{name} ({short_id})"

    wb = Workbook()
    ws_table = wb.active
    ws_table.title = "Таблица задач"

    headers = ["Оборудование", "Операция", "Партия", "Продукт", "Код продукта", "Начало", "Конец", "Длительность (мин)", "Длительность (часы)"]
    ws_table.append(headers)

    header_fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    for cell in ws_table[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for task in tasks:
        duration_mins = int(task.get("duration", 0))
        duration_hours = round(duration_mins / 60, 2)

        equipment_display = fmt_name(task.get("equipment_name"), task.get("equipment_id"))
        batch_display = fmt_name(task.get("batch_name"), task.get("batch_id"))
        product_display = fmt_name(task.get("product_name"), task.get("product_id"))

        start_str = task["start"].strftime("%Y-%m-%d %H:%M") if isinstance(task["start"], datetime) else str(task["start"])
        end_str = task["end"].strftime("%Y-%m-%d %H:%M") if isinstance(task["end"], datetime) else str(task["end"])

        ws_table.append([
            equipment_display,
            task.get("operation_name", ""),
            batch_display,
            product_display,
            task.get("product_code", ""),
            start_str,
            end_str,
            duration_mins,
            duration_hours
        ])

    for col in ws_table.columns:
        max_len = max(len(str(cell.value)) for cell in col if cell.value is not None)
        ws_table.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 2, 45)

    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    filename = f"APS_Gantt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        file_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )