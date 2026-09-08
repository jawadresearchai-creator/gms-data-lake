from __future__ import annotations

import json
import math
import runpy
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf
from sklearn.linear_model import LogisticRegression

SEED = 20260908
np.random.seed(SEED)
OUT = Path("output_final_lock")
OUT.mkdir(exist_ok=True)

REQUIRED = [
    Path("input/company_research_year.parquet"),
    Path("input/inference_hardening.json"),
    Path("input/sensitivity_summary.json"),
    Path("input/sensitivity_results.csv"),
    Path("input/design_freeze.json"),
]
for p in REQUIRED:
    if not p.exists():
        raise FileNotFoundError(p)

inference = json.loads(Path("input/inference_hardening.json").read_text(encoding="utf-8"))
sens_summary = json.loads(Path("input/sensitivity_summary.json").read_text(encoding="utf-8"))
sens_results = pd.read_csv("input/sensitivity_results.csv")
design_freeze = json.loads(Path("input/design_freeze.json").read_text(encoding="utf-8"))

# Reproduce the frozen design tables from the exact staged GMS release. This is only to finish H3
# sensitivity estimation in the four designs that already passed H3's frozen support threshold.
ns = runpy.run_path("tools/corporate_science_design_freeze_v1.py")
con = ns["con"]
grid = ns["grid"]
passing = [x for x in grid if bool(x["passes_gate"])]

r = pd.read_parquet("input/company_research_year.parquet", columns=["canonical_company_id", "publication_year", "work_count"])
r = r.rename(columns={"canonical_company_id": "company_id", "publication_year": "yr"})
r["company_id"] = r["company_id"].astype(str)
r["yr"] = r["yr"].astype(int)
r_lookup = {(a, int(y)): float(w) for a, y, w in r.itertuples(index=False, name=None)}

def pretrend_slope(row):
    a = r_lookup.get((str(row.company_id), int(row.entry_year) - 3), 0.0)
    b = r_lookup.get((str(row.company_id), int(row.entry_year) - 1), 0.0)
    return (math.log1p(b) - math.log1p(a)) / 2.0

ADJ = [
    "log_pre3_research_output",
    "log_pre3_research_citations",
    "pretrend_slope",
    "pre3_collab_countries",
    "pre3_network_hhi_complement",
    "pre3_network_entropy",
    "log_pre3_collab_works",
    "pre3_network_observed",
]
H3_COMMON = "z_log_pre3_research_output + z_log_pre3_research_citations + z_pretrend_slope + z_pre3_network_entropy + z_log_pre3_collab_works"

def prepare(tbl: str):
    d = con.execute(f"SELECT * FROM {tbl}").df()
    d["company_id"] = d["company_id"].astype(str)
    d["topic_id"] = d["topic_id"].astype(str)
    d["entry_year"] = d["entry_year"].astype(int)
    d["sic2"] = d["sic"].astype(str).str.extract(r"(\d{2})", expand=False).fillna("UNK")
    d["pretrend_slope"] = d.apply(pretrend_slope, axis=1)
    d["log_pre3_research_output"] = np.log1p(pd.to_numeric(d["pre3_research_output"], errors="coerce").fillna(0))
    d["log_pre3_research_citations"] = np.log1p(pd.to_numeric(d["pre3_research_citations"], errors="coerce").fillna(0))
    d["log_pre3_collab_works"] = np.log1p(pd.to_numeric(d["pre3_collab_works"], errors="coerce").fillna(0))
    d["y_h3"] = np.log1p(pd.to_numeric(d["post3_field_year_norm_citation_ratio"], errors="coerce"))

    for c in ADJ:
        x = pd.to_numeric(d[c], errors="coerce")
        med = float(x.median()) if x.notna().any() else 0.0
        x = x.fillna(med)
        sd = float(x.std(ddof=0))
        d[c] = x
        d["z_" + c] = (x - float(x.mean())) / sd if sd > 0 else 0.0

    Xc = d[["z_" + c for c in ADJ]].to_numpy(float)
    Xd = pd.get_dummies(d["sic2"], prefix="sic2", dtype=float)
    X = np.column_stack([Xc, Xd.to_numpy(float)])
    y = d["early_entry"].astype(int).to_numpy()
    ps = LogisticRegression(C=1.0, max_iter=10000, solver="lbfgs", random_state=SEED).fit(X, y).predict_proba(X)[:, 1]
    ps = np.clip(ps, 0.03, 0.97)
    d["propensity"] = ps
    d["overlap_weight"] = np.where(y == 1, 1 - ps, ps)
    d["overlap_weight"] /= d["overlap_weight"].mean()
    d["company_cluster"] = pd.factorize(d["company_id"], sort=True)[0].astype(np.int64)
    return d

