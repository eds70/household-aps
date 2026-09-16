# backend/tests/fixtures/tz_case.py
"""
Эталонный кейс из Раздела 4 ТЗ.

Используется для проверки корректности планировщика.
Все данные соответствуют ТЗ:
- 11 материалов с остатками
- 3 ПФ (крем-мыло, средство для посуды, антисептик)
- 4 ГП
- 4 реактора, 1 накопительная емкость, 3 линии розлива, 1 бойлер
- 4 заказа на сентябрь 2026
- Календарь простоев (выходные, ремонт Р3 10-20.09)

ВАЖНО: количество партий рассчитано точно по ТЗ:
- Крем-мыло 1л: 20 000 кг / (5000 × 0.7) = ceil(5.71) = 6 партий
- Крем-мыло 5л: 25 000 кг / (10000 × 0.7) = ceil(3.57) = 4 партии
- Средство 1л: 15 000 кг → 2 партии по 7000 (Р2) + 1 партия 1000 (Р3) = 3
- Антисептик 10л: 80 000 кг → 14 партий по 5600 (Р3) + 1 партия 1600 (Р4) = 15
ИТОГО: 6 + 4 + 3 + 15 = 28 партий.
"""

from uuid import UUID
from datetime import datetime, timezone, timedelta

# Часовой пояс +03:00 (Москва)
TZ = timezone(timedelta(hours=3))

# Фиксированный ID организации
ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


def _dt(date_str: str, time_str: str = "00:00:00") -> datetime:
    """Создать datetime с часовым поясом +03:00."""
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=TZ)


# ==========================================
# МАТЕРИАЛЫ (остатки на начало месяца)
# ==========================================
MATERIALS = [
    {"code": "WATER",     "name": "Вода",                 "unit": "kg", "category": "RAW",       "stock": 100_000},
    {"code": "SALT",      "name": "Соль экстра",          "unit": "kg", "category": "RAW",       "stock": 3_000},
    {"code": "FRAGRANCE", "name": "Отдушка цветочная",    "unit": "kg", "category": "RAW",       "stock": 1_500},
    {"code": "GLYCERIN",  "name": "Глицерин",             "unit": "kg", "category": "RAW",       "stock": 4_000},
    {"code": "BETAINE",   "name": "Бетаин",               "unit": "kg", "category": "RAW",       "stock": 1_000},
    {"code": "ALCOHOL",   "name": "Спирт",                "unit": "kg", "category": "RAW",       "stock": 30_000},
    {"code": "CHLORIDE",  "name": "Хлорид",               "unit": "kg", "category": "RAW",       "stock": 5_000},
    {"code": "BTL1",      "name": "Бутылки 1 литр",       "unit": "pc", "category": "PACKAGING", "stock": 30_000},
    {"code": "BTL5",      "name": "Бутылки 5 литров",     "unit": "pc", "category": "PACKAGING", "stock": 10_000},
    {"code": "BTL10",     "name": "Бутылки 10 литров",    "unit": "pc", "category": "PACKAGING", "stock": 10_000},
    {"code": "CAP",       "name": "Крышки универсальные", "unit": "pc", "category": "PACKAGING", "stock": 40_000},
]

# ==========================================
# ПОЛУФАБРИКАТЫ (ПФ)
# ==========================================
PF_PRODUCTS = [
    {
        "code": "PF_CREAM",
        "name": "Крем-мыло",
        "viscosity_coeff": 1.3,
        "requires_heating": True,
        "route_type": "VIA_TANK",  # по ТЗ — через накопительную емкость
        "max_fill_percent": 0.70,
        "recipe": {
            "base_volume_kg": 100,
            "items": [
                {"material_code": "WATER",     "qty": 85},
                {"material_code": "SALT",      "qty": 5},
                {"material_code": "FRAGRANCE", "qty": 2},
                {"material_code": "GLYCERIN",  "qty": 8},
            ],
        },
    },
    {
        "code": "PF_DISH",
        "name": "Средство для мытья посуды",
        "viscosity_coeff": 1.0,
        "requires_heating": False,
        "route_type": "DIRECT",  # без танка
        "max_fill_percent": 0.70,
        "recipe": {
            "base_volume_kg": 100,
            "items": [
                {"material_code": "WATER",     "qty": 70},
                {"material_code": "SALT",      "qty": 15},
                {"material_code": "FRAGRANCE", "qty": 5},
                {"material_code": "BETAINE",   "qty": 6},
                {"material_code": "ALCOHOL",   "qty": 4},
            ],
        },
    },
    {
        "code": "PF_ANTISEPTIC",
        "name": "Антисептик",
        "viscosity_coeff": 0.8,
        "requires_heating": False,
        "route_type": "DIRECT",
        "max_fill_percent": 0.70,
        "recipe": {
            "base_volume_kg": 100,
            "items": [
                {"material_code": "WATER",    "qty": 60},
                {"material_code": "ALCOHOL",  "qty": 35},
                {"material_code": "CHLORIDE", "qty": 5},
            ],
        },
    },
]

