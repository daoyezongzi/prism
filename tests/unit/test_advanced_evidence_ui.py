from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "app" / "api" / "static"


def test_advanced_evidence_markup_exposes_auditable_controls() -> None:
    markup = (STATIC / "index.html").read_text(encoding="utf-8")

    for element_id in (
        "advanced-evidence-explorer",
        "advanced-evidence-search",
        "advanced-evidence-quality",
        "advanced-evidence-mode",
        "advanced-evidence-source",
        "advanced-evidence-promotion",
        "advanced-evidence-summary",
        "advanced-evidence-list",
        "advanced-evidence-detail",
    ):
        assert f'id="{element_id}"' in markup
    assert "Evidence chain explorer" in markup
    assert "陈旧缓存与备用来源" in markup


def test_advanced_evidence_renderer_keeps_owner_and_quality_boundaries() -> None:
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    for token in (
        "function renderAdvancedEvidence()",
        "selectedEvent.owner_id === state.ownerId",
        "result.owner_id !== state.ownerId",
        "CACHE_FRESH",
        "FALLBACK_PROVIDER",
        "CACHE_STALE_FALLBACK",
        "STALE · 陈旧/需复核",
        "当前 Evidence 尚未进入 Fact/Finding",
        "textContent",
    ):
        assert token in script
    assert "innerHTML" not in script
    assert "outerHTML" not in script


def test_advanced_evidence_styles_have_keyboard_and_narrow_layout_rules() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")

    assert ".advanced-evidence-row:focus-visible" in styles
    assert ".advanced-evidence-layout" in styles
    assert ".advanced-evidence-controls" in styles
    assert "@media (max-width: 900px)" in styles
