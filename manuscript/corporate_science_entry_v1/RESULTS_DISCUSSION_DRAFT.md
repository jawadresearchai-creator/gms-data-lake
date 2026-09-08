# Corporate Science Entry v1 — Journal-Neutral Results and Discussion Draft

> **Status:** manuscript-development draft built after `FINAL_ANALYSIS_LOCK_V1` and the reviewer-facing results pack.  
> **Scientific constraint:** relative entry timing is endogenous. All language is associational; no causal interpretation is permitted.  
> **Primary design:** `p2_100_w2` (two consecutive global topic years at ≥100 works; early entry defined as entry within two years of the first linked corporate entrant).  
> **Title:** intentionally not frozen here because the earlier title-bearing specification is not available through the current repository connection.

## Frozen operational hypotheses

- **H1:** Earlier relative corporate entry is associated with higher subsequent firm-topic scientific output.
- **H2:** Earlier relative corporate entry is associated with greater persistence of firm activity in the entered scientific topic.
- **H3:** Earlier relative corporate entry is associated with higher field-year-normalized citation impact after entry.
- **H4:** Greater pre-entry international collaboration-network diversity is associated with earlier relative entry into emerging scientific topics.
- **H5:** Pre-entry international collaboration-network diversity positively moderates the association between earlier entry and subsequent persistence.

These formulations preserve the hypotheses that were analyzed. They are not revised in response to the observed results.

# Results

## 1. Analysis sample and selection adjustment

The frozen primary panel contained **171 firm-topic entry episodes** spanning **54 scientific topics** and **21 firms**. Of these episodes, **65** were classified as early entries and **106** as later entries. Because firms that enter emerging scientific domains early may differ systematically from later entrants, the primary estimators used overlap weighting based on genuine pre-entry firm characteristics together with outcome-model adjustment and absorbed fixed effects. The overlap-weighted effective sample size was **134.0** episodes.

The weighting procedure produced strong observed balance on the pre-entry adjustment set. The largest absolute weighted standardized mean difference was **0.044**, well below the prespecified 0.10 diagnostic threshold. Timing/maturity-at-entry variables were not included in the primary propensity adjustment because they are mechanically related to the treatment definition and would partially control away relative entry timing itself. This distinction is important because the estimand is an adjusted association between relative entry timing and subsequent scientific outcomes, not a causal treatment effect.

## 2. H1: earlier entry and subsequent topic output

H1 predicted that earlier entrants would produce greater scientific output in the entered topic after entry. The primary overlap-weighted, doubly adjusted fixed-effects estimate was **−0.045** for log-transformed output over years +1 to +3. The coefficient was close to zero and was not statistically distinguishable from zero under topic-clustered CRV1 inference (**p = 0.861**), topic-clustered CRV3 inference (**p = 0.926**), two-way topic-and-firm clustering (**p = 0.840**), or the firm-cluster wild bootstrap (**p = 0.306**).

The frozen sensitivity grid reinforced the absence of a stable positive early-entry output advantage. Across the 13 gate-passing and post-weight-balanced design definitions, the +3-year H1 coefficient was negative in approximately **77%** of specifications, with a median estimate of approximately **−0.062**. Results using a +5-year output window were also predominantly negative. The evidence therefore does not support H1.

## 3. H2: earlier entry and persistence

H2 predicted that earlier entrants would be more likely to remain active in the scientific topic. In the primary +3-year persistence model, the adjusted early-entry coefficient was **−0.147**. Topic-clustered CRV1 inference did not reject zero (**p = 0.217**), and the result was likewise non-significant under topic CRV3 (**p = 0.559**) and two-way clustering (**p = 0.191**). The firm-cluster wild-bootstrap result was smaller (**p = 0.064**) but retained the same negative direction; it therefore does not provide evidence for the hypothesized positive persistence advantage.

