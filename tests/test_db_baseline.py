from app.domain.db import NAMING_CONVENTION
from app.domain.db.base import Base
from app.domain.models import (
    Entitlement,
    EntitlementGrant,
    AccessKey,
    AccessKeyEntitlement,
    AccessKeyRedemption,
    LabTriageFlag,
    LabTriageRun,
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
    LabMarker,
    LabReport,
    LabReportEntry,
    LabPanel,
    LabPanelMarker,
    SpecialistCase,
    SpecialistCaseResponse,
    SpecialistCaseSnapshot,
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


def test_labs_models_bound_to_labs_schema() -> None:
    assert LabMarker.__table__.schema == "labs"
    assert LabPanel.__table__.schema == "labs"
    assert LabPanelMarker.__table__.schema == "labs"
    assert LabReport.__table__.schema == "labs"
    assert LabReportEntry.__table__.schema == "labs"


def test_ai_triage_models_bound_to_ai_triage_schema() -> None:
    assert LabTriageRun.__table__.schema == "ai_triage"
    assert LabTriageFlag.__table__.schema == "ai_triage"


def test_expert_cases_models_bound_to_expert_cases_schema() -> None:
    assert SpecialistCase.__table__.schema == "expert_cases"
    assert SpecialistCaseSnapshot.__table__.schema == "expert_cases"
    assert SpecialistCaseResponse.__table__.schema == "expert_cases"


def test_access_models_bound_to_access_schema() -> None:
    assert Entitlement.__table__.schema == "access"
    assert EntitlementGrant.__table__.schema == "access"
    assert AccessKey.__table__.schema == "access"
    assert AccessKeyEntitlement.__table__.schema == "access"
    assert AccessKeyRedemption.__table__.schema == "access"
