# Corporate Science Entry v1 — Methods Draft

> **Status:** journal-neutral Methods draft reconstructed directly from the frozen analysis code, immutable GMS data release, design-freeze outputs, estimator-hardening code, inference-hardening code, and prespecified sensitivity-analysis code.  
> **Scientific status:** the analysis is observational and associational. Relative corporate entry timing is endogenous; no causal treatment-effect claim is made.  
> **Primary design:** `p2_100_w2` — a scientific topic is treated as globally established/emerging for this study at the first year in which global output reaches at least 100 works and remains at or above 100 works in the immediately following calendar year; an early corporate entrant is a linked firm entering within 0–2 years of the first linked corporate entrant in that topic.

# Methods

## 1. Research design

We used a longitudinal firm–scientific-topic design to examine whether the relative timing of a firm's observable entry into an emerging scientific domain was associated with subsequent scientific output, persistence, and normalized citation impact, and whether pre-entry international collaboration-network diversity predicted or conditioned those relationships. The unit of analysis was a **firm × scientific-topic entry episode**. Each episode linked a firm's first observed publication activity in a topic to an independently constructed global topic-emergence trajectory and to the firm's pre-entry scientific and international collaboration history.

The empirical design was frozen before the H1–H5 outcome estimates were inspected. The design freeze specified the primary topic-emergence rule, early-entry window, outcome-complete period, feasibility gates, pre-entry adjustment variables, fixed-effect structures, support rules, and sensitivity grid. Subsequent estimator and inference hardening changed implementation details needed for numerically valid fixed-effect estimation and small-cluster inference but did not change the frozen sample definition, treatment definition, outcomes, or hypotheses.

Because firms self-select into scientific topics and into entry timing, the estimands are interpreted as **adjusted associations**, not causal effects. Selection adjustment, fixed effects, alternative clustering procedures, prespecified design sensitivity, and leave-one-firm-out analyses were used to improve comparability and characterize uncertainty, but none is treated as eliminating unobserved strategic selection.

## 2. Data sources and frozen release

The study used the GMS `sec_openalex_v10` cross-domain production release, frozen on **8 September 2026 at 04:57:54 UTC** and classified by the data pipeline as **VERIFIED / RESEARCH-READY** with zero recorded QA errors. The release linked SEC issuer information to OpenAlex-derived corporate scientific activity and collaboration marts. The analysis staged exact immutable input files and recorded SHA-256 hashes before computation.

Six frozen datasets were used directly in panel construction:

1. **Global OpenAlex topic-year mart (`WORK_YEAR_TOPIC`)** — global annual scientific-topic output and citation statistics, including publication year, topic identifier, work count, citation sum, mean citations, and topic-score sum.
2. **`COMPANY_TOPIC_YEAR`** — firm × topic × year scientific output, containing canonical company ID, linked OpenAlex institution ID, publication year, topic ID, work count, citation sum, and topic-score sum.
3. **`COMPANY_COLLABORATION_YEAR`** — firm × collaborator-country × year scientific collaboration measures, including collaborative work count, collaborator-institution count, and citation sum.
4. **`COMPANY_RESEARCH_YEAR`** — company-wide annual scientific output and citation totals.
5. **`COMPANY_CITATION_YEAR`** — company-wide annual citation measures used in the frozen research release and outcome-support checks.
6. **`SEC_ISSUER_METADATA`** — issuer metadata including Standard Industrial Classification (SIC), SIC description, SEC category, business country, and business state/country.

The cross-domain production release contained 46,265 company-topic-year observations, 7,151 company-country collaboration-year observations, and 1,047 observations in each of the company research-year and company citation-year marts. The global OpenAlex topic-year mart was maintained separately in the validated OpenAlex research layer and supplied the external field trajectory against which corporate entry was dated.

All primary analysis inputs were read from frozen Parquet/CSV artifacts. The reproducibility workflow stored SHA-256 checksums for the exact staged copies. Thus, later manuscript development did not re-query or regenerate the production data.

## 3. Temporal restrictions

The raw analytical views retained calendar years from 1900 through 2026 for construction and diagnostics. Several stricter restrictions were imposed for the research sample.

First, a firm's first observed topic participation was defined using positive `COMPANY_TOPIC_YEAR.work_count` and was allowed through 2025 for frontier construction. Second, the primary scientific-emergence and corporate-frontier years were restricted to **1990–2021**. Third, firm entry episodes used for the three-year primary outcomes were required to occur no later than **2022**, ensuring that the +1 to +3 follow-up window ended by 2025. Calendar year **2026 was deliberately excluded from primary outcome follow-up because it was incomplete as of 8 September 2026**.