The direction of the sensitivity evidence was notably consistent with this interpretation. Eleven of the 13 gate-passing +3-year sensitivity estimates were negative, and **all 13** +5-year persistence estimates were negative. Thus, the study does not identify a general persistence premium for firms that enter emerging topics earlier. If anything, the adjusted coefficients tend to point in the opposite direction, although the primary design does not justify a strong claim that early entry systematically reduces persistence.

## 4. H3: earlier entry and normalized citation impact

H3 concerned the post-entry field-year-normalized citation impact of firm-topic publications. The primary hypothesis was **not estimable under the frozen support rule**. After restricting to observations with a defined normalized-impact outcome and requiring within-topic representation of both early and later entrants, the primary design retained only **19 observations across 7 topics**, below the prespecified minimum of 30 observations across at least 8 topics. The primary H3 status is therefore neither supported nor rejected; it is unresolved because the planned contrast lacks adequate support.

Four prespecified sensitivity designs using the higher `p2_250` emergence threshold did meet the frozen support rule and were analyzed as sensitivity evidence only. Their estimates were **−0.151**, **−0.010**, **0.003**, and **0.022**. None approached conventional significance under topic CRV1, topic CRV3, two-way clustering, or firm wild-bootstrap inference; the multiplicity-adjusted q-values were approximately **0.989**. The median sensitivity estimate was approximately zero (**−0.004**). These sensitivity results do not replace the non-estimable primary H3 test, but they provide no indication of a concealed citation-impact advantage associated with earlier entry.

## 5. H4: collaboration-network diversity and relative entry timing

H4 predicted that firms with more internationally diverse collaboration networks before entry would enter emerging scientific domains earlier. The adjusted coefficient on standardized pre-entry network entropy was **−0.059** in the locked inference specification. It was not statistically distinguishable from zero under topic CRV1 (**p = 0.588**), topic CRV3 (**p = 0.700**), two-way clustering (**p = 0.607**), or the firm wild bootstrap (**p = 0.683**).

The frozen sensitivity grid was directionally unambiguous: the network-diversity coefficient was negative in **all 13** gate-passing design definitions. These results do not support the proposition that internationally diverse pre-entry scientific networks systematically select firms into earlier relative entry. This null main effect is consequential for interpreting H5, because any moderation pattern cannot simply be restated as evidence that diverse-network firms are themselves the earliest entrants.

## 6. H5: network diversity as a moderator of early-entry persistence

H5 predicted that pre-entry international collaboration-network diversity would strengthen the relationship between earlier entry and subsequent persistence. The primary interaction between early entry and standardized pre-entry network entropy was **0.184**. Under the primary topic-clustered CRV1 estimator, the interaction was positive and statistically significant (**p = 0.022**); it also remained positive under two-way topic-and-firm clustering (**p = 0.032**). However, the inference was materially weaker under the more conservative topic CRV3 estimator (**p = 0.193**) and the firm-cluster wild bootstrap (**p = 0.217**).

Coefficient stability was stronger than significance stability. The H5 interaction remained positive in **all 21 leave-one-firm-out refits**, ranging from approximately **0.034** to **0.235**. Across the 13 gate-passing and balanced sensitivity definitions, the +3-year H5 interaction was positive in **12 of 13 specifications (92.3%)**. Its sign was also positive in **76.9%** of +5-year sensitivity definitions. Nevertheless, conventional inferential support was not pervasive across the grid: only a minority of specifications achieved p < 0.05 with topic CRV1 or two-way clustering, and none achieved p < 0.10 under topic CRV3.

The correct interpretation is therefore **qualified directional support** for H5. The data show a recurring positive association between pre-entry network diversity and the persistence advantage associated with earlier entry, and the sign is not driven by a single firm. At the same time, the strength of statistical evidence depends on how the relatively small number of higher-level clusters is handled. H5 should not be described as confirmed, robustly significant, or causal.

## 7. Overall pattern

Taken together, the findings do not support a simple first-mover account of corporate scientific entry. Earlier entry is not associated with greater subsequent topic output (H1) or greater persistence (H2), and pre-entry international network diversity does not predict earlier relative entry (H4). The citation-impact hypothesis cannot be estimated in the primary design and yields near-zero estimates in the support-qualified sensitivity analyses (H3). The one recurring positive pattern is conditional: the association between early entry and subsequent persistence becomes more favorable as pre-entry international collaboration-network diversity rises (H5), although the uncertainty around this interaction is sensitive to small-cluster inference.

