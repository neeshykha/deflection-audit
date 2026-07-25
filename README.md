# deflection-audit

Your AI support vendor reports 85% deflection. That number counts tickets the bot
closed, not problems anyone solved.

A conversation where the resident gave up, took a help-article link and never
followed it, or came back 18 hours later with the same broken lock all close the
same way in the dashboard: no human touched it, so it counts as deflected. The
metric measures the absence of a handoff and gets read as the presence of a
resolution.

This audits the gap. It re-judges every AI-closed conversation on whether the
resident actually got what they needed, recomputes the deflection rate crediting
only the ones that hold up, and reports the difference.

---

## Two layers, in that order

**1. Is the auditor trustworthy?** Blind-classify every closed conversation, score
against hand-labeled ground truth, report accuracy, the over-credit split, and
per-trap results. → [`results/scorecard.md`](results/scorecard.md)

**2. What is the real deflection rate?** Recompute crediting only genuine
resolutions, and break down where the rest went. →
[`results/report.html`](results/report.html)

Layer 2 is worthless without layer 1, and it is the layer everyone skips. An
audited number produced by an unaudited judge is just a second opinion with a
percent sign on it. Most "AI ROI" writeups ship layer 2 alone.

---

## The judgment call this makes

The interesting part is not counting re-contacts — the vendor's own dashboard could
do that a day later. It is deciding **at close time**, from the transcript alone,
whether a closure is real. That is what would let you flag a bad deflection while
the resident is still in the conversation.

So the classifier never sees the follow-up signal. `followup_signal` exists in the
dataset only to derive ground truth. The model gets the resident's message, the AI's
reply, and nothing else.

What makes a closure false, per [`CLAUDE.md`](CLAUDE.md):

- **Generic troubleshooting with no diagnosis** — restart the app, check Bluetooth,
  toggle a permission. A response that would read identically for any ticket has
  diagnosed nothing, and ending with "let me know if that helps" closes the ticket
  while handing the work back.
- **A link instead of an answer** — especially when the resident already described a
  state the article's steps would not reach.
- **Correct answer, wrong problem** — the reply accurately explains how to reset a
  PIN; the resident mentioned in passing that the keypad is dead.
- **Policy refusal with no path** — declining and redirecting is fine when the
  redirect is specific and actionable. Citing policy and stopping is not.

And the thing that most naive versions of this get wrong — **tone is not a signal**.
Angry residents get helped correctly all the time. An auditor that scores hostility
as failure is a sentiment detector wearing a quality-metric costume, which is why
four of the traps are furious residents whose problems were genuinely solved.

---

## How it works

```
data/conversations.jsonl   40 conversations, 32 AI-closed, 8 escalated
        |
        v
audit.py  ---> blind classification via the Claude Code CLI
        |      (CLAUDE.md is the runtime prompt; the runner never sees ground truth)
        v
predictions.jsonl          committed, so --replay reproduces everything free
        |
        +--> eval_kit scoring ------> results/scorecard.md    is the auditor good?
        |
        +--> deflection.py ---------> results/report.html     what is the real rate?
                                      results/results.json
```

