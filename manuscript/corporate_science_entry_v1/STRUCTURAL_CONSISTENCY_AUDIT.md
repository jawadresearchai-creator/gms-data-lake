# Corporate Science Entry v1 — Structural Consistency Audit

## Audit status

**PASS WITH EDITORIAL CORRECTIONS / REVIEWER RISKS TO MANAGE**

This audit compares the locked Introduction/Theory, frozen H1–H5, reproducible Methods, locked Results/Discussion, reframing lock, and manuscript claim lock. It does not reopen the analysis.

## 1. Hypothesis-to-variable map

| Hypothesis | Theory construct | Frozen empirical construct | Outcome/model | Status |
|---|---|---|---|---|
| H1 | early scientific entry → cumulative scientific activity | `early_entry` (relative lag 0–2 years) | log(1 + firm-topic works, t+1:t+3), weighted FE | Consistent |
| H2 | early scientific entry → persistence | `early_entry` | active in same topic at t+3, weighted FE LPM | Consistent |
| H3 | early scientific entry → scientific influence | `early_entry` | log(1 + field-year-normalized citation ratio), support-gated | Consistent; primary not estimable |
| H4 | diverse external science network → earlier entry | standardized pre-entry country-network entropy | `early_entry` as outcome, topic+firm FE | Consistent |
| H5 | network diversity conditions early-entry persistence | `early_entry × z(pre3_network_entropy)` | active at t+3, weighted FE | Consistent; inference-sensitive |

No hypothesis was rewritten after observing results.

## 2. Time-window consistency

- Global emergence/frontier period: **1990–2021** in Methods and analysis code.
- Primary firm-entry cutoff: **2022**.
- Primary follow-up: **t+1 through t+3**, ending no later than 2025.
- Partial calendar year **2026 is excluded** from primary outcomes.
- Five-year sensitivity outcomes require entry by 2020.

**Verdict:** consistent across Methods and Results.

## 3. Sample consistency

The manuscript consistently reports the locked primary panel as:

- **171** firm-topic episodes;
- **54** scientific topics;
- **21** firms;
- **65** early-entry episodes;
- **106** later-entry episodes;
- overlap-weight effective sample size ≈ **134.0**;
- maximum absolute weighted SMD ≈ **0.044**.

**Verdict:** consistent.

## 4. Treatment/entry-language audit

### Measurement actually used

The corporate frontier is the earliest observed entry among the **linked firms in the frozen GMS SEC↔OpenAlex sample** for a topic. The study therefore measures **relative corporate entry timing within the linked sample**, not the globally verified first corporate entrant.

### Required wording

Preferred phrases:

- “earlier relative corporate entry”;
- “entry near the linked corporate adoption frontier”;
- “early entrants within the linked-firm sample”;
- “relative entry timing.”

Avoid unqualified wording such as:

- “the first corporation to enter the field”;
- “true first mover in the field”;
- “global corporate pioneer.”

### Title risk

The working title **“The Limits of First-Mover Advantage in Corporate Science”** is theoretically clear but may be read as implying observation of the true population first mover. A safer later-stage title candidate is:

**“When Early Entry Is Not Enough: Corporate Scientific Entry, Persistence, and International Knowledge Networks.”**

This is a manuscript-positioning issue, not a reason to alter the frozen measure.

## 5. H5 language audit

The locked evidence permits only a qualified moderation claim. The Results draft contains one phrase—“the persistence advantage associated with earlier entry”—that is stronger than necessary because H2 does not identify a general persistence advantage.

Preferred wording:

> “a recurring positive association between network diversity and the early-entry–persistence relationship”

or:

> “the early-entry–persistence association becomes more favorable as pre-entry network diversity increases.”

The following remain prohibited:

- “H5 is confirmed”;
- “H5 is robustly significant”;
- “network diversity causes early entrants to persist”;
- “early entry causes greater persistence.”

## 6. H2 interpretation audit

H2 is unsupported and estimates are predominantly negative, including all +5 sensitivity estimates. The manuscript correctly avoids converting this ex post directional pattern into a new “first-mover disadvantage” hypothesis.

