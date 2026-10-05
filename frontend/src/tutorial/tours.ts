// frontend/src/tutorial/tours.ts
/**
 * Конфигурация интерактивных туров (Итерация 15.3).
 *
 * Совместимо с react-joyride@3.2.0.
 *
 * Общие опции тура (skipBeacon, showProgress, buttons, width, ...)
 * передаются один раз через `<Joyride options={COMMON_OPTIONS} />`
 * в App.tsx — здесь они НЕ дублируются.
 *
 * Шаги содержат только уникальные поля:
 * target, title, content, placement.
 *
 * Итерация 15.3 (fix): добавлено поле `stepRoutes` —
 * карта «индекс шага → URL». TutorialRunner использует её,
 * чтобы автоматически переходить на нужные страницы
 * перед показом шага. Без этого тур «застревает» на шаге,
 * где target находится на другой странице.
 */
import type {Props, Step} from 'react-joyride';
import type {Tour} from './types';

// ==========================================
// Тур 1: Первый план за 5 минут
// ==========================================

const gettingStartedSteps: Step[] = [
    {
        target: 'body',
        title: 'Добро пожаловать!',
        content:
            'Этот тур проведёт вас от входа до первого плана. ' +
            'Займёт ~5 минут. Можно пропустить в любой момент.',
        placement: 'center',
    },
    {
        target: '[data-tour-id="sidebar"]',
        title: 'Главное меню',
        content:
            'В левой панели — все разделы системы: справочники, ' +
            'планирование, диаграмма Ганта, смены, настройки.',
        placement: 'right',
    },
    {
        target: '[data-tour-id="menu-equipment"]',
        title: 'Оборудование',
        content:
            'Здесь вы управляете реакторами, линиями, танками. ' +
            'Проверьте, что все справочники заполнены.',
        placement: 'right',
    },
    {
        target: '[data-tour-id="menu-products"]',
        title: 'Продукты',
        content:
            'Здесь — полуфабрикаты (ПФ) и готовая продукция (ГП).',
        placement: 'right',
    },
    {
        target: '[data-tour-id="menu-orders"]',
        title: 'Заказы',
        content:
            'Здесь создаются производственные заказы и партии.',
        placement: 'right',
    },
    {
        target: '[data-tour-id="menu-schedule"]',
        title: 'Планирование',
        content:
            'Это ключевой раздел. Здесь строится план. ' +
            'Сейчас тур перейдёт на эту страницу.',
        placement: 'right',
    },
    {
        target: '[data-tour-id="build-plan-button"]',
        title: 'Кнопка «Построить план»',
        content:
            'Нажмите эту кнопку, чтобы запустить solver. ' +
            'Он рассчитает расписание на 30–120 секунд.',
        placement: 'bottom',
    },
    {
        target: '[data-tour-id="advisor-panel"]',
        title: 'Advisor',
        content:
            'Здесь появятся подсказки: дефицит сырья, ' +
            'перегрузка оборудования, проблемы маршрутов.',
        placement: 'bottom',
    },
    {
        target: '[data-tour-id="plans-history"]',
        title: 'История планов',
        content:
            'Здесь — все версии планов. Синяя строка — активная.',
        placement: 'top',
    },
    {
        target: '[data-tour-id="open-gantt-button"]',
        title: 'Открыть Гант',
        content:
            'Нажмите 👁, чтобы открыть план на диаграмме Ганта. ' +
            'После тура попробуйте — увидите визуализацию.',
        placement: 'left',
    },
    {
        target: 'body',
        title: 'Готово!',
        content:
            'Вы построили первый план и открыли диаграмму Ганта. ' +
            'Дальше — экспериментируйте! Справка всегда доступна ' +
            'в разделе «Помощь».',
        placement: 'center',
    },
];

export const gettingStartedTour: Tour = {
    id: 'getting-started',
    name: 'Первый план за 5 минут',
    description:
        'Базовый тур для новых пользователей. Проведёт от входа ' +
        'до первой диаграммы Ганта.',
    steps: gettingStartedSteps,
    icon: 'RocketLaunch',
    stepRoutes: {
        // Шаг 6 («Планирование»): переходим на /schedule
        // Шаги 7, 8, 9, 10 — уже на /schedule
        6: '/schedule',
    },
};

// ==========================================
// Тур 2: Основы работы с диаграммой Ганта
// ==========================================

const ganttBasicsSteps: Step[] = [
    {
        target: 'body',
        title: 'Диаграмма Ганта',
        content:
            'Этот тур покажет, как читать диаграмму, переключать ' +
            'режимы и перетаскивать задачи. Сейчас перейдём на неё.',
        placement: 'center',
    },
    {
        target: '[data-tour-id="gantt-toolbar"]',
        title: 'Тулбар',
        content:
            'В верхней панели — все инструменты: группировка, ' +
            'фильтры, навигация, экспорт.',
        placement: 'bottom',
    },
    {
        target: '[data-tour-id="gantt-edit-toggle"]',
        title: 'Режим 🔒 / ✏️',
        content:
            'По умолчанию — режим просмотра 🔒. Кликните ✏️, ' +
            'чтобы перетаскивать задачи и менять длительность.',
        placement: 'bottom',
    },
    {
        target: '[data-tour-id="gantt-timeline"]',
        title: 'Диаграмма',
        content:
            'Строки — оборудование. Блоки — операции. ' +
            'Цветные скобки — партии.',
        placement: 'center',
    },
    {
        target: '[data-tour-id="gantt-timeline"] .vis-item.vis-range',
        title: 'Задача',
        content:
            'Каждая задача — прямоугольник. Тянется за тело, ' +
            'длительность — за края. Изменения копятся до пересчёта.',
        placement: 'top',
    },
    {
        target: '[data-tour-id="gantt-recalc-button"]',
        title: 'Пересчитать',
        content:
            'Эта кнопка активируется, когда есть несохранённые ' +
            'изменения (planDirty). Нажмите, чтобы пересчитать план.',
        placement: 'bottom',
    },
    {
        target: 'body',
        title: 'Готово!',
        content:
            'Теперь вы знаете основы. Попробуйте перетащить задачу ' +
            'и нажать «Пересчитать».',
        placement: 'center',
    },
];

