"""Application use cases that compose existing deterministic domain modules."""

from app.service.advisor_query import (
    AdvisorQueryError,
    FixtureAdvisorQueryService,
)
from app.service.contracts import (
    AdvisorQueryOutput,
    AdvisorQueryRequest,
    AdvisorQueryTemplate,
)
from app.service.specialist_matrix import (
    FixtureResearchSpecialistMatrixService,
    SpecialistMatrixError,
    SpecialistMatrixOutput,
)
from app.service.profile_confirmation import (
    ProfileConfirmationError,
    confirm_questionnaire,
)
from app.service.intent_planning import (
    AdvisorIntentRequest,
    AdvisorPlanResponse,
    IntentPlanningError,
    InvestmentIntentType,
    build_intent_plan,
)

__all__ = [
    "AdvisorQueryError",
    "AdvisorQueryOutput",
    "AdvisorQueryRequest",
    "AdvisorQueryTemplate",
    "FixtureAdvisorQueryService",
    "FixtureResearchSpecialistMatrixService",
    "SpecialistMatrixError",
    "SpecialistMatrixOutput",
    "ProfileConfirmationError",
    "confirm_questionnaire",
    "AdvisorIntentRequest",
    "AdvisorPlanResponse",
    "IntentPlanningError",
    "InvestmentIntentType",
    "build_intent_plan",
]
