"""Session-only Risk Questionnaire confirmation over the existing scorer."""

from __future__ import annotations

from hashlib import sha256

from app.profile import RiskProfile, RiskQuestionnaire, build_profile_draft, finalize_profile


class ProfileConfirmationError(RuntimeError):
    """A safe refusal while confirming a structured questionnaire."""


def _stable_profile_id(questionnaire: RiskQuestionnaire) -> str:
    payload = questionnaire.model_dump_json().encode("utf-8")
    return "profile-context:" + sha256(payload).hexdigest()[:32]


def confirm_questionnaire(questionnaire: RiskQuestionnaire) -> RiskProfile:
    """Build a deterministic profile without persistence or new scoring rules."""

    try:
        draft = build_profile_draft(questionnaire)
        return finalize_profile(
            draft,
            profile_id=_stable_profile_id(questionnaire),
            profile_version=1,
            created_at=questionnaire.answered_at,
        )
    except Exception as exc:
        raise ProfileConfirmationError("risk profile confirmation was refused") from exc


__all__ = ["ProfileConfirmationError", "confirm_questionnaire"]
