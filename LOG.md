# LOG

## 2026-09-01 — Independent repository foundation

### Decisions

- `Prism.md` is the project master document; no duplicate `PROJECT.md` will be created.
- Prism is an independent repository. `tradeeye-copilot` and `TradeEye` remain read-only upstream references and are not runtime dependencies.
- The first product slice is portfolio-to-adjustment decision support for a technology-fund-concentrated user, not a broad financial chat clone.
- The runtime will be a modular monolith with a bounded structured research DAG. LLM nodes do not calculate financial facts or bypass deterministic profile, portfolio, risk and compliance engines.
- Product differentiation is an auditable personalized adjustment delta: the user can see which profile constraint changed the recommendation, the quantified pre/post effect, the evidence chain and the invalidation conditions.
- Fund/ETF look-through analysis moves into P0 because the flagship scenario depends on it. The load-test harness also moves forward to the Provider/foundation phase.

### Upstream evidence

- `tradeeye-copilot` at `1675a87`, equal to `origin/main`, clean: 283 tests passed.
- `TradeEye` at `8a1bd8c`, equal to `origin/main`, clean: 172 tests passed.
- Reusable code and non-reusable strategy/storage boundaries are recorded in `docs/reuse-matrix.md`.
- Neither upstream root exposed a `LICENSE`, `COPYING`, or `NOTICE` file during the current inspection; provenance remains a submission gate.

### Implemented

- Initialized Git on branch `main`.
- Updated the master specification to identify `Prism.md`—not a duplicate `PROJECT.md`—as the execution entrypoint.
- Added project metadata, repository hygiene files and a truthful README.
- Added ADR-0001, implementation architecture, Reuse Matrix, Evidence Contract and a durable foundation plan.
- Added strict immutable Pydantic contracts for Evidence, Fact, Finding, Recommendation and DecisionTrace.
- Enforced timezone-aware retrieval timestamps, non-zero-vs-missing semantics, reference closure, matching fact/evidence values and periods, and independent compliance states.
- Allowed missing evidence to explain a `BLOCKED` decision while preventing it from supporting actionable recommendations.

### Verification

```text
python -m pytest
8 passed
```

This verifies only the initial domain contract. No real SkillHub request, financial recommendation, browser workflow, concurrency target or availability target is claimed yet.

### Open constraints

- Competition-specific SkillHub interface and usage authorization are not present in the repository.
- The scoring appendix referenced in the brief is not present in the repository.
- Storage, Provider, profile, research, portfolio, risk, compliance, API and Web workbench remain unimplemented.

## 2026-09-01 — Gemini MVP Phase 1 delegation contract

### Decision

- Gemini may execute the overall MVP route one accepted phase at a time; it does not own or rewrite the route in `Prism.md`.
- The first delegated phase is narrowed to the fixture-first Provider boundary. Live SkillHub, storage, profile, research, portfolio and UI are explicitly excluded.
- Each Gemini phase must run on an isolated branch/worktree, satisfy an executable acceptance contract, create a local commit without pushing, and return evidence for independent review.
- Provider call identity is split into a per-call `request_id` and a deterministic semantic `request_fingerprint`; credentials are excluded from both fixtures and fingerprints.

### Artifact

- Added `docs/plans/2026-09-01-mvp-phase-1-provider-protocol.md` as the copy-ready Gemini execution contract.
- The contract defines allowed files, four-state invariants, fixture data, timeout/redaction behavior, Evidence conversion, a 100-request isolation smoke test, stop conditions and the required handoff format.

### Current evidence boundary

- This change is planning only. No Provider implementation or real external request has been added.
- Phase 1 remains incomplete until Gemini's implementation is independently reviewed and accepted.

### Verification

- Existing baseline: `python -m pytest` -> 8 passed.
- Python compilation: passed.
- Local Markdown link validation: passed.
- Staged diff check: passed.

## 2026-09-01 — MVP Phase 1 fixture-first provider protocol

### Decisions

