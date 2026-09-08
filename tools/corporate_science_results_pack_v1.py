from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path("output_results_pack")
OUT.mkdir(exist_ok=True)

REQ = [
    Path("input/analysis_panel_hardened.csv"),
    Path("input/overlap_balance_hardened.csv"),
    Path("input/inference_hardening.json"),
    Path("input/sensitivity_results.csv"),
    Path("input/h5_leave_one_firm_out.csv"),
    Path("input/final_analysis_lock.json"),
    Path("input/h3_sensitivity_only.csv"),
]
for p in REQ:
    if not p.exists():
        raise FileNotFoundError(p)

panel = pd.read_csv("input/analysis_panel_hardened.csv")
bal = pd.read_csv("input/overlap_balance_hardened.csv")
inf = json.loads(Path("input/inference_hardening.json").read_text(encoding="utf-8"))
sens = pd.read_csv("input/sensitivity_results.csv")
loo = pd.read_csv("input/h5_leave_one_firm_out.csv")
lock = json.loads(Path("input/final_analysis_lock.json").read_text(encoding="utf-8"))
h3 = pd.read_csv("input/h3_sensitivity_only.csv")

# ---------- Table 1: sample and selection balance ----------
labels = {
    "log_pre3_research_output": "Prior research output, log(1+x)",
    "log_pre3_research_citations": "Prior research citations, log(1+x)",
    "pretrend_slope": "Pre-entry research-output slope",
    "pre3_collab_countries": "Pre-entry collaborator countries",
    "pre3_network_hhi_complement": "Pre-entry network diversity, 1-HHI",
    "pre3_network_entropy": "Pre-entry network entropy",
    "log_pre3_collab_works": "Pre-entry collaborative works, log(1+x)",
    "pre3_network_observed": "Pre-entry network observed indicator",
}
rows=[]
for _, b in bal.iterrows():
    c=str(b["covariate"])
    e=panel[panel.early_entry==1][c]
    l=panel[panel.early_entry==0][c]
    rows.append({
        "covariate": labels.get(c,c),
        "early_raw_mean": float(pd.to_numeric(e,errors="coerce").mean()),
        "later_raw_mean": float(pd.to_numeric(l,errors="coerce").mean()),
        "raw_smd": float(b["raw_smd"]),
        "weighted_smd": float(b["weighted_smd"]),
    })
t1=pd.DataFrame(rows)
t1.to_csv(OUT/"TABLE_1_SAMPLE_AND_BALANCE.csv",index=False)

sample_summary=pd.DataFrame([
    {"metric":"Episodes","value":int(len(panel))},
    {"metric":"Topics","value":int(panel.topic_id.nunique())},
    {"metric":"Firms","value":int(panel.company_id.nunique())},
    {"metric":"Early-entry episodes","value":int(panel.early_entry.sum())},
    {"metric":"Later-entry episodes","value":int((1-panel.early_entry).sum())},
    {"metric":"Primary overlap-weight ESS","value":float(lock["selection_adjustment"]["primary_overlap_ess"])},
    {"metric":"Max abs weighted SMD","value":float(t1.weighted_smd.abs().max())},
])
sample_summary.to_csv(OUT/"TABLE_1A_SAMPLE_SUMMARY.csv",index=False)

# ---------- Table 2: locked primary estimates and inference ----------
verdicts=lock["verdicts"]
res_rows=[]
for h in ["H1","H2","H4","H5"]:
    x=inf["results"][h]
    c=x["cluster_inference"]
    a=c.get("topic_crv1",{})
    b=c.get("topic_crv3",{})
    d=c.get("two_way_crv1",{})
    w=x.get("firm_wild_bootstrap_unweighted",{})
    res_rows.append({
        "hypothesis":h,
        "primary_estimate":a.get("estimate"),
        "topic_crv1_p":a.get("p"),
        "topic_crv3_p":b.get("p"),
        "two_way_topic_firm_crv1_p":d.get("p"),
        "firm_wild_bootstrap_p":w.get("p"),
        "locked_verdict":verdicts[h]["verdict"],
    })
res_rows.insert(2,{
    "hypothesis":"H3",
    "primary_estimate":None,
    "topic_crv1_p":None,
    "topic_crv3_p":None,
    "two_way_topic_firm_crv1_p":None,
    "firm_wild_bootstrap_p":None,
    "locked_verdict":verdicts["H3"]["verdict"],
})
t2=pd.DataFrame(res_rows)
t2.to_csv(OUT/"TABLE_2_LOCKED_HYPOTHESIS_RESULTS.csv",index=False)