# ==========================================
# ГОТОВАЯ ПРОДУКЦИЯ (ГП)
# ==========================================
GP_PRODUCTS = [
    {
        "code": "GP_CREAM_1L",
        "name": "Крем-мыло 1л",
        "parent_pf_code": "PF_CREAM",
        "bottle_volume_l": 1.0,
        "fill_speed_per_min": 10,
        "viscosity_coeff": 1.3,
    },
    {
        "code": "GP_CREAM_5L",
        "name": "Крем-мыло 5л",
        "parent_pf_code": "PF_CREAM",
        "bottle_volume_l": 5.0,
        "fill_speed_per_min": 1,
        "viscosity_coeff": 1.3,
    },
    {
        "code": "GP_DISH_1L",
        "name": "Средство для мытья посуды 1л",
        "parent_pf_code": "PF_DISH",
        "bottle_volume_l": 1.0,
        "fill_speed_per_min": 5,
        "viscosity_coeff": 1.0,
    },
    {
        "code": "GP_ANTISEPTIC_10L",
        "name": "Антисептик 10л",
        "parent_pf_code": "PF_ANTISEPTIC",
        "bottle_volume_l": 10.0,
        "fill_speed_per_min": 1,
        "viscosity_coeff": 0.8,
    },
]

# ==========================================
# ОБОРУДОВАНИЕ
# ==========================================
REACTORS = [
    {"code": "REACTOR_1", "name": "Реактор 1", "volume_kg": 5_000,  "speed_coeff": 1.0, "mixer_type": "standard",   "pf_codes": ["PF_CREAM"]},
    {"code": "REACTOR_2", "name": "Реактор 2", "volume_kg": 10_000, "speed_coeff": 1.2, "mixer_type": "high_speed", "pf_codes": ["PF_CREAM", "PF_DISH"]},
    {"code": "REACTOR_3", "name": "Реактор 3", "volume_kg": 8_000,  "speed_coeff": 1.1, "mixer_type": "standard",   "pf_codes": ["PF_DISH", "PF_ANTISEPTIC"]},
    {"code": "REACTOR_4", "name": "Реактор 4", "volume_kg": 5_000,  "speed_coeff": 0.9, "mixer_type": "low_speed",  "pf_codes": ["PF_ANTISEPTIC"]},
]

TANKS = [
    {
        "code": "TANK_1",
        "name": "Накопительная емкость 1",
        "volume_kg": 5_000,
        "speed_coeff": 1.0,
        "connected_to_reactors": ["REACTOR_1"],
    },
]

FILLING_LINES = [
    {
        "code": "LINE_1",
        "name": "Линия 1 (1л)",
        "type": "FILLING_LINE",
        "connected_to_reactors": ["REACTOR_1", "REACTOR_2"],
        "connected_to_tanks": ["TANK_1"],
        "gp_codes": ["GP_CREAM_1L", "GP_DISH_1L"],
    },
    {
        "code": "LINE_2",
        "name": "Линия 2 (5/10л)",
        "type": "FILLING_LINE",
        "connected_to_reactors": ["REACTOR_1", "REACTOR_2", "REACTOR_3"],
        "connected_to_tanks": [],
        "gp_codes": ["GP_CREAM_5L", "GP_ANTISEPTIC_10L"],
    },
    {
        "code": "LINE_3",
        "name": "Линия 3 (ручной слив 10л)",
        "type": "MANUAL_STATION",
        "connected_to_reactors": ["REACTOR_4"],
        "connected_to_tanks": [],
        "gp_codes": ["GP_ANTISEPTIC_10L"],
    },
]

