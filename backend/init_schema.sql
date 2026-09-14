-- ==========================================
-- APS СИСТЕМА: ПОЛНАЯ СХЕМА БД
-- PostgreSQL 17
-- Для производства бытовой химии
-- ==========================================

-- ==========================================
-- 1. МУЛЬТИ-ТЕНАНТНОСТЬ
-- ==========================================

CREATE TABLE organization (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    comment TEXT
);
COMMENT ON TABLE organization IS 'Организации (тенанты). Все бизнес-данные привязаны к организации для поддержки мульти-тенантной архитектуры.';
COMMENT ON COLUMN organization.id IS 'Уникальный идентификатор организации';
COMMENT ON COLUMN organization.name IS 'Полное наименование организации (например, "ООО Бытовая Химия")';
COMMENT ON COLUMN organization.slug IS 'URL-friendly идентификатор организации (латиницей, без пробелов)';
COMMENT ON COLUMN organization.settings IS 'JSONB поле для хранения глобальных настроек организации (рабочее время, лимиты, параметры по умолчанию)';
COMMENT ON COLUMN organization.is_active IS 'Флаг активности организации. Если FALSE - организация заблокирована';
COMMENT ON COLUMN organization.created_at IS 'Дата и время создания записи об организации';
COMMENT ON COLUMN organization.comment IS 'Дополнительные комментарии или примечания к организации';

CREATE TABLE app_user (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    email VARCHAR(200) NOT NULL,
    full_name VARCHAR(200),
    role VARCHAR(30) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE (organization_id, email)
);
COMMENT ON TABLE app_user IS 'Пользователи системы с привязкой к организации и ролью. Каждый пользователь принадлежит одной организации.';
COMMENT ON COLUMN app_user.id IS 'Уникальный идентификатор пользователя';
COMMENT ON COLUMN app_user.organization_id IS 'Ссылка на организацию, к которой принадлежит пользователь';
COMMENT ON COLUMN app_user.email IS 'Email пользователя (уникален в пределах одной организации)';
COMMENT ON COLUMN app_user.full_name IS 'Полное имя пользователя (ФИО)';
COMMENT ON COLUMN app_user.role IS 'Роль пользователя в системе: ADMIN (администратор), PLANNER (планировщик), MASTER (мастер смены), LAB (лаборант), VIEWER (наблюдатель)';
COMMENT ON COLUMN app_user.is_active IS 'Флаг активности пользователя. Если FALSE - пользователь заблокирован и не может войти в систему';

-- ==========================================
-- 2. СПРАВОЧНИКИ ОБОРУДОВАНИЯ И РЕСУРСОВ
-- ==========================================

CREATE TABLE equipment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(30) NOT NULL,
    volume_kg NUMERIC(10,2),
    speed_coeff NUMERIC(6,3) DEFAULT 1.0,
    mixer_type VARCHAR(50),
    pump_power_kw NUMERIC(6,2),
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    comment TEXT
);
COMMENT ON TABLE equipment IS 'Оборудование производственной линии: реакторы, накопительные емкости, линии розлива, бойлеры, ручные посты. Привязано к организации.';
COMMENT ON COLUMN equipment.id IS 'Уникальный идентификатор единицы оборудования';
COMMENT ON COLUMN equipment.organization_id IS 'Ссылка на организацию, которой принадлежит оборудование';
COMMENT ON COLUMN equipment.name IS 'Наименование оборудования (например, "Реактор 1", "Линия розлива 2")';
COMMENT ON COLUMN equipment.type IS 'Тип оборудования: REACTOR (реактор), TANK (накопительная емкость), FILLING_LINE (линия розлива), BOILER (бойлер), MANUAL_STATION (ручной пост)';
COMMENT ON COLUMN equipment.volume_kg IS 'Максимальный объем загрузки оборудования в килограммах (для реакторов и емкостей). Для линий розлива может быть NULL';
COMMENT ON COLUMN equipment.speed_coeff IS 'Коэффициент скорости работы оборудования. Влияет на время выполнения операций (набора воды, слива, перемешивания). 1.0 - стандартная скорость';
COMMENT ON COLUMN equipment.mixer_type IS 'Тип мешалки в реакторе: standard (стандартная), high_speed (высокоскоростная), low_speed (низкоскоростная). Влияет на время перемешивания';
COMMENT ON COLUMN equipment.pump_power_kw IS 'Мощность насоса в киловаттах (для емкостей и линий с насосами). Влияет на скорость перекачки';
COMMENT ON COLUMN equipment.is_active IS 'Флаг доступности оборудования. Если FALSE - оборудование выведено из эксплуатации или на ремонте';
COMMENT ON COLUMN equipment.metadata IS 'JSONB поле для хранения дополнительных параметров оборудования (температурный режим, максимальное давление и т.п.)';
COMMENT ON COLUMN equipment.comment IS 'Дополнительные комментарии или примечания к оборудованию';

