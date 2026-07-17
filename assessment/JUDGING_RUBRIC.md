# Judging Rubric & Process

This rubric is **published to teams** — criteria are transparent and known upfront. Every team is scored on **exactly these criteria**, by the **same judges**, using the **same bands**. Nothing off-rubric counts.

The task is identical for all teams (see `PARTICIPANT_BRIEF.md`), so submissions are directly comparable.

---

## Scoring model

- **6 criteria**, each scored **0–5** by the judge, then multiplied by its weight.
- **Total = 100 points.**
- **A finished product is not required.** Score the **progress and soundness of what exists** — a working thin slice scores higher than a broken ambitious one. Do not penalize a team for honestly listing what doesn't work.
- Each criterion requires a **one-line written justification** from the judge.

| # | Criterion | Weight | Ability it proves |
|---|-----------|-------:|-------------------|
| 1 | Technical execution | 25 | They can actually build and ship a working end-to-end slice. |
| 2 | AI integration quality | 20 | They can use AI to solve a real problem correctly. |
| 3 | Innovation / creativity | 20 | Original problem-solving within a fixed constraint. |
| 4 | Problem & product thinking | 15 | Judgment about what is worth building, and for whom. |
| 5 | Demo & communication | 10 | They can explain and defend their work honestly. |
| 6 | Code quality & collaboration | 10 | Engineering discipline and real teamwork. |

**Score conversion:** `criterion points = (band score / 5) × weight`. Sum all six for the total out of 100.

---

## Scoring bands (per criterion)

### 1. Technical execution — weight 25
- **0** — Nothing runs; no working path from input to output.
- **3** — A core path works end-to-end (upload → process → result), even if narrow or rough.
- **5** — A solid, reliable end-to-end app; handles the main flow cleanly and doesn't fall over on normal use.

### 2. AI integration quality — weight 20
- **0** — No AI, or AI is decorative / doesn't affect the result.
- **3** — AI is genuinely used to understand/extract/transform content and materially drives the output.
- **5** — Thoughtful, correct AI use — good prompting/model choice, handles messy input, output is trustworthy and clearly better than a non-AI approach.

### 3. Innovation / creativity — weight 20
- **0** — Generic, no distinct idea.
- **3** — A clear, sensible angle on the problem; some original thinking.
- **5** — A genuinely fresh or clever approach within the fixed task that judges hadn't expected.

### 4. Problem & product thinking — weight 15
- **0** — No clear problem or user; scope makes no sense for 24h.
- **3** — Clear problem, plausible user, reasonable scope.
- **5** — Sharp problem framing, real user need, and scope chosen wisely so the important part actually got built.

### 5. Demo & communication — weight 10
- **0** — No demo, or can't show the core flow.
- **3** — Clear demo of the main flow; explains what it does.
- **5** — Crisp ≤3-min demo, explains a key decision and why, and is honest about limitations.

### 6. Code quality & collaboration — weight 10
- **0** — Unstructured code; git history shows one person or a single dump.
- **3** — Reasonable structure; git history shows the team working within the window.
- **5** — Clean, readable structure and a healthy commit history showing real collaboration across the team.

---

## Judging process (standardized, bias-controlled)

1. **≥ 2 judges per team.** The same judges apply this same rubric to every team they score.
2. **Calibration pass.** Judges score the **first** submission together and align on what a "3" vs "5" means before scoring the rest. This anchors the scale.
3. **Score to the rubric only.** Ignore hype, branding, and polish that isn't a listed criterion. Write a one-line justification per criterion.
4. **Average** the judges' totals per team.
5. **Rank** by averaged total (out of 100).
6. **Tie-break** order: higher **Criterion 1 (execution)**, then higher **Criterion 3 (innovation)**.

---

## Judge scorecard (copy one per team)

```
Team: ____________________        Judge: ____________________

1. Technical execution      band _/5  → ____/25   note: ______________________
2. AI integration quality   band _/5  → ____/20   note: ______________________
3. Innovation / creativity  band _/5  → ____/20   note: ______________________
4. Problem & product        band _/5  → ____/15   note: ______________________
5. Demo & communication     band _/5  → ____/10   note: ______________________
6. Code quality & collab    band _/5  → ____/10   note: ______________________

TOTAL: ____/100
```