Scoring is [claude-eval-kit](https://github.com/neeshykha/claude-eval-kit) —
installed from its own repo, not vendored. An independent project consuming it over
the network is the actual test of whether it generalizes; this is its second domain
after support triage.

The outcome scale is ordered `false_deflection > partial > resolved`, most costly
first, so eval-kit's under-prediction bucket reads directly as **over-crediting the
AI** — the expensive direction, and the same under/over-triage framing the triage
repo uses for severity.

---

## Results (last run)

| | |
|---|---|
| Claimed deflection | **80.0%** — 32 of 40 closed without a handoff |
| Audited deflection | **55.0%** — 22 of 40 genuinely resolved |
| Overstatement | **25.0 points**, 1.45× the audited rate |
| Auditor accuracy | 25/32 outcomes (78%), 26/32 failure modes (81%) |
| Confusable-pattern traps | 8/11 |

The 25-point gap is the number, and it is the least interesting thing here — it is
a property of a dataset built to contain false deflections. **The finding is in the
confusion matrix.**

| true \ pred | false_deflection | partial | resolved |
|---|---|---|---|
| **false_deflection** | 6 | **0** | 1 |
| **partial** | 2 | **0** | 2 |
| **resolved** | 2 | **0** | 19 |

**The auditor never predicted `partial`. Not once, in 32 conversations.** It
collapsed a three-way ordinal scale into a binary, splitting all four true partials
between `resolved` and `false_deflection`, two each.

Four of the seven total misses are that one category. On the two unambiguous
outcomes the auditor is 25/28 — 89%. Every bit of the error is concentrated in the
middle band.

That matters more than the accuracy number, because "correct but incomplete, the
resident will be back" is the most common real closure state in support and the most
contestable one in any deflection claim. An auditor blind to it does not fail
loudly — it produces a confident rate that shifts by several points depending on
which way the borderline cases happen to land. The bar in
[`results/report.html`](results/report.html) has no middle segment at all, which is
the failure rendered literally.

**Traps: 8/11.** The three groups testing false closures held up — polite closure
3/3, correct-answer-wrong-problem 2/2, unactionable guidance 1/2. The tone trap came
in at 2/4: D017 and D019 are hostile residents who were genuinely helped and got
scored as false deflections.

That result comes with a caveat about this repo's own eval design, not the model.
D017 and D019 both pair hostile tone with a remedy the agent never confirmed ("try
this, let me know"), while D018 and D020 — the two that passed — end in a definitive
factual answer. The group therefore varies two things at once, and its failures
cannot be cleanly attributed to tone. Isolating that would mean rewriting two
conversations after seeing the results, which is how eval datasets quietly become
fitted to the model they are measuring. The confound is documented instead.

Full breakdown, both confusion matrices, and the over-credit split:
[`results/scorecard.md`](results/scorecard.md).

---

## Repo structure

```
audit.py                     orchestrator: classify -> score -> compute -> render
CLAUDE.md                    the auditor's judgment rules (runtime prompt, not docs)
deflection.py                claimed vs. audited rate math -- the only new logic here
render_html.py               self-contained static report, stdlib templating
app.py                       optional Streamlit view over results.json
data/conversations.jsonl     40 labeled conversations
predictions.jsonl            committed on purpose -- see below
results/scorecard.md         auditor quality
results/report.html          the deflection finding
results/results.json         machine-readable twin of the report
tests/test_deflection.py     18 tests over the deterministic half
```

**`predictions.jsonl` is committed**, unlike the sibling repos where it is
gitignored. That is what makes `--replay` work: anyone can regenerate the full
scorecard and report with no API access, no subscription, and no cost, and check
that the committed results actually follow from the committed predictions.

---

## Setup

```bash
git clone https://github.com/neeshykha/deflection-audit
cd deflection-audit
python3 -m venv .venv && .venv/bin/pip install pytest git+https://github.com/neeshykha/claude-eval-kit.git
```

## Running it

Reproduce the committed results with no API calls:

```bash
.venv/bin/python audit.py --replay
```

Run the tests:

```bash
.venv/bin/python -m pytest tests/ -q
```

Re-run the classification for real (needs an authenticated `claude` CLI; roughly
10–30s per conversation, and it is resumable — interrupt it and re-run to pick up
where it stopped):

```bash
rm predictions.jsonl && .venv/bin/python audit.py
```

Retry only the conversations that failed, keeping the ones that succeeded:

```bash
.venv/bin/python audit.py --retry-failed
```

Long CLI-driven evals hit transient failures — this one lost 16 of 32 conversations
mid-run when the Claude Code CLI updated itself and its symlink briefly vanished.
Because the runner skips any id already recorded, and failures *are* recorded, a
plain re-run would skip exactly the rows that need retrying. `--retry-failed` drops
the error rows so the next run picks them up; throwing away good work to recover
from a blip is not a reasonable default.

Two auth failures worth recognizing, since both are quiet:

- `claude CLI exited 1` on every conversation — check `claude auth status` rather
  than the exit code. `claude -p` reports an expired session *inside* its JSON
  envelope while still exiting 0, so shell-level checks see success.
- `[Errno 2] No such file or directory: 'claude'` mid-run — the CLI updated itself.
  Wait for it to finish, then `--retry-failed`.

View the report:

```bash
python3 -m http.server 8000 --directory results
```

Optional interactive view:

```bash
.venv/bin/pip install streamlit && .venv/bin/streamlit run app.py
```

---

## On testing

The deterministic half and the stochastic half are verified differently on purpose,
and conflating them is how AI projects end up with a green test suite that proves
nothing.

**Unit tests** cover the rate arithmetic and the renderer — `deflection.py` is pure
functions over labels, so zero-denominator cases, unscored conversations, partial
crediting, and HTML escaping are all ordinary testable behavior. These are fast,
free, and would run in CI.

**The eval** covers the judgment. There is no assertion that makes a classifier
correct; the scorecard is the measurement, and the confusable-pattern traps are
where the interesting failures show up — grouping them separately from headline
accuracy is what turns "78%" into "it cannot see the middle category."

The traps also caught a flaw in the traps. Group 4 was written to detect an auditor
drifting into sentiment scoring, and its 2/4 result cannot support that reading,
because the two failures differ from the two passes on a second axis as well. An
eval group that varies more than one thing measures neither. That is worth knowing
about a dataset before trusting what it reports, and it is the argument for reading
per-group results rather than a single accuracy figure.

A passing test suite here says nothing about whether the auditor's judgment is
good. The scorecard says nothing about whether the arithmetic is right. Both are
needed and neither substitutes for the other.

---

## On the dataset

All 40 conversations are synthetic. No production ticket content, resident data, or
employer material appears in this repo — real support patterns informed how the
conversations were written, and nothing was copied.

The sample is **deliberately weighted toward hard cases**, in the same spirit as the
hard-case-weighted subset in
[agent-ops-bench](https://github.com/neeshykha/agent-ops-bench). Whatever gap this
reports is a property of this dataset, chosen to exercise the failure modes, and is
not an estimate of the inflation in any real deployment. The transferable claim is
the method, not the number.

Ground truth carries `true_` prefixes and the escalated conversations are labeled
`null` — they were never counted as deflected, so they are not audited, but they
stay in the denominator, because a claimed deflection rate is computed over total
volume and dropping them would flatter the vendor.

---

## Why this exists

I run support operations for an IoT SaaS platform in multifamily residential, where
I deployed an AI copilot that took ticket deflection to 85%. I am the person who
reports that number, which is exactly why I wanted to know what it survives.

Deflection is the metric AI support vendors lead with and the one that is easiest to
report honestly and still be wrong about. Nobody is faking it. The instrumentation
genuinely cannot see the difference between a resident who was helped and a resident
who gave up, because both look like a conversation that ended without a human.

Building the thing that checks your own headline number is a different posture than
building a dashboard that displays it. That posture is most of the job in any role
that deploys AI into a customer-facing workflow.

---

## Tech stack

- **Claude Code** — CLI-driven blind classification; `CLAUDE.md` is the runtime
  instruction layer, not documentation written afterward
- **Python (stdlib only)** — no runtime dependencies beyond eval-kit; `render_html.py`
  templates with `string.Template` so the report needs no build step
- **[claude-eval-kit](https://github.com/neeshykha/claude-eval-kit)** — scoring,
  confusion matrices, ordinal miss splits, confusable-pattern audits
- **pytest** — for the deterministic half only, on purpose