Permitted interpretation:

> Early entry does not show the hypothesized persistence premium, and adjusted estimates tend to be negative.

Not permitted without a new preregistered analysis version:

> Early scientific entry creates a persistence penalty.

## 7. H3 interpretation audit

Primary H3 support is insufficient (19 supported observations across 7 topics versus the frozen minimum of 30 across 8). The manuscript correctly labels H3 **not estimable**, not “null,” “rejected,” or “supported.”

The four support-qualified sensitivity estimates may be described only as sensitivity-only evidence centered near zero.

## 8. Selection-adjustment consistency

Methods correctly distinguishes genuine pre-entry covariates from field-age/global-scale variables mechanically related to relative entry timing. The latter are excluded from the primary propensity adjustment and retained for diagnostics/sensitivity.

Overlap weighting and outcome regression are described as improving observed comparability rather than creating causal identification.

**Verdict:** consistent.

## 9. Fixed-effects and inference consistency

- H1/H2/H5: topic + firm + entry-year absorbed FE.
- H4: topic + firm absorbed FE; no entry-year FE because entry timing is the dependent construct.
- Topic CRV1: primary inference.
- Topic CRV3, two-way topic+firm CRV1, and firm wild bootstrap: robustness inference.
- H5: additional FE-structure and leave-one-firm-out stability checks.

The manuscript correctly distinguishes sign stability from p-value stability.

**Verdict:** consistent.

## 10. Network-measure interpretation

Network diversity is geographic scientific-collaboration diversity, operationalized through collaborator-country work shares in t−3:t−1. It is not a direct measure of:

- internal absorptive capacity;
- partner quality;
- alliance governance;
- informal knowledge exchange;
- technological complementarity.

Therefore, absorptive capacity is a **theoretical interpretation/boundary condition**, not an observed mediation mechanism. The Discussion currently preserves this distinction.

## 11. Publication-level entry limitation

Firm-topic entry is observed through publication activity. A firm may acquire or use scientific knowledge earlier through unpublished R&D, hiring, licensing, acquisition, private collaboration, or monitoring. The manuscript must therefore refer to **observable corporate scientific production/participation**, not the first moment at which the firm became scientifically aware of the topic.

## 12. Main reviewer threats remaining

### Major

1. **Only 21 firms in the primary panel.** Firm-topic episodes do not eliminate higher-level small-cluster uncertainty.
2. **Relative frontier rather than population frontier.** The linked sample may miss earlier corporate entrants.
3. **Endogenous entry timing.** Weighting/FE cannot eliminate unobserved strategic selection.
4. **Publication-based measurement.** Observable scientific entry may lag private knowledge acquisition.
5. **H5 inference sensitivity.** Direction is stable, conventional significance is not.

### Moderate

6. H3 has inadequate primary support.
7. Topic emergence remains an operational threshold despite a strong frozen sensitivity grid.
8. Country-network entropy captures geographic breadth but not the content or quality of external knowledge.
9. Five-year analyses necessarily use an earlier-entry subset.

## 13. Editorial corrections required in complete manuscript assembly

The first complete manuscript should:

1. use the reframed working title or the safer “When Early Entry Is Not Enough” title;
2. remove the obsolete Results-draft note saying the title is not frozen;
3. replace “persistence advantage associated with earlier entry” with calibrated interaction wording;
4. keep H1–H5 exactly as originally tested;
5. state explicitly that the corporate frontier is sample-relative;
6. state explicitly that publication entry is observable scientific participation;
7. keep H3 primary status as not estimable;
8. report all four inference approaches for the locked primary coefficients;
9. describe H5 as qualified directional evidence only;
10. keep the 13-design sensitivity grid as stability evidence rather than specification selection.

## 14. Audit conclusion

The manuscript is structurally coherent enough to assemble into a first complete paper. No mismatch was found that requires reopening or changing the frozen analysis. The remaining issues are claim calibration, title precision, and reviewer-facing limitations. The complete manuscript should be assembled from the frozen source sections with the editorial corrections above applied during assembly, leaving the original analysis checkpoints unchanged.