def extract(fit, param="early_entry"):
    if param not in list(fit.coef().index):
        return {"status": "not_identified", "n": int(getattr(fit, "_N", 0))}
    ci = fit.confint().loc[param]
    return {
        "status": "identified",
        "n": int(getattr(fit, "_N", 0)),
        "estimate": float(fit.coef().loc[param]),
        "se": float(fit.se().loc[param]),
        "p": float(fit.pvalue().loc[param]),
        "ci95": [float(ci.iloc[0]), float(ci.iloc[1])],
        "dropped": list(getattr(fit, "_collin_vars", [])),
    }

def fit_h3(d):
    formula = f"y_h3 ~ early_entry + {H3_COMMON} | topic_id"
    out = {}
    for name, vcov in [
        ("topic_crv1", {"CRV1": "topic_id"}),
        ("topic_crv3", {"CRV3": "topic_id"}),
        ("two_way_crv1", {"CRV1": "topic_id + company_id"}),
    ]:
        try:
            fit = pf.feols(
                formula,
                data=d,
                weights="overlap_weight",
                weights_type="aweights",
                vcov=vcov,
                fixef_rm="singleton",
                collin_tol=1e-9,
            )
            out[name] = extract(fit)
        except Exception as exc:
            out[name] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}

    # Small-firm-count robustness is deliberately unweighted, matching the prior inference-hardening rule.
    try:
        fit_u = pf.feols(formula, data=d, vcov={"CRV1": "topic_id"}, fixef_rm="singleton", collin_tol=1e-9)
        wb = fit_u.wildboottest(
            reps=9999,
            cluster="company_cluster",
            param="early_entry",
            weights_type="webb",
            impose_null=True,
            bootstrap_type="11",
            seed=SEED,
            parallel=False,
        )
        vals = wb.to_dict() if hasattr(wb, "to_dict") else dict(wb)
        p = None
        for k, v in vals.items():
            ks = str(k)
            if "Pr(" in ks or ks.lower() in {"p", "pvalue", "p-value", "p_value"}:
                try:
                    p = float(v)
                    break
                except Exception:
                    pass
        out["firm_wild_unweighted"] = {"status": "ok" if p is not None else "p_not_parsed", "p": p}
    except Exception as exc:
        out["firm_wild_unweighted"] = {"status": "failed", "p": None, "error": f"{type(exc).__name__}: {exc}"}
    return out

h3_rows = []
h3_details = {}
for g in passing:
    spec = str(g["emergence_spec"])
    w = int(g["early_window"])
    key = f"{spec}_w{w}"
    d = prepare(f"p_{spec}_w{w}")
    x = d[d.y_h3.notna()].copy()
    if len(x):
        support = x.groupby("topic_id")["early_entry"].agg(["min", "max"])
        valid = support[(support["min"] == 0) & (support["max"] == 1)].index
        x = x[x.topic_id.isin(valid)].copy()
    n = int(len(x)); topics = int(x.topic_id.nunique()) if len(x) else 0
    support_ok = bool(n >= 30 and topics >= 8)
    if not support_ok:
        continue
    rr = fit_h3(x)
    prim = rr.get("topic_crv1", {})
    h3_rows.append({
        "design": key,
        "n": n,
        "topics": topics,
        "estimate": prim.get("estimate"),
        "p_topic_crv1": prim.get("p"),
        "p_topic_crv3": rr.get("topic_crv3", {}).get("p"),
        "p_two_way_crv1": rr.get("two_way_crv1", {}).get("p"),
        "p_firm_wild": rr.get("firm_wild_unweighted", {}).get("p"),
    })
    h3_details[key] = rr

