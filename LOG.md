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