- Implemented the fixture-first Provider Protocol strictly adhering to `docs/plans/2026-09-01-mvp-phase-1-provider-protocol.md`.
- Enforced strict four-state execution invariants: `SUCCESS`, `PARTIAL`, `EMPTY`, and `FAILED` cannot be interchanged or masqueraded.
- Separated per-call correlation (`request_id`) from deterministic canonical SHA-256 semantic query fingerprints (`request_fingerprint`).
- Hardened contract safety based on review feedback:
  - Added `FrozenDict` deep immutability to prevent runtime parameter mutation and fingerprint drift;
  - Added recursive forbidden key detection (`_find_forbidden_key`) traversing nested dictionaries and sequences;
  - Enforced per-record required field validation in `SUCCESS` (requiring all records to have all required fields with non-None values);
  - Enforced veracity checking on `PARTIAL.missing_fields` (ensuring missing fields were actually requested and actually missing in records);
  - Added record identity to `evidence_id` (`ev:{provider}:{source}:{record_identity}:{field}:{period}`) to prevent duplicate Evidence IDs across multiple records and ensure DecisionTrace closure;
  - Added fixture template validation and duplicate fingerprint detection at FixtureProvider initialization.
- Created purely synthetic, credential-free fixtures covering all four result states.
- Normalization safely converts `SUCCESS` to `VERIFIED` Evidence, `PARTIAL` to `PARTIAL` Evidence with quality notes, and `EMPTY`/`FAILED` to zero Evidence (preventing false zeros).
- Standard library `asyncio` execution budget wrapper maps timeouts and internal errors safely without leaking stack traces or credentials.
- 100-concurrent request in-memory smoke test verified request ID isolation and fingerprint stability.

### Implemented

- `app/providers/contracts.py`: ProviderOperation, ProviderStatus, ProviderIssueCode, FrozenDict, ProviderRequest, ProviderRecord, ProviderIssue, ProviderResult, FinancialProvider protocol, and validate_result_for_request.
- `app/providers/fingerprint.py`: canonical JSON request dictionary, SHA-256 fingerprinting, and recursive redaction.
- `app/providers/fixture.py`: FixtureFinancialProvider with in-memory fingerprint indexing, template validation, and deterministic execution.
- `app/providers/runtime.py`: execute_with_budget async wrapper with timeout and error mapping.
- `app/providers/normalization.py`: normalize_result_to_evidence converter to Evidence domain model with record-identity-aware Evidence IDs.
- `app/providers/__init__.py`: package exports.
- `tests/fixtures/providers/*.json`: synthetic test fixtures (fund_data_success, fund_data_partial, fund_data_empty, fund_data_failed).
- `tests/unit/test_provider_contract.py`, `tests/unit/test_provider_fingerprint.py`, `tests/integration/test_fixture_provider.py`: 35 new tests covering all 21 acceptance cases and 6 review hardening items (43 total tests in repo).
- `docs/provider-protocol.md`: comprehensive documentation of the provider protocol.

### Verification

```text
python -m pytest
43 passed in 0.33s

python -m compileall -q app
passed

python -c "from app.providers import FinancialProvider, FixtureFinancialProvider; print('provider-import-ok')"
provider-import-ok

git diff --check
passed
```

### Current evidence boundary

- Live SkillHub network requests, production credentials, storage persistence, user profiles, research DAG, and UI workbench remain un-implemented and are explicitly out-of-scope for Phase 1.

## 2026-09-01 — Phase 1 hardening and takeover

### Decisions

- Codex took over the phase gate after an independent review of Gemini's `68ed7ff` implementation. Phase 2 remains blocked until this hardening pass is independently verified.
- The original `JsonValue` semantics are preserved while adding recursive freezing; `FrozenDict` must reject non-JSON values and `ProviderRecord.units` must contain strings.
- `PARTIAL.missing_fields` must exactly account for requested fields missing or null in any record; issue-only partial results may keep the set empty when no required field is missing.
- Evidence IDs encode provider/source/record/field/period and request fingerprint, and duplicate effective record identities are rejected before creating Evidence.

### Implemented

- Added `docs/plans/2026-09-01-mvp-phase-1-hardening.md` with explicit scope, non-goals, design decisions, acceptance cases and stop conditions.
- Added regression tests for non-JSON values, deep nested sequence mutation, `|=`, unit types, omitted partial fields, duplicate record IDs, missing record identity, delimiter-safe IDs and cross-request ID isolation.
- Preserved fixture-first, offline-only behavior; no upstream, network, credential, storage or UI changes.

### Verification

```text
python -m pytest
50 passed

python -m compileall -q app
passed

python -c "from app.providers import FinancialProvider, FixtureFinancialProvider, FrozenDict; print('provider-import-ok')"
provider-import-ok

git diff --check
passed
```

Independent adversarial checks passed: actual PARTIAL omissions are rejected; non-JSON parameters are rejected; nested sequences and `|=` cannot mutate requests; duplicate record identities are rejected; delimiter-containing and cross-request Evidence IDs remain distinct.

