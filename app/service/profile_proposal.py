"""Owner-scoped structured profile proposal and explicit confirmation service."""

from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256

from app.profile import (
    ConflictResolution,
    ProfileDraft,
    ProfileExtractionProposal,
    RiskProfile,
    RiskQuestionnaire,
    build_profile_draft,
    finalize_profile,
)


class ProfileProposalError(RuntimeError):
    """Safe refusal for an invalid or unresolved structured profile proposal."""


def build_profile_proposal(
    questionnaire: RiskQuestionnaire,
    extraction: ProfileExtractionProposal,
) -> ProfileDraft:
    """Rebuild a profile draft from typed inputs; never trust a client draft."""

    try:
        if questionnaire.owner_id != extraction.owner_id:
            raise ValueError("profile proposal owners do not match")
        return build_profile_draft(questionnaire, extraction)
    except ProfileProposalError:
        raise
    except Exception as exc:
        raise ProfileProposalError("profile proposal was refused") from exc


def _stable_profile_id(
    questionnaire: RiskQuestionnaire,
    extraction: ProfileExtractionProposal,
    resolutions: Mapping[str, ConflictResolution | str],
) -> str:
    normalized_resolutions = {
        str(key): ConflictResolution(value).value
        for key, value in resolutions.items()
    }
    payload = "\x1f".join(
        (
            questionnaire.model_dump_json(),
            extraction.model_dump_json(),
            json.dumps(
                normalized_resolutions,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    ).encode("utf-8")
    return "profile-proposal:" + sha256(payload).hexdigest()[:32]


def confirm_profile_proposal(
    questionnaire: RiskQuestionnaire,
    extraction: ProfileExtractionProposal,
    resolutions: Mapping[str, ConflictResolution | str],
) -> RiskProfile:
    """Rebuild and explicitly resolve a draft before producing a profile."""

    try:
        draft = build_profile_proposal(questionnaire, extraction)
        return finalize_profile(
            draft,
            resolutions,
            profile_id=_stable_profile_id(questionnaire, extraction, resolutions),
            profile_version=1,
            created_at=questionnaire.answered_at,
        )
    except ProfileProposalError:
        raise
    except Exception as exc:
        raise ProfileProposalError("profile proposal confirmation was refused") from exc


__all__ = [
    "ProfileProposalError",
    "build_profile_proposal",
    "confirm_profile_proposal",
]
