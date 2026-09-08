from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf
from sklearn.linear_model import LogisticRegression

OUT = Path("output_hardened")
OUT.mkdir(exist_ok=True)
PANEL = Path("input/primary_analysis_panel.csv")
RESEARCH = Path("input/company_research_year.parquet")
if not PANEL.exists() or not RESEARCH.exists():
    raise FileNotFoundError("Frozen panel or research mart missing")

SEED = 20260908
np.random.seed(SEED)

df = pd.read_csv(PANEL)
r = pd.read_parquet(RESEARCH, columns=["canonical_company_id", "publication_year", "work_count"])
r = r.rename(columns={"canonical_company_id": "company_id", "publication_year": "yr"})
r["company_id"] = r["company_id"].astype(str)
r["yr"] = r["yr"].astype(int)
r_lookup = {(a, int(y)): float(w) for a, y, w in r.itertuples(index=False, name=None)}

# Frozen pre-trend definition from design-freeze code.
def pretrend_slope(row):
    a = r_lookup.get((str(row.company_id), int(row.entry_year) - 3), 0.0)
    b = r_lookup.get((str(row.company_id), int(row.entry_year) - 1), 0.0)
    return (math.log1p(b) - math.log1p(a)) / 2.0

df["pretrend_slope"] = df.apply(pretrend_slope, axis=1)
df["company_id"] = df["company_id"].astype(str)
df["topic_id"] = df["topic_id"].astype(str)
df["entry_year"] = df["entry_year"].astype(int)
df["sic2"] = df["sic"].astype(str).str.extract(r"(\d{2})", expand=False).fillna("UNK")

df["log_pre3_research_output"] = np.log1p(pd.to_numeric(df["pre3_research_output"], errors="coerce").fillna(0))
df["log_pre3_research_citations"] = np.log1p(pd.to_numeric(df["pre3_research_citations"], errors="coerce").fillna(0))
df["log_pre3_collab_works"] = np.log1p(pd.to_numeric(df["pre3_collab_works"], errors="coerce").fillna(0))
df["y_h1"] = np.log1p(pd.to_numeric(df["post3_topic_output"], errors="coerce").fillna(0))
df["y_h2"] = pd.to_numeric(df["active_at_plus3"], errors="coerce")
df["y_h2_5"] = pd.to_numeric(df["active_at_plus5"], errors="coerce")
df["y_h3"] = np.log1p(pd.to_numeric(df["post3_field_year_norm_citation_ratio"], errors="coerce"))

# Genuine pre-entry variables only. Field age/global scale at entry are mechanically linked to treatment
# and remain sensitivity variables, not primary selection-adjustment variables.
adj = [
    "log_pre3_research_output",
    "log_pre3_research_citations",
    "pretrend_slope",
    "pre3_collab_countries",
    "pre3_network_hhi_complement",
    "pre3_network_entropy",
    "log_pre3_collab_works",
    "pre3_network_observed",
]
for c in adj:
    x = pd.to_numeric(df[c], errors="coerce")
    med = float(x.median()) if x.notna().any() else 0.0
    x = x.fillna(med)
    sd = float(x.std(ddof=0))
    df[c] = x
    df["z_" + c] = (x - x.mean()) / sd if sd > 0 else 0.0

# Recreate the frozen selection adjustment independently.
Xc = df[["z_" + c for c in adj]].to_numpy(float)
Xd = pd.get_dummies(df["sic2"], prefix="sic2", dtype=float)
X = np.column_stack([Xc, Xd.to_numpy(float)])
y = df["early_entry"].astype(int).to_numpy()
ps = LogisticRegression(C=1.0, max_iter=10000, solver="lbfgs", random_state=SEED).fit(X, y).predict_proba(X)[:, 1]
ps = np.clip(ps, 0.03, 0.97)
df["propensity"] = ps
df["overlap_weight"] = np.where(y == 1, 1 - ps, ps)
df["overlap_weight"] /= df["overlap_weight"].mean()

def wmean(x, w):
    x = np.asarray(x, float); w = np.asarray(w, float)
    return float(np.sum(w * x) / np.sum(w))

