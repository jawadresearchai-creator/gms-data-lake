# Corporate Science Entry v1 — Introduction & Theory Blueprint

## Working title
**The Limits of First-Mover Advantage in Corporate Science: Entry Timing, Persistence, and International Knowledge Networks**

## Manuscript purpose
Build the Introduction and theory section around the **pre-existing ex ante hypotheses** while positioning the realized study as a boundary-condition test of scientific first-mover advantage. The paper must not rewrite hypotheses after seeing the results.

# 1. Introduction architecture

## Paragraph 1 — Strategic problem
Open with the firm's allocation problem in emerging science:

Firms increasingly participate directly in scientific research, but managers face an unresolved timing problem. Entering a nascent scientific domain early can provide learning and positioning opportunities, yet it also commits resources before the trajectory, partners, standards, or commercial relevance of the field are clear. Unlike product-market entry, scientific entry may precede appropriable commercial outcomes by years and may expose firms to broad spillovers.

**Purpose:** establish scientific entry timing as a distinct strategic decision, not merely a bibliometric phenomenon.

## Paragraph 2 — What first-mover theory predicts, and why it may not transfer automatically
Introduce conventional first-mover mechanisms:
- cumulative learning;
- preemption of scarce partners/talent;
- reputation/legitimacy;
- knowledge-position advantages;
- path-dependent capability accumulation.

Then establish the opposing scientific-domain mechanisms:
- extreme uncertainty;
- dead-end research trajectories;
- delayed appropriation;
- immature complementary assets;
- high integration burden;
- spillovers to rivals.

**Theoretical tension:** first-mover advantage versus learning-from-waiting / premature-entry liability.

## Paragraph 3 — Corporate science literature gap
Corporate-science research shows that scientific activity can contribute to technological search, absorptive capacity, patents, and innovation. However, most work asks whether firms conduct science, how much science they produce, or how science links to downstream invention. The unresolved question is **when firms enter emerging scientific domains and whether earlier entry creates persistent scientific advantage**.

Avoid claiming that no one has studied first-mover advantage in science. The novelty is the firm × emerging-topic × longitudinal persistence design across many scientific domains.

## Paragraph 4 — Why external networks should matter
Introduce the knowledge-network contingency:
- scientific knowledge is distributed across organizations and countries;
- international collaboration broadens access to heterogeneous knowledge pools;
- breadth can create recombination and sensing advantages;
- but benefits require integration/absorptive capacity and can create coordination burden.

This motivates two distinct questions:
1. Does network diversity predict earlier entry? (H4)
2. Does it condition what happens after early entry? (H5)

Keep these conceptually separate.

## Paragraph 5 — Study design
State what the study does without results:
- identify emerging scientific topics from global OpenAlex topic trajectories;
- identify relative corporate entry timing within topics;
- construct firm-topic entry episodes;
- measure pre-entry international collaboration-network diversity;
- follow output, persistence, and citation impact after entry;
- use overlap weighting, absorbed fixed effects, multiple cluster-robust inference methods, and a frozen 13-design sensitivity grid.

## Paragraph 6 — Contributions, written after analysis but constrained by the reframing lock
Contribution 1: boundary condition on automatic first-mover advantage in corporate science.

Contribution 2: separation of entry timing from sustained participation.

Contribution 3: qualified network-contingency evidence distinguishing network selection (H4) from post-entry conditioning (H5).

Contribution 4: methodological contribution separating sign stability from significance stability across prespecified alternative designs/inference choices.

Do not reveal full results in the opening contributions paragraph unless target-journal practice favors a results-forward Introduction.

# 2. Theory and hypotheses

## 2.1 Scientific entry timing and subsequent output

### First-mover mechanism
Earlier entry may increase subsequent scientific output because firms accumulate topic-specific routines, human capital, partner relationships, and problem-solving experience before later entrants. Learning is cumulative; earlier participation may create path dependence in attention and capability allocation.

### Countervailing mechanism acknowledged but not formalized as a competing hypothesis
Earlier entry may also expose firms to immature research trajectories and higher uncertainty. This should be acknowledged before H1 so the directional hypothesis is presented as theoretically contestable rather than obvious.

### H1
**H1: Earlier relative corporate entry into an emerging scientific domain is associated with higher subsequent firm-topic scientific output.**

## 2.2 Scientific entry timing and persistence

Persistence requires continued allocation of researchers and organizational attention beyond the initial entry event. First-mover logic predicts that accumulated topic-specific capability and network position should reduce the probability of exit and sustain participation.

Acknowledge that persistence may be harder than initial entry because firms learn about technical infeasibility and opportunity costs only after engaging with the domain.

### H2
**H2: Earlier relative corporate entry into an emerging scientific domain is associated with greater persistence of firm activity in that domain.**

## 2.3 Scientific entry timing and scientific impact

Earlier entrants may help define problems, methods, or application directions while a field is less crowded, potentially increasing visibility and influence. Cumulative advantage and early access to frontier problems motivate an impact prediction.

Acknowledge citation-age bias and field heterogeneity; explain that the empirical outcome is normalized within field-year rather than raw citations.

### H3
**H3: Earlier relative corporate entry into an emerging scientific domain is associated with higher field-year-normalized post-entry citation impact.**

## 2.4 International collaboration-network diversity as an antecedent of earlier entry

