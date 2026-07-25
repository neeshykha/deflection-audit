# Deflection Auditor Scorecard

**Items scored:** 32/32 (0 failed to classify)

**Outcome accuracy:** 25/32 (78%)

**Failure_mode accuracy:** 26/32 (81%)


## Outcome Confusion Matrix

| true \ pred | false_deflection | partial | resolved |
|---|---|---|---|
| false_deflection | 6 | 0 | 1 |
| partial | 2 | 0 | 2 |
| resolved | 2 | 0 | 19 |

**Under-predicted (predicted less urgent than reality):** 3
- D022: true partial -> predicted resolved -- "My thermostat keeps switching back to 68 no matter what I set it to...."
- D024: true partial -> predicted resolved -- "I was double charged for the smart home fee in March. Please refund the duplicate...."
- D031: true false_deflection -> predicted resolved -- "My thermostat reads about 6 degrees colder than the actual room. Can it be calibrated?..."

**Over-predicted (predicted more urgent than reality):** 4
- D017: true resolved -> predicted false_deflection -- "This is the THIRD time this month I cannot get into my own apartment. The app spins foreve..."
- D019: true resolved -> predicted false_deflection -- "Your app is complete garbage. It shows my thermostat at 62 degrees when the actual wall un..."
- D023: true partial -> predicted false_deflection -- "The deadbolt motor sounds like it is straining and sometimes it does not fully retract. It..."
- D025: true partial -> predicted false_deflection -- "Two things: my guest code for the cleaner stopped working, and the lobby door has not been..."

## Outcome Confusable-Pattern Audit

Items deliberately written to test whether the classifier applies
nuance rules, not just keyword matching.

- **Polite closure is not resolution (generic troubleshooting handed back)**: 3/3 correct
  - [OK] D026: true false_deflection, predicted false_deflection
  - [OK] D027: true false_deflection, predicted false_deflection
  - [OK] D028: true false_deflection, predicted false_deflection
- **Correct answer to the wrong problem (a detail in the ticket invalidates the advice)**: 2/2 correct
  - [OK] D029: true false_deflection, predicted false_deflection
  - [OK] D030: true false_deflection, predicted false_deflection
- **Closed with guidance the resident cannot act on**: 1/2 correct
  - [MISS] D031: true false_deflection, predicted resolved
  - [OK] D032: true false_deflection, predicted false_deflection
- **Hostile tone but genuinely resolved (auditor must not become a sentiment detector)**: 2/4 correct
  - [MISS] D017: true resolved, predicted false_deflection
  - [OK] D018: true resolved, predicted resolved
  - [MISS] D019: true resolved, predicted false_deflection
  - [OK] D020: true resolved, predicted resolved

## Failure_mode Confusion Matrix

| true \ pred | none | answered_wrong_question | stale_or_wrong_article | needed_human_action | resident_abandoned | policy_refusal_loop |
|---|---|---|---|---|---|---|
| none | 19 | 0 | 0 | 0 | 2 | 0 |
| answered_wrong_question | 0 | 2 | 0 | 0 | 1 | 0 |
| stale_or_wrong_article | 1 | 0 | 0 | 0 | 0 | 0 |
| needed_human_action | 2 | 0 | 0 | 1 | 0 | 0 |
| resident_abandoned | 0 | 0 | 0 | 0 | 3 | 0 |
| policy_refusal_loop | 0 | 0 | 0 | 0 | 0 | 1 |