def smd(a, b, wa=None, wb=None):
    a = np.asarray(a, float); b = np.asarray(b, float)
    if wa is None:
        ma, mb = float(np.mean(a)), float(np.mean(b))
        va, vb = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    else:
        wa = np.asarray(wa, float); wb = np.asarray(wb, float)
        ma, mb = wmean(a, wa), wmean(b, wb)
        va = float(np.sum(wa * (a - ma) ** 2) / np.sum(wa))
        vb = float(np.sum(wb * (b - mb) ** 2) / np.sum(wb))
    den = math.sqrt(max((va + vb) / 2, 0.0))
    return 0.0 if den == 0 else float((ma - mb) / den)

def ess(w):
    w = np.asarray(w, float)
    return float((w.sum() ** 2) / np.sum(w ** 2))

balance = []
e = df[df.early_entry == 1]
l = df[df.early_entry == 0]
for c in adj:
    balance.append({
        "covariate": c,
        "raw_smd": smd(e[c], l[c]),
        "weighted_smd": smd(e[c], l[c], e.overlap_weight, l.overlap_weight),
    })
bal = pd.DataFrame(balance)
bal.to_csv(OUT / "overlap_balance_hardened.csv", index=False)

common = "z_log_pre3_research_output + z_log_pre3_research_citations + z_pretrend_slope + z_pre3_network_entropy + z_log_pre3_collab_works + z_pre3_network_observed"
common_no_entropy = "z_log_pre3_research_output + z_log_pre3_research_citations + z_pretrend_slope + z_log_pre3_collab_works + z_pre3_network_observed"

FE_SPECS = {
    "threeway_primary": "topic_id + company_id + entry_year",
    "topic_year": "topic_id + entry_year",
    "topic_firm": "topic_id + company_id",
}

def scalar(obj, param):
    if hasattr(obj, "loc"):
        return float(obj.loc[param])
    if isinstance(obj, dict):
        return float(obj[param])
    return float(obj[param])

def extract_fit(fit, param):
    coef = fit.coef()
    names = list(coef.index) if hasattr(coef, "index") else list(getattr(fit, "_coefnames", []))
    if param not in names:
        return {"status": "not_identified", "dropped_collinear": list(getattr(fit, "_collin_vars", [])), "n": int(getattr(fit, "_N", 0))}
    ci = fit.confint()
    if hasattr(ci, "loc"):
        cirow = ci.loc[param]
        low, high = float(cirow.iloc[0]), float(cirow.iloc[1])
    else:
        low, high = [float(x) for x in ci[param]]
    return {
        "status": "identified",
        "n": int(getattr(fit, "_N", 0)),
        "k": int(getattr(fit, "_k", 0)),
        "estimate": scalar(fit.coef(), param),
        "se_topic_crv1": scalar(fit.se(), param),
        "p_topic_crv1": scalar(fit.pvalue(), param),
        "ci95_topic_crv1": [low, high],
        "dropped_collinear": list(getattr(fit, "_collin_vars", [])),
    }

def wild_p_unweighted(formula, data, param, cluster="company_id"):
    try:
        fit = pf.feols(formula, data=data, vcov={"CRV1": "topic_id"}, fixef_rm="singleton", collin_tol=1e-9)
        if param not in list(fit.coef().index):
            return {"status": "not_identified", "p": None}
        wb = fit.wildboottest(
            reps=4999,
            cluster=cluster,
            param=param,
            weights_type="webb",
            impose_null=True,
            bootstrap_type="11",
            seed=SEED,
        )
        vals = wb.to_dict() if hasattr(wb, "to_dict") else dict(wb)
        p = None
        for key, value in vals.items():
            if "Pr(" in str(key) or str(key).lower().startswith("p"):
                try:
                    p = float(value)
                    break
                except Exception:
                    pass
        return {"status": "ok" if p is not None else "p_not_parsed", "p": p, "raw": {str(k): str(v) for k, v in vals.items()}}
    except Exception as exc:
        return {"status": "failed", "p": None, "error": f"{type(exc).__name__}: {exc}"}