# ---------- Table 3: H3 sensitivity-only evidence ----------
h3.to_csv(OUT/"TABLE_3_H3_SENSITIVITY_ONLY.csv",index=False)

# ---------- Figure 1: H5 across frozen sensitivity definitions ----------
plot_sens=sens[["design","h5_plus3_est","h5_plus3_p_topic","h5_plus3_p_crv3"]].copy()
plot_sens=plot_sens.reset_index(drop=True)
y=np.arange(len(plot_sens))
fig,ax=plt.subplots(figsize=(8.2,6.5))
ax.axvline(0,linewidth=1)
ax.scatter(plot_sens["h5_plus3_est"],y,marker="o")
prim_idx=plot_sens.index[plot_sens.design=="p2_100_w2"].tolist()
if prim_idx:
    i=prim_idx[0]
    ax.scatter([plot_sens.loc[i,"h5_plus3_est"]],[i],marker="*")
    ax.annotate("primary",(plot_sens.loc[i,"h5_plus3_est"],i),xytext=(6,4),textcoords="offset points")
ax.set_yticks(y)
ax.set_yticklabels(plot_sens.design)
ax.set_xlabel("H5 interaction estimate: early entry × pre-entry network entropy")
ax.set_ylabel("Frozen design definition")
ax.set_title("H5 coefficient stability across gate-passing sensitivity designs")
fig.tight_layout()
fig.savefig(OUT/"FIGURE_1_H5_SENSITIVITY_PROFILE.png",dpi=300,bbox_inches="tight")
plt.close(fig)

# ---------- Figure 2: H5 leave-one-firm-out ----------
loo2=loo[loo.status=="identified"].copy().reset_index(drop=True)
fig,ax=plt.subplots(figsize=(9.0,4.8))
ax.axhline(0,linewidth=1)
primary=float(lock["primary_reference_estimates"]["H5"]["estimate"])
ax.axhline(primary,linestyle="--",linewidth=1)
ax.scatter(np.arange(len(loo2)),loo2["estimate"],marker="o")
ax.set_xticks(np.arange(len(loo2)))
ax.set_xticklabels(loo2["left_out_firm"].astype(str),rotation=75,ha="right",fontsize=7)
ax.set_ylabel("H5 interaction estimate")
ax.set_xlabel("Firm omitted")
ax.set_title("H5 leave-one-firm-out coefficient stability")
fig.tight_layout()
fig.savefig(OUT/"FIGURE_2_H5_LEAVE_ONE_FIRM_OUT.png",dpi=300,bbox_inches="tight")
plt.close(fig)

# ---------- Figure 3: balance before vs after overlap weighting ----------
fig,ax=plt.subplots(figsize=(8.2,5.5))
y=np.arange(len(t1))
ax.axvline(0,linewidth=1)
ax.axvline(0.1,linestyle="--",linewidth=1)
ax.axvline(-0.1,linestyle="--",linewidth=1)
ax.scatter(t1.raw_smd,y,marker="o",label="Raw")
ax.scatter(t1.weighted_smd,y,marker="x",label="Overlap weighted")
ax.set_yticks(y)
ax.set_yticklabels(t1.covariate)
ax.set_xlabel("Standardized mean difference (early − later)")
ax.set_ylabel("Pre-entry covariate")
ax.set_title("Selection balance before and after overlap weighting")
ax.legend()
fig.tight_layout()
fig.savefig(OUT/"FIGURE_3_SELECTION_BALANCE.png",dpi=300,bbox_inches="tight")
plt.close(fig)