-- Связи между оборудованием (реактор -> линия, реактор -> емкость)
CREATE TABLE equipment_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    from_equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    to_equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    is_direct BOOLEAN DEFAULT TRUE,
    UNIQUE (from_equipment_id, to_equipment_id)
);
COMMENT ON TABLE equipment_link IS 'Физические связи между оборудованием. Определяет, из какого оборудования можно сливать продукт в какое другое оборудование (реактор -> линия, реактор -> емкость).';
COMMENT ON COLUMN equipment_link.id IS 'Уникальный идентификатор связи';
COMMENT ON COLUMN equipment_link.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN equipment_link.from_equipment_id IS 'Исходное оборудование (откуда сливается продукт: реактор или емкость)';
COMMENT ON COLUMN equipment_link.to_equipment_id IS 'Целевое оборудование (куда сливается продукт: линия розлива или емкость)';
COMMENT ON COLUMN equipment_link.is_direct IS 'Флаг прямого слива. Если TRUE - продукт может сливаться напрямую, минуя промежуточные емкости';

-- Глобальные ресурсы с ограничением параллельности
CREATE TABLE resource_pool (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL,
    capacity INT NOT NULL,
    comment TEXT
);
COMMENT ON TABLE resource_pool IS 'Переиспользуемые ресурсы с ограничением параллельности. Например, аппаратчики (людей меньше чем реакторов), зона охлаждения (максимум 2 реактора одновременно).';
COMMENT ON COLUMN resource_pool.id IS 'Уникальный идентификатор пула ресурсов';
COMMENT ON COLUMN resource_pool.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN resource_pool.name IS 'Наименование ресурса (например, "Аппаратчики реакторов", "Зона охлаждения площадка 1")';
COMMENT ON COLUMN resource_pool.type IS 'Тип ресурса: OPERATOR (аппаратчик/оператор), COOLING_ZONE (зона охлаждения), BOILER (бойлер), LAB (лаборант)';
COMMENT ON COLUMN resource_pool.capacity IS 'Максимальное количество одновременно используемых ресурсов этого типа. Например, 3 для аппаратчиков, 2 для зоны охлаждения';
COMMENT ON COLUMN resource_pool.comment IS 'Дополнительные комментарии к ресурсу';

-- ==========================================
-- 3. МАТЕРИАЛЫ И ОСТАТКИ
-- ==========================================

CREATE TABLE material (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    unit VARCHAR(20) NOT NULL DEFAULT 'kg',
    category VARCHAR(30) NOT NULL,
    comment TEXT,
    UNIQUE (organization_id, code)
);
COMMENT ON TABLE material IS 'Справочник материалов: сырье (вода, соль, отдушки), упаковка (бутылки, канистры), этикетки, крышки. Привязан к организации.';
COMMENT ON COLUMN material.id IS 'Уникальный идентификатор материала';
COMMENT ON COLUMN material.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN material.code IS 'Код материала (артикул, SKU). Уникален в пределах организации';
COMMENT ON COLUMN material.name IS 'Наименование материала (например, "Вода", "Соль экстра", "Бутылка 1 литр")';
COMMENT ON COLUMN material.unit IS 'Единица измерения: kg (килограммы), pc (штуки), l (литры)';
COMMENT ON COLUMN material.category IS 'Категория материала: RAW (сырье для производства), PACKAGING (тара/упаковка), LABEL (этикетки/маркировка)';
COMMENT ON COLUMN material.comment IS 'Дополнительные комментарии к материалу';