### Current evidence boundary

- Phase 1 hardening was accepted in local commit `84bbe3b`; Phase 2 began only after that gate.
- Real external providers, credentials, production concurrency/SLA and all later product layers remain unimplemented.

## 2026-09-01 — MVP Phase 2 profile and portfolio contracts

### Plan and boundary

- Added `docs/plans/2026-09-01-mvp-phase-2-profile-portfolio-contracts.md` and committed it before implementation in `ae9c68c`.
- The phase fixes two input boundaries for the flagship vertical slice: deterministic user risk profiles with explicit extraction conflict confirmation, and raw owner-scoped position/fund/ETF imports.
- Portfolio analytics, exposure, risk budgets, recommendations, LLM/network access, persistence, API, UI and upstream changes remain explicitly out of scope.

### Implemented locally

- Added immutable, versioned `RiskQuestionnaire`, `ProfileExtractionProposal`, `ProfileConflict`, `ProfileDraft` and `RiskProfile` contracts.
- Added fixed Decimal scoring and fixed risk-level thresholds; maximum drawdown remains an independent user constraint.
- Added explicit `USE_QUESTIONNAIRE` / `USE_EXTRACTION` resolution with no silent overwrite and no raw natural-language field.
- Added immutable `Position`, `PositionSnapshot`, four-state `PositionImportResult`, safe import issues, raw `LookThroughHolding`, `FundHoldingSnapshot` and owner/parent-closed `PortfolioImportBundle` contracts.
- Added credential-free synthetic fixtures, unit反例 and integration tests.

### Current review evidence

- Final full suite: `69 passed` (the original 50 Phase 1/Evidence tests remain green).
- Compilation, import, `git diff --check`, fixture JSON parsing and import checks passed after commit.
- Independent adversarial checks passed for stale conflicts, unknown resolutions, risk-level tampering, owner mismatch, deep tuple mutation, four-state misuse, illegal weights and unknown fund parents.
- Phase 2 was accepted in the single local commit `0de0c43`; no Phase 3 implementation has started yet.

## 2026-09-01 — MVP Phase 3 look-through exposure plan

### Plan and worktree

- Created dedicated worktree `D:\Github_Storage\prism-phase-3` on branch `codex/mvp-phase-3-exposure-risk` from Phase 2 accepted commit `0de0c43`.
- Added `docs/plans/2026-09-01-mvp-phase-3-lookthrough-exposure.md` before implementation.
- The plan narrows this phase to deterministic base-currency direct/look-through attribution, residuals and data coverage; concentration, risk budgets and recommendations remain deferred.

### Current boundary

- No Phase 3 implementation or real data-source access has started.
- The Phase 3 plan is ready for implementation after its plan commit; Phase 2 artifacts remain unchanged.

## 2026-09-01 — MVP Phase 3 look-through exposure implementation

### Implemented locally

- Added immutable `ExposureContribution`, `ExposureReport`, `ExposureIssue` and `ExposureResult` contracts with complete/partial/failed invariants.
- Added deterministic Decimal attribution for direct positions, valid fund/ETF holdings and explicit unlooked-through residuals.
- Added non-base-currency and future-snapshot safety issues, fixed technology-sector classification, contribution closure and deterministic IDs.
- Added synthetic multi-position fixture and unit/integration counterexamples; no network, FX, LLM, persistence, risk or recommendation code was introduced.

### Current review evidence

- Final full suite: `79 passed` (Phase 1/2's 69 tests remain green).
- Compilation, import, `git diff --check`, fixture JSON/sensitive-field scan and post-commit independent adversarial checks all passed.
- Phase 3 was accepted in the single local implementation commit `f6a1af4`; the next concentration/risk plan must use a new worktree.

## 2026-09-01 — MVP Phase 4 concentration and risk-budget plan

### Plan and worktree

- Created dedicated worktree `D:\Github_Storage\prism-phase-4` on branch `codex/mvp-phase-4-concentration-risk` from Phase 3 accepted commit `f6a1af4`.
- Added `docs/plans/2026-09-01-mvp-phase-4-concentration-risk-budget.md` before implementation.
- The phase narrows the next slice to deterministic asset/sector concentration and profile-conditioned risk-budget assessment; correlation, liquidity, optimization and recommendations remain deferred.

### Current boundary

- No Phase 4 implementation or real data-source access has started.
- The Phase 4 plan is ready for implementation after its plan commit; Phase 1/2/3 artifacts remain unchanged.
