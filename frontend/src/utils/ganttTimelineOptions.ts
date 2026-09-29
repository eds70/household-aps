// frontend/src/utils/ganttTimelineOptions.ts
/**
 * Построение TimelineOptions для диаграммы Ганта (Итерация 13.17 + 13.18).
 *
 * Итерация 13.18 (fix #7): ВАЖНО — поле `editable` ДОЛЖНО быть задано,
 *   иначе vis-timeline не генерирует события itemmoving/itemmoved/
 *   itemresizing/itemresized, и задачи нельзя перетаскивать.
 *
 *   `editable.updateTime: true` включает И move, И resize.
 */
import type {TimelineOptions} from 'vis-timeline/standalone';
import {SNAP_MS, ZOOM_MAX_MS, ZOOM_MIN_MS} from '../components/gantt/constants';

// ==========================================
// ОСНОВНОЙ TIMELINE
// ==========================================

export interface BuildMainTimelineOptionsParams {
    isReadOnly: boolean;
}

export const buildMainTimelineOptions = (
    params: BuildMainTimelineOptionsParams,
): TimelineOptions => {
    const {isReadOnly} = params;

    return {
        groupOrder: 'content',
        moveable: true,
        zoomable: true,
        // ==========================================
        // Итерация 13.18 (fix #7): editable ОБЯЗАТЕЛЬНО
        // ==========================================
        // updateTime: true — включает И move, И resize.
        // При false — задачи нельзя двигать вообще.
        editable: {
            add: false,
            updateTime: !isReadOnly,
            updateGroup: false,
            remove: false,
        },
        selectable: true,
        multiselect: false,
        margin: {item: 2, axis: 5},
        orientation: 'top',
        stack: false,
        showCurrentTime: true,
        zoomMin: ZOOM_MIN_MS,
        zoomMax: ZOOM_MAX_MS,
        format: {
            minorLabels: {
                millisecond: 'SSS',
                second: 'ss',
                minute: 'HH:mm',
                hour: 'HH:mm',
                weekday: 'ddd D MMM',
                day: 'D MMM',
                week: 'w',
                month: 'MMMM',
                year: 'YYYY',
            },
            majorLabels: {
                millisecond: 'HH:mm:ss',
                second: 'D MMMM HH:mm',
                minute: 'ddd D MMMM',
                hour: 'ddd D MMMM',
                weekday: 'MMMM YYYY',
                day: 'MMMM YYYY',
                week: 'MMMM YYYY',
                month: 'YYYY',
                year: '',
            },
        },
        locale: 'ru',
        tooltip: {
            followMouse: true,
            overflowMethod: 'cap',
            delay: 100,
        },
        snap: (date: Date) => {
            return new Date(
                Math.round(date.getTime() / SNAP_MS) * SNAP_MS,
            );
        },
        verticalScroll: true,
    };
};

// ==========================================
// МИНИКАРТА
// ==========================================

export const buildMinimapTimelineOptions = (): TimelineOptions => {
    return {
        groupOrder: 'content',
        editable: false,
        selectable: false,
        moveable: false,
        margin: {item: 0, axis: 0},
        orientation: 'top',
        stack: false,
        showCurrentTime: true,
        zoomMin: ZOOM_MIN_MS,
        zoomMax: ZOOM_MAX_MS,
        format: {
            minorLabels: {hour: '', weekday: ''},
            majorLabels: {day: ''},
        },
        locale: 'ru',
        height: '100%',
        showMajorLabels: false,
        showMinorLabels: false,
    };
};