export const ganttBasicsTour: Tour = {
    id: 'gantt-basics',
    name: 'Основы диаграммы Ганта',
    description:
        'Тур по диаграмме Ганта: режимы, перетаскивание, ' +
        'закрепление задач.',
    steps: ganttBasicsSteps,
    icon: 'Timeline',
    stepRoutes: {
        // Шаг 1 («Тулбар») — уже на /gantt. Переходим туда.
        1: '/gantt',
    },
};

// ==========================================
// Тур 3: Работа мастера смены
// ==========================================

const shiftManagementSteps: Step[] = [
    {
        target: 'body',
        title: 'Мастер смены',
        content:
            'Этот тур — для мастеров смен. Покажет, как выбрать ' +
            'смену, внести факт и заблокировать партию.',
        placement: 'center',
    },
    {
        target: '[data-tour-id="shift-date-picker"]',
        title: 'Дата смены',
        content:
            'Выберите дату. Если на эту дату есть смены — ' +
            'появится выпадающий список.',
        placement: 'bottom',
    },
    {
        target: '[data-tour-id="shift-selector"]',
        title: 'Смена',
        content:
            'Выберите смену (1–3 в день, зависит от режима). ' +
            'Нерабочие смены помечены.',
        placement: 'bottom',
    },
    {
        target: '[data-tour-id="shift-tasks-list"]',
        title: 'Задания смены',
        content:
            'Задания сгруппированы по оборудованию. Каждое — ' +
            'с операциями и статусами.',
        placement: 'center',
    },
    {
        target: '[data-tour-id="task-material-load"]',
        title: '▶ Загрузка сырья',
        content:
            'Кликните ▶, когда мастер загрузил сырьё в реактор. ' +
            'Это переведёт задачу в статус IN_PROGRESS.',
        placement: 'top',
    },
    {
        target: '[data-tour-id="task-complete"]',
        title: '✓ Отметить DONE',
        content:
            'Кликните ✓, когда задача выполнена.',
        placement: 'top',
    },
    {
        target: '[data-tour-id="task-lab-block"]',
        title: '🔒 Блокировка',
        content:
            'Кликните 🔒, чтобы заблокировать партию. ' +
            'Она будет исключена из планирования до разблокировки.',
        placement: 'top',
    },
    {
        target: 'body',
        title: 'Готово!',
        content:
            'Теперь вы знаете, как работать с заданиями смены. ' +
            'Успешной смены!',
        placement: 'center',
    },
];

export const shiftManagementTour: Tour = {
    id: 'shift-management',
    name: 'Работа мастера смены',
    description:
        'Тур по рабочему месту мастера: выбор смены, внесение ' +
        'факта, блокировка партий.',
    steps: shiftManagementSteps,
    icon: 'Assignment',
    stepRoutes: {
        // Шаг 1 («Дата смены») — уже на /shift. Переходим туда.
        1: '/shift',
    },
};

// ==========================================
// Экспорт всех туров
// ==========================================

export const ALL_TOURS: Tour[] = [
    gettingStartedTour,
    ganttBasicsTour,
    shiftManagementTour,
];

/**
 * Получить тур по ID.
 */
export const getTourById = (tourId: string): Tour | undefined => {
    return ALL_TOURS.find((t) => t.id === tourId);
};

// ==========================================
// Итерация 15.3: Общие опции для <Joyride options={...}>
// ==========================================
/**
 * Эти опции применяются ко всем шагам всех туров.
 * Передаются один раз в App.tsx:
 *
 *   <Joyride options={COMMON_TOUR_OPTIONS} ... />
 *
 * Соответствует интерфейсу Options из react-joyride@3.2.0.
 *
 * Тип выводится из Props['options'] компонента <Joyride> — так
 * мы гарантированно получаем корректный Partial<Options> без
 * необходимости импортировать непубличный тип Options.
 */
type JoyrideOptions = NonNullable<Props['options']>;

export const COMMON_TOUR_OPTIONS: JoyrideOptions = {
    // Показывать «Шаг N из M» в тултипе
    showProgress: true,

    // Не показывать пульсирующий «маяк» перед тултипом
    skipBeacon: true,

    // Кнопки в тултипе: Назад, Закрыть, Далее, Пропустить
    // (по умолчанию ['back', 'close', 'primary'] — без skip)
    buttons: ['back', 'close', 'primary', 'skip'],

    // Ширина тултипа
    width: 380,

    // Клик по затемнению закрывает тур
    overlayClickAction: 'close',

    // Цвет основной кнопки («Далее») и маяка
    primaryColor: '#3498db',

    // Цвет затемнения фона
    overlayColor: 'rgba(0, 0, 0, 0.55)',

    // Цвет фона тултипа и текста
    backgroundColor: '#ffffff',
    textColor: '#2c3e50',

    // Z-index
    zIndex: 10000,
};