Five-year outcomes were computed only for episodes entering by 2020 so that +5 follow-up was complete by 2025.

## 4. Global scientific-topic emergence

Topic emergence was identified from the global `WORK_YEAR_TOPIC` trajectory rather than from the corporate sample. This separation prevented the corporate-entry variable from mechanically defining field emergence.

For every topic-year, the analysis calculated adjacent-year output values and prior output diagnostics. Missing calendar years did not count as continuous threshold persistence. Five objective emergence rules were generated before hypothesis estimation:

- **`once100`**: first year global topic output reached at least 100 works;
- **`p2_100`**: first year output reached at least 100 works and remained at least 100 in the immediately following calendar year;
- **`p3_100`**: first year output reached at least 100 works and remained at least 100 in each of the next two consecutive calendar years;
- **`p2_50`**: first year output reached at least 50 works and remained at least 50 in the next calendar year;
- **`p2_250`**: first year output reached at least 250 works and remained at least 250 in the next calendar year.

The **primary emergence definition was fixed as `p2_100`** before H1–H5 were estimated. Thus, a primary-sample topic entered the emerging/established-topic set at the first year in which it recorded at least 100 global works and also recorded at least 100 works in the next consecutive year. The emergence year had to fall between 1990 and 2021.

The threshold should be interpreted as an operational definition of a topic becoming sufficiently visible and sustained for comparable corporate entry analysis, not as a claim that the threshold marks the intrinsic scientific birth of the field.

## 5. Corporate scientific entry and corporate adoption frontier

For each linked firm-topic pair, **entry year** was the earliest year in which the company recorded positive scientific work count in `COMPANY_TOPIC_YEAR`. For each topic, the **corporate adoption frontier** was the minimum entry year among linked firms. Topics were required to have at least two linked firms so that relative-entry comparisons could exist.

Relative entry lag was defined as:

\[
\text{Relative Entry Lag}_{ik}=\text{Firm Entry Year}_{ik}-\text{First Linked Corporate Entry Year}_{k}.
\]

Because the corporate frontier is the earliest linked-firm entry, this lag is non-negative by construction. The frozen primary early-entry window was **0–2 years**:

- **Early entrant:** relative entry lag ≤ 2 years;
- **Later entrant:** relative entry lag > 2 years.

The first linked corporate entry year also had to fall between 1990 and 2021. After the early/later classification was formed, the analysis retained only topics containing at least one early and at least one later entrant in the outcome-complete sample. This ensured that topic-level fixed-effect comparisons were not supported only by a single exposure category.

The primary design was therefore labeled **`p2_100_w2`**: two consecutive years of at least 100 global works combined with a corporate-relative early-entry window of two years.

## 6. Primary sample and feasibility gate

Before inspecting H1–H5 outcomes, every candidate emergence × entry-window design was evaluated against a frozen feasibility gate. A design passed only if it contained:

- at least **50 topics**;
- at least **150 firm-topic episodes**;
- at least **15 firms**;
- at least **50 early-entry episodes**;
- at least **50 later-entry episodes**; and
- pre-entry network data observed for at least **90%** of episodes.

The frozen primary `p2_100_w2` design passed this gate. The final primary panel contained **171 firm-topic entry episodes across 54 scientific topics and 21 firms**, comprising **65 early-entry** and **106 later-entry** episodes.

The primary panel was not expanded or narrowed after hypothesis results were observed.

## 7. Pre-entry international collaboration network

International collaboration measures were constructed from the three complete years preceding firm-topic entry, **t−3 through t−1**. For each firm-topic episode, collaborator-country records from `COMPANY_COLLABORATION_YEAR` were aggregated over that window.

For collaborator country \(c\), collaborative work counts were summed across the three pre-entry years. Let \(w_c\) denote collaborative work count with country \(c\), and let \(W=\sum_c w_c\). The analysis constructed:

- **collaborator-country count**: number of distinct collaborator countries;
- **pre-entry collaboration volume**: \(\sum_c w_c\);
- **collaborator-institution count**: sum of collaborator-institution counts across countries;
- **network concentration complement**:

\[
1-\sum_c\left(\frac{w_c}{W}\right)^2,
\]

