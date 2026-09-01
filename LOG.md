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

## 2026-09-01 — MVP Phase 4 concentration and risk-budget implementation

### Implemented locally

- Added immutable concentration groups/reports/results with Decimal asset/sector aggregation, HHI, deterministic tie-breaking and upstream status propagation.
- Added versioned fixed `RiskBudget` rules selected by `RiskProfile` risk level and explicit `RiskBudgetBreach` / `RiskBudgetAssessment` states (`PASS`, `REVIEW_REQUIRED`, `BLOCKED`).
- Preserved unlooked-through and unknown data, enforced owner/profile/exposure closure, and added synthetic offline tests without recommendations or real data access.

### Current review evidence

- Final full suite: `92 passed` (Phase 1/2/3's 79 tests remain green).
- Compilation, import, `git diff --check`, fixture scan and post-commit independent adversarial checks all passed.
- Phase 4 was accepted in the single local implementation commit recorded by this worktree; the final commit hash is reported by `git log -1` and the handoff message. The next optimization/recommendation plan must use a new worktree.

## 2026-09-01 — MVP Phase 5 allocation-envelope implementation

### Plan and worktree

- Created dedicated worktree `D:\Github_Storage\prism-phase-5` on branch `codex/mvp-phase-5-minimal-adjustment` from the accepted Phase 4 worktree.
- Added `docs/plans/2026-09-01-mvp-phase-5-allocation-envelope.md` before implementation.
- The phase is limited to deterministic profile-conditioned constraint bands and per-constraint impact; it does not create executable recommendations or modify the Evidence Contract.

### Implemented locally

- Added immutable `AllocationBand`, `ConstraintImpact`, `AllocationEnvelope` and `AllocationResult` contracts with owner/profile/report closure and `READY`/`REVIEW_REQUIRED`/`BLOCKED` semantics.
- Added deterministic asset, sector, technology and unclassified bands using the fixed Phase 4 budget; partial inputs stay `UNRESOLVED`, and each impact is explicitly constraint-only without cross-dimension reallocation.
- Added a synthetic offline fixture, unit/integration counterexamples and `docs/allocation-envelope.md`; no network, credentials, LLM, persistence, API, UI, order, price, quantity or return calculation was introduced.

### Independent review evidence

- Full suite: `103 passed` (Phase 1–4's 92 tests remain green).
- `python -m compileall -q app`, allocation import, `git diff --check`, fixture JSON and source/fixture sensitive-field scans passed.
- Independent adversarial checks passed for deterministic repeatability, partial/failed propagation, stale/tampered budget breaches, blocked outputs and absence of recommendation/order/secret-shaped output fields.
- Phase 5 is accepted in this worktree after the above review; the next structured-research/cross-validation plan must use a new worktree.

## 2026-09-01 — MVP Phase 6 structured research and cross-validation plan

### Plan and worktree

- Created dedicated worktree `D:\Github_Storage\prism-phase-6` on branch `codex/mvp-phase-6-research-cross-validation` from the accepted Phase 5 worktree.
- Added `docs/plans/2026-09-01-mvp-phase-6-research-cross-validation.md` before implementation.
- The phase narrows structured research to scalar observation contracts, four-state node results and lineage-aware validation; live providers, orchestration and Evidence/Finding conversion remain deferred.

### Implemented locally

- Added immutable `ResearchObservation`, `ResearchNodeResult`, `ValidationClaim`, `CrossValidationResult` and safe issue contracts.
- Added deterministic equality/lineage validation: duplicate lineage rows count once, no-lineage rows cannot prove independence, non-VERIFIED and scope-mismatched observations stay visible but cannot support a claim, and conflicts become `UNRESOLVED`.
- Added synthetic offline fixture, unit/integration counterexamples and `docs/research-cross-validation.md`; no network, credentials, LLM, provider adapter, DAG, persistence, API, UI or recommendation path was introduced.

### Independent review evidence

- Full suite: `122 passed` (Phase 1–5's 103 tests remain green).
- `python -m compileall -q app`, research import, `git diff --check`, fixture JSON and source/fixture sensitive-field scans passed.
- Independent adversarial checks passed for repeated-lineage de-duplication, no-lineage insufficiency, support/contradiction conflicts, non-VERIFIED exclusion, scope mismatch, partial/failed nodes, forged result rejection, stable IDs and absence of recommendation/order/secret-shaped output fields.
- Phase 6 is accepted in this worktree after the above review; the next bounded-orchestration/Evidence-integration plan must use a new worktree.

## 2026-09-01 — MVP Phase 7 bounded orchestration plan

### Plan and worktree

- Created dedicated worktree `D:\Github_Storage\prism-phase-7` on branch `codex/mvp-phase-7-bounded-orchestration` from the accepted Phase 6 worktree.
- Added `docs/plans/2026-09-01-mvp-phase-7-bounded-orchestration.md` before implementation.
- The phase narrows orchestration to a pure, owner-scoped DAG/run state contract with explicit budget, deadline, dependency and degradation semantics; it does not execute a Provider or Agent.

### Implemented locally

- Added immutable `ResearchNodeSpec`, `ResearchPlan`, `ResearchNodeRun` and `ResearchRunState` contracts with deterministic topology, metadata closure and terminal-state invariants.
- Added pure transitions for run creation/start, dependency-gated node results, required/optional degradation, deadline failure, blocked descendants and cancellation; old states remain unchanged and raw exceptions/payloads are not stored.
- Added synthetic offline fixture, unit/integration counterexamples and `docs/bounded-orchestration.md`; no network, credentials, LLM, Provider, async executor, persistence, API, UI or recommendation path was introduced.

### Independent review evidence

- Full suite: `138 passed` (Phase 1–6's 122 tests remain green).
- `python -m compileall -q app`, orchestration import, `git diff --check`, fixture JSON and secret-like assignment scans passed.
- Independent adversarial checks passed for deterministic topology, request normalization, deadline rejection, active-node closure, required-node failure, dependency cancellation, forged state rejection, safe cancellation reasons and immutable source states.
- Phase 7 is accepted in this worktree after the above review; the next Evidence-grounded Finding/compliance plan must use a new worktree.

## 2026-09-01 — MVP Phase 8 Evidence-grounded Fact/Finding bridge

### Plan and worktree

- Created dedicated worktree `D:\Github_Storage\prism-phase-8` on branch `codex/mvp-phase-8-evidence-finding` from the accepted Phase 7 commit `3e5a021`.
- Added `docs/plans/2026-09-01-mvp-phase-8-evidence-finding.md` and committed the plan before implementation (`b9e7dc5`).
- The phase is limited to deterministic closure from `CrossValidationResult` plus owner/lineage-bound `ResearchObservation` and normalized `Evidence`; Recommendation, compliance, network, persistence and UI remain out of scope.

### Implemented locally

- Added `EvidenceFindingBridgeResult` with explicit `READY`, `REVIEW_REQUIRED` and `BLOCKED` states and safe issue codes.
- Added `bridge_cross_validation` / `build_evidence_grounded_finding`: only a clean `SUPPORTED` result with two independent lineages, VERIFIED evidence, exact scope/value/unit/period/provenance and owner closure can produce stable `VERIFIED Fact -> Finding` objects.
- Added bounded sensitive-input filtering, no raw validation issue/payload propagation, deterministic fact/finding IDs, synthetic fixture, unit/integration counterexamples and `docs/evidence-finding-bridge.md`.
- No Provider execution, LLM, Recommendation, order, database, API, UI or upstream repository change was introduced.

### Independent review evidence

- Phase-specific bridge tests and independent adversarial review pass; full suite reports `156 passed` (Phase 1–7's 138 tests remain green).
- `python -m compileall -q app`, research bridge import, `git diff --check`, fixture JSON and sensitive-value scans all pass.
- Adversarial checks cover stable ordering, DecisionTrace closure, forged `SUPPORTED`, duplicate lineage, missing/unknown evidence, owner/provenance tampering, sensitive text/IDs and immutable inputs.
- Phase 8 is accepted in this worktree; the next bounded fixture-backed async research execution plan must use a new worktree.

## 2026-09-01 — MVP Phase 9 fixture-backed async research run

### Plan and worktree

- Created dedicated worktree `D:\Github_Storage\prism-phase-9` on branch `codex/mvp-phase-9-fixture-research-run` from the accepted Phase 8 commit `6606be1`.
- Added `docs/plans/2026-09-01-mvp-phase-9-fixture-research-run.md` and committed the plan before implementation (`8d1cabb`).
- The phase is limited to an injected-provider execution adapter: bounded parallel ready nodes, dependency gating, four-state mapping, and normalized Evidence/Observation output. Live SkillHub, LLM, persistence, UI and recommendation generation remain out of scope.

### Implemented locally

- Added `ResearchNodeRequest`, `ResearchRunExecutionResult` and `execute_research_run`/`run_research` under `app/orchestration/executor.py`.
- Reused `execute_with_budget`, `normalize_result_to_evidence` and all Phase 7 transitions; ready roots run concurrently, children wait for completed parents, and required/optional/deadline semantics remain authoritative.
- Mapped Provider `SUCCESS/PARTIAL/EMPTY/FAILED` and timeout/exception paths to safe typed research results. Textual Evidence is retained, finite scalar fields become owner-bound Observations, and missing lineage remains visible without counting as independent support.
- Added synthetic multi-node fixture, unit/integration counterexamples and `docs/fixture-research-run.md`; no raw exception, credential, zero fallback, network call, LLM, persistence, UI or Recommendation path was introduced.

### Independent review evidence

- Phase-specific tests and independent review pass; full suite reports `169 passed` (Phase 1–8's 156 tests remain green).
- Parallel timing, dependency order, four-state mapping, timeout/exception safety, provider identity, sensitive value filtering, no-lineage behavior, output closure and input immutability are covered.
- `python -m compileall -q app`, orchestration import, `git diff --check`, fixture JSON and sensitive-value scans all pass.
- Phase 9 is accepted in this worktree; the next Evidence/Finding consumer plus risk/compliance gate plan must use a new worktree.

## 2026-09-01 — MVP Phase 10 research-to-Evidence pipeline

### Plan and worktree

- Created dedicated worktree `D:\Github_Storage\prism-phase-10` on branch `codex/mvp-phase-10-research-evidence-pipeline` from the accepted Phase 9 commit `7ae186b`.
- Added `docs/plans/2026-09-01-mvp-phase-10-research-evidence-pipeline.md` and committed the plan before implementation (`405f80e`).
- The phase is limited to consuming a `ResearchRunExecutionResult`: run-aware Cross Validation and Phase 8 Evidence/Finding registration. Risk, compliance, Recommendation, network, persistence and UI remain out of scope.

### Implemented locally

- Added `ResearchClaimSpec`, `ResearchEvidencePipelineResult`, safe pipeline issue contracts and `build_research_evidence_pipeline`/`evaluate_research_run`.
- Complete runs with two independent lineages can produce READY `VERIFIED Fact -> Finding` objects and a closed `DecisionTrace`; PARTIAL/FAILED/EMPTY runs downgrade supported claims to explicit unresolved review and expose no Facts/Findings in the trace.
- Added deterministic claim ordering, validation/bridge closure, duplicate/owner checks, sensitive-output filtering, two-lineage fixture and unit/integration counterexamples; no Recommendation, network, LLM, persistence, UI or upstream change was introduced.

### Independent review evidence

- Phase-specific pipeline tests and independent adversarial review pass; full suite reports `177 passed` (Phase 1–9's 169 tests remain green).
- Verified complete/partial/contradictory/single-lineage semantics, forged execution/evidence, duplicate/foreign claims, sensitive text, closed DecisionTrace and input immutability.
- `python -m compileall -q app`, imports from both orchestration and research pipeline modules, `git diff --check`, fixture JSON and sensitive-value scans all pass.
- Phase 10 is accepted in this worktree; the next independent risk/compliance gate plan must use a new worktree.

## 2026-09-02 — MVP Phase 11 independent risk and compliance gates

### Plan and worktree

- Created dedicated worktree `D:\Github_Storage\prism-phase-11` on branch `codex/mvp-phase-11-risk-compliance-gates` from the accepted Phase 10 commit `039c7c8`.
- Added `docs/plans/2026-09-01-mvp-phase-11-risk-compliance-gates.md` and committed the plan before implementation (`98dc23f`).
- The phase is limited to independent Recommendation eligibility checks over existing profile, research, risk-budget, and allocation artifacts. It does not create a Recommendation or call a network/LLM/storage/UI boundary.

### Implemented locally

- Added frozen `AdvisoryCandidate`, risk/compliance issue and result contracts, `DecisionGateResult`, fixed disclosure codes, and `PASS`/`REVIEW_REQUIRED`/`BLOCKED` semantics under `app/gates`.
- Added `evaluate_risk_gate`, which revalidates every input and closes owner/profile/version/drawdown, research trace quality, budget limits, report identities, timestamps, band limits, breach references, and assessment/allocation status. A complete deterministic breach may pass only as explicit remediation eligibility bound to the exact breach IDs; partial or unresolved risk data still requires review.
- Added `evaluate_compliance_gate`, which closes candidate Finding references through VERIFIED Facts/Evidence, requires four explicit disclosures, and blocks credential-shaped input, guarantee/no-loss language, and numeric target-return promises without echoing rejected prose.
- Added `evaluate_decision_gates`; Recommendation eligibility is true only when both independent gates PASS. Gate IDs bind full inputs through local content signatures, while outputs contain no candidate prose, Recommendation, action, order, or return target.
- Added a full offline fixture and unit/integration counterexamples. No real SkillHub, credential, LLM, persistence, API, UI, order execution, optimization, or legal-coverage claim was introduced.

### Independent review evidence

- Phase-specific gate tests: `20 passed`.
- Final full regression suite after adversarial hardening: `197 passed` (Phase 1–10's 177 tests remain green).
- `python -m compileall -q app`, public gate imports, all 15 fixture JSON files, `git diff --check`, no-network/storage/LLM import scan, and fixture sensitive-key scan passed.
- Independent post-commit checks passed for wrong-type inputs, 100-run determinism, immutable inputs, sensitive owner redaction, combined review/block precedence, candidate prose non-echo, content-bound IDs, deterministic breach remediation, bridge/trace divergence, and absence of Recommendation/action fields.
- Phase 11 is accepted in this worktree. Phase 12 must start from this accepted commit in a new worktree and may consume only a dual-PASS gate result; no push was performed.

## 2026-09-02 — MVP Phase 12 Recommendation and Decision Receipt

### Plan and worktree

- Created dedicated worktree `D:\Github_Storage\prism-phase-12` on branch `codex/mvp-phase-12-recommendation-receipt` from accepted Phase 11 commit `38c53c2`.
- Added `docs/plans/2026-09-02-mvp-phase-12-recommendation-decision-receipt.md` and committed the plan before implementation (`5796192`).
- The phase is limited to deterministic Recommendation composition after a dual-PASS gate and an in-memory self-validating Decision Receipt; API, persistence, UI, live providers and LLM remain out of scope.

### Implemented locally

- Added frozen `RecommendationBinding`, `DecisionReceipt`, `RecommendationCompositionResult`, rule-version and issue contracts under `app/recommendation`.
- Added `compose_recommendations`: revalidates all profile/portfolio/research/risk/allocation/candidate/gate inputs, reruns the Phase 11 gate, emits only ASSET `HOLD` for no-breach envelopes or breach-bound `REDUCE` within exact allocation bands, and rebuilds a closed `DecisionTrace`.
- Added an explicit aggregate-breach guard: sector/technology/unclassified breaches without an asset mapping are blocked rather than presented as a fake security recommendation.
- Added canonical content signatures and a receipt builder recording owner/profile/snapshot/report/gate/evidence/fact/finding/recommendation identities, rule versions, deterministic generation mode, band/breach bindings, trace hash and content hash.
- Added balanced/conservative fixtures, unit/integration counterexamples, and `docs/recommendation-decision-receipt.md`. No ADD/EXIT, price, quantity, target return, order, cash redistribution, LLM, network, persistence or UI behavior was introduced.

### Current review evidence

- Phase-specific Recommendation/Receipt tests: `17 passed`.
- Full regression suite: `215 passed`.
- `python -m compileall -q app`, public Recommendation imports, all fixture JSON
  parsing, `git diff --check`, no-network/storage/LLM boundary scan, and fixture
  sensitive-value scan passed.
- Additional adversarial checks cover non-VERIFIED trace reuse, forged extra
  remediation breaches, gate/candidate/run/assessment/allocation receipt identity,
  non-ASSET REDUCE rejection, receipt hash tampering, 100-run determinism and
  input immutability.
- Independent post-commit review passed on commit `d0fe0b6`: clean worktree,
  full `215 passed`, compile/import checks, fixture/sensitive scans, and
  no-network/storage/LLM boundary checks all passed.
- Phase 12 is accepted locally. No push was performed; Phase 13 must start from
  this accepted commit in a new worktree.

## 2026-09-02 — MVP Phase 13 owner-scoped API, persistence and explainable UI

### Plan and worktree

- Created dedicated worktree `D:\Github_Storage\prism-phase-13` on branch
  `codex/mvp-phase-13-api-persistence-ui` from accepted Phase 12 commit `076e1e6`.
- Added the Phase 13 plan before implementation: owner-scoped SQLite decision
  events, FastAPI health/create/list/detail boundaries, and a zero-build
  explainable workbench first slice. Real authentication, PostgreSQL, live
  providers and API-triggered orchestration remain explicitly out of scope.

### Implemented locally

- Added immutable `DecisionEvent`/summary contracts, idempotent content hashes,
  a migration-backed SQLite store with owner queries, conflict detection,
  corruption checks and serialized read/write revalidation.
- Added FastAPI app factory with safe validation/conflict/scope errors and
  health/create/list/detail routes. `PASS` events retain a closed Receipt;
  `REVIEW_REQUIRED`/`BLOCKED` events remain empty-trace refusals.
- Added the Prism workbench first slice with Overview, Advisor, Evidence and
  Risk Profile panels, CSP, text-only DOM insertion and the reused warm-white /
  deep-ink / clay visual grammar.
- Added Phase 13 unit/API tests and updated architecture/API documentation.

### Pre-commit verification

- Phase-specific store/API/fixture tests: `12 passed` (one upstream
  Starlette/httpx deprecation warning only).
- Full regression suite: `227 passed`; `python -m compileall -q app`, public API/store
  imports, all fixture JSON parsing, `git diff --check`, and static DOM/boundary
  scans passed.
- Built a local wheel with `--no-build-isolation` and confirmed the SQLite migration
  and all three static workbench assets are packaged.
- Real local browser acceptance against uvicorn: the owner-scoped workbench loaded
  four fixture events, showed balanced `HOLD` and conservative `REDUCE`, expanded
  `Finding → Fact → Evidence`, and rendered explicit `待复核`/`已阻断` empty-result
  states without a Receipt or executable recommendation.

Independent post-commit adversarial review and final acceptance are still pending.

### Independent post-commit review and acceptance

- Re-ran the committed tree at `e7eddd2`: full suite `227 passed`, with only the
  installed Starlette/httpx deprecation warning; compile/import, all fixture JSON,
  `git diff --check`, full-app network/LLM boundary, static DOM safety, and wheel
  package-data checks passed.
- Replayed owner isolation, idempotent retry/conflict, JSON/hash corruption,
  sensitive owner/body rejection, and non-PASS Receipt/trace invariants through the
  tests and store/API boundary.
- Restarted uvicorn from the committed worktree and verified the real browser: four
  owner-scoped events, BALANCED `HOLD`, CONSERVATIVE `REDUCE`, expandable
  `Finding → Fact → Evidence`, and explicit `待复核`/`已阻断` states. The latter two
  expose no Receipt or executable recommendation.
- Phase 13 is accepted locally. No push was performed. The next phase must start in
  a new worktree from `e7eddd2` and keep the API owner-scoped while adding only the
  planned fixture-query/Profile/Portfolio integration.

## 2026-09-02 — MVP Phase 14 Advisor query, Profile and Portfolio integration

### Plan and worktree

- Created dedicated worktree `D:\Github_Storage\prism-phase-14` on branch
  `codex/mvp-phase-14-api-fixture-query-profile-portfolio` from accepted Phase 13
  commit `0156f1b`.
- Added `docs/plans/2026-09-02-mvp-phase-14-advisor-query-profile-portfolio.md` and
  committed the plan before implementation (`52bb2e3`).
- This phase is limited to a structured, offline fixture-first Advisor query. It
  does not add live SkillHub/Tushare, credentials, LLM/chat, production storage,
  orders, target prices or a new UI business structure.

### Implemented locally

- Added immutable `AdvisorQueryRequest`/`AdvisorQueryOutput` contracts with owner
  closure, timezone replay anchor, bounded identifiers, extra-field rejection and
  sensitive-input refusal.
- Added a fixture manifest and two independent source/record/lineage Provider
  fixtures. The service reuses Profile, Portfolio Exposure/Concentration, Risk
  Budget, Allocation, Research Executor/Pipeline, Risk/Compliance Gates,
  Recommendation Composer and DecisionEvent Store rather than duplicating rules.
- Added `POST /api/v1/advisor/queries`; successful calls persist an owner-scoped,
  content-addressed DecisionEvent and repeated fixed inputs return `created=false`.
  Provider degradation remains REVIEW_REQUIRED/BLOCKED with no executable receipt,
  recommendation or trace.
- Added `docs/advisor-query-api.md`, package data declarations, unit/API tests and
  updated README, architecture, TODO and this execution log.

### Current verification

- Phase-specific tests: `11 passed`.
- Full regression suite: `238 passed` with only the installed Starlette/httpx
  deprecation warning.
- Deterministic replay now uses the injected `generated_at` clock through fixture
  load and execution; evidence integrity checks match each expected source,
  record, lineage, field, unit, period and Decimal value.
- Post-commit compile/import, fixture JSON, package-data, source boundary, static UI
  and real-browser acceptance all passed. Browser evidence shows an API-triggered
  BALANCED `HOLD` Receipt with expanded Finding→Fact→two Evidence sources; another
  owner sees no events.
- Independent adversarial review passed for Pydantic-bypass revalidation, 100-run
  deterministic/concurrent execution, one-for-one manifest evidence integrity,
  owner/error isolation and non-executable degraded results.
- Phase 14 is accepted locally at the current worktree `HEAD`. No push was
  performed; the next phase
  must start in a new worktree with a plan committed before implementation.

## 2026-09-02 — MVP Phase 16 four-track research specialist matrix

### Plan and worktree

- Created dedicated worktree `D:\Github_Storage\prism-phase-16` on branch
  `codex/mvp-phase-16-research-node-matrix` from accepted Phase 15 `HEAD`.
- Committed the plan before implementation as `33892dd`. Scope is deterministic
  Macro/Industry/Stock/ETF-Fund source recipes and a fixture-first matrix runner;
  SkillHub/Tushare, authentication, Gemini/LLM, persistence, UI and orders remain
  explicitly out of scope.

### Implemented locally

- Added `ResearchSpecialistRole`, owner-closed `ResearchSpecialistNode` and
  `ResearchSpecialistMatrix` contracts with a shared kind→Provider operation whitelist,
  deterministic dependency validation, dual-lineage claim closure and safe replay request.
- Added packaged four-track manifest and eight synthetic Provider fixtures. The service
  rebinds owner, creates the existing `ResearchPlan`, runs all roots through the existing
  bounded executor, scopes multi-claim observations safely and consumes the existing
  Cross Validation/Evidence bridge.
- Extended `ResearchClaimSpec` with an explicit observation scope that cannot omit an
  executed observation of the same subject/metric/unit/period; repeated pipeline issue
  codes are aggregated without losing per-claim bridge detail.
- Added unit/integration/adversarial tests, package-data configuration and the
  [research specialist matrix contract](research-specialist-matrix.md).

### Independent review and acceptance

- Full regression: `257 passed` with only the installed Starlette/httpx deprecation
  warning; compile/import, JSON/fixture, wheel, static and `git diff --check` checks passed.
- Review covered four-kind/operation and cycle rejection, owner/Pydantic bypass, source
  and Provider identity tampering, conflict/partial/failed/timeout degradation, no-zero
  semantics, deterministic replay, scope anti-bypass, and 100 concurrent runs.
- No network, LLM/Gemini, transaction, recommendation or order path was introduced.
  Phase 15 API/UI regression remains green; no new browser flow was required by this
  plan because it does not change the UI.
- Phase 16 is accepted locally at the current worktree `HEAD`; no push was performed.
  The next phase must begin in a new worktree with a plan-only commit.

## 2026-09-02 — MVP Phase 15 structured Advisor Query workbench

### Plan and worktree

- Created dedicated worktree `D:\Github_Storage\prism-phase-15` on branch
  `codex/mvp-phase-15-query-workbench` from the accepted Phase 14 tree.
- Committed the plan before implementation as `765d64c`. Scope is a structured,
  owner-scoped query form and packaged synthetic template; live Provider access,
  authentication, LLM/chat, CRUD, new financial rules and orders remain out of scope.

### Implemented locally

- Added a validated `AdvisorQueryTemplate` contract and packaged two-lineage synthetic
  query template. The service rebinds every owner-bearing nested model and rejects
  sensitive or mismatched templates.
- Added `GET /api/v1/advisor/query-template` and a form with explicit risk, horizon,
  liquidity, experience, return-expectation and drawdown fields. Submission reuses the
  Phase 14 `AdvisorQueryRequest`/service/store chain and keeps CSP/text-only DOM safety.
- Added focused contract/API/static tests and the [structured workbench contract](docs/advisor-query-workbench.md).

### Independent acceptance

- Full regression: `243 passed`; compile/import, fixture JSON, wheel package-data,
  `git diff --check`, no-network/LLM/transaction and static DOM boundary scans passed.
- Adversarial review passed template owner isolation, sensitive and forged-input refusal,
  generic error handling, 100 concurrent deterministic runs, unique events, and replay.
- Real local browser passed BALANCED `HOLD`, CONSERVATIVE `REDUCE`, `PASS · 已复用`,
  `Finding → Fact → Evidence` expansion and a second owner seeing `0 events`.
- Phase 15 is accepted locally at the current worktree `HEAD`; no push was performed.
  The next phase must start in a new worktree after a plan-only commit.

## 2026-09-02 — MVP Phase 17 Research Tracks 工作台

## 计划与 worktree

- 在已接受的 Phase 16 `b04740c` 上创建独立 worktree
  `D:\Github_Storage\prism-phase-17`，分支为
  `codex/mvp-phase-17-research-workbench`。
- 先提交范围、复用边界、产品差异化、验收门和明确不做项计划
  `aeefebc`；本阶段仍不接入真实 SkillHub/Tushare、鉴权、LLM、生产持久化或交易。

## 本地实现

- 在 `app/api` 增加 owner-scoped `research-matrix-template` 与 `research-runs` 路由，
  使用严格 `ResearchSpecialistMatrixRequest`，统一映射 owner scope、invalid input
  和 matrix refusal 错误；输出只保留节点状态、交叉验证和闭合 DecisionTrace。
- 增加 Research Tracks 静态工作台区域：四类轨道的节点状态、独立 lineage 数、
  READY/REVIEW/BLOCKED 语义和 Finding → Fact → Evidence 展开均来自既有 pipeline；
  动态文字继续用 text-only DOM/CSP 渲染，owner 切换和异步竞态会清空旧研究状态。
- 新增 [Research Tracks 工作台契约](docs/research-workbench.md) 与 Phase 17 API、
  owner 隔离、降级、重放、伪造 Pydantic 输出和静态安全测试。

## 独立审查与验收

- 实现提交：`8db4246`；补强伪造输出/敏感输入/无时区/100 次重放测试并修正空白：
  `9d210bc`。
- 全量回归：`264 passed`，仅已知 Starlette/httpx deprecation warning；
  `compileall`、公开导入、`node --check`、`git diff --check` 通过。
- 100 次相同 API request replay 返回完全相同的 run/pipeline/trace，且不写入
  `DecisionEventStore`；PARTIAL fixture 通过 API 保持 `REVIEW_REQUIRED`/`FAILED`，
  不暴露 Fact/Finding/Recommendation。
- adversarial review 覆盖额外字段、敏感 owner、无时区、未知矩阵、跨 owner、
  `model_copy(update=...)` 伪造输出与异常安全映射；没有发现可将研究状态升级为
  Recommendation/Receipt 的路径。
- wheel package-data 检查确认静态资源、四轨道 manifest/provider fixtures 和
  service 均在包内；边界扫描确认没有新增外网、LLM/Gemini、订单或事务路径。
- 真实本地浏览器完成最新代码的 owner→研究矩阵→8 节点/4 role READY→展开
  Finding/Fact/Evidence→换 owner 清空；同一浏览器还回归了 Advisor `HOLD` 与
  `REDUCE` 两条 Receipt 路径，浏览器错误日志为空。

Phase 17 在本地 worktree 接受，未 push；下一阶段必须从本阶段接受提交创建新
worktree，并先提交计划书。