CREATE TABLE material_stock (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    material_id UUID NOT NULL REFERENCES material(id) ON DELETE CASCADE,
    qty NUMERIC(12,3) NOT NULL DEFAULT 0,
    reserved_qty NUMERIC(12,3) DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE material_stock IS 'Текущие остатки материалов на складе. Одна запись на каждый материал в организации.';
COMMENT ON COLUMN material_stock.id IS 'Уникальный идентификатор записи об остатке';
COMMENT ON COLUMN material_stock.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN material_stock.material_id IS 'Ссылка на материал';
COMMENT ON COLUMN material_stock.qty IS 'Текущее физическое количество материала на складе';
COMMENT ON COLUMN material_stock.reserved_qty IS 'Количество материала, зарезервированное под запланированные партии (не доступно для нового планирования)';
COMMENT ON COLUMN material_stock.updated_at IS 'Дата и время последнего обновления остатка';

CREATE TABLE material_supply (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    material_id UUID NOT NULL REFERENCES material(id) ON DELETE CASCADE,
    expected_at TIMESTAMPTZ NOT NULL,
    qty NUMERIC(12,3) NOT NULL,
    status VARCHAR(20) DEFAULT 'PLANNED'
);
COMMENT ON TABLE material_supply IS 'График поставок сырья от поставщиков. Используется при планировании для учета будущего поступления материалов.';
COMMENT ON COLUMN material_supply.id IS 'Уникальный идентификатор поставки';
COMMENT ON COLUMN material_supply.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN material_supply.material_id IS 'Ссылка на материал, который будет поставлен';
COMMENT ON COLUMN material_supply.expected_at IS 'Ожидаемая дата и время поступления материала на склад';
COMMENT ON COLUMN material_supply.qty IS 'Ожидаемое количество материала в поставке';
COMMENT ON COLUMN material_supply.status IS 'Статус поставки: PLANNED (запланирована), CONFIRMED (подтверждена поставщиком), RECEIVED (получена на складе)';

-- ==========================================
-- 4. ПРОДУКЦИЯ (ПФ и ГП) И РЕЦЕПТУРЫ
-- ==========================================

CREATE TABLE product (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(10) NOT NULL,
    viscosity_coeff NUMERIC(5,2) DEFAULT 1.0,
    requires_heating BOOLEAN DEFAULT FALSE,
    bottle_volume_l NUMERIC(5,2),
    fill_speed_per_min NUMERIC(8,2),
    parent_pf_id UUID REFERENCES product(id),
    comment TEXT,
    UNIQUE (organization_id, code)
);
COMMENT ON TABLE product IS 'Продукция: полуфабрикаты (ПФ) и готовая продукция (ГП). ПФ - это смесь в реакторе, ГП - разлитая продукция. ГП ссылается на свой ПФ.';
COMMENT ON COLUMN product.id IS 'Уникальный идентификатор продукта';
COMMENT ON COLUMN product.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN product.code IS 'Код продукта (артикул). Уникален в пределах организации';
COMMENT ON COLUMN product.name IS 'Наименование продукта (например, "Крем-мыло", "Средство для мытья посуды", "Крем-мыло 1л")';
COMMENT ON COLUMN product.type IS 'Тип продукта: PF (полуфабрикат - смесь для производства), GP (готовая продукция - разлитый товар)';
COMMENT ON COLUMN product.viscosity_coeff IS 'Коэффициент вязкости продукта. Влияет на время перемешивания, слива и перекачки. 1.0 - стандартная вязкость, >1.0 - более вязкий';
COMMENT ON COLUMN product.requires_heating IS 'Флаг необходимости нагрева. Если TRUE - продукт требует этапа нагрева в технологической карте';
COMMENT ON COLUMN product.bottle_volume_l IS 'Объем тары в литрах (только для ГП). Например, 1.0, 5.0, 10.0. Для ПФ - NULL';
COMMENT ON COLUMN product.fill_speed_per_min IS 'Скорость розлива в бутылках/минуту (для ГП). Зависит от вязкости и объема тары';
COMMENT ON COLUMN product.parent_pf_id IS 'Ссылка на родительский полуфабрикат (только для ГП). Например, "Крем-мыло 1л" производится из ПФ "Крем-мыло"';
COMMENT ON COLUMN product.comment IS 'Дополнительные комментарии к продукту';

CREATE TABLE recipe (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    base_volume_kg NUMERIC(10,2) NOT NULL,
    comment TEXT
);
COMMENT ON TABLE recipe IS 'Рецептура полуфабриката. Определяет пропорции компонентов на базовый объем (обычно 100 кг). Из рецептуры рассчитывается количество сырья для партии любого объема.';
COMMENT ON COLUMN recipe.id IS 'Уникальный идентификатор рецептуры';
COMMENT ON COLUMN recipe.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN recipe.product_id IS 'Ссылка на полуфабрикат, для которого определена рецептура';
COMMENT ON COLUMN recipe.base_volume_kg IS 'Базовый объем рецептуры в килограммах (обычно 100 кг). Пропорции компонентов указаны на этот объем';
COMMENT ON COLUMN recipe.comment IS 'Дополнительные комментарии к рецептуре';

CREATE TABLE recipe_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_id UUID NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    material_id UUID NOT NULL REFERENCES material(id),
    qty_per_base NUMERIC(10,3) NOT NULL
);
COMMENT ON TABLE recipe_item IS 'Компоненты рецептуры. Список материалов и их количество на базовый объем. Например, на 100 кг ПФ нужно 85 кг воды, 5 кг соли и т.д.';
COMMENT ON COLUMN recipe_item.id IS 'Уникальный идентификатор компонента рецептуры';
COMMENT ON COLUMN recipe_item.recipe_id IS 'Ссылка на рецептуру, к которой относится компонент';
COMMENT ON COLUMN recipe_item.material_id IS 'Ссылка на материал (сырье)';
COMMENT ON COLUMN recipe_item.qty_per_base IS 'Количество материала на базовый объем рецептуры (в кг или шт). Например, 85.0 кг воды на 100 кг ПФ';