which increases as collaborative work is spread more evenly across countries; and

- **international network entropy**:

\[
-\sum_c\left(\frac{w_c}{W}\right)\ln\left(\frac{w_c}{W}\right).
\]

If no pre-entry country collaboration record was present, the diversity measures were set to zero and a separate `pre3_network_observed` indicator recorded whether any pre-entry network record existed. **Pre-entry network entropy was the principal diversity measure for H4 and H5.**

## 8. Pre-entry scientific capacity and trajectory

Company-wide scientific capacity was measured over the same t−3 through t−1 window using `COMPANY_RESEARCH_YEAR`. Missing annual company rows in this fixed three-year window were treated as zero scientific output for that year. The analysis constructed:

- cumulative pre-entry company-wide work count;
- cumulative pre-entry company-wide citation count;
- the number of observed research-year records; and
- a pre-entry output slope.

The frozen pre-trend measure was:

\[
\text{Pretrend Slope}_{i}=\frac{\ln(1+\text{Works}_{t-1})-\ln(1+\text{Works}_{t-3})}{2}.
\]

Absent t−3 or t−1 rows were treated as zero output in this calculation. This slope was used to reduce imbalance in recent firm-level scientific trajectory before topic entry.

## 9. Field characteristics and diagnostic variables

For each entry episode, the analysis attached global topic characteristics at the firm's entry year, including global work count, global mean citations, prior three-year average topic output, year-over-year global topic growth when the immediately preceding year existed, and field age measured as entry year minus global emergence year.

These variables were retained for design diagnostics and sensitivity analyses. **Field age and global scale at entry were deliberately excluded from the primary propensity-score adjustment**, because both are mechanically related to relative entry timing. Conditioning on them in the primary selection model would partially adjust away the treatment construct itself.

SEC issuer metadata supplied two-digit SIC industry categories and descriptive firm metadata. Two-digit SIC indicators were included in the propensity model to account for broad industry differences in the probability of early entry.

## 10. Outcome variables

### 10.1 Subsequent topic output (H1)

The primary H1 outcome was cumulative firm-topic scientific output in years **t+1 through t+3** after first entry. Work counts were summed over those three years and transformed as:

\[
Y^{H1}=\ln(1+\text{Post-entry Topic Works}_{t+1:t+3}).
\]

Prespecified sensitivity outcomes used t+1 through t+2 and, where follow-up was complete, t+1 through t+5.

### 10.2 Persistence (H2)

Primary persistence was a binary indicator equal to one if the firm recorded positive work count in the same scientific topic in **t+3**, and zero otherwise. A five-year persistence indicator measured positive topic activity at **t+5** for entry episodes with complete five-year follow-up.

### 10.3 Field-year-normalized citation impact (H3)

For each post-entry year t+1 through t+3, firm-topic mean citations were compared with global mean citations for the same topic-year. For years with positive firm output and positive global mean citations, the firm-topic citation ratio was:

\[
\frac{\text{Firm-topic Citations}/\text{Firm-topic Works}}{\text{Global Topic-Year Mean Citations}}.
\]

The three-year normalized-impact measure was the work-count-weighted mean of those annual ratios. The model outcome used \(\ln(1+\text{normalized citation ratio})\).

H3 was subject to a frozen support rule. After requiring a defined normalized-impact outcome and retaining only topics containing both early and later entrants, the hypothesis was estimable only if at least **30 observations across at least 8 topics** remained. The primary sample did not meet this requirement, so H3 was not forced into a primary model. Sensitivity-only H3 estimates were permitted only for prespecified designs that independently cleared the support threshold.

### 10.4 Earlier relative entry (H4)

H4 treated the binary early-entry indicator as the dependent variable and pre-entry standardized international network entropy as the focal predictor. Because calendar entry timing is part of the dependent construct, entry-year fixed effects were not included in the primary H4 model.

### 10.5 Network moderation of persistence (H5)

H5 used the primary t+3 persistence outcome and estimated the interaction between the early-entry indicator and standardized pre-entry network entropy. The interaction coefficient was the focal H5 estimand.

## 11. Selection adjustment and overlap weighting

Observed early and later entrants were not assumed to be exchangeable. The frozen analysis therefore combined propensity-based overlap weighting with outcome regression.

The propensity model was a regularized logistic regression predicting early-entry status from genuine pre-entry characteristics. Continuous covariates were median-imputed where necessary and standardized. The adjustment set comprised:

- log(1 + pre-entry three-year company-wide research output);
- log(1 + pre-entry three-year company-wide research citations);
- pre-entry output slope;
- number of collaborator countries;
- international network HHI complement;
- international network entropy;
- log(1 + pre-entry collaborative work count);
- indicator for observed pre-entry network data; and
- two-digit SIC indicators.

The logistic model used `C=1.0`, the `lbfgs` solver, and a fixed seed of **20260908**. Estimated propensity scores were truncated to the interval **[0.03, 0.97]**.

Overlap weights were assigned as:

- early entrants: \(1-\hat p_i\);
- later entrants: \(\hat p_i\).

Weights were then normalized to mean one. Balance was evaluated using standardized mean differences on the genuine pre-entry adjustment covariates. The prespecified post-weight balance criterion was a maximum absolute SMD ≤ **0.10**. In the locked primary panel, the overlap-weight effective sample size was approximately **134.0**, and the maximum absolute weighted SMD was **0.044**, indicating strong balance on observed pre-entry covariates.

Timing/maturity-at-entry variables were not included in this primary propensity model for the reasons described above.

## 12. Primary regression specifications

Absorbed fixed-effect models were estimated with PyFixest after an earlier dummy-expanded implementation was found to be rank-deficient. The absorbed implementation changed numerical estimation only; it did not change the frozen scientific design.

### 12.1 H1 and H2

The primary H1 and H2 models were overlap-weighted fixed-effect regressions containing:

- early-entry indicator;
- standardized log pre-entry research output;
- standardized log pre-entry research citations;
- standardized pre-entry output slope;
- standardized pre-entry network entropy;
- standardized log pre-entry collaborative work count; and
- the pre-entry network-observed indicator where identified.

The models absorbed **topic fixed effects, firm fixed effects, and entry-year fixed effects**. H1 used log post-entry topic output as the outcome. H2 used the binary t+3 persistence indicator and was estimated as a fixed-effect linear probability specification.

### 12.2 H4

H4 estimated early-entry status as a function of standardized pre-entry network entropy, pre-entry research output, pre-entry citations, pre-entry slope, pre-entry collaboration volume, and the network-observed indicator where identified. The primary H4 specification absorbed **topic and firm fixed effects**. Entry-year fixed effects were excluded because entry timing is intrinsic to the dependent variable.

H4 was not overlap weighted because the hypothesis asks whether pre-entry network diversity predicts the treatment classification itself; applying weights constructed from that treatment model would alter the intended estimand.

### 12.3 H5

The H5 model used the t+3 persistence indicator and included early entry, standardized pre-entry network entropy, their interaction, the remaining pre-entry adjustment covariates, and **topic, firm, and entry-year fixed effects**. It used the same overlap weights as H1 and H2.

## 13. Primary and small-cluster inference

The primary covariance estimator clustered observations by **scientific topic using CRV1**. Because the primary panel contained only 21 firms and 54 topics, inference was deliberately hardened with additional methods rather than relying on a single clustered standard error.

For H1, H2, H4, and H5, the locked analysis additionally reported:

1. **topic-clustered CRV3** inference;
2. **two-way CRV1 clustering by topic and firm**; and
3. an **unweighted firm-cluster wild bootstrap** using the same scientific regressors and absorbed fixed effects.

The firm wild bootstrap used numeric firm cluster codes, **9,999 replications**, Webb bootstrap weights, null imposition, bootstrap type `11`, and seed **20260908**. The bootstrap robustness model was unweighted because the bootstrap implementation was not relied upon to support the analytic overlap weights; the weighted topic-cluster model remained primary.

H5 was also estimated under three prespecified fixed-effect structures to evaluate specification stability:

- topic + firm + entry year (primary);
- topic + entry year; and
- topic + firm.

Finally, the H5 interaction was re-estimated in **leave-one-firm-out** analyses, omitting each firm in turn, to determine whether the direction of the result was driven by any single company.

Where multiple primary hypothesis p-values were simultaneously estimable, Benjamini-Hochberg adjusted q-values were calculated as a supplementary multiplicity diagnostic. Hypothesis verdicts were not assigned from a single p-value alone; sign stability, alternative covariance estimators, support, and prespecified sensitivity evidence were considered together under the locked interpretation rules.

## 14. Prespecified sensitivity grid

