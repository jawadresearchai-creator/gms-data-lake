from pathlib import Path

PATH = Path('manuscript/corporate_science_entry_v1/TECHNOVATION_MANUSCRIPT_DRAFT.md')
text = PATH.read_text(encoding='utf-8')

replacements = [
(
'**Keywords:** corporate science; entry timing; technological innovation; international collaboration; scientific networks; absorptive capacity; persistence; emerging scientific domains',
'**Keywords:** corporate science; entry timing; technology management; international collaboration; absorptive capacity; scientific persistence'
),
(
"We use the frozen GMS `sec_openalex_v10` cross-domain production release, which links SEC issuer information with OpenAlex-derived corporate scientific activity. The release was frozen on 8 September 2026 and classified by the pipeline as verified/research-ready with zero recorded QA errors. The analysis uses global OpenAlex topic-year trajectories together with firm-topic output, firm-country collaboration, company-wide research and citation histories, and SEC issuer metadata.",
"We use the frozen GMS `sec_openalex_v10` cross-domain production release, which links SEC issuer information with OpenAlex-derived corporate scientific activity (Priem et al., 2022). The release was frozen on 8 September 2026 and classified by the pipeline as verified/research-ready with zero recorded QA errors. We use only organization links retained in the production bridge; those bridge records preserve match-method and confidence fields, country-consistency diagnostics, reclassification decisions, and production-approval metadata. The analysis does not re-estimate those organization links. The analysis uses global OpenAlex topic-year trajectories together with firm-topic output, firm-country collaboration, company-wide research and citation histories, and SEC issuer metadata."
),
(
"The unit of analysis is a **firm × scientific-topic entry episode**. The primary panel contains 171 episodes across 54 scientific topics and 21 linked firms. Sixty-five episodes are classified as early and 106 as later. The observational structure provides within-topic and within-firm variation, but the number of firms remains modest; consequently, we use multiple small-cluster inference procedures and limit external-validity claims to the linked-firm sample.",
"The unit of analysis is a **firm × scientific-topic entry episode**. The primary panel contains 171 episodes across 54 scientific topics and 21 linked firms. Sixty-five episodes are classified as early and 106 as later. The observational structure provides within-topic and within-firm variation, but the number of firms remains modest; consequently, we use multiple small-cluster inference procedures and limit external-validity claims to the linked-firm sample.\n\nThe linked-firm sample is also unevenly distributed across industries. SIC 60 depository/banking firms contribute 81 of 171 episodes (47.4%), chemicals/pharmaceutical firms contribute 35 (20.5%), and the largest single firm contributes 36 episodes (21.1%). Firm fixed effects and leave-one-firm-out checks reduce the risk that stable firm characteristics or one firm drive the within-sample estimates, but they do not make the sample representative of the broader corporate population. We therefore report the complete firm and SIC composition as reviewer-facing supplementary tables and treat industry concentration as an external-validity limitation."
),
(
"Because early and later entrants differ on observed pre-entry characteristics, we use overlap weighting based on a regularized logistic propensity model.",
"Because early and later entrants differ on observed pre-entry characteristics, we use overlap weighting based on a regularized logistic propensity model, following the overlap-weighting logic of Li, Thomas, and Li (2019)."
),
(
"Across individual pre-entry covariates, raw standardized differences as large as approximately 0.34 in magnitude are reduced to no more than approximately 0.044 after weighting.",
"Across individual pre-entry covariates, raw standardized differences as large as approximately 0.34 in magnitude are reduced to no more than approximately 0.044 after weighting.\n\n**Table 1B. Industry composition of the frozen primary panel**\n\n| SIC2 / group | Firms | Episodes | Share of episodes |\n|---|---:|---:|---:|\n| 60 — Depository institutions/banking | 6 | 81 | 47.4% |\n| 28 — Chemicals and pharmaceuticals | 5 | 35 | 20.5% |\n| 27 — Printing and publishing | 1 | 20 | 11.7% |\n| SIC unavailable | 2 | 9 | 5.3% |\n| 73 — Business/computer services | 1 | 7 | 4.1% |\n| 36 — Electronic equipment | 1 | 6 | 3.5% |\n| 80 — Health services | 2 | 6 | 3.5% |\n| 49 — Electric/gas utilities | 1 | 3 | 1.8% |\n| 13 — Oil and gas extraction | 1 | 2 | 1.2% |\n| 35 — Industrial/computer machinery | 1 | 2 | 1.2% |\n\nThe complete 21-firm composition, including ticker, SIC description, early/later counts, and episode shares, is retained in the reproducibility package."
),
(
"Primary inference clusters by scientific topic using CRV1. Given 21 firms and 54 topics, we additionally report topic CRV3, two-way topic-and-firm CRV1, and a firm-cluster wild bootstrap with 9,999 replications and Webb weights.",
"Primary inference clusters by scientific topic using CRV1. Given 21 firms and 54 topics, we additionally report topic CRV3, two-way topic-and-firm CRV1, and a firm-cluster wild bootstrap with 9,999 replications and Webb weights; these additional procedures reflect the known sensitivity of cluster-robust inference when cluster counts or cluster sizes are limited (MacKinnon & Webb, 2017, 2018)."
),
(
"Second, the primary analysis includes only 21 firms. Firm-topic variation supports within-firm and within-topic comparisons, and leave-one-firm-out analysis addresses single-firm dependence, but the sample does not support universal claims about corporate behavior. Replication across a broader corporate population is important.",
"Second, the primary analysis includes only 21 firms. Firm-topic variation supports within-firm and within-topic comparisons, and leave-one-firm-out analysis addresses single-firm dependence, but the sample does not support universal claims about corporate behavior. The sample is also industry-concentrated: banking/depository institutions account for 47.4% of primary episodes and the largest firm accounts for 21.1%. These concentrations are transparent and partly addressed by firm fixed effects and leave-one-firm-out analysis, but they remain an external-validity limitation rather than a problem that statistical adjustment can remove. Replication across a broader corporate population is important."
),
(
"Lieberman, M. B., & Montgomery, D. B. (1988).",
"Li, F., Thomas, L. E., & Li, F. (2019). Addressing extreme propensity scores via the overlap weights. *American Journal of Epidemiology, 188*(1), 250–257. https://doi.org/10.1093/aje/kwy201\n\nMacKinnon, J. G., & Webb, M. D. (2017). Wild bootstrap inference for wildly different cluster sizes. *Journal of Applied Econometrics, 32*(2), 233–254. https://doi.org/10.1002/jae.2508\n\nMacKinnon, J. G., & Webb, M. D. (2018). The wild bootstrap for few (treated) clusters. *The Econometrics Journal, 21*(2), 114–135. https://doi.org/10.1111/ectj.12107\n\nLieberman, M. B., & Montgomery, D. B. (1988)."
),
(
"Sabatier, M., & Chollet, B. (2017).",
"Priem, J., Piwowar, H., & Orr, R. (2022). OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts. *arXiv*. https://doi.org/10.48550/arXiv.2205.01833\n\nSabatier, M., & Chollet, B. (2017)."
),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'Expected exactly one match, found {count}: {old[:120]}')
    text = text.replace(old, new, 1)

PATH.write_text(text, encoding='utf-8')
print(f'Patched {PATH}: {len(replacements)} exact replacements')