This result pattern shifts the empirical question away from whether firms benefit simply by entering scientific domains earlier and toward whether **organizational knowledge-access conditions determine which early entrants are able to sustain participation**.

# Discussion

## 1. Entry timing alone does not constitute a persistent scientific advantage

The first contribution of the study is the separation of relative entry timing from sustained scientific performance. The frozen primary design provides no evidence that earlier corporate entry is followed by higher firm-topic output or higher persistence. This is consistent with a contingency view of first-mover advantage in which early positioning creates opportunities but does not itself guarantee durable performance. Prior work has repeatedly found that entry timing can generate benefits in some outcome domains while producing nonlinear, weak, or context-dependent effects in others. Park, Shin, and Choy (2020), for example, reported early-mover benefits for venture funding among blockchain startups but an inverted-U association between entry timing and innovation performance. Likewise, contemporary first-mover theory emphasizes that observed first-mover advantages combine timing with selection on firm resources, information, and capabilities.

This distinction is particularly important in scientific domains. Entering an emerging topic early may expose a firm to a larger opportunity set, but maintaining a scientific program requires repeated allocation of researchers, attention, external relationships, and complementary internal capabilities. A firm can therefore be early without being positioned to convert early exposure into sustained scientific activity. The negative or null H1 and H2 estimates suggest that, in this sample, timing alone is a poor empirical proxy for durable scientific advantage.

The study also adopts a deliberately conservative interpretation because relative entry is endogenous. Cirik and Makadok's distinction between observed first-mover advantage and counterfactual first-mover benefit is directly relevant: firms choose or arrive at entry positions partly because of pre-existing differences, meaning an observed early-late contrast cannot be treated as a pure treatment effect. The overlap-weighted design substantially reduces imbalance in observed pre-entry characteristics, but it cannot eliminate unobserved selection. Accordingly, the findings speak to adjusted associations and comparative patterns, not to the causal effect that an otherwise identical firm would experience if it entered a topic earlier.

## 2. Network diversity appears more relevant to sustaining early entry than to producing it

The joint interpretation of H4 and H5 is more informative than either hypothesis alone. H4 receives no support: firms with more diverse international collaboration networks do not systematically enter emerging scientific topics earlier after adjustment. Across all 13 gate-passing sensitivity definitions, the H4 coefficient is negative. Network diversity therefore should not be described as an antecedent of early entry in these data.

Yet H5 shows that the relationship between early entry and persistence tends to become more positive when pre-entry collaboration networks are more internationally diverse. The contrast between H4 and H5 suggests a **conditioning rather than selection** interpretation. Diverse networks may not determine who arrives first, but they may influence whether an early entrant can continue operating in the domain after entry.

This interpretation is consistent with absorptive-capacity theory. Cohen and Levinthal (1990) argued that firms need prior related knowledge to recognize, assimilate, and exploit external knowledge, and that R&D contributes to this capacity. Fabrizio (2009) further showed that internal research and collaboration with university scientists can improve access to external knowledge and the timing and quality of innovative search. A diverse scientific collaboration network can plausibly expose firms to multiple knowledge pools, reduce dependence on a narrow set of partners, and improve the probability that useful knowledge remains accessible as an emerging domain changes. Importantly, the present study does not directly observe the internal routines required to absorb and integrate those inputs, so this mechanism remains an interpretation rather than a tested mediation pathway.

The moderation pattern also aligns with broader collaboration research showing that network effects often depend on complementary organizational capabilities. Najafi-Tavani et al. (2018) found that collaboration with different partners improved innovation capabilities only when absorptive capacity was sufficiently developed. This helps explain why a direct H4 effect need not accompany an H5 interaction: external-network breadth may have little systematic effect on *when* a firm enters but may become valuable once the firm must interpret, recombine, and continue investing in a new scientific domain.