A full sensitivity grid was constructed before outcome-driven specification selection. The five global emergence definitions (`once100`, `p2_100`, `p3_100`, `p2_50`, and `p2_250`) were crossed with four corporate-relative early-entry windows: **0, 1, 2, and 3 years** after the first linked corporate entrant. This yielded 20 candidate designs.

Each design was constructed from the same frozen marts and subjected to the feasibility gate described above. Only designs passing that gate before hypothesis estimation were carried into inferential sensitivity analysis. **Thirteen designs passed the frozen gate.** Failed designs were not mined for favorable coefficients or p-values.

For every gate-passing design, the propensity model and overlap weights were recomputed using the same adjustment rules, and post-weight balance was reassessed. Inferential sensitivity then repeated H1, H2, H4, and H5 under the hardened absorbed fixed-effect estimator family.

Outcome-window sensitivity was prespecified as follows:

- H1: output over t+1:t+2, t+1:t+3 (primary), and t+1:t+5 where complete;
- H2: persistence at t+3 (primary) and t+5 where complete;
- H5: persistence moderation at t+3 (primary) and t+5 where complete;
- H3: only designs independently satisfying its frozen within-topic support rule.

For +5 analyses, a separate complete-follow-up support rule required at least **50 observations across at least 15 topics** with both early and later entrants.

The primary `p2_100_w2` specification remained primary regardless of sensitivity results. Sensitivity designs were used only to characterize stability across reasonable alternative operational definitions.

## 15. Reproducibility and computational environment

All research stages were executed through version-controlled GitHub Actions workflows against immutable Google Drive checkpoints. Input staging used exact Drive paths and wrote SHA-256 checksums before estimation. Design-freeze, estimator-hardening, inference-hardening, sensitivity-analysis, final-analysis-lock, reviewer-results, and manuscript checkpoints were stored in separate immutable project folders.

The hardened analysis used **Python 3.11**. The reproducibility workflow pinned **PyFixest 0.60.0** and **wildboottest 0.3.2** and installed pandas, PyArrow, SciPy, scikit-learn, and the project's analytics requirements. DuckDB was used for panel construction from the frozen Parquet marts. Randomized procedures used seed **20260908**.

The workflow architecture deliberately separated data release, design freeze, hypothesis estimation, inference hardening, sensitivity analysis, final result lock, and manuscript drafting. Manuscript claim-lock files prohibit later drafts from converting associational evidence into causal language, describing H5 as confirmed or robustly significant, treating the non-estimable primary H3 result as either support or rejection, or selecting a sensitivity specification because it yields a more favorable p-value.

## 16. Ethical and interpretive scope

The study uses organization-level publication, collaboration, citation, and SEC issuer metadata. It does not analyze individual-level private or sensitive data. The principal interpretive limitation is causal rather than ethical: observed corporate scientific entry timing reflects strategic choice, capability, opportunity, and potentially unobserved firm-topic fit. Consequently, all empirical statements are framed as associations within the linked-firm sample and should not be read as estimates of what would happen if a firm were exogenously forced to enter a scientific domain earlier.

# Methods audit notes for later journal adaptation

The following details are frozen and should not be changed during journal-specific editing unless a new analysis version is explicitly opened:

- primary emergence definition = `p2_100`;
- primary early-entry window = 0–2 years;
- emergence/frontier period = 1990–2021;
- primary entry cutoff = 2022;
- primary follow-up ends = 2025;
- 2026 excluded from primary outcomes as incomplete;
- primary panel = 171 episodes / 54 topics / 21 firms / 65 early / 106 later;
- H1 outcome = log(1 + topic works, t+1:t+3);
- H2 outcome = active in topic at t+3;
- H3 support rule = ≥30 supported observations across ≥8 topics;
- H4 predictor = standardized pre-entry international network entropy;
- H5 focal term = early-entry × standardized pre-entry network entropy;
- overlap-weight propensity truncation = 0.03–0.97;
- primary balance threshold = maximum absolute weighted SMD ≤0.10;
- primary fixed effects H1/H2/H5 = topic + firm + entry year;
- primary fixed effects H4 = topic + firm;
- primary inference = topic CRV1;
- robustness inference = topic CRV3, two-way topic+firm CRV1, firm wild bootstrap;
- wild-bootstrap replications = 9,999;
- sensitivity candidate grid = 5 emergence rules × 4 entry windows;
- sensitivity inference restricted to designs passing the pre-outcome feasibility gate;
- scientific language = associational, not causal.
