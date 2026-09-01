"""Fixture-driven deterministic financial provider."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from app.providers.contracts import (
    FinancialProvider,
    ProviderIssue,
    ProviderIssueCode,
    ProviderRecord,
    ProviderRequest,
    ProviderResult,
    ProviderStatus,
    validate_result_for_request,
)
from app.providers.fingerprint import compute_request_fingerprint

DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "providers"


class FixtureFinancialProvider:
    """Deterministic offline provider backed by validated synthetic JSON fixtures."""

    def __init__(self, fixture_dir: Path | str | None = None) -> None:
        self._provider_name = "fixture-provider"
        if fixture_dir is None:
            self._fixture_dir = DEFAULT_FIXTURE_DIR
        else:
            self._fixture_dir = Path(fixture_dir).resolve()

        if not self._fixture_dir.exists() or not self._fixture_dir.is_dir():
            raise ValueError(f"Fixture directory not found: {self._fixture_dir}")

        self._fixtures: dict[str, tuple[ProviderRequest, ProviderResult]] = {}
        self._fixture_sources: dict[str, Path] = {}
        self._load_fixtures()

    @property
    def name(self) -> str:
        return self._provider_name

    def _load_fixtures(self) -> None:
        for path in sorted(self._fixture_dir.glob("*.json")):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "request" not in data or "result" not in data:
                raise ValueError(
                    f"Invalid fixture file {path.name}: must contain 'request' and 'result' keys"
                )

            req_data = dict(data["request"])
            req_data.setdefault("request_id", f"fixture-req-{path.stem}")
            template_req = ProviderRequest.model_validate(req_data)
            fp = compute_request_fingerprint(template_req)

            if fp in self._fixtures:
                existing_path = self._fixture_sources[fp]
                raise ValueError(
                    f"Duplicate request fingerprint {fp!r} in {path.name}, "
                    f"already loaded from {existing_path.name}"
                )

            res_data = dict(data["result"])
            records = tuple(
                ProviderRecord.model_validate(rec)
                for rec in res_data.get("records", [])
            )
            missing_fields = tuple(res_data.get("missing_fields", []))
            issues = tuple(
                ProviderIssue.model_validate(iss)
                for iss in res_data.get("issues", [])
            )

            template_res = ProviderResult.model_validate({
                "request_id": template_req.request_id,
                "request_fingerprint": fp,
                "provider": self.name,
                "status": ProviderStatus(res_data["status"]),
                "retrieved_at": datetime.now(UTC),
                "records": records,
                "missing_fields": missing_fields,
                "issues": issues,
                "scope_description": res_data.get("scope_description"),
                "latency_ms": res_data.get("latency_ms", 5),
            })

            # Strictly validate that template result satisfies template request
            validate_result_for_request(template_req, template_res)

            self._fixtures[fp] = (template_req, template_res)
            self._fixture_sources[fp] = path

    async def execute(self, request: ProviderRequest) -> ProviderResult:
        """Execute request against loaded fixtures without network access."""
        fp = compute_request_fingerprint(request)
        entry = self._fixtures.get(fp)

        if entry is None:
            return ProviderResult(
                request_id=request.request_id,
                request_fingerprint=fp,
                provider=self.name,
                status=ProviderStatus.FAILED,
                retrieved_at=datetime.now(UTC),
                records=(),
                missing_fields=(),
                issues=(
                    ProviderIssue(
                        code=ProviderIssueCode.UNSUPPORTED_OPERATION,
                        stage="lookup",
                        safe_message=f"No matching fixture found for fingerprint {fp}",
                        retriable=False,
                        diagnostics={"subject": request.subject, "operation": request.operation.value},
                    ),
                ),
                scope_description=None,
                latency_ms=1,
            )

        _, template_res = entry

        result = ProviderResult(
            request_id=request.request_id,
            request_fingerprint=fp,
            provider=self.name,
            status=template_res.status,
            retrieved_at=datetime.now(UTC),
            records=template_res.records,
            missing_fields=template_res.missing_fields,
            issues=template_res.issues,
            scope_description=template_res.scope_description,
            latency_ms=template_res.latency_ms,
        )

        validate_result_for_request(request, result)
        return result