# ---------- Claims discipline for manuscript handoff ----------
claims={
    "H1_allowed":"We find no evidence that earlier corporate entry is associated with higher subsequent topic output under the frozen primary design and sensitivity grid.",
    "H2_allowed":"Earlier entry is not associated with greater persistence; adjusted estimates are predominantly negative, including all +5 sensitivity estimates.",
    "H3_allowed":"The primary citation-impact hypothesis is not estimable under the frozen within-topic support rule; sensitivity-only estimates that meet support thresholds are near zero and non-significant.",
    "H4_allowed":"Pre-entry international collaboration-network diversity does not predict earlier relative entry in the adjusted models.",
    "H5_allowed":"The interaction between earlier entry and pre-entry collaboration-network diversity is positive across most frozen design definitions, but statistical support is sensitive to the inference method; this is qualified directional evidence rather than a robust or causal finding.",
    "prohibited":[
        "early entry causes higher persistence",
        "H5 is confirmed",
        "H5 is robustly significant",
        "H3 is supported in the primary model",
        "H3 is rejected in the primary model",
        "selecting a sensitivity design because it produces a smaller p-value",
    ],
}
(OUT/"MANUSCRIPT_CLAIMS_LOCK.json").write_text(json.dumps(claims,indent=2),encoding="utf-8")

manifest={
    "status":"REVIEWER_FACING_RESULTS_PACK_COMPLETE",
    "source_lock_status":lock["status"],
    "tables":[
        "TABLE_1A_SAMPLE_SUMMARY.csv",
        "TABLE_1_SAMPLE_AND_BALANCE.csv",
        "TABLE_2_LOCKED_HYPOTHESIS_RESULTS.csv",
        "TABLE_3_H3_SENSITIVITY_ONLY.csv",
    ],
    "figures":[
        "FIGURE_1_H5_SENSITIVITY_PROFILE.png",
        "FIGURE_2_H5_LEAVE_ONE_FIRM_OUT.png",
        "FIGURE_3_SELECTION_BALANCE.png",
    ],
    "claim_lock":"MANUSCRIPT_CLAIMS_LOCK.json",
    "qa":{
        "no_model_refit":True,
        "no_hypothesis_redefinition":True,
        "primary_design_unchanged":True,
        "h3_sensitivity_not_promoted":True,
        "causal_language_prohibited":True,
    },
}
(OUT/"RESULTS_PACK_MANIFEST.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")

md=[]
md.append("# Corporate Science Entry — Reviewer-Facing Results Pack")
md.append("")
md.append("This pack is generated only from the locked analysis outputs. No model, treatment definition, outcome definition, or hypothesis has been changed.")
md.append("")
md.append("## Locked scientific message")
md.append("")
md.append("- **H1:** not supported; no stable positive output advantage for earlier entrants.")
md.append("- **H2:** not supported; persistence estimates are predominantly negative and all +5 sensitivity estimates are negative.")
md.append("- **H3:** primary model not estimable; four sensitivity-only estimates are near zero and uniformly non-significant.")
md.append("- **H4:** not supported; network-diversity coefficients are negative across all 13 gate-passing designs.")
md.append("- **H5:** qualified directional evidence only. The interaction is positive in 12/13 +3 designs and all 21 leave-one-firm-out primary refits, but small-cluster inference is sensitive.")
md.append("")
md.append("## Reviewer-facing evidence")
md.append("")
md.append("1. `TABLE_1A_SAMPLE_SUMMARY.csv` and `TABLE_1_SAMPLE_AND_BALANCE.csv` document sample size and selection adjustment.")
md.append("2. `TABLE_2_LOCKED_HYPOTHESIS_RESULTS.csv` reports the final primary estimates with topic CRV1, topic CRV3, two-way clustering, and firm wild-bootstrap inference.")
md.append("3. `TABLE_3_H3_SENSITIVITY_ONLY.csv` keeps the H3 sensitivity evidence separate from the non-estimable primary hypothesis.")
md.append("4. `FIGURE_1_H5_SENSITIVITY_PROFILE.png` shows coefficient direction across all 13 gate-passing definitions without selecting favorable specifications.")
md.append("5. `FIGURE_2_H5_LEAVE_ONE_FIRM_OUT.png` shows whether any single firm drives the H5 sign.")
md.append("6. `FIGURE_3_SELECTION_BALANCE.png` shows raw versus overlap-weighted pre-entry balance.")
md.append("")
md.append("## Drafting boundary")
md.append("")
md.append("Use `MANUSCRIPT_CLAIMS_LOCK.json` as the claim boundary for Results and Discussion. The next stage may improve presentation and prose, but may not alter the frozen statistical interpretation.")
(OUT/"REVIEWER_FACING_RESULTS_PACK.md").write_text("\n".join(md)+"\n",encoding="utf-8")

print(json.dumps(manifest,indent=2))