BOILER = {"code": "BOILER", "name": "Бойлер", "volume_kg": 2_000}

# ==========================================
# СВЯЗИ ОБОРУДОВАНИЯ
# ==========================================
EQUIPMENT_LINKS = [
    ("REACTOR_1", "TANK_1", True),
    ("TANK_1", "LINE_1", True),
    ("REACTOR_1", "LINE_1", True),
    ("REACTOR_2", "LINE_1", True),
    ("REACTOR_2", "LINE_2", True),
    ("REACTOR_3", "LINE_2", True),
    ("REACTOR_4", "LINE_3", True),
]

# ==========================================
# РЕСУРСНЫЕ ПУЛЫ
# ==========================================
RESOURCE_POOLS = [
    {"code": "OPERATORS_REACTOR", "name": "Аппаратчики реакторов", "type": "OPERATOR",     "capacity": 3},
    {"code": "COOLING_ZONE",      "name": "Зона охлаждения",       "type": "COOLING_ZONE", "capacity": 2},
    {"code": "BOILER",            "name": "Бойлер",                "type": "BOILER",       "capacity": 1},
    {"code": "LAB",               "name": "Лаборатория",           "type": "LAB",          "capacity": 1},
]

# ==========================================
# ТЕХНОЛОГИЧЕСКИЕ КАРТЫ
# ==========================================
# Формат: (stage, name, duration, boiler, cooling, operator, lab, formula, parallel_group)
OPERATIONS_CREAM = [
    (1,  "Загрузка сырья (вода)",            60,  False, False, True,  False, "water_loading", None),
    (2,  "Нагрев воды",                      120, True,  False, False, False, "heating",       None),
    (3,  "Перемешивание",                    90,  False, False, True,  False, "mixing",        "GROUP1"),
    (4,  "Охлаждение 80→60°C",               120, False, True,  False, False, "cooling",       "GROUP1"),
    (5,  "Лабораторный анализ",              30,  False, False, False, True,  None,            None),
    (6,  "Загрузка доп. сырья",              30,  False, False, True,  False, "water_loading", None),
    (7,  "Перемешивание (2 этап)",           60,  False, False, True,  False, "mixing",        "GROUP2"),
    (8,  "Охлаждение 60→40°C",               120, False, True,  False, False, "cooling",       "GROUP2"),
    (9,  "Лабораторный анализ (финал)",      30,  False, False, False, True,  None,            None),
    (10, "Перекачка в накопительную емкость", 60, False, False, True,  False, "pumping",       None),
    (11, "Промывка реактора",                90,  False, False, True,  False, "washing",       None),
]

OPERATIONS_DISH = [
    (1, "Загрузка сырья (вода)",        60,  False, False, True,  False, "water_loading", None),
    (2, "Перемешивание",                120, False, False, True,  False, "mixing",        "GROUP1"),
    (3, "Охлаждение 90→50°C",           90,  False, True,  False, False, "cooling",       "GROUP1"),
    (4, "Лабораторный анализ",          30,  False, False, False, True,  None,            None),
    (5, "Перемешивание (2 этап)",       60,  False, False, True,  False, "mixing",        "GROUP2"),
    (6, "Охлаждение 50→30°C",           90,  False, True,  False, False, "cooling",       "GROUP2"),
    (7, "Лабораторный анализ (финал)",  30,  False, False, False, True,  None,            None),
    (8, "Промывка реактора",            90,  False, False, True,  False, "washing",       None),
]

OPERATIONS_ANTISEPTIC = [
    (1, "Загрузка сырья (вода)",           60, False, False, True,  False, "water_loading", None),
    (2, "Перемешивание",                   60, False, False, True,  False, "mixing",        None),
    (3, "Лабораторный анализ",             30, False, False, False, True,  None,            None),
    (4, "Загрузка доп. сырья",             30, False, False, True,  False, "water_loading", None),
    (5, "Перемешивание (2 этап)",          30, False, False, True,  False, "mixing",        None),
    (6, "Лабораторный анализ (финал)",     30, False, False, False, True,  None,            None),
    (7, "Перекачка в накопительную емкость", 45, False, False, True, False, "pumping",      None),
    (8, "Промывка реактора",               30, False, False, True,  False, "washing",       None),
]

