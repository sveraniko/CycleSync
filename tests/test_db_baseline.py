from app.domain.db import NAMING_CONVENTION
from app.domain.db.base import Base
from app.domain.models import JobRun, OutboxEvent, ProjectionCheckpoint


def test_sqlalchemy_naming_convention_configured() -> None:
    assert Base.metadata.naming_convention == NAMING_CONVENTION


def test_ops_models_bound_to_ops_schema() -> None:
    assert OutboxEvent.__table__.schema == "ops"
    assert JobRun.__table__.schema == "ops"
    assert ProjectionCheckpoint.__table__.schema == "ops"
