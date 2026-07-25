"""Renders the deflection finding as a self-contained static HTML page.

Stdlib only (string.Template, not str.format, so CSS braces pass through
untouched). The output has no external requests, so it works as a committed file
opened straight from disk or served by GitHub Pages -- a reviewer sees the finding
without installing anything.
"""

import html
import json
from string import Template

PAGE = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<style>
  :root {
    --bg: #ffffff; --fg: #1a1a1a; --muted: #666; --line: #e3e3e3;
    --card: #f7f7f8; --claimed: #b45309; --audited: #15803d; --bad: #b91c1c;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #16181c; --fg: #e8e8ea; --muted: #9a9aa2; --line: #2c2f36;
      --card: #1e2127; --claimed: #f59e0b; --audited: #4ade80; --bad: #f87171;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 2.5rem 1.25rem 4rem; background: var(--bg); color: var(--fg);
    font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }
  main { max-width: 860px; margin: 0 auto; }
  h1 { font-size: 1.75rem; line-height: 1.25; margin: 0 0 .4rem; letter-spacing: -.02em; }
  h2 { font-size: 1.15rem; margin: 2.75rem 0 .85rem; letter-spacing: -.01em; }
  .sub { color: var(--muted); margin: 0 0 2rem; font-size: .95rem; }
  .headline { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 1rem; }
  .stat { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 1.15rem 1.25rem; }
  .stat .label { font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
  .stat .value { font-size: 2.1rem; font-weight: 650; line-height: 1.15; margin-top: .35rem; font-variant-numeric: tabular-nums; }
  .stat .note { font-size: .82rem; color: var(--muted); margin-top: .3rem; }
  .claimed .value { color: var(--claimed); }
  .audited .value { color: var(--audited); }
  .gap .value { color: var(--bad); }
  .bar { display: flex; height: 34px; border-radius: 7px; overflow: hidden; border: 1px solid var(--line); margin: .5rem 0 .6rem; }
  .bar span { display: flex; align-items: center; justify-content: center; font-size: .8rem; font-weight: 600; color: #fff; }
  .seg-resolved { background: #15803d; }
  .seg-partial { background: #ca8a04; }
  .seg-false { background: #b91c1c; }
  .seg-unscored { background: #6b7280; }
  .legend { font-size: .85rem; color: var(--muted); }
  .legend b { color: var(--fg); font-weight: 600; }
  table { border-collapse: collapse; width: 100%; font-size: .9rem; }
  th, td { text-align: left; padding: .5rem .6rem; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { font-size: .78rem; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); font-weight: 600; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  code { background: var(--card); padding: .1rem .35rem; border-radius: 4px; font-size: .86em; }
  .scroll { overflow-x: auto; }
  .callout { border-left: 3px solid var(--claimed); background: var(--card); padding: .9rem 1.1rem; border-radius: 0 8px 8px 0; margin: 1.25rem 0; font-size: .93rem; }
  footer { margin-top: 3.5rem; padding-top: 1.25rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .84rem; }
  a { color: inherit; }
</style>
</head>
<body>
<main>
  <h1>$title</h1>
  <p class="sub">$subtitle</p>

  <div class="headline">
    <div class="stat claimed">
      <div class="label">Claimed deflection</div>
      <div class="value">$claimed_rate</div>
      <div class="note">$claimed_deflected of $total closed without handoff</div>
    </div>
    <div class="stat audited">
      <div class="label">Audited deflection</div>
      <div class="value">$audited_rate</div>
      <div class="note">$audited_resolved of $total genuinely resolved</div>
    </div>
    <div class="stat gap">
      <div class="label">Overstatement</div>
      <div class="value">$inflation pts</div>
      <div class="note">dashboard reports $factor&times; the audited rate</div>
    </div>
  </div>

  <h2>Where the claimed deflections went</h2>
  <div class="bar">$segments</div>
  <p class="legend">$legend</p>

  <h2>Why the closures failed</h2>
  <div class="scroll">
  <table>
    <thead><tr><th>Failure mode</th><th class="num">Count</th><th>What it means</th></tr></thead>
    <tbody>$failure_rows</tbody>
  </table>
  </div>

  <h2>Is the auditor trustworthy?</h2>
  <div class="callout">$trust</div>

  <h2>Every closure the audit rejected</h2>
  <div class="scroll">
  <table>
    <thead><tr><th>ID</th><th>Outcome</th><th>Failure mode</th><th>Resident said</th></tr></thead>
    <tbody>$miss_rows</tbody>
  </table>
  </div>

  <footer>$footer</footer>
</main>
</body>
</html>
""")

MODE_GLOSS = {
    "answered_wrong_question": "Accurate response aimed at the wrong problem, or one of several issues left unaddressed",
    "stale_or_wrong_article": "Guidance that does not apply to this device, app version, or account state",
    "needed_human_action": "Correct as far as it goes, but resolution needs a truck roll, refund, or replacement",
    "resident_abandoned": "Generic troubleshooting handed back with no diagnosis, closed without confirmation",
    "policy_refusal_loop": "Declined on policy grounds without giving the resident a workable path",
}

SEGMENTS = [
    ("audited_resolved", "seg-resolved", "resolved"),
    ("partial", "seg-partial", "partial"),
    ("false_deflections", "seg-false", "false"),
    ("unscored", "seg-unscored", "unscored"),
]


def _esc(text: str) -> str:
    return html.escape(str(text))


def render(report, items: dict, outcomes: dict, failure_modes: dict, trust: str, footer: str) -> str:
    closed = report.claimed_deflected or 1

    segments = ""
    legend_bits = []
    for attr, css, label in SEGMENTS:
        count = getattr(report, attr)
        if not count:
            continue
        pct = count / closed * 100
        text = str(count) if pct >= 7 else ""
        segments += f'<span class="{css}" style="width:{pct:.4f}%">{text}</span>'
        legend_bits.append(f"<b>{count}</b> {label} ({pct:.0f}%)")
    legend = " &middot; ".join(legend_bits)

    failure_rows = "".join(
        f"<tr><td><code>{_esc(mode)}</code></td><td class='num'>{count}</td>"
        f"<td>{_esc(MODE_GLOSS.get(mode, ''))}</td></tr>"
        for mode, count in report.failure_modes.items()
    ) or "<tr><td colspan='3'>No failed closures.</td></tr>"

    miss_rows = ""
    for cid in sorted(outcomes):
        if outcomes[cid] == "resolved":
            continue
        excerpt = items[cid]["ticket_text"]
        if len(excerpt) > 130:
            excerpt = excerpt[:130].rstrip() + "..."
        miss_rows += (
            f"<tr><td><code>{_esc(cid)}</code></td>"
            f"<td>{_esc(outcomes[cid])}</td>"
            f"<td><code>{_esc(failure_modes.get(cid, ''))}</code></td>"
            f"<td>{_esc(excerpt)}</td></tr>"
        )
    miss_rows = miss_rows or "<tr><td colspan='4'>No rejected closures.</td></tr>"

    return PAGE.substitute(
        title="Deflection Audit",
        subtitle="What an AI support deployment counted as deflected, versus what actually resolved.",
        claimed_rate=f"{report.claimed_rate:.1%}",
        audited_rate=f"{report.audited_rate:.1%}",
        inflation=f"{report.inflation_points:.1f}",
        factor=f"{report.overstatement_factor:.2f}",
        claimed_deflected=report.claimed_deflected,
        audited_resolved=report.audited_resolved,
        total=report.total,
        segments=segments,
        legend=legend,
        failure_rows=failure_rows,
        miss_rows=miss_rows,
        trust=trust,
        footer=footer,
    )


def to_json(report, outcomes: dict, failure_modes: dict) -> str:
    """Machine-readable twin of the page. app.py reads this so the Streamlit view
    and the HTML report never compute anything separately."""
    return json.dumps(
        {
            "total": report.total,
            "claimed_deflected": report.claimed_deflected,
            "audited_resolved": report.audited_resolved,
            "partial": report.partial,
            "false_deflections": report.false_deflections,
            "unscored": report.unscored,
            "claimed_rate": round(report.claimed_rate, 4),
            "audited_rate": round(report.audited_rate, 4),
            "inflation_points": round(report.inflation_points, 2),
            "overstatement_factor": round(report.overstatement_factor, 3),
            "false_deflection_rate": round(report.false_deflection_rate, 4),
            "failure_modes": report.failure_modes,
            "outcomes": outcomes,
            "audited_failure_modes": failure_modes,
        },
        indent=2,
    )