OPERATIONS = {
    "PF_CREAM":      OPERATIONS_CREAM,
    "PF_DISH":       OPERATIONS_DISH,
    "PF_ANTISEPTIC": OPERATIONS_ANTISEPTIC,
}

# ==========================================
# МАТРИЦА ЗАМЫВКИ (setup times)
# ==========================================
SETUP_MATRIX = {
    ("PF_CREAM", "PF_CREAM"):           30,
    ("PF_CREAM", "PF_DISH"):            90,
    ("PF_CREAM", "PF_ANTISEPTIC"):      90,
    ("PF_DISH", "PF_DISH"):             30,
    ("PF_DISH", "PF_CREAM"):            90,
    ("PF_DISH", "PF_ANTISEPTIC"):       90,
    ("PF_ANTISEPTIC", "PF_ANTISEPTIC"): 30,
    ("PF_ANTISEPTIC", "PF_CREAM"):      90,
    ("PF_ANTISEPTIC", "PF_DISH"):       90,
}

# ==========================================
# КАЛЕНДАРЬ ПРОСТОЕВ (сентябрь 2026)
# ==========================================
CALENDAR_EVENTS = [
    {"event_type": "WEEKEND", "equipment_code": None,        "starts_at": _dt("2026-09-05"), "ends_at": _dt("2026-09-07"), "comment": "Выходные"},
    {"event_type": "WEEKEND", "equipment_code": None,        "starts_at": _dt("2026-09-12"), "ends_at": _dt("2026-09-14"), "comment": "Выходные"},
    {"event_type": "WEEKEND", "equipment_code": None,        "starts_at": _dt("2026-09-19"), "ends_at": _dt("2026-09-21"), "comment": "Выходные"},
    {"event_type": "WEEKEND", "equipment_code": None,        "starts_at": _dt("2026-09-26"), "ends_at": _dt("2026-09-28"), "comment": "Выходные"},
    {"event_type": "REPAIR",  "equipment_code": "REACTOR_3", "starts_at": _dt("2026-09-10"), "ends_at": _dt("2026-09-21"), "comment": "Плановый ремонт Р3"},
]

CALENDAR_EVENTS_AFTER_PLANNING = [
    {"event_type": "BREAKDOWN", "equipment_code": "REACTOR_4", "starts_at": _dt("2026-09-25"), "ends_at": _dt("2026-09-29"), "comment": "Аварийная остановка Р4"},
]

# ==========================================
# ПРОИЗВОДСТВЕННЫЕ ЗАКАЗЫ (план на месяц)
# ==========================================
ORDERS = [
    {"gp_code": "GP_CREAM_1L",      "target_qty": 20_000, "due_date": _dt("2026-09-30", "23:59:59"), "priority": 5},
    {"gp_code": "GP_CREAM_5L",      "target_qty": 5_000,  "due_date": _dt("2026-09-30", "23:59:59"), "priority": 5},
    {"gp_code": "GP_DISH_1L",       "target_qty": 15_000, "due_date": _dt("2026-09-30", "23:59:59"), "priority": 5},
    {"gp_code": "GP_ANTISEPTIC_10L","target_qty": 8_000,  "due_date": _dt("2026-09-30", "23:59:59"), "priority": 5},
]

