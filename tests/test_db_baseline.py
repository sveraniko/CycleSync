from app.domain.db import NAMING_CONVENTION
from app.domain.db.base import Base
from app.domain.models import (
    Brand,
    JobRun,
    OutboxEvent,
    ProjectionCheckpoint,
    SearchProjectionState,
    SearchQueryLog,
    ProtocolDraft,
    ProtocolDraftItem,
    ProtocolDraftSettings,
    PulseCalculationRun,
    PulsePlanPreview,
    PulsePlanPreviewEntry,
)


def test_sqlalchemy_naming_convention_configured() -> None:
    assert Base.metadata.naming_convention == NAMING_CONVENTION


def test_ops_models_bound_to_ops_schema() -> None:
    assert OutboxEvent.__table__.schema == "ops"
    assert JobRun.__table__.schema == "ops"
    assert ProjectionCheckpoint.__table__.schema == "ops"


def test_compound_catalog_models_bound_to_compound_catalog_schema() -> None:
    assert Brand.__table__.schema == "compound_catalog"



def test_search_read_models_bound_to_search_read_schema() -> None:
    assert SearchProjectionState.__table__.schema == "search_read"
    assert SearchQueryLog.__table__.schema == "search_read"


def test_protocol_models_bound_to_protocols_schema() -> None:
    assert ProtocolDraft.__table__.schema == "protocols"
    assert ProtocolDraftItem.__table__.schema == "protocols"
    assert ProtocolDraftSettings.__table__.schema == "protocols"



def test_pulse_engine_models_bound_to_pulse_engine_schema() -> None:
    assert PulseCalculationRun.__table__.schema == "pulse_engine"
    assert PulsePlanPreview.__table__.schema == "pulse_engine"
    assert PulsePlanPreviewEntry.__table__.schema == "pulse_engine"
