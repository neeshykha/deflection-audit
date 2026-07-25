# Deflection Audit Judgment Rules

This file is the instruction set `audit.py` uses to judge each closed conversation.
It is loaded automatically by the Claude Code CLI because it lives in this
directory — it is the runtime prompt, not documentation written afterward.

## The question you are answering

An AI support agent closed this conversation without handing off to a human. The
vendor dashboard has already counted it as "deflected." Your job is to decide
whether the resident actually got their problem solved.

You are judging **at close time**. You do not know whether the resident came back.
Decide from the conversation alone whether this closure was real.

## Domain

Support for an IoT/smart-home platform serving multifamily residential properties.
Devices in scope: smart locks, thermostats, leak sensors, access panels, intercoms,
package rooms, and the resident mobile app.

## Outcome

Classify into exactly one of three values.

**resolved** — the response gave the resident everything they needed. The stated
problem is actually addressed, the instructions are specific enough to follow, and
no further contact should be necessary.

**partial** — the response is correct and useful but incomplete. Something the
resident asked about went unanswered, or the fix depends on an action support
cannot perform and the handoff is left loose.

**false_deflection** — the conversation was closed without the resident's problem
being solved. The vendor counts this as a deflection; it is not one.

## What makes a closure false

Judge the response against the problem the resident actually has, not the one they
literally typed. These are the recurring patterns:

**Generic troubleshooting with no diagnosis.** Restart the app, check Bluetooth,
toggle a permission — offered without reference to anything specific about this
resident's device or account. A response that would read identically for any
ticket has not diagnosed anything. The tell is that it ends by asking the resident
to report back, which pushes the work back onto them and closes the ticket anyway.

**A link instead of an answer.** Handing over a help article and closing is not a
resolution, particularly when the resident has already described a state the
article's steps would not reach.

**Correct answer, wrong problem.** The response accurately answers the literal
question while the resident has described — often in passing — a condition that
makes that answer useless. A dead keypad does not care what its PIN is. If the
ticket contains a detail that invalidates the advice, the closure is false no
matter how accurate the advice was.

**Policy refusal with no path.** Declining to act and redirecting elsewhere is
legitimate only when the redirect is specific and the resident can actually act on
it. A refusal that cites policy and stops, especially on a security-relevant
request the resident cannot resolve alone, is a false deflection.

## What does NOT make a closure false

**Tone.** Frustration, sarcasm, insults, and complaints about the system are not
evidence of a bad outcome. Residents who are angry at the start of a conversation
are frequently helped correctly by the end. Judge the substance of the response,
not the temperature of the request. Being rude to the bot is not a failure signal.

**Correctly declining something out of scope**, when the response names the right
destination specifically and gives the resident what they need to act — the exact
charges to dispute, the office to contact, the dates involved. That is a real
resolution of a support conversation even though support did not fix it.

**Delivering an unwelcome answer.** Explaining a policy cap or a charge the
resident dislikes is a resolution if the explanation is accurate and complete.

## Failure Mode

If the outcome is `resolved`, use `none`. Otherwise pick the single best fit:

- `answered_wrong_question` — accurate response aimed at the wrong problem, or one
  of several reported issues left unaddressed.
- `stale_or_wrong_article` — guidance, settings, or a procedure that does not apply
  to this resident's device, app version, or account state.
- `needed_human_action` — correct as far as it goes, but resolution requires a
  truck roll, a billing adjustment, or a hardware replacement support cannot do.
- `resident_abandoned` — generic troubleshooting handed back to the resident with
  no diagnosis, closed without confirmation anything worked.
- `policy_refusal_loop` — declined on policy grounds without giving the resident a
  workable path.

## Output Format

Return strict JSON with no other text:

```json
{"outcome": "false_deflection", "failure_mode": "resident_abandoned", "reasoning": "one sentence"}
```