-- Матрица совместимости: какой ПФ можно варить в каком реакторе / на какой линии
CREATE TABLE equipment_capability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    max_fill_percent NUMERIC(3,2) DEFAULT 0.80,
    UNIQUE (organization_id, equipment_id, product_id)
);
COMMENT ON TABLE equipment_capability IS 'Матрица совместимости оборудования и продукции. Определяет, какой полуфабрикат можно производить на каком оборудовании (реакторе, линии).';
COMMENT ON COLUMN equipment_capability.id IS 'Уникальный идентификатор записи совместимости';
COMMENT ON COLUMN equipment_capability.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN equipment_capability.equipment_id IS 'Ссылка на оборудование (реактор или линию розлива)';
COMMENT ON COLUMN equipment_capability.product_id IS 'Ссылка на продукт (ПФ или ГП)';
COMMENT ON COLUMN equipment_capability.max_fill_percent IS 'Максимальный процент загрузки оборудования для этого продукта. Например, 0.70 (70%) для крем-мыла из-за вспенивания';

-- ==========================================
-- 5. ТЕХНОЛОГИЧЕСКИЕ КАРТЫ
-- ==========================================

CREATE TABLE operation_template (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    stage_order INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    base_duration_mins INT NOT NULL,
    is_setup BOOLEAN DEFAULT FALSE,
    is_parallel_group BOOLEAN DEFAULT FALSE,
    parallel_group_id VARCHAR(50),
    needs_boiler BOOLEAN DEFAULT FALSE,
    needs_cooling_zone BOOLEAN DEFAULT FALSE,
    needs_operator BOOLEAN DEFAULT FALSE,
    needs_lab BOOLEAN DEFAULT FALSE,
    duration_formula VARCHAR(200),
    comment TEXT
);
COMMENT ON TABLE operation_template IS 'Технологическая карта: этапы производства полуфабриката. Определяет последовательность операций (загрузка, нагрев, перемешивание, охлаждение, лаборатория, перекачка, замыв).';
COMMENT ON COLUMN operation_template.id IS 'Уникальный идентификатор этапа технологической карты';
COMMENT ON COLUMN operation_template.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN operation_template.product_id IS 'Ссылка на полуфабрикат, для которого определена операция';
COMMENT ON COLUMN operation_template.stage_order IS 'Порядковый номер этапа в технологической карте. Определяет последовательность выполнения (1, 2, 3...)';
COMMENT ON COLUMN operation_template.name IS 'Наименование этапа: "Загрузка воды", "Нагрев", "Перемешивание", "Охлаждение", "Лабораторный анализ", "Перекачка", "Промывка"';
COMMENT ON COLUMN operation_template.base_duration_mins IS 'Базовая длительность этапа в минутах. Может корректироваться по формуле в зависимости от объема, оборудования, вязкости';
COMMENT ON COLUMN operation_template.is_setup IS 'Флаг этапа переналадки/замывки. Если TRUE - это не производственная операция, а подготовка оборудования';
COMMENT ON COLUMN operation_template.is_parallel_group IS 'Флаг параллельного выполнения. Если TRUE - этап может выполняться параллельно с другими этапами той же группы';
COMMENT ON COLUMN operation_template.parallel_group_id IS 'Идентификатор группы параллельных этапов. Этапы с одинаковым ID выполняются параллельно';
COMMENT ON COLUMN operation_template.needs_boiler IS 'Флаг необходимости бойлера. Если TRUE - этап требует ресурс бойлера (нагрев воды)';
COMMENT ON COLUMN operation_template.needs_cooling_zone IS 'Флаг необходимости зоны охлаждения. Если TRUE - этап требует ресурс зоны охлаждения (ограничение - макс. 2 реактора одновременно)';
COMMENT ON COLUMN operation_template.needs_operator IS 'Флаг необходимости аппаратчика. Если TRUE - этап требует участия оператора (ограничение по количеству людей)';
COMMENT ON COLUMN operation_template.needs_lab IS 'Флаг необходимости лаборанта. Если TRUE - этап требует проверки лабораторией';
COMMENT ON COLUMN operation_template.duration_formula IS 'Имя формулы/стратегии расчета длительности (для точек расширения). Например, "water_loading", "heating", "mixing"';
COMMENT ON COLUMN operation_template.comment IS 'Дополнительные комментарии к этапу';