Firms embedded in more internationally diverse scientific networks may observe nascent developments across a broader knowledge landscape, increasing sensing capacity and reducing dependence on a single local scientific community. Diverse networks can provide early signals about emerging opportunities.

But network diversity can also impose search and coordination costs; mention this as a theoretical boundary rather than an alternative hypothesis.

### H4
**H4: Greater pre-entry international collaboration-network diversity is associated with earlier relative corporate entry into emerging scientific domains.**

## 2.5 International collaboration-network diversity as a moderator of persistence

Network diversity may matter most after entry. Early entrants face immature knowledge, uncertain trajectories, and incomplete complementary resources. Access to heterogeneous partners can broaden problem-solving inputs, create alternative routes when one trajectory fails, and help firms remain connected as the domain evolves.

This is the main absorptive-capacity/network-capability contingency. Explicitly distinguish the resource-access mechanism from the unmeasured internal capacity to integrate those resources.

### H5
**H5: Pre-entry international collaboration-network diversity positively moderates the association between earlier entry and subsequent persistence.**

# 3. Ex ante conceptual model

```text
Pre-entry firm capabilities/conditions
          │
          ├──────────────→ Relative entry timing
          │                     │
          │                     ├────────→ Subsequent topic output (H1)
          │                     ├────────→ Persistence (H2)
          │                     └────────→ Normalized citation impact (H3)
          │
Pre-entry international network diversity ──→ Earlier entry (H4)
          │
          └──── moderates Early entry → Persistence (H5)
```

The figure is an ex ante hypothesis map. It must not be redrawn after results to imply that only H5 was hypothesized.

# 4. Post-results interpretation architecture

The Discussion should follow this sequence:

1. **Simple timing advantage is not supported.** H1/H2 do not show the predicted benefit.
2. **Do not convert H2 into a proved disadvantage.** The negative direction is suggestive, not causal and not uniformly significant.
3. **H3 remains primarily unresolved.** Sensitivity-only nulls do not replace the primary support failure.
4. **Network diversity is not an entry-selection mechanism in this sample.** H4 is consistently non-positive.
5. **H5 is the conditional pattern.** Sign stability is high, but inference is sensitive.
6. **Theoretical synthesis:** scientific entry timing is capability-contingent; being early is an opportunity, not an advantage by itself.
7. **Future mechanism test:** exploration costs, premature commitment, partner access, recombination, or absorptive capacity should be tested with richer data rather than claimed here.

# 5. Evidence that must appear in Results

- Primary sample: 171 episodes, 54 topics, 21 firms.
- Early episodes: 65; later episodes: 106.
- Overlap-weight ESS: 134.0.
- Maximum weighted absolute SMD: 0.044.
- H1: estimate −0.045; topic CRV1 p=.861; CRV3 p=.926; two-way p=.840; firm wild p=.306.
- H2: estimate −0.147; topic CRV1 p=.217; CRV3 p=.559; two-way p=.191; firm wild p=.064.
- H3: primary not estimable under the frozen support rule; four support-qualified sensitivity estimates near zero and non-significant.
- H4: estimate −0.059; topic CRV1 p=.588; CRV3 p=.700; two-way p=.607; firm wild p=.683.
- H5: estimate +0.184; topic CRV1 p=.022; CRV3 p=.193; two-way p=.032; firm wild p=.217.
- H5 sign positive in 12/13 +3 frozen sensitivity designs and all 21 leave-one-firm-out primary refits.
- H5 +5 sign positive in 76.9% of designs.

# 6. Literature map

## Core first-mover / endogenous-entry anchors
- Cirik & Makadok — observed first-mover advantage versus counterfactual first-mover benefit; endogenous entry timing.
- Entry-timing research with learning/preemption trade-offs and mixed first-mover effects.
- Early-mover studies in emerging technologies that find contingent or nonlinear performance rather than universal advantage.

## Core absorptive-capacity anchors
- Cohen & Levinthal (1990).
- Fabrizio (2009).
- Zahra & George (2002) as an optional capability-process extension if needed.

## Corporate-science anchors
- Corporate scientific publication/innovation linkage literature.
- Research showing science-to-technology linkage and downstream inventive benefits.

## Network anchors
- Collaboration-network effects on innovation conditional on absorptive capacity.
- Partner/network diversity as heterogeneous knowledge access with potential integration costs.

# 7. Journal positioning

The theoretical center should remain **innovation strategy / corporate science**, not bibliometrics.

Recommended order for later journal-specific adaptation:
1. Research Policy — ambitious.
2. Technovation — strong fit.
3. R&D Management — strong realistic fit.

Do not choose a journal until the complete Introduction, Methods, Results, Discussion, tables, figures, and hostile-reviewer audit are available; target choice should be based on the finished contribution and empirical strength.

# 8. Non-negotiable claim controls

Never write:
- "Earlier entry causes..."
- "Early entry creates a persistence disadvantage."
- "H5 is confirmed."
- "H5 is robustly significant."
- "Network diversity causes early entrants to persist."
- "H3 is rejected."

Permitted:
- "The results do not support a general first-mover advantage in corporate scientific output or persistence."
- "The persistence estimates are predominantly negative across frozen specifications."
- "H5 provides qualified directional evidence of a network contingency, but the statistical support is inference-sensitive."
- "The pattern is consistent with the possibility that knowledge-network resources help some early entrants sustain participation; the mechanism is not directly identified."
