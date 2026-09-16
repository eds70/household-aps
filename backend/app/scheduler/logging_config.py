# backend/app/scheduler/logging_config.py
"""
Structured logging для планировщика.

Формирует единый формат логов:
    [2026-09-15 10:30:45] [INFO] [scheduler] [org=...] [stage=load] Сообщение
Позволяет фильтровать логи по стадии (load, solve, save) и организации.
"""

import logging
import sys
from typing import Optional


class SchedulerFormatter(logging.Formatter):
    """
    Форматтер с фиксированными полями:
    - timestamp
    - level
    - logger name
    - stage (если передан)
    - org_id (если передан)
    - message
    """

    DEFAULT_FMT = "[%(asctime)s] [%(levelname)s] [%(name)s]%(stage)s%(org)s %(message)s"
    DATE_FMT = "%Y-%m-%d %H:%M:%S"

    def format(self, record: logging.LogRecord) -> str:
        # Подставляем stage
        stage = getattr(record, "stage", None)
        record.stage = f" [stage={stage}]" if stage else ""

        # Подставляем org_id
        org_id = getattr(record, "org_id", None)
        if org_id:
            org_str = str(org_id)
            # Сокращаем UUID до первых 8 символов для читаемости
            record.org = f" [org={org_str[:8]}]"
        else:
            record.org = ""

        formatter = logging.Formatter(self.DEFAULT_FMT, datefmt=self.DATE_FMT)
        return formatter.format(record)


def setup_scheduler_logging(
        level: int = logging.INFO,
        log_file: Optional[str] = None,
) -> logging.Logger:
    """
    Настроить логирование для планировщика.

    Args:
        level: уровень логирования (по умолчанию INFO)
        log_file: путь к файлу (если None — только stdout)

    Returns:
        Настроенный logger для 'app.scheduler'
    """
    logger = logging.getLogger("app.scheduler")
    logger.setLevel(level)
    logger.propagate = False

    # Убираем старые хендлеры (на случай повторного вызова)
    if logger.handlers:
        logger.handlers.clear()

    formatter = SchedulerFormatter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (опционально)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def log_with_context(
        logger: logging.Logger,
        level: int,
        message: str,
        stage: Optional[str] = None,
        org_id: Optional[str] = None,
        **extra,
) -> None:
    """
    Удобная обёртка для логирования с контекстом.

    Пример:
        log_with_context(logger, logging.INFO, "Загружено партий: 34",
                         stage="load", org_id=str(org_id), batches=34)
    """
    logger.log(level, message, extra={"stage": stage, "org_id": org_id, **extra})