-- Матрица времени замывки: ПФ_пред -> ПФ_след = время
CREATE TABLE setup_matrix (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    from_product_id UUID NOT NULL REFERENCES product(id),
    to_product_id UUID NOT NULL REFERENCES product(id),
    setup_mins INT NOT NULL,
    UNIQUE (organization_id, from_product_id, to_product_id)
);
COMMENT ON TABLE setup_matrix IS 'Матрица времени переналадки (замывки) при переходе между полуфабрикатами. Определяет, сколько времени нужно на промывку реактора при смене продукта.';
COMMENT ON COLUMN setup_matrix.id IS 'Уникальный идентификатор записи матрицы';
COMMENT ON COLUMN setup_matrix.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN setup_matrix.from_product_id IS 'Предыдущий полуфабрикат (который производился)';
COMMENT ON COLUMN setup_matrix.to_product_id IS 'Следующий полуфабрикат (который будет производиться)';
COMMENT ON COLUMN setup_matrix.setup_mins IS 'Время переналадки/замывки в минутах. Например, 30 мин если тот же ПФ, 90 мин (1.5 часа) если другой ПФ';

-- ==========================================
-- 6. КАЛЕНДАРЬ (выходные, ремонты, аварии)
-- ==========================================

CREATE TABLE calendar_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    equipment_id UUID REFERENCES equipment(id) ON DELETE CASCADE,
    event_type VARCHAR(30) NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    comment TEXT,
    CONSTRAINT chk_dates CHECK (ends_at > starts_at)
);
COMMENT ON TABLE calendar_event IS 'Календарь простоев оборудования: выходные дни, плановые ремонты, аварийные остановки, перерывы на обед. Используется при планировании для исключения недоступного времени.';
COMMENT ON COLUMN calendar_event.id IS 'Уникальный идентификатор события';
COMMENT ON COLUMN calendar_event.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN calendar_event.equipment_id IS 'Ссылка на оборудование. Если NULL - событие относится ко всему производству (выходные, праздники)';
COMMENT ON COLUMN calendar_event.event_type IS 'Тип события: WEEKEND (выходной), REPAIR (плановый ремонт), BREAKDOWN (аварийная остановка), SHIFT_END (конец смены), LUNCH (обед)';
COMMENT ON COLUMN calendar_event.starts_at IS 'Дата и время начала простоя';
COMMENT ON COLUMN calendar_event.ends_at IS 'Дата и время окончания простоя';
COMMENT ON COLUMN calendar_event.comment IS 'Дополнительные комментарии к событию (причина простоя, ответственный и т.п.)';

-- ==========================================
-- 7. ПЛАНИРОВАНИЕ: ЗАКАЗЫ, ПАРТИИ, ГАНТ
-- ==========================================