# ==========================================
# ПАРТИИ (разбивка по реакторам, пересчитано точно)
# ==========================================
# Формула: num_batches = ceil(target_kg / (reactor.volume * max_fill))
#
# Крем-мыло 1л: 20 000 кг ПФ
#   Р1 (5000 × 0.7 = 3500): 5×3500 + 1×2500 = 6 партий → 20 000 кг ✅
#
# Крем-мыло 5л: 25 000 кг ПФ
#   Р2 (10000 × 0.7 = 7000): 3×7000 + 1×4000 = 4 партии → 25 000 кг ✅
#
# Средство 1л: 15 000 кг ПФ
#   Р2 (7000): 2 партии + Р3 (8000 × 0.7 = 5600, но берём 1000 для остатка)
#   2×7000 (Р2) + 1×1000 (Р3) = 3 партии → 15 000 кг ✅
#
# Антисептик 10л: 80 000 кг ПФ
#   Р3 (8000 × 0.7 = 5600): 14×5600 = 78 400 кг + остаток 1600 кг
#   Р4 (5000 × 0.7 = 3500): 1×1600 = 1600 кг
#   Итого: 14 (Р3) + 1 (Р4) = 15 партий → 80 000 кг ✅
#
# ВСЕГО: 6 + 4 + 3 + 15 = 28 партий
BATCHES = (
    # --- Крем-мыло 1л (Р1): 5×3500 + 1×2500 = 20 000 кг ---
        [{"order_gp_code": "GP_CREAM_1L", "pf_code": "PF_CREAM", "volume_kg": 3500, "reactor_code": "REACTOR_1"}] * 5
        + [{"order_gp_code": "GP_CREAM_1L", "pf_code": "PF_CREAM", "volume_kg": 2500, "reactor_code": "REACTOR_1"}]

        # --- Крем-мыло 5л (Р2): 3×7000 + 1×4000 = 25 000 кг ---
        + [{"order_gp_code": "GP_CREAM_5L", "pf_code": "PF_CREAM", "volume_kg": 7000, "reactor_code": "REACTOR_2"}] * 3
        + [{"order_gp_code": "GP_CREAM_5L", "pf_code": "PF_CREAM", "volume_kg": 4000, "reactor_code": "REACTOR_2"}]

        # --- Средство 1л (Р2 + Р3): 2×7000 + 1×1000 = 15 000 кг ---
        + [
            {"order_gp_code": "GP_DISH_1L", "pf_code": "PF_DISH", "volume_kg": 7000, "reactor_code": "REACTOR_2"},
            {"order_gp_code": "GP_DISH_1L", "pf_code": "PF_DISH", "volume_kg": 7000, "reactor_code": "REACTOR_2"},
            {"order_gp_code": "GP_DISH_1L", "pf_code": "PF_DISH", "volume_kg": 1000, "reactor_code": "REACTOR_3"},
        ]

        # --- Антисептик 10л (Р3): 14×5600 = 78 400 кг ---
        + [{"order_gp_code": "GP_ANTISEPTIC_10L", "pf_code": "PF_ANTISEPTIC", "volume_kg": 5600, "reactor_code": "REACTOR_3"}] * 14

        # --- Антисептик 10л (Р4): 1×1600 = 1600 кг ---
        + [{"order_gp_code": "GP_ANTISEPTIC_10L", "pf_code": "PF_ANTISEPTIC", "volume_kg": 1600, "reactor_code": "REACTOR_4"}]
)

# ==========================================
# ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ (общие)
# ==========================================
EXPECTED = {
    "total_batches": 28,   # пересчитано: 6 + 4 + 3 + 15
    "total_orders": 4,
    "reactors_count": 4,
    "lines_count": 3,
    "planning_start": _dt("2026-09-01", "08:00:00"),
    "makespan_max_hours": 30 * 24,  # не более 30 дней
}

# ==========================================
# СМЕНЫ НА СЕНТЯБРЬ 2026
# ==========================================
# Одна смена в день: 08:00-20:00.
# Выходные (сб-вс) — нерабочие, но смены создаются.
SHIFTS = []
for day in range(1, 31):  # 01.09 - 30.09
    d = _dt(f"2026-09-{day:02d}", "08:00:00")
    e = _dt(f"2026-09-{day:02d}", "20:00:00")
    dow = d.weekday()  # 0=пн, 6=вс
    is_working = dow < 5  # пн-пт — рабочие
    SHIFTS.append({
        "name": f"Смена {day:02d}.09.2026",
        "starts_at": d,
        "ends_at": e,
        "is_working": is_working,
        "comment": "Рабочая смена" if is_working else "Выходной",
    })

EXPECTED_SHIFTS = {
    "total": 30,
    "working": 22,  # 30 - 8 (4 субботы + 4 воскресенья)
}