## 3. Corporate science should be treated as a capability system rather than an entry event

A second theoretical implication is that corporate scientific activity is better conceptualized as a system of internal and external knowledge capabilities than as a sequence of discrete entry events. Recent work linking scientific publications to corporate technological innovation supports the importance of such knowledge-system connections. Chen et al. (2024) show that stronger linkages between corporate scientific publications and patenting are associated with greater technological innovation, including benefits from scientific knowledge generated at earlier stages. Their evidence reinforces the broader argument that scientific activity creates value when firms can connect produced or accessed science to downstream knowledge use.

The present study examines an earlier part of that process: whether firms sustain participation in newly emerging scientific topics after initial entry. The results indicate that simply being early is insufficient. The conditional H5 pattern instead points toward a capability configuration in which early positioning may matter more when coupled with a diversified external scientific knowledge base. This is compatible with a view of corporate science as an option-generating and learning infrastructure: entry may create access to a knowledge trajectory, while network diversity helps determine whether the firm can continue learning as that trajectory develops.

Because H5 is inference-sensitive, this capability interpretation should be treated as a theory-building result rather than a settled empirical regularity. The positive sign survives all 21 leave-one-firm-out exercises and almost all frozen +3 design definitions, which makes a single-firm artifact unlikely. At the same time, the loss of conventional significance under CRV3 and firm wild-bootstrap inference indicates that uncertainty is substantial once the small number of clusters is respected. The most defensible contribution is therefore the repeated **directional pattern** and its theoretical consistency, not a claim of precise effect magnitude.

## 4. No evidence of a general citation-quality premium

The citation-impact results add a useful boundary condition. The primary H3 contrast does not have sufficient within-topic support to be estimated according to the frozen rule. This is an identification limitation, not a null result. However, the four higher-scale sensitivity definitions that do satisfy the support rule produce estimates centered very near zero and uniformly non-significant across multiple inference methods. There is therefore no sensitivity-based evidence that early entrants systematically produce more highly cited post-entry science.

This separation between participation persistence and citation impact matters conceptually. Sustaining activity in a topic and producing more influential publications are different dimensions of scientific advantage. A diversified external network may help firms remain connected to a changing scientific conversation without necessarily increasing the average normalized citation impact of their publications. Future research with denser firm-topic citation support could test whether network diversity affects particular types of scientific influence—such as breakthrough publications, cross-domain diffusion, or downstream patent linkage—rather than average normalized citation impact.

## 5. Methodological contribution: defining emerging scientific entry without ex post specification choice

The study also contributes methodologically by separating the scientific result from specification selection. Emerging topics and relative corporate entry can be operationalized in multiple defensible ways, creating a substantial researcher-degree-of-freedom problem. Here, alternative emergence thresholds, persistence requirements, early-entry windows, and outcome windows were defined before the inferential sensitivity phase, and only designs that passed objective feasibility gates were analyzed. All 13 gate-passing designs also achieved strong observed balance after overlap weighting.

This matters especially for H5. A conventional analysis could emphasize the primary CRV1 p-value of 0.022 and stop. The frozen-grid approach instead shows that the coefficient sign is far more stable than the statistical significance. That distinction materially changes the substantive conclusion from "H5 is significant" to "H5 displays qualified directional support that is inference-sensitive." The approach therefore makes uncertainty across reasonable design and inference choices part of the result rather than an after-the-fact robustness appendix.

## 6. Limitations

Several limitations bound the conclusions. First, relative entry timing is endogenous. Overlap weighting, pre-entry covariates, pretrend adjustment, industry information, and fixed effects improve comparability but do not identify a causal entry-timing effect in the presence of unobserved differences in strategy, managerial attention, scientific talent, or proprietary technological opportunity.

Second, the analysis contains only 21 firms in the frozen primary panel. The firm-topic structure provides many episodes and topics, but inference can still be sensitive to the number of higher-level clusters. This is visible in H5, where topic CRV1 and two-way clustered inference are favorable but topic CRV3 and the firm wild bootstrap are not.

