# TODO

> Updated: 2026-09-01
>
> Source of truth for product scope: [Prism.md](Prism.md)
>
> Overall execution plan: [docs/plans/2026-09-01-foundation.md](docs/plans/2026-09-01-foundation.md)
>
> Active phase: [MVP Phase 10 Research-to-Evidence Pipeline](docs/plans/2026-09-01-mvp-phase-10-research-evidence-pipeline.md)

## P0 — Foundation

- [x] Initialize the independent `main` Git repository.
- [x] Record the modular-monolith and structured-DAG decision.
- [x] Produce and verify the upstream Reuse Matrix.
- [x] Implement the first Evidence/Fact/Finding/Recommendation contract.
- [x] Test missing data, stale evidence, reference closure and blocked decisions.
- [x] Define a fixture-first Provider Protocol with distinct `SUCCESS`, `PARTIAL`, `EMPTY`, and `FAILED` results.
- [x] Add per-call correlation IDs, deterministic request fingerprints, time budgets and redacted diagnostics.
- [x] Add recorded, synthetic Wencai/Tushare fixtures without credentials or private data.
- [ ] Define schema versioning and Decision Receipt content hashes.
- [ ] Add PostgreSQL-oriented storage models and migrations for owner-isolated profiles, evidence and decision events.
- [ ] Add an early load-test harness before implementing the full research graph.

## P0 — Flagship vertical slice

- [x] Implement deterministic risk questionnaire scoring.
- [x] Define structured profile extraction proposals and explicit conflict confirmation (without LLM parsing).
- [x] Define portfolio and fund/ETF position import contracts.
- [x] Calculate look-through technology exposure and data coverage.
- [x] Implement concentration and profile-conditioned risk-budget findings; correlation, liquidity and optimization remain deferred.
- [x] Generate conservative, balanced and growth-oriented allocation ranges (constraint envelope; final Recommendation remains deferred).
- [x] Show deterministic per-constraint pre/post impact and profile/snapshot invalidation conditions.
- [x] Prove that the same evidence produces materially different valid outputs for different profiles.

## P0 — Structured research and UI

- [x] Define four-state structured research-node results and lineage-aware Cross-Validation contract; real Provider/DAG integration remains deferred.
- [x] Define bounded owner-scoped research-run state, dependency closure and deadline semantics; async execution remains deferred.
- [x] Bridge only fully supported cross-validation claims into closed `VERIFIED Fact -> Finding` objects; degraded and mismatched evidence remains review/blocked.
- [x] Implement bounded Fixture-backed async orchestration with structured `ResearchRunState`, dependency gating and four-state mapping; live execution remains deferred.
- [ ] Add macro, industry, stock and fund/ETF research nodes.
- [x] Implement source-lineage-aware cross validation and disagreement handling for executed fixture observations; live provider nodes remain deferred.
- [x] Consume complete-run validation through the Evidence/Finding bridge and emit a closed DecisionTrace; degraded runs remain review/blocked.
- [ ] Implement independent risk and compliance gates.
- [ ] Build Portfolio, Advisor, Evidence and Risk Profile workbench views.
- [ ] Verify the complete flagship flow in a real browser.

## External inputs / decisions

- [ ] Obtain competition-specific SkillHub development documentation and credentials.
- [ ] Confirm SkillHub quotas, caching, retention, attribution and output-display rights.
- [ ] Obtain the scoring appendix referenced by the competition brief.
- [ ] Confirm reuse/provenance terms for both upstream repositories; neither root currently exposes a LICENSE/NOTICE file.
- [ ] Choose the Prism repository license before any public publication.

These inputs block claims of real SkillHub integration or submission readiness, but they do not block fixture-driven contract and vertical-slice development.

## Explicitly deferred

- Convertible-bond research;
- broad persistent conversational memory beyond profile/decision audit state;
- autonomous trading or real order execution;
- microservices and Kubernetes;
- complex animation, persona-heavy Agent presentations and custom model training.

## Next useful action

Phase 10 is accepted only after its independent review evidence is recorded; the next phase must use a new worktree for independent risk/compliance gates and Recommendation eligibility.
