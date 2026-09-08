# Corporate Science Entry v1 — Hostile Reviewer Audit

## Overall verdict

**PROMISING, PUBLISHABLE WITH REPOSITIONING; NOT YET STRONG ENOUGH FOR AN UNQUALIFIED FIRST-MOVER-ADVANTAGE CLAIM**

The paper survives a hostile scientific review because the null/negative primary results are transparently preserved, the design was frozen before outcome inspection, H3 was not forced when support failed, and H5 is explicitly classified as inference-sensitive. The strongest contribution is therefore a **boundary-condition result**: relative early entry into observable corporate scientific production does not generate a general output or persistence premium in this linked-firm sample, while pre-entry international collaboration diversity shows a recurring—but not robustly inferential—positive moderation pattern for persistence.

No current issue requires reopening the frozen analysis before producing a submission-quality paper. However, the paper should be targeted and written around what the design can defend, not around the original expectation that first movers should generally outperform later entrants.

## Reviewer scorecard

| Dimension | Score /10 | Hostile assessment |
|---|---:|---|
| Question importance | 8.5 | Strategic timing of corporate scientific participation is important and under-studied. |
| Novelty | 8.0 | Firm × emerging-topic entry timing plus international science-network moderation is unusual; novelty weakens if framed merely as generic first-mover advantage. |
| Theory | 7.5 | Good integration of first-mover theory and absorptive capacity; mechanism is interpretive rather than directly measured. |
| Data originality | 8.0 | SEC↔OpenAlex corporate-science panel is unusual and valuable. |
| Sample breadth | 5.5 | Only 21 firms in primary panel is the clearest external-validity weakness. |
| Construct validity | 6.5 | Publication-based entry and sample-relative corporate frontier are defensible but narrower than true scientific entry/first mover. |
| Design transparency | 9.5 | Frozen design, support rules, exact checksums, and sensitivity grid are unusually strong. |
| Identification | 5.5 | Observational timing remains endogenous; adjustment is not causal identification. |
| Statistical rigor | 8.5 | Overlap weighting, absorbed FE, CRV1/CRV3/two-way/wild bootstrap and leave-one-firm-out checks are strong. |
| Result robustness | 6.5 | H1/H2/H4 conclusions are stable; H5 sign is stable but inference is sensitive; H3 primary not estimable. |
| Narrative coherence | 8.0 | Boundary-condition story is coherent if the paper avoids treating H5 as confirmed. |
| Reproducibility | 9.5 | Excellent immutable checkpoints and code/data hashing. |
| Managerial implication strength | 6.5 | Useful caution against “early is automatically better,” but causal prescriptions must remain restrained. |
| Publication readiness | 7.5 | Full draft exists; needs shortening, table/figure integration, title refinement, and journal-specific formatting. |

**Overall hostile-review score: 7.6/10.**

## Major concern 1 — The study does not observe the true population first mover

The corporate adoption frontier is defined as the first observed entrant among firms successfully linked in the frozen SEC↔OpenAlex sample. That is not necessarily the first corporation anywhere to participate in the topic.

### Reviewer attack

> “You call this a first-mover study, but you only observe the first mover among 21–24 linked companies. How do I know your ‘early entrant’ was actually early in the corporate population?”

### Defense

The empirical construct is explicitly **relative corporate entry timing within the linked-firm sample**. Global topic emergence is defined independently from corporate entry, so the study still measures whether being nearer the observed corporate adoption frontier within each emerging topic is associated with later outcomes.

### Required manuscript action

- Use “relative entry,” “early within the linked corporate sample,” and “near the observed corporate adoption frontier.”
- Do not claim observation of the global first corporate mover.
- Prefer the safer title **“When Early Entry Is Not Enough: Corporate Scientific Entry, Persistence, and International Knowledge Networks.”**

**Severity:** major but manageable.

## Major concern 2 — Only 21 firms support the primary analysis

Firm-topic episodes create 171 observations across 54 topics, but the highest organizational level remains 21 firms.

### Reviewer attack

> “Your nominal N is 171, but corporate strategy is being inferred from only 21 firms. Are the results driven by a handful of science-intensive corporations?”

### Defense

- The model absorbs firm fixed effects.
- H5 was re-estimated leaving out every firm individually and retained a positive sign in all 21 refits.
- Firm-cluster wild-bootstrap inference is reported precisely because firm count is small.
- Claims are limited to the linked-firm sample rather than universal corporate behavior.

### Remaining weakness

External validity remains limited. Firm fixed effects and leave-one-out analyses address within-sample stability, not population representativeness.

**Severity:** major and irreducible in v1.

## Major concern 3 — H5 cannot carry the paper as a confirmed result

The primary H5 interaction is positive and favorable under topic CRV1 and two-way clustering but not under topic CRV3 or firm wild bootstrap.

### Reviewer attack

> “Your only positive result disappears under conservative small-cluster inference. Is the paper a collection of nulls plus one fragile interaction?”

### Defense

The paper should not be sold as an H5-discovery paper. The contribution is broader:

1. the expected general first-mover premium fails across output and persistence;
2. network diversity does not explain who enters earlier;
3. the one recurring conditional pattern is positive across 12/13 +3 frozen designs and all 21 leave-one-firm-out refits;
4. significance stability is explicitly distinguished from sign stability.

### Required manuscript action

Describe H5 as **qualified directional evidence** and present it as a theory-building boundary condition, not confirmation.

**Severity:** major if overstated; manageable under current claim lock.

## Major concern 4 — Entry timing remains endogenous

Overlap weighting, pre-entry trajectory controls, firm/topic/year fixed effects, industry information, and matching improve observed comparability but do not create an exogenous timing shock.

### Reviewer attack