def fit_weighted(formula, data, param, fe_name):
    try:
        fit = pf.feols(
            formula,
            data=data,
            weights="overlap_weight",
            weights_type="aweights",
            vcov={"CRV1": "topic_id"},
            fixef_rm="singleton",
            collin_tol=1e-9,
        )
        out = extract_fit(fit, param)
        out["fe_spec"] = fe_name
        return out
    except Exception as exc:
        return {"status": "fit_failed", "fe_spec": fe_name, "error": f"{type(exc).__name__}: {exc}"}

def run_spec(outcome, rhs, param, data=df, fe_specs=FE_SPECS, weighted=True):
    allres = {}
    for name, fe in fe_specs.items():
        f = f"{outcome} ~ {rhs} | {fe}"
        if weighted:
            rr = fit_weighted(f, data, param, name)
        else:
            try:
                fit = pf.feols(f, data=data, vcov={"CRV1": "topic_id"}, fixef_rm="singleton", collin_tol=1e-9)
                rr = extract_fit(fit, param); rr["fe_spec"] = name
            except Exception as exc:
                rr = {"status": "fit_failed", "fe_spec": name, "error": f"{type(exc).__name__}: {exc}"}
        allres[name] = rr
    return allres

results = {}

# H1/H2/H5: weighted doubly-adjusted models with absorbed topic + firm + entry-year FE primary.
results["H1_specs"] = run_spec("y_h1", f"early_entry + {common}", "early_entry")
results["H2_specs"] = run_spec("y_h2", f"early_entry + {common}", "early_entry")
results["H5_specs"] = run_spec(
    "y_h2",
    f"early_entry * z_pre3_network_entropy + {common_no_entropy}",
    "early_entry:z_pre3_network_entropy",
)

# H4 asks whether network diversity predicts earlier entry. Entry-year FE is inappropriate because entry timing
# is the outcome; compare within topic and firm, with topic-only as a pre-declared sensitivity.
h4_specs = {"topic_firm_primary": "topic_id + company_id", "topic_only": "topic_id"}
results["H4_specs"] = run_spec(
    "early_entry",
    f"z_pre3_network_entropy + {common_no_entropy}",
    "z_pre3_network_entropy",
    fe_specs=h4_specs,
    weighted=False,
)

# H3 remains governed by the design-freeze within-topic support rule; do not force an estimate.
d3 = df[df["y_h3"].notna()].copy()
sup = d3.groupby("topic_id")["early_entry"].agg(["min", "max", "count"])
valid_topics = sup[(sup["min"] == 0) & (sup["max"] == 1)].index
d3 = d3[d3.topic_id.isin(valid_topics)].copy()
results["H3"] = {
    "status": "not_estimable" if (len(d3) < 30 or d3.topic_id.nunique() < 8) else "support_passed",
    "n_within_topic_supported": int(len(d3)),
    "topics_with_both_groups": int(d3.topic_id.nunique()),
    "frozen_min_n": 30,
    "frozen_min_topics": 8,
    "conditional_on_continued_output": True,
}

# Firm wild-cluster inference is an unweighted robustness model because the bootstrap implementation may not
# support analytic overlap weights. Same covariates and absorbed FE are retained.
wild = {}
for h, outcome, rhs, param, fe in [
    ("H1", "y_h1", f"early_entry + {common}", "early_entry", FE_SPECS["threeway_primary"]),
    ("H2", "y_h2", f"early_entry + {common}", "early_entry", FE_SPECS["threeway_primary"]),
    ("H4", "early_entry", f"z_pre3_network_entropy + {common_no_entropy}", "z_pre3_network_entropy", h4_specs["topic_firm_primary"]),
    ("H5", "y_h2", f"early_entry * z_pre3_network_entropy + {common_no_entropy}", "early_entry:z_pre3_network_entropy", FE_SPECS["threeway_primary"]),
]:
    wild[h] = wild_p_unweighted(f"{outcome} ~ {rhs} | {fe}", df, param)

# Leave-one-firm-out for H1/H2 using primary absorbed-FE weighted specification.
loo = []
for firm in sorted(df.company_id.unique()):
    d = df[df.company_id != firm].copy()
    for h, outcome in [("H1", "y_h1"), ("H2", "y_h2")]:
        formula = f"{outcome} ~ early_entry + {common} | {FE_SPECS['threeway_primary']}"
        rr = fit_weighted(formula, d, "early_entry", "threeway_primary")
        loo.append({
            "left_out_firm": firm,
            "hypothesis": h,
            "status": rr.get("status"),
            "estimate": rr.get("estimate"),
            "p_topic_crv1": rr.get("p_topic_crv1"),
            "n": rr.get("n"),
        })