CREATE TABLE production_order (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES product(id),
    target_qty NUMERIC(10,2) NOT NULL,
    due_date TIMESTAMPTZ NOT NULL,
    priority INT DEFAULT 5,
    status VARCHAR(20) DEFAULT 'PLANNED',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    comment TEXT
);
COMMENT ON TABLE production_order IS 'Заказ на производство готовой продукции. Определяет, сколько и к какому сроку нужно произвести. Один заказ разбивается на несколько партий ПФ.';
COMMENT ON COLUMN production_order.id IS 'Уникальный идентификатор производственного заказа';
COMMENT ON COLUMN production_order.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN production_order.product_id IS 'Ссылка на готовую продукцию (ГП), которую нужно произвести';
COMMENT ON COLUMN production_order.target_qty IS 'Целевое количество продукции (в бутылках/шт для ГП, в кг для ПФ)';
COMMENT ON COLUMN production_order.due_date IS 'Дедлайн - дата, не позже которой нужно выпустить продукцию';
COMMENT ON COLUMN production_order.priority IS 'Приоритет заказа: 1 - высший (срочно), 5 - средний, 10 - низкий. Влияет на очередность планирования';
COMMENT ON COLUMN production_order.status IS 'Статус заказа: PLANNED (запланирован), IN_PROGRESS (в производстве), DONE (выполнен), CANCELLED (отменен)';
COMMENT ON COLUMN production_order.created_at IS 'Дата и время создания заказа';
COMMENT ON COLUMN production_order.comment IS 'Дополнительные комментарии к заказу';

CREATE TABLE batch (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    order_id UUID NOT NULL REFERENCES production_order(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES product(id),
    volume_kg NUMERIC(10,2) NOT NULL,
    assigned_equipment_id UUID REFERENCES equipment(id),
    planned_start TIMESTAMPTZ,
    planned_end TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'NOT_STARTED',
    comment TEXT
);
COMMENT ON TABLE batch IS 'Производственная партия полуфабриката. Объем заказа разбивается на партии по объему реактора. Например, заказ 20000 кг разбивается на 4 партии по 5000 кг.';
COMMENT ON COLUMN batch.id IS 'Уникальный идентификатор партии';
COMMENT ON COLUMN batch.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN batch.order_id IS 'Ссылка на производственный заказ, к которому относится партия';
COMMENT ON COLUMN batch.product_id IS 'Ссылка на полуфабрикат (ПФ), который производится в партии';
COMMENT ON COLUMN batch.volume_kg IS 'Объем партии в килограммах. Рассчитывается с учетом максимального % загрузки реактора (обычно 70-80%)';
COMMENT ON COLUMN batch.assigned_equipment_id IS 'Назначенный реактор для производства партии. Определяется при планировании';
COMMENT ON COLUMN batch.planned_start IS 'Запланированное время начала производства партии';
COMMENT ON COLUMN batch.planned_end IS 'Запланированное время окончания производства партии';
COMMENT ON COLUMN batch.status IS 'Статус партии: NOT_STARTED (не начата), IN_PROGRESS (в процессе), COMPLETED (завершена), BLOCKED (заблокирована лабораторией)';
COMMENT ON COLUMN batch.comment IS 'Дополнительные комментарии к партии';

CREATE TABLE schedule_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    version_type VARCHAR(20) NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES app_user(id),
    comment TEXT
);
COMMENT ON TABLE schedule_version IS 'Версии производственного плана. Позволяет хранить историю планирования и сравнивать разные варианты (базовый план, после аварии, после перепланирования).';
COMMENT ON COLUMN schedule_version.id IS 'Уникальный идентификатор версии плана';
COMMENT ON COLUMN schedule_version.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN schedule_version.name IS 'Наименование версии (например, "План на сентябрь 2026 v1", "После аварии Реактор 4")';
COMMENT ON COLUMN schedule_version.version_type IS 'Тип версии: MONTHLY (объемно-календарный план на месяц/ОКП), SHIFT (посменный план), WHAT_IF (сценарий "что если")';
COMMENT ON COLUMN schedule_version.is_active IS 'Флаг активной версии. Только одна версия может быть активной (текущий план производства)';
COMMENT ON COLUMN schedule_version.created_at IS 'Дата и время создания версии плана';
COMMENT ON COLUMN schedule_version.created_by IS 'Ссылка на пользователя, создавшего версию плана';
COMMENT ON COLUMN schedule_version.comment IS 'Дополнительные комментарии к версии (причина перепланирования, изменения и т.п.)';

