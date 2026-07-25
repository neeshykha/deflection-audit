"""Tests for the deterministic half of the audit.

The rate math and the report renderer are pure functions over labels -- they get
unit tests. The classifier is stochastic and gets an eval instead (results/
scorecard.md). Keeping those two kinds of verification apart is deliberate: a
passing test suite here says nothing about whether the auditor's judgment is good,
and the scorecard says nothing about whether the arithmetic is right.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import deflection
import render_html


def rec(cid, disposition="ai_closed"):
    return {
        "id": cid,
        "system_disposition": disposition,
        "ticket_text": f"ticket text for {cid}",
        "ai_response": "response",
    }


def test_audit_population_excludes_escalated():
    records = [rec("A"), rec("B"), rec("C", "escalated_to_human")]
    assert [r["id"] for r in deflection.audit_population(records)] == ["A", "B"]


def test_escalated_stay_in_the_denominator():
    """The claimed rate is closures over total volume, so escalations dilute it.
    Dropping them would flatter the vendor."""
    records = [rec("A"), rec("B", "escalated_to_human")]
    report = deflection.compute(records, {"A": "resolved"})
    assert report.total == 2
    assert report.claimed_deflected == 1
    assert report.claimed_rate == 0.5


def test_rates_and_inflation():
    records = [rec(c) for c in "ABCD"]
    outcomes = {"A": "resolved", "B": "resolved", "C": "partial", "D": "false_deflection"}
    report = deflection.compute(records, outcomes)

    assert report.claimed_rate == 1.0
    assert report.audited_rate == 0.5
    assert report.inflation_points == pytest.approx(50.0)
    assert report.overstatement_factor == pytest.approx(2.0)


def test_partials_are_not_credited():
    """A conversation the resident has to reopen was not deflected."""
    records = [rec("A"), rec("B")]
    report = deflection.compute(records, {"A": "resolved", "B": "partial"})
    assert report.audited_resolved == 1
    assert report.partial == 1
    assert report.audited_rate == 0.5


def test_false_deflection_rate_is_share_of_claimed():
    records = [rec(c) for c in "ABCD"]
    outcomes = {"A": "resolved", "B": "resolved", "C": "partial", "D": "false_deflection"}
    report = deflection.compute(records, outcomes)
    assert report.false_deflection_rate == pytest.approx(0.5)


def test_unscored_conversations_are_never_credited():
    """An audit that could not read a conversation does not get to assume the
    best about it."""
    records = [rec("A"), rec("B")]
    report = deflection.compute(records, {"A": "resolved"})
    assert report.unscored == 1
    assert report.audited_resolved == 1
    assert report.audited_rate == 0.5


def test_empty_input_does_not_divide_by_zero():
    report = deflection.compute([], {})
    assert report.claimed_rate == 0.0
    assert report.audited_rate == 0.0
    assert report.overstatement_factor == 0.0
    assert report.false_deflection_rate == 0.0


def test_all_false_deflection():
    records = [rec("A"), rec("B")]
    report = deflection.compute(records, {"A": "false_deflection", "B": "false_deflection"})
    assert report.audited_rate == 0.0
    assert report.inflation_points == pytest.approx(100.0)
    assert report.overstatement_factor == 0.0  # undefined against a zero audited rate
    assert report.false_deflection_rate == pytest.approx(1.0)


def test_honest_dashboard_shows_no_inflation():
    records = [rec("A"), rec("B")]
    report = deflection.compute(records, {"A": "resolved", "B": "resolved"})
    assert report.inflation_points == pytest.approx(0.0)
    assert report.overstatement_factor == pytest.approx(1.0)


def test_failure_modes_exclude_none_and_sort_by_frequency():
    records = [rec(c) for c in "ABCD"]
    outcomes = dict.fromkeys("ABCD", "false_deflection")
    modes = {
        "A": "resident_abandoned",
        "B": "resident_abandoned",
        "C": "answered_wrong_question",
        "D": "none",
    }
    report = deflection.compute(records, outcomes, modes)
    assert list(report.failure_modes.items()) == [
        ("resident_abandoned", 2),
        ("answered_wrong_question", 1),
    ]


def test_outcome_order_puts_costliest_first():
    """eval_kit's ordinal_misses reads index 0 as most severe; over-crediting the
    AI has to land in the under-predicted bucket for the scorecard to read right."""
    assert deflection.OUTCOME_ORDER[0] == deflection.FALSE_DEFLECTION
    assert deflection.OUTCOME_ORDER[-1] == deflection.RESOLVED


# --- renderer -------------------------------------------------------------


@pytest.fixture
def rendered():
    records = [rec(c) for c in "ABCD"] + [rec("E", "escalated_to_human")]
    outcomes = {"A": "resolved", "B": "resolved", "C": "partial", "D": "false_deflection"}
    modes = {"A": "none", "B": "none", "C": "needed_human_action", "D": "resident_abandoned"}
    report = deflection.compute(records, outcomes, modes)
    items = {r["id"]: r for r in records}
    return report, render_html.render(
        report, items, outcomes, modes, trust="trust note", footer="footer note"
    )


def test_render_reports_the_headline_figures(rendered):
    report, page = rendered
    assert f"{report.claimed_rate:.1%}" in page   # 80.0%
    assert f"{report.audited_rate:.1%}" in page   # 40.0%
    assert "40.0" in page                          # inflation points
    assert "trust note" in page and "footer note" in page


def test_render_lists_rejected_closures_only(rendered):
    _, page = rendered
    assert ">C<" in page and ">D<" in page
    assert "needed_human_action" in page and "resident_abandoned" in page


def test_render_is_self_contained(rendered):
    """No external requests -- the page has to work opened straight from disk."""
    _, page = rendered
    assert "http://" not in page
    assert "<script" not in page.lower()
    for token in ("src=", "cdn", "@import"):
        assert token not in page.lower()


def test_render_escapes_ticket_text():
    records = [rec("A")]
    records[0]["ticket_text"] = "<script>alert(1)</script> & \"quotes\""
    outcomes, modes = {"A": "false_deflection"}, {"A": "resident_abandoned"}
    report = deflection.compute(records, outcomes, modes)
    page = render_html.render(report, {"A": records[0]}, outcomes, modes, trust="t", footer="f")
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_json_twin_matches_the_report(rendered):
    import json

    report, _ = rendered
    data = json.loads(render_html.to_json(report, {"A": "resolved"}, {"A": "none"}))
    assert data["total"] == report.total
    assert data["claimed_deflected"] == report.claimed_deflected
    assert data["audited_resolved"] == report.audited_resolved
    assert data["inflation_points"] == pytest.approx(report.inflation_points)


# --- the shipped dataset --------------------------------------------------


def test_shipped_dataset_is_well_formed():
    import json

    path = Path(__file__).resolve().parents[1] / "data" / "conversations.jsonl"
    rows = [json.loads(line) for line in path.open()]

    assert len({r["id"] for r in rows}) == len(rows), "duplicate ids"
    for r in rows:
        if r["system_disposition"] == "ai_closed":
            assert r["true_outcome"] in deflection.OUTCOME_ORDER
            assert r["true_failure_mode"] in deflection.FAILURE_MODES
            assert (r["true_outcome"] == "resolved") == (r["true_failure_mode"] == "none")
        else:
            assert r["true_outcome"] is None, "escalated conversations are not audited"


def test_every_trap_id_exists_in_the_dataset():
    import json

    from audit import CONFUSABLE_GROUPS

    path = Path(__file__).resolve().parents[1] / "data" / "conversations.jsonl"
    ids = {json.loads(line)["id"] for line in path.open()}
    for group in CONFUSABLE_GROUPS:
        missing = set(group.ids) - ids
        assert not missing, f"{group.label} references missing ids: {missing}"