pd.DataFrame(loo).to_csv(OUT / "leave_one_firm_out_hardened.csv", index=False)

# Matching robustness, identical treatment/support logic, with replacement within topic.
pairs = []
for _, er in df[df.early_entry == 1].iterrows():
    cand = df[(df.topic_id == er.topic_id) & (df.early_entry == 0)]
    if cand.empty:
        continue
    j = (cand.propensity - er.propensity).abs().idxmin()
    lr = df.loc[j]
    pairs.append({
        "topic_id": er.topic_id,
        "early_company": er.company_id,
        "later_company": lr.company_id,
        "ps_distance": abs(float(er.propensity) - float(lr.propensity)),
        "h1_diff": float(er.y_h1 - lr.y_h1),
        "h2_diff": float(er.y_h2 - lr.y_h2),
    })
match = pd.DataFrame(pairs)
match.to_csv(OUT / "within_topic_matches_hardened.csv", index=False)

# Primary estimates are accepted only if the three-way absorbed model identifies the target coefficient.
primary_map = {
    "H1": results["H1_specs"]["threeway_primary"],
    "H2": results["H2_specs"]["threeway_primary"],
    "H4": results["H4_specs"]["topic_firm_primary"],
    "H5": results["H5_specs"]["threeway_primary"],
}

# BH adjustment across estimable primary H1/H2/H4/H5. H3 is not included when not estimable.
pset = [(h, rr["p_topic_crv1"]) for h, rr in primary_map.items() if rr.get("status") == "identified" and rr.get("p_topic_crv1") is not None]
if pset:
    vals = np.array([p for _, p in pset], float)
    order = np.argsort(vals)
    q = np.empty_like(vals)
    running = 1.0
    m = len(vals)
    for idx in order[::-1]:
        rank = int(np.where(order == idx)[0][0]) + 1
        running = min(running, vals[idx] * m / rank)
        q[idx] = running
    for (h, _), qq in zip(pset, q):
        primary_map[h]["bh_q_estimable_primary"] = float(qq)

for h, rr in primary_map.items():
    if rr.get("status") != "identified":
        rr["evidence_label"] = "not_identified"
        continue
    est = float(rr["estimate"]); p = float(rr["p_topic_crv1"]); q = float(rr.get("bh_q_estimable_primary", 1.0))
    if est > 0 and p < 0.05 and q < 0.10:
        label = "positive_adjusted_association"
    elif est > 0 and p < 0.10:
        label = "positive_directional_signal"
    else:
        label = "no_positive_adjusted_signal"
    rr["evidence_label"] = label
    rr["firm_wild_bootstrap"] = wild.get(h)

summary = {
    "analysis_status": "ESTIMATOR_HARDENING_COMPLETE",
    "estimand_language": "associational; relative entry is endogenous; no causal claim",
    "estimator": {
        "package": "pyfixest",
        "package_version": getattr(pf, "__version__", "unknown"),
        "weighted_primary": "overlap-weighted FE-OLS with absorbed fixed effects and topic CRV1",
        "wild_cluster_robustness": "unweighted same-covariate absorbed-FE model; Webb weights; company cluster; 4999 reps",
        "primary_fe_h1_h2_h5": FE_SPECS["threeway_primary"],
        "primary_fe_h4": h4_specs["topic_firm_primary"],
    },
    "frozen_panel": {
        "episodes": int(len(df)), "topics": int(df.topic_id.nunique()), "firms": int(df.company_id.nunique()),
        "early": int(df.early_entry.sum()), "later": int((1 - df.early_entry).sum()),
    },
    "selection_adjustment": {
        "overlap_weight_ess": ess(df.overlap_weight),
        "max_abs_weighted_smd": float(bal.weighted_smd.abs().max()),
        "propensity_min": float(df.propensity.min()),
        "propensity_max": float(df.propensity.max()),
    },
    "h3_support": results["H3"],
    "primary": primary_map,
    "all_fe_specs": results,
    "wild_bootstrap": wild,
    "matching": {
        "pairs": int(len(match)),
        "median_ps_distance": float(match.ps_distance.median()) if len(match) else None,
        "mean_h1_diff": float(match.h1_diff.mean()) if len(match) else None,
        "mean_h2_diff": float(match.h2_diff.mean()) if len(match) else None,
    },
}