CREATE TABLE scheduled_task (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    schedule_version_id UUID NOT NULL REFERENCES schedule_version(id) ON DELETE CASCADE,
    batch_id UUID REFERENCES batch(id) ON DELETE CASCADE,
    operation_template_id UUID NOT NULL REFERENCES operation_template(id),
    equipment_id UUID NOT NULL REFERENCES equipment(id),
    resource_pool_id UUID REFERENCES resource_pool(id),
    planned_start TIMESTAMPTZ NOT NULL,
    planned_end TIMESTAMPTZ NOT NULL,
    actual_start TIMESTAMPTZ,
    actual_end TIMESTAMPTZ,
    is_pinned BOOLEAN DEFAULT FALSE,
    comment TEXT
);
COMMENT ON TABLE scheduled_task IS 'Задача на диаграмме Ганта. Конкретная операция (этап технологической карты) для партии на определенном оборудовании в запланированное время.';
COMMENT ON COLUMN scheduled_task.id IS 'Уникальный идентификатор задачи';
COMMENT ON COLUMN scheduled_task.organization_id IS 'Ссылка на организацию';
COMMENT ON COLUMN scheduled_task.schedule_version_id IS 'Ссылка на версию плана, к которой относится задача';
COMMENT ON COLUMN scheduled_task.batch_id IS 'Ссылка на партию, для которой выполняется операция';
COMMENT ON COLUMN scheduled_task.operation_template_id IS 'Ссылка на шаблон операции (этап технологической карты)';
COMMENT ON COLUMN scheduled_task.equipment_id IS 'Оборудование, на котором выполняется задача (реактор, линия, емкость)';
COMMENT ON COLUMN scheduled_task.resource_pool_id IS 'Глобальный ресурс, который занимает задача (аппаратчик, зона охлаждения, бойлер). Может быть NULL';
COMMENT ON COLUMN scheduled_task.planned_start IS 'Запланированное время начала задачи';
COMMENT ON COLUMN scheduled_task.planned_end IS 'Запланированное время окончания задачи';
COMMENT ON COLUMN scheduled_task.actual_start IS 'Фактическое время начала задачи. Заполняется мастером смены при старте';
COMMENT ON COLUMN scheduled_task.actual_end IS 'Фактическое время окончания задачи. Заполняется мастером смены при завершении';
COMMENT ON COLUMN scheduled_task.is_pinned IS 'Флаг закрепленной задачи. Если TRUE - задача зафиксирована пользователем на Ганте и не двигается при перепланировании';
COMMENT ON COLUMN scheduled_task.comment IS 'Дополнительные комментарии к задаче';

-- ==========================================
-- 8. ИНДЕКСЫ
-- ==========================================

-- GiST-индекс для быстрого поиска пересечений на одном оборудовании
-- ВАЖНО: используется tstzrange (не tsrange), т.к. поля planned_start/planned_end имеют тип TIMESTAMPTZ
CREATE INDEX idx_task_equipment_time
    ON scheduled_task USING GIST (
        organization_id,
        equipment_id,
        tstzrange(planned_start, planned_end)
    );
COMMENT ON INDEX idx_task_equipment_time IS 'GiST-индекс для быстрого поиска пересечений задач на одном оборудовании. Использует tstzrange для работы с TIMESTAMPTZ. Позволяет эффективно проверять конфликты расписания.';

-- Дополнительные индексы для ускорения запросов по организации
CREATE INDEX idx_equipment_org ON equipment(organization_id);
COMMENT ON INDEX idx_equipment_org IS 'Индекс для быстрого поиска оборудования по организации';

CREATE INDEX idx_product_org ON product(organization_id);
COMMENT ON INDEX idx_product_org IS 'Индекс для быстрого поиска продукции по организации';

CREATE INDEX idx_batch_org ON batch(organization_id);
COMMENT ON INDEX idx_batch_org IS 'Индекс для быстрого поиска партий по организации';

CREATE INDEX idx_scheduled_task_org ON scheduled_task(organization_id);
COMMENT ON INDEX idx_scheduled_task_org IS 'Индекс для быстрого поиска задач по организации';

CREATE INDEX idx_production_order_org ON production_order(organization_id);
COMMENT ON INDEX idx_production_order_org IS 'Индекс для быстрого поиска заказов по организации';

-- ==========================================
-- ГОТОВО! Схема создана.
-- ==========================================