h3_df = pd.DataFrame(h3_rows)
if len(h3_df):
    pvals = pd.to_numeric(h3_df["p_topic_crv1"], errors="coerce").to_numpy(float)
    valid_idx = np.where(np.isfinite(pvals))[0]
    qvals = np.full(len(h3_df), np.nan)
    if len(valid_idx):
        vals = pvals[valid_idx]
        order = np.argsort(vals)
        running = 1.0
        m = len(vals)
        qlocal = np.empty_like(vals)
        for pos in range(m - 1, -1, -1):
            idx = order[pos]
            rank = pos + 1
            running = min(running, vals[idx] * m / rank)
            qlocal[idx] = running
        qvals[valid_idx] = qlocal
    h3_df["bh_q_sensitivity_h3"] = qvals
h3_df.to_csv(OUT / "h3_sensitivity_only.csv", index=False)
(OUT / "h3_sensitivity_details.json").write_text(json.dumps(h3_details, indent=2), encoding="utf-8")

if len(h3_df):
    est = pd.to_numeric(h3_df.estimate, errors="coerce").dropna()
    h3_sens_summary = {
        "support_passing_designs": int(len(h3_df)),
        "positive_share": float((est > 0).mean()) if len(est) else None,
        "negative_share": float((est < 0).mean()) if len(est) else None,
        "median_estimate": float(est.median()) if len(est) else None,
        "topic_crv1_p_lt_005_share": float((pd.to_numeric(h3_df.p_topic_crv1, errors="coerce") < 0.05).mean()),
        "topic_crv3_p_lt_010_share": float((pd.to_numeric(h3_df.p_topic_crv3, errors="coerce") < 0.10).mean()),
        "two_way_p_lt_005_share": float((pd.to_numeric(h3_df.p_two_way_crv1, errors="coerce") < 0.05).mean()),
        "firm_wild_p_lt_010_share": float((pd.to_numeric(h3_df.p_firm_wild, errors="coerce") < 0.10).mean()),
    }
else:
    h3_sens_summary = {"support_passing_designs": 0}

# Consolidated lock. This is a scientific status lock, not a claim of causality.
h5_primary = inference["results"]["H5"]["cluster_inference"]["topic_crv1"]
h2_primary = inference["results"]["H2"]["cluster_inference"]["topic_crv1"]
h1_primary = inference["results"]["H1"]["cluster_inference"]["topic_crv1"]
h4_primary = inference["results"]["H4"]["cluster_inference"]["topic_crv1"]

verdicts = {
    "H1": {
        "verdict": "NOT_SUPPORTED",
        "reason": "Primary adjusted estimate is non-positive and the +3/+5 frozen sensitivity grid is predominantly negative; no stable positive first-mover output advantage.",
    },
    "H2": {
        "verdict": "NOT_SUPPORTED_DIRECTION_MOSTLY_NEGATIVE",
        "reason": "Primary +3 persistence estimate is negative; 11/13 +3 sensitivity estimates are negative and all 13 +5 sensitivity estimates are negative.",
    },
    "H3": {
        "verdict": "PRIMARY_NOT_ESTIMABLE_SENSITIVITY_ONLY",
        "reason": "Primary design fails the frozen H3 support threshold. Support-passing alternative definitions are reported only as sensitivity evidence and cannot replace the primary verdict.",
        "sensitivity": h3_sens_summary,
    },
    "H4": {
        "verdict": "NOT_SUPPORTED",
        "reason": "Primary adjusted estimate is negative/no-signal and all 13 gate-passing sensitivity designs have negative entropy coefficients.",
    },
    "H5": {
        "verdict": "QUALIFIED_DIRECTIONAL_SUPPORT_INFERENCE_SENSITIVE",
        "reason": "Primary interaction is positive and sign-stable in leave-one-firm-out and 12/13 +3 sensitivity designs, but CRV3 and firm wild-bootstrap inference do not support a robust significance claim; +5 sign stability is weaker.",
    },
}

