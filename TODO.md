# TODO

> Updated: 2026-09-02
>
> Source of truth for product scope: [Prism.md](Prism.md)
>
> Overall execution plan: [docs/plans/2026-09-01-foundation.md](docs/plans/2026-09-01-foundation.md)
>
> Active phase: Phase 29 structured Context Memory is accepted in the dedicated
> `D:\Github_Storage\prism-phase-29` worktree. The next phase must start in a new worktree
> with its plan committed before implementation.

## P0 — Foundation

- [x] Initialize the independent `main` Git repository.
- [x] Record the modular-monolith and structured-DAG decision.
- [x] Produce and verify the upstream Reuse Matrix.
- [x] Implement the first Evidence/Fact/Finding/Recommendation contract.
- [x] Test missing data, stale evidence, reference closure and blocked decisions.
- [x] Define a fixture-first Provider Protocol with distinct `SUCCESS`, `PARTIAL`, `EMPTY`, and `FAILED` results.
- [x] Add per-call correlation IDs, deterministic request fingerprints, time budgets and redacted diagnostics.
- [x] Add recorded, synthetic Wencai/Tushare fixtures without credentials or private data.
- [x] Define schema versioning and Decision Receipt content hashes.
- [x] Add an owner-scoped local decision-event store and migration; PostgreSQL-oriented profile/evidence storage remains deferred.
- [x] Add an early load-test harness before implementing the full research graph; record
  local fixture P50/P95/P99 and keep production SLA claims deferred.

## P0 — Flagship vertical slice

- [x] Implement deterministic risk questionnaire scoring.
- [x] Define structured profile extraction proposals and explicit conflict confirmation (without LLM parsing).
- [x] Define portfolio and fund/ETF position import contracts.
- [x] Calculate look-through technology exposure and data coverage.
- [x] Implement concentration and profile-conditioned risk-budget findings; correlation, liquidity and advanced optimization remain deferred.
- [x] Generate conservative, balanced and growth-oriented allocation ranges (constraint envelope; final Recommendation remains deferred).
- [x] Show deterministic per-constraint pre/post impact and profile/snapshot invalidation conditions.
- [x] Prove that the same evidence produces materially different valid outputs for different profiles.

## P0 — Structured research and UI

- [x] Define four-state structured research-node results and lineage-aware Cross-Validation contract; real Provider/DAG integration remains deferred.
- [x] Define bounded owner-scoped research-run state, dependency closure and deadline semantics; async execution remains deferred.
- [x] Bridge only fully supported cross-validation claims into closed `VERIFIED Fact -> Finding` objects; degraded and mismatched evidence remains review/blocked.
- [x] Implement bounded Fixture-backed async orchestration with structured `ResearchRunState`, dependency gating and four-state mapping; live execution remains deferred.
- [x] Add deterministic Macro, Industry, Stock and Fund/ETF specialist node recipes with
  dual-lineage fixture execution; live Provider access remains deferred.
- [x] Implement source-lineage-aware cross validation and disagreement handling for executed fixture observations; live provider nodes remain deferred.
- [x] Consume complete-run validation through the Evidence/Finding bridge and emit a closed DecisionTrace; degraded runs remain review/blocked.
- [x] Implement and independently accept the risk and compliance gates.
- [x] Build Portfolio, Advisor, Evidence and Risk Profile workbench views.
- [x] Connect a structured Advisor Query form to the fixture-first API, replay receipt and
  owner-isolated Evidence view; broader Portfolio/Risk Profile interactions remain open.
- [x] Compose deterministic HOLD/REDUCE Recommendations from a dual-PASS gate and create a self-validating Decision Receipt.
- [x] Expose stored decision receipts through a FastAPI boundary and the first explainable workbench slice.
- [x] Trigger the fixture-first Advisor vertical slice from a structured API request and persist an idempotent DecisionEvent.
- [x] Add the owner-scoped Research Tracks template/run API and four-track workbench view;
  keep READY research separate from Recommendation/Decision Receipt.
- [x] Add the read-only Portfolio snapshot and Risk Profile questionnaire context views;
  keep template values owner-closed and defer CRUD/real account import.
- [x] Add structured Portfolio JSON and Risk Profile session confirmation before Advisor;
  keep real account upload, authentication and persistence deferred.
- [x] Add the versioned `eval_cases/` fixed-set evaluator and replay report required by
  `Prism.md`; keep market accuracy and live Provider claims deferred.
- [x] Add explicit owner-scoped investment intent contracts and a read-only four-track task
  plan preview; keep natural-language understanding, LLM/Gemini and research execution
  deferred.
- [x] Verify the complete flagship flow in a real browser.
- [x] Verify the Phase 15 form → API → HOLD/REDUCE → Evidence → owner isolation path in a
  real browser.
- [x] Add the typed ProfileExtractionProposal preview and explicit conflict confirmation;
  keep natural-language parsing, LLM/Gemini and raw-text persistence deferred.
- [x] Add an explicit Research Tracks scenario catalog for baseline, source disagreement,
  PARTIAL, EMPTY and FAILED replays; keep live Provider access and recommendation side
  effects deferred.
- [x] Add the independent Demo F stock research Evidence Card with six financial claims,
  deterministic quality/leverage Findings, five safe replay scenarios and visible node
  degradation reasons; keep live market data, valuation and Recommendation effects deferred.
- [x] Add the independent Demo G ETF/Fund asset research Evidence Card with six fund claims,
  deterministic concentration/cost/volatility/drawdown Findings, five safe replay scenarios
  and visible node degradation reasons; keep live market data, portfolio adjustment and
  Recommendation effects deferred.
- [x] Add the independent Phase 28 Portfolio Optimization target-structure proposal with
  `CAP_AND_REDISTRIBUTE_V1`, owner-scoped API/UI, profile-conditioned caps, closed target /
  constraint arithmetic, and explicit REVIEW_REQUIRED/BLOCKED scenarios; keep correlation,
  liquidity, asset-category caps, backtest, trading and Recommendation effects deferred.
- [x] Add the independent Phase 29 owner-scoped structured Context Memory ledger with immutable
  profile/questionnaire/portfolio snapshots, optional typed references, deterministic identity,
  SQLite migration/restart reads, explicit browser recovery and stale/owner isolation; keep
  raw chat, semantic retrieval, automatic restore, cloud sync, authentication and delete/TTL
  deferred.

## External inputs / decisions

- [ ] Obtain competition-specific SkillHub development documentation and credentials.
- [ ] Confirm SkillHub quotas, caching, retention, attribution and output-display rights.
- [ ] Obtain the scoring appendix referenced by the competition brief.
- [ ] Confirm reuse/provenance terms for both upstream repositories; neither root currently exposes a LICENSE/NOTICE file.
- [ ] Choose the Prism repository license before any public publication.

These inputs block claims of real SkillHub integration or submission readiness, but they do not block fixture-driven contract and vertical-slice development.

## Explicitly deferred

- broad persistent conversational memory beyond profile/decision audit state;
- autonomous trading or real order execution;
- microservices and Kubernetes;
- complex animation, persona-heavy Agent presentations and custom model training.

## Next useful action

Phase 29 is accepted in the dedicated `D:\Github_Storage\prism-phase-29` worktree; its final
browser, concurrency, wheel and regression evidence is recorded in the Phase 29 plan. The next
useful action is to select and plan Phase 30 in a brand-new worktree. Keep real authentication,
live Provider access, cloud/production persistence and broad conversational memory deferred.