Third, publication-based entry captures visible scientific participation rather than all scientific knowledge acquisition. Firms can monitor, license, hire, collaborate privately, acquire startups, or conduct unpublished research before appearing in the publication record. Thus, measured entry is best understood as entry into observable corporate scientific production in a topic.

Fourth, network diversity is measured from observed international scientific collaboration before entry. It captures breadth in external geographic knowledge connections but not partner quality, tie strength beyond observed collaborative work, informal knowledge exchange, or the firm's internal ability to integrate external science. The absorptive-capacity mechanism is therefore theoretically plausible but not directly identified.

Fifth, H3 has limited outcome support in the primary sample. The study appropriately preserves the non-estimable primary status rather than replacing it with a better-powered sensitivity specification, but stronger conclusions about post-entry citation impact require a larger or denser firm-topic publication base.

## 7. Implications and conclusion

The study yields a deliberately qualified conclusion. Firms do not appear to obtain a general scientific advantage simply by entering emerging scientific domains earlier. Earlier entrants do not consistently produce more subsequent topic output or persist longer, and pre-entry network diversity does not systematically predict earlier relative entry. Instead, the most persistent pattern is conditional: early entry is associated with more favorable persistence when the firm enters with a more internationally diverse collaboration network.

For theory, this points toward a contingent view of scientific first-mover advantage. Timing may create an opportunity, but external knowledge architecture appears to shape whether that opportunity can be sustained. For managers, the result cautions against treating early entry into fashionable scientific domains as a stand-alone strategy. Building and maintaining diverse scientific connections may be at least as important as arriving early, although the present evidence cannot establish a causal managerial prescription.

The central empirical takeaway is therefore not "first is best." It is that **the value of being early in corporate science may depend on the knowledge network a firm brings with it**. Because the H5 evidence is directionally stable but inference-sensitive, replication with broader firm coverage, richer collaboration measures, and designs that more directly address endogenous entry is the appropriate next empirical test.

# References used for Discussion grounding

- Chen, X., Mao, J., Ma, Y., & Li, G. (2024). The knowledge linkage between science and technology influences corporate technological innovation: Evidence from scientific publications and patents. *Technological Forecasting and Social Change, 198*, 122985. https://doi.org/10.1016/j.techfore.2023.122985
- Cirik, K., & Makadok, R. (2023; online-first record also indexed earlier). First-Mover Advantages versus First-Mover Benefits: What's the Difference and Why Does It Matter? *Academy of Management Review, 48*(3), 409–431. https://doi.org/10.5465/amr.2017.0499
- Cohen, W. M., & Levinthal, D. A. (1990). Absorptive Capacity: A New Perspective on Learning and Innovation. *Administrative Science Quarterly, 35*(1), 128–152. https://doi.org/10.2307/2393553
- Fabrizio, K. R. (2009). Absorptive capacity and the search for innovation. *Research Policy, 38*(2), 255–267. https://doi.org/10.1016/j.respol.2008.10.023
- Najafi-Tavani, S., Najafi-Tavani, Z., Naudé, P., Oghazi, P., & Zeynaloo, E. (2018). How collaborative innovation networks affect new product performance: Product innovation capability, process innovation capability, and absorptive capacity. *Industrial Marketing Management, 73*, 193–205. https://doi.org/10.1016/j.indmarman.2018.02.009
- Park, G., Shin, S. R., & Choy, M. (2020). Early mover (dis)advantages and knowledge spillover effects on blockchain startups' funding and innovation performance. *Journal of Business Research, 109*, 64–75. https://doi.org/10.1016/j.jbusres.2019.11.068

# Manuscript claim boundary

The following formulations remain prohibited in all later drafts:

- "Early entry causes higher persistence."
- "H5 is confirmed."
- "H5 is robustly significant."
- "H3 is supported in the primary model."
- "H3 is rejected in the primary model."
- Any selection of a sensitivity design because it yields a more favorable coefficient or p-value.
