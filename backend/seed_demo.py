"""
Скрипт заполнения базы демо-данными
Используется SQLAlchemy для корректной работы с кодировкой UTF-8 и типами asyncpg
"""
import asyncio
from uuid import UUID
from datetime import datetime, timezone, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Конфигурация
DATABASE_URL = "postgresql+asyncpg://aps:aps_secret@localhost:5432/household"
ORG_ID = UUID("00000000-0000-0000-0000-000000000001")

# Часовой пояс +03:00 (как в ТЗ)
TZ_PLUS_3 = timezone(timedelta(hours=3))

def parse_dt(date_str: str, time_str: str = "00:00:00") -> datetime:
    """Вспомогательная функция для создания datetime с часовым поясом"""
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=TZ_PLUS_3)

async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        print("🔄 Очистка существующих данных...")
        await session.execute(text("TRUNCATE TABLE batch CASCADE"))
        await session.execute(text("TRUNCATE TABLE production_order CASCADE"))
        await session.execute(text("TRUNCATE TABLE calendar_event CASCADE"))
        await session.execute(text("TRUNCATE TABLE setup_matrix CASCADE"))
        await session.execute(text("TRUNCATE TABLE operation_template CASCADE"))
        await session.execute(text("TRUNCATE TABLE equipment_capability CASCADE"))
        await session.execute(text("TRUNCATE TABLE equipment_link CASCADE"))
        await session.execute(text("TRUNCATE TABLE resource_pool CASCADE"))
        await session.execute(text("TRUNCATE TABLE recipe_item CASCADE"))
        await session.execute(text("TRUNCATE TABLE recipe CASCADE"))
        await session.execute(text("TRUNCATE TABLE product CASCADE"))
        await session.execute(text("TRUNCATE TABLE material_stock CASCADE"))
        await session.execute(text("TRUNCATE TABLE material_supply CASCADE"))
        await session.execute(text("TRUNCATE TABLE material CASCADE"))
        await session.execute(text("TRUNCATE TABLE equipment CASCADE"))
        await session.execute(text("TRUNCATE TABLE app_user CASCADE"))
        await session.execute(text("TRUNCATE TABLE organization CASCADE"))
        await session.commit()
        print("✅ Данные очищены")
        
        # 1. Организация
        print("📝 Создание организации...")
        await session.execute(text("""
            INSERT INTO organization (id, name, slug, settings)
            VALUES (:id, :name, :slug, :settings)
        """), {
            "id": ORG_ID,
            "name": "Бытовая Химия ООО",
            "slug": "household-demo",
            "settings": '{"work_start": "08:00", "work_end": "20:00"}'
        })
        await session.commit()
        
        # 2. Материалы
        print("📦 Создание материалов...")
        materials_data = [
            ("WATER", "Вода", "kg", "RAW", 100000),
            ("SALT", "Соль экстра", "kg", "RAW", 3000),
            ("FRAGRANCE", "Отдушка цветочная", "kg", "RAW", 1500),
            ("GLYCERIN", "Глицерин", "kg", "RAW", 4000),
            ("BETAINE", "Бетаин", "kg", "RAW", 1000),
            ("ALCOHOL", "Спирт", "kg", "RAW", 30000),
            ("CHLORIDE", "Хлорид", "kg", "RAW", 5000),
            ("BTL1", "Бутылки 1 литр", "pc", "PACKAGING", 30000),
            ("BTL5", "Бутылки 5 литров", "pc", "PACKAGING", 10000),
            ("BTL10", "Бутылки 10 литров", "pc", "PACKAGING", 10000),
            ("CAP", "Крышки универсальные", "pc", "PACKAGING", 40000),
        ]
        
        material_ids = {}
        for code, name, unit, category, qty in materials_data:
            result = await session.execute(text("""
                INSERT INTO material (organization_id, code, name, unit, category)
                VALUES (:org_id, :code, :name, :unit, :category)
                RETURNING id
            """), {"org_id": ORG_ID, "code": code, "name": name, "unit": unit, "category": category})
            mat_id = result.scalar()
            material_ids[code] = mat_id
            
            await session.execute(text("""
                INSERT INTO material_stock (organization_id, material_id, qty)
                VALUES (:org_id, :mat_id, :qty)
            """), {"org_id": ORG_ID, "mat_id": mat_id, "qty": qty})
        
        await session.commit()
        print(f"✅ Создано {len(materials_data)} материалов")
        
        # 3. Продукты (ПФ)
        print("🧪 Создание полуфабрикатов...")
        products_pf = {
            "PF_CREAM": ("Крем-мыло", "PF", 1.3, True),
            "PF_DISH": ("Средство для мытья посуды", "PF", 1.0, False),
            "PF_ANTISEPTIC": ("Антисептик", "PF", 0.8, False),
        }
        
        product_ids = {}
        for code, (name, ptype, viscosity, needs_heating) in products_pf.items():
            result = await session.execute(text("""
                INSERT INTO product (organization_id, code, name, type, viscosity_coeff, requires_heating)
                VALUES (:org_id, :code, :name, :type, :viscosity, :needs_heating)
                RETURNING id
            """), {"org_id": ORG_ID, "code": code, "name": name, "type": ptype, 
                   "viscosity": viscosity, "needs_heating": needs_heating})
            product_ids[code] = result.scalar()
        
        # 4. Продукты (ГП)
        print("🧴 Создание готовой продукции...")
        products_gp = {
            "GP_CREAM_1L": ("Крем-мыло 1л", "GP", 1.3, 1.0, 10, "PF_CREAM"),
            "GP_CREAM_5L": ("Крем-мыло 5л", "GP", 1.3, 5.0, 1, "PF_CREAM"),
            "GP_DISH_1L": ("Средство для мытья посуды 1л", "GP", 1.0, 1.0, 5, "PF_DISH"),
            "GP_ANTISEPTIC_10L": ("Антисептик 10л", "GP", 0.8, 10.0, 1, "PF_ANTISEPTIC"),
        }
        
        for code, (name, ptype, viscosity, bottle_vol, fill_speed, pf_code) in products_gp.items():
            result = await session.execute(text("""
                INSERT INTO product (organization_id, code, name, type, viscosity_coeff, 
                                   bottle_volume_l, fill_speed_per_min, parent_pf_id)
                VALUES (:org_id, :code, :name, :type, :viscosity, :bottle_vol, :fill_speed, :pf_id)
                RETURNING id
            """), {"org_id": ORG_ID, "code": code, "name": name, "type": ptype,
                   "viscosity": viscosity, "bottle_vol": bottle_vol, "fill_speed": fill_speed,
                   "pf_id": product_ids[pf_code]})
            # ИСПРАВЛЕНИЕ: сохраняем ID готовой продукции в тот же словарь
            product_ids[code] = result.scalar()
        
        await session.commit()
        print(f"✅ Создано {len(products_pf) + len(products_gp)} продуктов")
        
        # 5. Оборудование
        print("⚙️ Создание оборудования...")
        reactors = {
            "REACTOR_1": ("Реактор 1", "REACTOR", 5000, 1.0, "standard"),
            "REACTOR_2": ("Реактор 2", "REACTOR", 10000, 1.2, "high_speed"),
            "REACTOR_3": ("Реактор 3", "REACTOR", 8000, 1.1, "standard"),
            "REACTOR_4": ("Реактор 4", "REACTOR", 5000, 0.9, "low_speed"),
        }
        
        equipment_ids = {}
        for code, (name, etype, volume, speed, mixer) in reactors.items():
            result = await session.execute(text("""
                INSERT INTO equipment (organization_id, name, type, volume_kg, speed_coeff, mixer_type)
                VALUES (:org_id, :name, :type, :volume, :speed, :mixer)
                RETURNING id
            """), {"org_id": ORG_ID, "name": name, "type": etype, 
                   "volume": volume, "speed": speed, "mixer": mixer})
            equipment_ids[code] = result.scalar()
        
        result = await session.execute(text("""
            INSERT INTO equipment (organization_id, name, type, volume_kg)
            VALUES (:org_id, :name, :type, :volume)
            RETURNING id
        """), {"org_id": ORG_ID, "name": "Бойлер", "type": "BOILER", "volume": 2000})
        equipment_ids["BOILER"] = result.scalar()
        
        result = await session.execute(text("""
            INSERT INTO equipment (organization_id, name, type, volume_kg, speed_coeff)
            VALUES (:org_id, :name, :type, :volume, :speed)
            RETURNING id
        """), {"org_id": ORG_ID, "name": "Накопительная емкость 1", "type": "TANK", 
               "volume": 5000, "speed": 1.0})
        equipment_ids["TANK_1"] = result.scalar()
        
        lines = {
            "LINE_1": ("Линия 1 (1л)", "FILLING_LINE", 10),
            "LINE_2": ("Линия 2 (5/10л)", "FILLING_LINE", 5),
            "LINE_3": ("Линия 3 (ручной слив 10л)", "MANUAL_STATION", 0.2),
        }
        
        for code, (name, etype, speed) in lines.items():
            result = await session.execute(text("""
                INSERT INTO equipment (organization_id, name, type, speed_coeff)
                VALUES (:org_id, :name, :type, :speed)
                RETURNING id
            """), {"org_id": ORG_ID, "name": name, "type": etype, "speed": speed})
            equipment_ids[code] = result.scalar()
        
        await session.commit()
        print(f"✅ Создано {len(equipment_ids)} единиц оборудования")
        
        # 6. Матрица совместимости
        print("🔗 Создание матрицы совместимости...")
        capabilities = [
            ("REACTOR_1", "PF_CREAM", 0.70),
            ("REACTOR_2", "PF_CREAM", 0.70),
            ("REACTOR_2", "PF_DISH", 0.70),
            ("REACTOR_3", "PF_DISH", 0.70),
            ("REACTOR_3", "PF_ANTISEPTIC", 0.70),
            ("REACTOR_4", "PF_ANTISEPTIC", 0.70),
        ]
        
        for eq_code, prod_code, max_fill in capabilities:
            await session.execute(text("""
                INSERT INTO equipment_capability (organization_id, equipment_id, product_id, max_fill_percent)
                VALUES (:org_id, :eq_id, :prod_id, :max_fill)
            """), {"org_id": ORG_ID, "eq_id": equipment_ids[eq_code], 
                   "prod_id": product_ids[prod_code], "max_fill": max_fill})
        
        await session.commit()
        
        # 7. Рецептуры
        print("📋 Создание рецептур...")
        recipes = {
            "PF_CREAM": [("WATER", 85), ("SALT", 5), ("FRAGRANCE", 2), ("GLYCERIN", 8)],
            "PF_DISH": [("WATER", 70), ("SALT", 15), ("FRAGRANCE", 5), ("BETAINE", 6), ("ALCOHOL", 4)],
            "PF_ANTISEPTIC": [("WATER", 60), ("ALCOHOL", 35), ("CHLORIDE", 5)],
        }
        
        for pf_code, ingredients in recipes.items():
            result = await session.execute(text("""
                INSERT INTO recipe (organization_id, product_id, base_volume_kg)
                VALUES (:org_id, :prod_id, :base_vol)
                RETURNING id
            """), {"org_id": ORG_ID, "prod_id": product_ids[pf_code], "base_vol": 100})
            recipe_id = result.scalar()
            
            for mat_code, qty in ingredients:
                await session.execute(text("""
                    INSERT INTO recipe_item (recipe_id, material_id, qty_per_base)
                    VALUES (:recipe_id, :mat_id, :qty)
                """), {"recipe_id": recipe_id, "mat_id": material_ids[mat_code], "qty": qty})
        
        await session.commit()
        print(f"✅ Создано {len(recipes)} рецептур")
        
        # 8. Технологические карты
        print("📝 Создание технологических карт...")
        
        ops_cream = [
            (1, "Загрузка сырья (вода)", 60, False, False, True, False, "water_loading", None),
            (2, "Нагрев воды", 120, True, False, False, False, "heating", None),
            (3, "Перемешивание", 90, False, False, True, False, "mixing", "GROUP1"),
            (4, "Охлаждение 80->60C", 120, False, True, False, False, "cooling", "GROUP1"),
            (5, "Лабораторный анализ", 30, False, False, False, True, None, None),
            (6, "Загрузка доп. сырья", 30, False, False, True, False, "water_loading", None),
            (7, "Перемешивание (2 этап)", 60, False, False, True, False, "mixing", "GROUP2"),
            (8, "Охлаждение 60->40C", 120, False, True, False, False, "cooling", "GROUP2"),
            (9, "Лабораторный анализ (финал)", 30, False, False, False, True, None, None),
            (10, "Перекачка в накопительную емкость", 60, False, False, True, False, "pumping", None),
            (11, "Промывка реактора", 90, False, False, True, False, "washing", None),
        ]
        
        for order, name, duration, needs_boiler, needs_cooling, needs_operator, needs_lab, formula, group in ops_cream:
            await session.execute(text("""
                INSERT INTO operation_template (organization_id, product_id, stage_order, name, 
                    base_duration_mins, needs_boiler, needs_cooling_zone, needs_operator, needs_lab,
                    duration_formula, parallel_group_id)
                VALUES (:org_id, :prod_id, :order, :name, :duration, :boiler, :cooling, :operator, :lab, :formula, :group)
            """), {"org_id": ORG_ID, "prod_id": product_ids["PF_CREAM"], "order": order,
                   "name": name, "duration": duration, "boiler": needs_boiler,
                   "cooling": needs_cooling, "operator": needs_operator, "lab": needs_lab,
                   "formula": formula, "group": group})
        
        ops_dish = [
            (1, "Загрузка сырья (вода)", 60, False, False, True, False, "water_loading", None),
            (2, "Перемешивание", 120, False, False, True, False, "mixing", "GROUP1"),
            (3, "Охлаждение 90->50C", 90, False, True, False, False, "cooling", "GROUP1"),
            (4, "Лабораторный анализ", 30, False, False, False, True, None, None),
            (5, "Перемешивание (2 этап)", 60, False, False, True, False, "mixing", "GROUP2"),
            (6, "Охлаждение 50->30C", 90, False, True, False, False, "cooling", "GROUP2"),
            (7, "Лабораторный анализ (финал)", 30, False, False, False, True, None, None),
            (8, "Промывка реактора", 90, False, False, True, False, "washing", None),
        ]
        
        for order, name, duration, needs_boiler, needs_cooling, needs_operator, needs_lab, formula, group in ops_dish:
            await session.execute(text("""
                INSERT INTO operation_template (organization_id, product_id, stage_order, name, 
                    base_duration_mins, needs_boiler, needs_cooling_zone, needs_operator, needs_lab,
                    duration_formula, parallel_group_id)
                VALUES (:org_id, :prod_id, :order, :name, :duration, :boiler, :cooling, :operator, :lab, :formula, :group)
            """), {"org_id": ORG_ID, "prod_id": product_ids["PF_DISH"], "order": order,
                   "name": name, "duration": duration, "boiler": needs_boiler,
                   "cooling": needs_cooling, "operator": needs_operator, "lab": needs_lab,
                   "formula": formula, "group": group})
        
        ops_antiseptic = [
            (1, "Загрузка сырья (вода)", 60, False, False, True, False, "water_loading", None),
            (2, "Перемешивание", 60, False, False, True, False, "mixing", None),
            (3, "Лабораторный анализ", 30, False, False, False, True, None, None),
            (4, "Загрузка доп. сырья", 30, False, False, True, False, "water_loading", None),
            (5, "Перемешивание (2 этап)", 30, False, False, True, False, "mixing", None),
            (6, "Лабораторный анализ (финал)", 30, False, False, False, True, None, None),
            (7, "Перекачка в накопительную емкость", 45, False, False, True, False, "pumping", None),
            (8, "Промывка реактора", 30, False, False, True, False, "washing", None),
        ]
        
        for order, name, duration, needs_boiler, needs_cooling, needs_operator, needs_lab, formula, group in ops_antiseptic:
            await session.execute(text("""
                INSERT INTO operation_template (organization_id, product_id, stage_order, name, 
                    base_duration_mins, needs_boiler, needs_cooling_zone, needs_operator, needs_lab,
                    duration_formula, parallel_group_id)
                VALUES (:org_id, :prod_id, :order, :name, :duration, :boiler, :cooling, :operator, :lab, :formula, :group)
            """), {"org_id": ORG_ID, "prod_id": product_ids["PF_ANTISEPTIC"], "order": order,
                   "name": name, "duration": duration, "boiler": needs_boiler,
                   "cooling": needs_cooling, "operator": needs_operator, "lab": needs_lab,
                   "formula": formula, "group": group})
        
        await session.commit()
        print("✅ Технологические карты созданы")
        
        # 9. Матрица замывки
        print("🧼 Создание матрицы замывки...")
        pf_codes = ["PF_CREAM", "PF_DISH", "PF_ANTISEPTIC"]
        for from_code in pf_codes:
            for to_code in pf_codes:
                setup_time = 30 if from_code == to_code else 90
                await session.execute(text("""
                    INSERT INTO setup_matrix (organization_id, from_product_id, to_product_id, setup_mins)
                    VALUES (:org_id, :from_id, :to_id, :time)
                """), {"org_id": ORG_ID, "from_id": product_ids[from_code],
                       "to_id": product_ids[to_code], "time": setup_time})
        
        await session.commit()
        
        # 10. Календарь простоев
        print("📅 Создание календаря простоев...")
        weekends = [
            ("2026-09-05", "2026-09-07"),
            ("2026-09-12", "2026-09-14"),
            ("2026-09-19", "2026-09-21"),
            ("2026-09-26", "2026-09-28"),
        ]
        
        for start, end in weekends:
            start_dt = parse_dt(start, "00:00:00")
            end_dt = parse_dt(end, "00:00:00")
            
            await session.execute(text("""
                INSERT INTO calendar_event (organization_id, event_type, starts_at, ends_at, comment)
                VALUES (:org_id, 'WEEKEND', :start, :end, 'Выходные')
            """), {
                "org_id": ORG_ID,
                "start": start_dt,
                "end": end_dt
            })
        
        repair_start = parse_dt("2026-09-10", "00:00:00")
        repair_end = parse_dt("2026-09-21", "00:00:00")
        
        await session.execute(text("""
            INSERT INTO calendar_event (organization_id, equipment_id, event_type, starts_at, ends_at, comment)
            VALUES (:org_id, :eq_id, 'REPAIR', :start, :end, 'Плановый ремонт')
        """), {"org_id": ORG_ID, "eq_id": equipment_ids["REACTOR_3"], "start": repair_start, "end": repair_end})
        
        await session.commit()
        print("✅ Календарь создан")
        
        # 11. Производственные заказы
        print("📦 Создание производственных заказов...")
        orders = {
            "GP_CREAM_1L": (20000, "2026-09-30"),
            "GP_CREAM_5L": (5000, "2026-09-30"),
            "GP_DISH_1L": (15000, "2026-09-30"),
            "GP_ANTISEPTIC_10L": (8000, "2026-09-30"),
        }
        
        order_ids = {}
        for gp_code, (qty, due_date) in orders.items():
            due_dt = parse_dt(due_date, "23:59:59")
            
            result = await session.execute(text("""
                INSERT INTO production_order (organization_id, product_id, target_qty, due_date, priority)
                VALUES (:org_id, :prod_id, :qty, :due, 5)
                RETURNING id
            """), {
                "org_id": ORG_ID, 
                "prod_id": product_ids[gp_code], # Теперь этот ключ существует!
                "qty": qty, 
                "due": due_dt
            })
            order_ids[gp_code] = result.scalar()
        
        await session.commit()
        
        # 12. Партии
        print("🔬 Создание партий...")
        
        # Крем-мыло 1л
        for i in range(5):
            await session.execute(text("""
                INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id)
                VALUES (:org_id, :order_id, :prod_id, 3500, :eq_id)
            """), {"org_id": ORG_ID, "order_id": order_ids["GP_CREAM_1L"], 
                   "prod_id": product_ids["PF_CREAM"], "eq_id": equipment_ids["REACTOR_1"]})
        
        await session.execute(text("""
            INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id)
            VALUES (:org_id, :order_id, :prod_id, 2500, :eq_id)
        """), {"org_id": ORG_ID, "order_id": order_ids["GP_CREAM_1L"], 
               "prod_id": product_ids["PF_CREAM"], "eq_id": equipment_ids["REACTOR_1"]})
        
        # Крем-мыло 5л
        for i in range(3):
            await session.execute(text("""
                INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id)
                VALUES (:org_id, :order_id, :prod_id, 7000, :eq_id)
            """), {"org_id": ORG_ID, "order_id": order_ids["GP_CREAM_5L"], 
                   "prod_id": product_ids["PF_CREAM"], "eq_id": equipment_ids["REACTOR_2"]})
        
        await session.execute(text("""
            INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id)
            VALUES (:org_id, :order_id, :prod_id, 4000, :eq_id)
        """), {"org_id": ORG_ID, "order_id": order_ids["GP_CREAM_5L"], 
               "prod_id": product_ids["PF_CREAM"], "eq_id": equipment_ids["REACTOR_2"]})
        
        # Средство для мытья посуды
        await session.execute(text("""
            INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id)
            VALUES (:org_id, :order_id, :prod_id, 7000, :eq_id)
        """), {"org_id": ORG_ID, "order_id": order_ids["GP_DISH_1L"], 
               "prod_id": product_ids["PF_DISH"], "eq_id": equipment_ids["REACTOR_2"]})
        
        await session.execute(text("""
            INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id)
            VALUES (:org_id, :order_id, :prod_id, 7000, :eq_id)
        """), {"org_id": ORG_ID, "order_id": order_ids["GP_DISH_1L"], 
               "prod_id": product_ids["PF_DISH"], "eq_id": equipment_ids["REACTOR_2"]})
        
        await session.execute(text("""
            INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id)
            VALUES (:org_id, :order_id, :prod_id, 1000, :eq_id)
        """), {"org_id": ORG_ID, "order_id": order_ids["GP_DISH_1L"], 
               "prod_id": product_ids["PF_DISH"], "eq_id": equipment_ids["REACTOR_3"]})
        
        # Антисептик
        for i in range(10):
            await session.execute(text("""
                INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id)
                VALUES (:org_id, :order_id, :prod_id, 5600, :eq_id)
            """), {"org_id": ORG_ID, "order_id": order_ids["GP_ANTISEPTIC_10L"], 
                   "prod_id": product_ids["PF_ANTISEPTIC"], "eq_id": equipment_ids["REACTOR_3"]})
        
        for i in range(6):
            await session.execute(text("""
                INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id)
                VALUES (:org_id, :order_id, :prod_id, 3500, :eq_id)
            """), {"org_id": ORG_ID, "order_id": order_ids["GP_ANTISEPTIC_10L"], 
                   "prod_id": product_ids["PF_ANTISEPTIC"], "eq_id": equipment_ids["REACTOR_4"]})
        
        await session.execute(text("""
            INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id)
            VALUES (:org_id, :order_id, :prod_id, 2000, :eq_id)
        """), {"org_id": ORG_ID, "order_id": order_ids["GP_ANTISEPTIC_10L"], 
               "prod_id": product_ids["PF_ANTISEPTIC"], "eq_id": equipment_ids["REACTOR_4"]})
        
        await session.commit()
        print("✅ Партии созданы")
        
        print("\n" + "="*50)
        print("🎉 ВСЕ ДАННЫЕ УСПЕШНО ЗАГРУЖЕНЫ!")
        print("="*50)
        
        # Проверка
        result = await session.execute(text("SELECT COUNT(*) FROM batch"))
        batch_count = result.scalar()
        
        result = await session.execute(text("SELECT COUNT(*) FROM product"))
        product_count = result.scalar()
        
        result = await session.execute(text("SELECT COUNT(*) FROM equipment"))
        equipment_count = result.scalar()
        
        print(f"\n📊 Статистика:")
        print(f"   - Продуктов: {product_count}")
        print(f"   - Оборудования: {equipment_count}")
        print(f"   - Партий: {batch_count}")
        print(f"   - Организация: {ORG_ID}")

if __name__ == "__main__":
    asyncio.run(main())