final_lock = {
    "status": "FINAL_ANALYSIS_LOCK_V1",
    "locked_at_stage": "post-primary-estimation + estimator-hardening + inference-hardening + frozen-sensitivity + H3-sensitivity-completion",
    "causal_language": "PROHIBITED; relative entry timing is endogenous",
    "primary_design": "p2_100_w2",
    "primary_panel": {
        "episodes": int(design_freeze.get("primary", {}).get("episodes", 171)) if isinstance(design_freeze.get("primary"), dict) else 171,
        "topics": 54,
        "firms": 21,
    },
    "selection_adjustment": {
        "all_13_gate_passing_designs_balanced_below_0_10_weighted_smd": bool(sens_summary.get("balanced_gate_passing_designs") == 13),
        "primary_overlap_ess": inference.get("frozen_panel", {}).get("n"),
    },
    "primary_reference_estimates": {
        "H1": h1_primary,
        "H2": h2_primary,
        "H4": h4_primary,
        "H5": h5_primary,
    },
    "h3_sensitivity_only": h3_sens_summary,
    "verdicts": verdicts,
    "sensitivity_signs": {
        "H1_post3": sens_summary.get("H1_post3_signs"),
        "H2_plus3": sens_summary.get("H2_plus3_signs"),
        "H4": sens_summary.get("H4_signs"),
        "H5_plus3": sens_summary.get("H5_plus3_signs"),
        "H2_plus5": sens_summary.get("H2_plus5_signs"),
        "H5_plus5": sens_summary.get("H5_plus5_signs"),
    },
    "rules_after_lock": [
        "Do not redefine H1-H5 after seeing results.",
        "Do not promote any sensitivity specification over the frozen primary design.",
        "Do not describe H5 as confirmed, robustly significant, or causal.",
        "Do not describe H3 as supported or unsupported from the primary design; it is not estimable there.",
        "Any manuscript claim must preserve the distinction between primary, robustness, and sensitivity evidence.",
    ],
    "next_phase": "descriptive-result tables/figures, reviewer-facing robustness presentation, then manuscript Results/Discussion drafting from the locked analysis",
}
(OUT / "final_analysis_lock.json").write_text(json.dumps(final_lock, indent=2), encoding="utf-8")

md = []
md.append("# Corporate Science Entry — FINAL ANALYSIS LOCK v1")
md.append("")
md.append("This file freezes the scientific interpretation after the primary analysis, estimator hardening, inference hardening, the full pre-frozen sensitivity grid, and H3 sensitivity-only completion. Relative entry timing is endogenous; **no causal claim is permitted**.")
md.append("")
md.append("## Locked hypothesis verdicts")
md.append("")
md.append("| Hypothesis | Locked verdict | Interpretation |")
md.append("|---|---|---|")
for h in ["H1", "H2", "H3", "H4", "H5"]:
    v = verdicts[h]
    md.append(f"| {h} | **{v['verdict']}** | {v['reason']} |")
md.append("")
md.append("## H3 sensitivity-only completion")
md.append("")
if len(h3_df):
    md.append("| Design | N | Topics | Estimate | Topic CRV1 p | CRV3 p | Two-way p | Firm wild p | BH q |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, x in h3_df.iterrows():
        def f(v): return "NA" if pd.isna(v) else f"{float(v):.4f}"
        md.append(f"| {x.design} | {int(x.n)} | {int(x.topics)} | {f(x.estimate)} | {f(x.p_topic_crv1)} | {f(x.p_topic_crv3)} | {f(x.p_two_way_crv1)} | {f(x.p_firm_wild)} | {f(x.bh_q_sensitivity_h3)} |")
else:
    md.append("No sensitivity design passed the frozen H3 support threshold.")
md.append("")
md.append(f"H3 sensitivity summary: `{json.dumps(h3_sens_summary)}`")
md.append("")
md.append("## H5 interpretation lock")
md.append("")
md.append(f"- Primary +3 interaction: **{h5_primary.get('estimate'):.4f}**, topic-CRV1 p={h5_primary.get('p'):.4f}.")
md.append(f"- Across 13 balanced gate-passing definitions, H5 +3 is positive in **{100*sens_summary['H5_plus3_signs']['positive_share']:.1f}%** of designs.")
md.append(f"- H5 +5 is positive in **{100*sens_summary['H5_plus5_signs']['positive_share']:.1f}%** of designs.")
md.append("- Prior inference hardening showed the primary H5 result is not robust to topic CRV3 or firm wild-cluster bootstrap; therefore it remains **qualified directional evidence only**.")
md.append("")
md.append("## Post-lock rules")
for rule in final_lock["rules_after_lock"]:
    md.append(f"- {rule}")
md.append("")
md.append("## Next phase")
md.append("")
md.append("Create descriptive and model-result tables/figures from these locked outputs, perform reviewer-facing robustness presentation, and then draft Results and Discussion without altering the analysis specification.")
(OUT / "FINAL_ANALYSIS_LOCK.md").write_text("\n".join(md) + "\n", encoding="utf-8")

print(json.dumps(final_lock, indent=2))