(OUT / "estimator_hardening.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
df.to_csv(OUT / "analysis_panel_hardened.csv", index=False)

md = []
md.append("# Corporate Science Entry — Estimator Hardening")
md.append("")
md.append("This checkpoint replaces the rank-deficient dummy-matrix diagnostic with absorbed fixed effects. It does not change the frozen treatment, sample, outcomes, or H1–H5.")
md.append("")
md.append("## Estimator integrity")
md.append(f"- Frozen panel: **{len(df)}** episodes, **{df.topic_id.nunique()}** topics, **{df.company_id.nunique()}** firms.")
md.append(f"- Overlap-weight ESS: **{ess(df.overlap_weight):.1f}**.")
md.append(f"- Maximum absolute weighted SMD on genuine pre-entry adjustment covariates: **{bal.weighted_smd.abs().max():.3f}**.")
md.append(f"- PyFixest version: **{getattr(pf, '__version__', 'unknown')}**.")
md.append("- H1/H2/H5 primary FE: **topic + firm + entry year**, absorbed rather than expanded into a rank-deficient dummy matrix.")
md.append("- H4 primary FE: **topic + firm**; entry-year FE is excluded because entry timing is the dependent construct.")
md.append("")
md.append("## Hardened primary estimates")
md.append("")
md.append("| Hypothesis | Estimate | Topic-CRV1 p | BH q | Firm wild-bootstrap p | Status |")
md.append("|---|---:|---:|---:|---:|---|")
for h in ["H1", "H2", "H4", "H5"]:
    rr = primary_map[h]
    if rr.get("status") == "identified":
        wb = wild.get(h, {}).get("p")
        md.append(f"| {h} | {rr['estimate']:.4f} | {rr['p_topic_crv1']:.4f} | {rr.get('bh_q_estimable_primary', float('nan')):.4f} | {'NA' if wb is None else f'{wb:.4f}'} | {rr['evidence_label']} |")
    else:
        md.append(f"| {h} | — | — | — | — | {rr.get('status')} |")
md.append("")
md.append(f"- H3 frozen support: **{results['H3']['n_within_topic_supported']} rows across {results['H3']['topics_with_both_groups']} topics**; status: **{results['H3']['status']}**.")
md.append("")
md.append("## Pre-declared FE-specification comparison")
for h, key in [("H1", "H1_specs"), ("H2", "H2_specs"), ("H5", "H5_specs")]:
    md.append(f"### {h}")
    for spec, rr in results[key].items():
        if rr.get("status") == "identified":
            md.append(f"- {spec}: estimate {rr['estimate']:.4f}, p={rr['p_topic_crv1']:.4f}, n={rr['n']}; collinear dropped={rr.get('dropped_collinear', [])}.")
        else:
            md.append(f"- {spec}: {rr.get('status')} ({rr.get('error', '')}).")
md.append("")
md.append("## Robustness carried forward")
md.append(f"- Within-topic propensity matches: **{len(match)}**; matched H1 mean difference: **{match.h1_diff.mean() if len(match) else float('nan'):.4f}**; H2 mean difference: **{match.h2_diff.mean() if len(match) else float('nan'):.4f}**.")
md.append("- Leave-one-firm-out H1/H2 estimates are saved separately.")
md.append("- Wild-cluster results are robustness inference only; the overlap-weighted topic-cluster model remains the primary estimator.")
md.append("")
md.append("## Interpretation rule")
md.append("No estimate here is described as causal. H3 is not redefined to force estimability. If the absorbed three-way FE target coefficient is not identified, that hypothesis remains unresolved under the frozen primary specification rather than being silently moved to a more favorable model.")
(OUT / "ESTIMATOR_HARDENING.md").write_text("\n".join(md) + "\n", encoding="utf-8")

print(json.dumps(summary, indent=2))
