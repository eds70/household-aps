# backend/tests/test_audit_models.py
"""
Тесты Pydantic-моделей аудита (Итерация 13.3).

Все тесты быстрые, БЕЗ БД.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.v1.audit_models import (
    AUDIT_SOURCES,
    AuditEvent,
    AuditListResponse,
    AuditStatsResponse,
)


# ==========================================
# AuditEvent
# ==========================================

def test_audit_event_minimal():
    """Минимальное событие — только обязательные поля."""
    event = AuditEvent(
        id=uuid4(),
        source="STOCK",
        event_type="UPDATE",
        severity="INFO",
        title="Test event",
        occurred_at=datetime.now(timezone.utc),
    )
    assert event.title == "Test event"
    assert event.details == {}


def test_audit_event_full():
    """Полное событие — все поля."""
    event = AuditEvent(
        id=uuid4(),
        source="LAB",
        event_type="BLOCKED",
        severity="WARNING",
        title="Лаборатория: заблокировано",
        description="Причина: pH вне нормы",
        entity_type="batch",
        entity_id=uuid4(),
        entity_name="GP_CREAM_1L",
        actor_id=uuid4(),
        actor_name="Иванов И.И.",
        occurred_at=datetime.now(timezone.utc),
        details={"reason": "pH вне нормы"},
    )
    assert event.source == "LAB"
    assert event.severity == "WARNING"
    assert event.details["reason"] == "pH вне нормы"


def test_audit_event_requires_title():
    """Без title — ошибка валидации."""
    with pytest.raises(ValidationError):
        AuditEvent(
            id=uuid4(),
            source="STOCK",
            event_type="UPDATE",
            severity="INFO",
            occurred_at=datetime.now(timezone.utc),
        )


def test_audit_event_requires_source():
    """Без source — ошибка."""
    with pytest.raises(ValidationError):
        AuditEvent(
            id=uuid4(),
            event_type="UPDATE",
            severity="INFO",
            title="Test",
            occurred_at=datetime.now(timezone.utc),
        )


# ==========================================
# AuditListResponse
# ==========================================

def test_audit_list_response_empty():
    """Пустой список событий."""
    resp = AuditListResponse(
        events=[],
        total=0,
        by_source={s: 0 for s in AUDIT_SOURCES},
    )
    assert resp.total == 0
    assert resp.by_source["STOCK"] == 0


def test_audit_list_response_with_events():
    """Список с событиями."""
    events = [
        AuditEvent(
            id=uuid4(),
            source="STOCK",
            event_type="UPDATE",
            severity="INFO",
            title=f"Event {i}",
            occurred_at=datetime.now(timezone.utc),
        )
        for i in range(3)
    ]
    resp = AuditListResponse(
        events=events,
        total=3,
        by_source={"STOCK": 3, "RESCHEDULE": 0, "LAB": 0, "CZ": 0},
    )
    assert len(resp.events) == 3


# ==========================================
# AuditStatsResponse
# ==========================================

def test_audit_stats_response_full():
    """Статистика за 30 дней."""
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    resp = AuditStatsResponse(
        period_days=30,
        date_from=now - timedelta(days=30),
        date_to=now,
        total=100,
        by_source={"STOCK": 50, "RESCHEDULE": 30, "LAB": 15, "CZ": 5},
        by_severity={"INFO": 80, "WARNING": 18, "CRITICAL": 2},
    )
    assert resp.period_days == 30
    assert resp.by_severity["CRITICAL"] == 2


# ==========================================
# AUDIT_SOURCES
# ==========================================

def test_audit_sources_tuple():
    """AUDIT_SOURCES — tuple из 4 элементов."""
    assert isinstance(AUDIT_SOURCES, tuple)
    assert len(AUDIT_SOURCES) == 4
    assert "STOCK" in AUDIT_SOURCES
    assert "RESCHEDULE" in AUDIT_SOURCES
    assert "LAB" in AUDIT_SOURCES
    assert "CZ" in AUDIT_SOURCES


if __name__ == "__main__":
    pytest.main([__file__, "-v"])