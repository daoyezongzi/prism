# TODO

> Updated: 2026-09-01
>
> Source of truth for product scope: [Prism.md](Prism.md)
>
> Overall execution plan: [docs/plans/2026-09-01-foundation.md](docs/plans/2026-09-01-foundation.md)
>
> Active delegated phase: [MVP Phase 1 Provider Protocol](docs/plans/2026-09-01-mvp-phase-1-provider-protocol.md)

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

- [ ] Implement deterministic risk questionnaire scoring.
- [ ] Implement structured natural-language profile extraction and conflict confirmation.
- [ ] Define portfolio and fund/ETF position import contracts.
- [ ] Calculate look-through technology exposure and data coverage.
- [ ] Implement concentration, correlation, liquidity and risk-budget findings.
- [ ] Generate conservative, balanced and growth-oriented allocation ranges.
- [ ] Show pre/post impact and recommendation invalidation conditions.
- [ ] Prove that the same evidence produces materially different valid outputs for different profiles.

## P0 — Structured research and UI

- [ ] Implement bounded async orchestration with structured `ResearchState`.
- [ ] Add macro, industry, stock and fund/ETF research nodes.
- [ ] Implement source-lineage-aware cross validation and disagreement handling.
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

Dispatch Phase 1B (persistence & storage contracts) or Phase 2 (user profile & portfolio import contracts) according to the execution route.
