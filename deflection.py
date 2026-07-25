"""Deflection rate math: what a vendor dashboard claims versus what an audit finds.

Vendors report deflection as the share of conversations the AI closed without a
human handoff. That counts closures, not resolutions. This module recomputes the
rate crediting only conversations an auditor judged genuinely resolved, and reports
the gap between the two.

Everything here is deterministic arithmetic over labels -- no model calls -- which
is why it is the part of the repo that gets unit tests rather than an eval.
"""

from collections import Counter
from dataclasses import dataclass

RESOLVED = "resolved"
PARTIAL = "partial"
FALSE_DEFLECTION = "false_deflection"

# Most costly first: this ordering is what makes eval_kit's "under-predicted"
# bucket read as over-crediting the AI, which is the expensive direction here.
OUTCOME_ORDER = [FALSE_DEFLECTION, PARTIAL, RESOLVED]

FAILURE_MODES = [
    "none",
    "answered_wrong_question",
    "stale_or_wrong_article",
    "needed_human_action",
    "resident_abandoned",
    "policy_refusal_loop",
]

CLOSED_BY_AI = "ai_closed"


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


@dataclass
class DeflectionReport:
    total: int
    claimed_deflected: int
    audited_resolved: int
    partial: int
    false_deflections: int
    unscored: int
    failure_modes: dict[str, int]

    @property
    def claimed_rate(self) -> float:
        """What the vendor dashboard reports: closures over total volume."""
        return _rate(self.claimed_deflected, self.total)

    @property
    def audited_rate(self) -> float:
        """Genuinely resolved over total volume. Partials are not credited -- a
        conversation the resident has to reopen was not deflected."""
        return _rate(self.audited_resolved, self.total)

    @property
    def inflation_points(self) -> float:
        """Percentage points of deflection the dashboard reports that the audit
        does not support."""
        return (self.claimed_rate - self.audited_rate) * 100

    @property
    def overstatement_factor(self) -> float:
        """Claimed rate as a multiple of audited rate. 1.0 means the dashboard is
        honest; 2.0 means it reports double the real figure."""
        return self.claimed_rate / self.audited_rate if self.audited_rate else 0.0

    @property
    def false_deflection_rate(self) -> float:
        """Share of claimed deflections that did not hold up."""
        return _rate(self.false_deflections + self.partial, self.claimed_deflected)


def audit_population(records: list[dict]) -> list[dict]:
    """The conversations a deflection claim actually rests on. Escalated
    conversations were never counted as deflected, so they are not audited -- but
    they stay in the denominator, because the claimed rate is computed over total
    volume."""
    return [r for r in records if r["system_disposition"] == CLOSED_BY_AI]


def tally_failure_modes(failure_modes: dict[str, str]) -> dict[str, int]:
    """Counts of each failure mode, excluding the `none` bucket that resolved
    conversations carry. Ordered most frequent first."""
    counts = Counter(m for m in failure_modes.values() if m and m != "none")
    return dict(counts.most_common())


def compute(
    records: list[dict],
    outcomes: dict[str, str],
    failure_modes: dict[str, str] | None = None,
) -> DeflectionReport:
    """records: every conversation in the sample, including escalated ones.
    outcomes: id -> audited outcome, for AI-closed conversations that classified
    successfully.
    failure_modes: id -> audited failure mode, same population.

    Conversations that failed to classify are counted as unscored and are never
    credited as resolved -- an audit that cannot read a conversation does not get
    to assume the best about it.
    """
    closed_ids = [r["id"] for r in audit_population(records)]
    tally = Counter(outcomes.get(cid) for cid in closed_ids)

    modes = {cid: (failure_modes or {}).get(cid) for cid in closed_ids}

    return DeflectionReport(
        total=len(records),
        claimed_deflected=len(closed_ids),
        audited_resolved=tally[RESOLVED],
        partial=tally[PARTIAL],
        false_deflections=tally[FALSE_DEFLECTION],
        unscored=tally[None],
        failure_modes=tally_failure_modes(modes),
    )