> “Better firms may enter earlier for unobserved reasons. Your paper cannot identify a first-mover benefit.”

### Defense

The paper explicitly adopts the first-mover-advantage versus first-mover-benefit distinction and makes associational claims only. The analysis asks whether an adjusted empirical advantage is visible, not whether exogenously forcing a firm to enter earlier would improve performance.

### Required manuscript action

Do not use “effect,” “causes,” “leads to,” or causal managerial prescriptions unless clearly referring to theory rather than the empirical estimate.

**Severity:** major but transparently bounded.

## Major concern 5 — Publication entry is an imperfect proxy for scientific entry

A corporation may privately monitor or work on a topic before its first observable publication.

### Reviewer attack

> “The first publication is not necessarily first scientific entry.”

### Defense

The construct should be defined as **entry into observable corporate scientific production/participation**. Publication activity is valuable precisely because it provides a systematic cross-topic measure, but the paper should not equate it with first internal awareness or first confidential R&D investment.

**Severity:** moderate-to-major construct-validity limitation.

## Major concern 6 — Topic emergence threshold is operational

The p2_100 rule is not a natural law of scientific emergence.

### Reviewer attack

> “Why 100 publications and two years? Would your answer change at 50 or 250?”

### Defense

This is one of the paper’s strongest design features. The threshold was frozen before outcomes; five objective global-emergence definitions × four entry windows were generated; only designs passing pre-outcome feasibility gates were analyzed; 13 designs entered inference; the primary p2_100_w2 model remained primary regardless of later results.

**Severity:** well controlled.

## Major concern 7 — H3 is underpowered/support-limited

The primary normalized citation-impact contrast contains only 19 supported observations across 7 topics after enforcing within-topic early/later comparability.

### Reviewer attack

> “Why include an impact hypothesis you cannot estimate?”

### Defense

The ex ante hypothesis should remain because dropping it after seeing support would be selective. The paper can state that the primary design cannot estimate it and report the four support-qualified sensitivity estimates as secondary evidence centered near zero.

**Severity:** moderate; transparency is a strength.

## Major concern 8 — The network mechanism is not directly observed

Country-level collaboration entropy is not absorptive capacity.

### Reviewer attack

> “You interpret network diversity through absorptive capacity, but you do not measure assimilation or transformation.”

### Defense

The manuscript already treats absorptive capacity as the theoretical mechanism/boundary condition rather than a measured mediator. Network entropy captures access breadth, not internal integration capability.

### Required manuscript action

Use “consistent with,” “may provide,” and “plausibly,” not mediation language.

**Severity:** moderate.

## Statistical audit

### Strengths

- exact design freeze before H1–H5 outcome estimation;
- feasibility thresholds determined before inference;
- overlap weighting with strong observed balance (max weighted SMD ≈0.044);
- absorbed multi-way fixed effects after rank-deficiency was diagnosed;
- primary topic CRV1 plus CRV3 and two-way clustering;
- 9,999-rep firm wild bootstrap;
- leave-one-firm-out H5 stability;
- no forced H3 estimate;
- frozen sensitivity grid rather than result-driven specification search;
- claim lock prevents later overstatement.

### Reviewer cautions

- H2 is a fixed-effect linear-probability model for a binary outcome; this is acceptable for interpretability and fixed effects but a reviewer may request nonlinear sensitivity. Such an analysis would constitute a new, explicitly labeled robustness extension rather than a replacement of the locked primary model.
- Small firm count makes asymptotic inference sensitive; this is already visible and honestly reported.
- The paper should report effective sample size and cluster counts directly in the main methods/results table.

## Narrative audit

### Strong narrative

> Earlier relative entry into observable corporate science does not show a general output or persistence premium. International collaboration-network diversity does not systematically predict who enters earlier. However, the early-entry–persistence association is more favorable at higher levels of pre-entry network diversity across most frozen definitions, although the statistical evidence is sensitive to small-cluster inference. This pattern supports a contingent rather than automatic view of scientific first-mover advantage.

### Weak narrative to avoid

> First movers succeed only when they have diverse networks.

The latter is too causal and too dependent on H5.

## Novelty audit

The novelty is strongest when the manuscript emphasizes the **combination** of:

- firm-level observable scientific production;
- objective global topic emergence;
- within-topic relative corporate entry timing;
- post-entry output and persistence;
- pre-entry international scientific-network diversity;
- frozen multiverse-style operational sensitivity.

The novelty is weakest if the paper is presented simply as another first-mover-advantage test or another bibliometric ranking study.

## Required pre-submission revisions

1. Use the safer relative-entry title or explicitly qualify “first mover.”
2. Make the sample-relative corporate frontier explicit in Abstract, Introduction, and Methods.
3. State “observable scientific production/participation” when defining entry.
4. Keep H5 as qualified directional evidence.
5. Integrate one main hypothesis-results table rather than relying on prose p-values.
6. Include a visual showing global topic emergence, corporate frontier, early window, and later entry.
7. Include the H5 sensitivity plot and leave-one-firm-out plot in the main or appendix materials.
8. Add a compact firm/sample table so readers see the 21-firm composition and industry coverage.
9. Shorten the Methods for the main paper while preserving a reproducibility appendix/versioned technical note.
10. Merge and normalize the reference list and verify every DOI/citation before submission.
11. Keep the frozen claim-lock wording through all editing.

## Submit / do-not-submit decision

**DO NOT ABANDON.**

**DO NOT submit yet as an unqualified Research Policy-style first-mover paper.**

**PROCEED to journal-specific revision as a boundary-condition/contingency study.**

The empirical contribution is credible enough to support a paper, but acceptance probability will depend heavily on choosing a journal that values R&D/innovation-management boundary conditions and transparent null evidence rather than requiring strong causal identification or a large firm population.
