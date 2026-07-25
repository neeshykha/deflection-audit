#!/usr/bin/env python3
"""Audits an AI support deployment's deflection claim.

Two layers, in order, because the second is worthless without the first:

  1. Is the auditor trustworthy? -- blind-classify every AI-closed conversation,
     score against labeled ground truth, write results/scorecard.md.
  2. What is the real deflection rate? -- recompute the rate crediting only
     genuinely resolved conversations, write results/report.html.

Classification logic lives in CLAUDE.md, loaded by the Claude Code CLI at runtime.
This file only orchestrates.

  python audit.py            # classify (costs money), score, render
  python audit.py --replay   # reuse committed predictions, no API calls
"""

import argparse
import json
import sys
from pathlib import Path

from eval_kit import BlindClassifier, TrapGroup, render_scorecard
from eval_kit.report import FieldConfig
from eval_kit.scorer import accuracy

import deflection
import render_html

ROOT = Path(__file__).parent
DATA_PATH = ROOT / "data" / "conversations.jsonl"
PREDICTIONS_PATH = ROOT / "predictions.jsonl"
RESULTS = ROOT / "results"

PROMPT_TEMPLATE = """Judge this closed support conversation per the outcome \
definitions, failure modes, and output format in CLAUDE.md.

Channel: {channel}

Resident wrote:
\"\"\"{ticket_text}\"\"\"

AI agent replied, then closed the conversation:
\"\"\"{ai_response}\"\"\"

Return only the JSON object described in the Output Format section. No other text."""

CONFUSABLE_GROUPS = [
    TrapGroup(
        ["D026", "D027", "D028"],
        "Polite closure is not resolution (generic troubleshooting handed back)",
        field="outcome",
    ),
    TrapGroup(
        ["D029", "D030"],
        "Correct answer to the wrong problem (a detail in the ticket invalidates the advice)",
        field="outcome",
    ),
    TrapGroup(
        ["D031", "D032"],
        "Closed with guidance the resident cannot act on",
        field="outcome",
    ),
    TrapGroup(
        ["D017", "D018", "D019", "D020"],
        "Hostile tone but genuinely resolved (auditor must not become a sentiment detector)",
        field="outcome",
    ),
]


def load_jsonl(path: Path) -> dict:
    return {json.loads(line)["id"]: json.loads(line) for line in path.open()}


def build_trust_note(scored: dict, truth: dict, traps_summary: str) -> str:
    correct, total = accuracy(scored, truth, "outcome")
    pct = correct / total if total else 0
    return (
        f"The deflection numbers above are only as good as the auditor producing them. "
        f"Scored against {total} hand-labeled conversations, the auditor agreed with ground "
        f"truth on <b>{correct}/{total} ({pct:.0%})</b> outcomes. {traps_summary} "
        f"Full confusion matrix, over-credit split, and per-trap breakdown are in "
        f"<a href=\"scorecard.md\">scorecard.md</a>."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replay",
        action="store_true",
        help="score and render from committed predictions.jsonl without calling the API",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="drop recorded error rows so the next run reclassifies only those",
    )
    parser.add_argument("--model", default="sonnet")
    args = parser.parse_args()

    if args.retry_failed and args.replay:
        sys.exit("--retry-failed reclassifies; it cannot be combined with --replay.")

    records = load_jsonl(DATA_PATH)
    population = deflection.audit_population(list(records.values()))
    items = {r["id"]: r for r in population}

    if args.replay:
        if not PREDICTIONS_PATH.exists():
            sys.exit("--replay needs predictions.jsonl; run without --replay first.")
        print(f"Replaying {PREDICTIONS_PATH.name} -- no API calls.", file=sys.stderr)
    else:
        classifier = BlindClassifier(PROMPT_TEMPLATE, model=args.model, cwd=ROOT)
        classifier.run(population, PREDICTIONS_PATH, retry_failed=args.retry_failed)

    predictions = load_jsonl(PREDICTIONS_PATH)
    errors = [pid for pid, p in predictions.items() if "error" in p]
    scored = {pid: p for pid, p in predictions.items() if "error" not in p and pid in items}

    if not scored:
        sample = next((predictions[e].get("error", "") for e in errors), "")
        sys.exit(
            f"Nothing classified: {len(errors)} of {len(predictions)} conversations failed.\n"
            f"First error: {sample[:200]}\n"
            "Delete predictions.jsonl before retrying -- failed rows are recorded and "
            "would otherwise be skipped as already done."
        )

    truth = {
        pid: {"outcome": r["true_outcome"], "failure_mode": r["true_failure_mode"]}
        for pid, r in items.items()
    }

    fields = [
        FieldConfig(
            "outcome",
            deflection.OUTCOME_ORDER,
            order=deflection.OUTCOME_ORDER,
            traps=CONFUSABLE_GROUPS,
            text_field="ticket_text",
        ),
        FieldConfig("failure_mode", deflection.FAILURE_MODES, text_field="ticket_text"),
    ]

    RESULTS.mkdir(exist_ok=True)
    scorecard = render_scorecard(
        "Deflection Auditor Scorecard", scored, truth, items, fields, errors
    )
    (RESULTS / "scorecard.md").write_text(scorecard)

    outcomes = {pid: p["outcome"] for pid, p in scored.items()}
    failure_modes = {pid: p.get("failure_mode", "") for pid, p in scored.items()}
    report = deflection.compute(list(records.values()), outcomes, failure_modes)

    trap_hits = sum(
        1
        for g in CONFUSABLE_GROUPS
        for pid in g.ids
        if pid in scored and scored[pid].get("outcome") == truth[pid]["outcome"]
    )
    trap_total = sum(len(g.ids) for g in CONFUSABLE_GROUPS)
    traps_summary = (
        f"It passed <b>{trap_hits}/{trap_total}</b> confusable-pattern traps -- "
        f"cases written so that a naive read gets them wrong."
    )

    page = render_html.render(
        report,
        items,
        outcomes,
        failure_modes,
        trust=build_trust_note(scored, truth, traps_summary),
        footer=(
            f"Generated by audit.py from {report.total} conversations "
            f"({report.claimed_deflected} AI-closed, {report.total - report.claimed_deflected} escalated). "
            "Synthetic dataset, deliberately weighted toward hard cases -- the gap shown "
            "is a property of this sample, not an estimate of any real deployment."
        ),
    )
    (RESULTS / "report.html").write_text(page)
    (RESULTS / "results.json").write_text(render_html.to_json(report, outcomes, failure_modes))

    print(f"Claimed deflection:  {report.claimed_rate:>6.1%}  ({report.claimed_deflected}/{report.total} closed by AI)")
    print(f"Audited deflection:  {report.audited_rate:>6.1%}  ({report.audited_resolved}/{report.total} genuinely resolved)")
    print(f"Overstatement:       {report.inflation_points:>5.1f} pts  ({report.overstatement_factor:.2f}x the audited rate)")
    print(f"Auditor accuracy:    {accuracy(scored, truth, 'outcome')[0]}/{len(scored)} outcomes, {trap_hits}/{trap_total} traps")
    if errors:
        print(f"Failed to classify:  {len(errors)}", file=sys.stderr)
    print(f"\nWrote {RESULTS/'scorecard.md'}, {RESULTS/'report.html'}, {RESULTS/'results.json'}")


if __name__ == "__main__":
    main()
