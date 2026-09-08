from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf

OUT = Path("output_inference")
OUT.mkdir(exist_ok=True)
PANEL = Path("input/analysis_panel_hardened.csv")
if not PANEL.exists():
    raise FileNotFoundError(PANEL)

SEED = 20260908
df = pd.read_csv(PANEL)
df["company_id"] = df["company_id"].astype(str)
df["topic_id"] = df["topic_id"].astype(str)
df["entry_year"] = df["entry_year"].astype(int)
# Numeric cluster codes avoid Numba object-array failure in wildboottest.
df["company_cluster"] = pd.factorize(df["company_id"], sort=True)[0].astype(np.int64)
df["topic_cluster"] = pd.factorize(df["topic_id"], sort=True)[0].astype(np.int64)

# z_pre3_network_observed was deterministically dropped as collinear in the absorbed-FE hardening run;
# omit this nuisance term here without changing treatment, outcomes, sample, or scientific hypotheses.
common = "z_log_pre3_research_output + z_log_pre3_research_citations + z_pretrend_slope + z_pre3_network_entropy + z_log_pre3_collab_works"
common_no_entropy = "z_log_pre3_research_output + z_log_pre3_research_citations + z_pretrend_slope + z_log_pre3_collab_works"
FE3 = "topic_id + company_id + entry_year"
FE_H4 = "topic_id + company_id"

def extract(fit, param):
    co = fit.coef()
    if param not in list(co.index):
        return {"status":"not_identified","n":int(getattr(fit,"_N",0)),"dropped":list(getattr(fit,"_collin_vars",[]))}
    ci = fit.confint().loc[param]
    return {
        "status":"identified",
        "n":int(getattr(fit,"_N",0)),
        "estimate":float(fit.coef().loc[param]),
        "se":float(fit.se().loc[param]),
        "p":float(fit.pvalue().loc[param]),
        "ci95":[float(ci.iloc[0]),float(ci.iloc[1])],
        "dropped":list(getattr(fit,"_collin_vars",[])),
    }

def fit_inference(formula, param, data, weighted=True):
    kw = {"data":data,"fixef_rm":"singleton","collin_tol":1e-9}
    if weighted:
        kw.update({"weights":"overlap_weight","weights_type":"aweights"})
    out = {}
    for name, vcov in [
        ("topic_crv1", {"CRV1":"topic_id"}),
        ("topic_crv3", {"CRV3":"topic_id"}),
        ("two_way_crv1", {"CRV1":"topic_id + company_id"}),
    ]:
        try:
            fit = pf.feols(formula, vcov=vcov, **kw)
            out[name] = extract(fit,param)
        except Exception as exc:
            out[name] = {"status":"failed","error":f"{type(exc).__name__}: {exc}"}
    return out

def wild_company(formula, param, data):
    try:
        fit = pf.feols(formula, data=data, vcov={"CRV1":"topic_id"}, fixef_rm="singleton", collin_tol=1e-9)
        if param not in list(fit.coef().index):
            return {"status":"not_identified","p":None}
        wb = fit.wildboottest(
            reps=9999,
            cluster="company_cluster",
            param=param,
            weights_type="webb",
            impose_null=True,
            bootstrap_type="11",
            seed=SEED,
            parallel=False,
        )
        vals = wb.to_dict() if hasattr(wb,"to_dict") else dict(wb)
        p = None
        for k,v in vals.items():
            ks = str(k)
            if "Pr(" in ks or ks.lower() in {"p","pvalue","p-value","p_value"}:
                try:
                    p=float(v); break
                except Exception:
                    pass
        return {"status":"ok" if p is not None else "p_not_parsed","p":p,"raw":{str(k):str(v) for k,v in vals.items()}}
    except Exception as exc:
        return {"status":"failed","p":None,"error":f"{type(exc).__name__}: {exc}"}

specs = {
    "H1": {"formula":f"y_h1 ~ early_entry + {common} | {FE3}","param":"early_entry","weighted":True},
    "H2": {"formula":f"y_h2 ~ early_entry + {common} | {FE3}","param":"early_entry","weighted":True},
    "H4": {"formula":f"early_entry ~ z_pre3_network_entropy + {common_no_entropy} | {FE_H4}","param":"z_pre3_network_entropy","weighted":False},
    "H5": {"formula":f"y_h2 ~ early_entry * z_pre3_network_entropy + {common_no_entropy} | {FE3}","param":"early_entry:z_pre3_network_entropy","weighted":True},
}

results={}
for h,s in specs.items():
    results[h]={
        "cluster_inference":fit_inference(s["formula"],s["param"],df,weighted=s["weighted"]),
        "firm_wild_bootstrap_unweighted":wild_company(s["formula"],s["param"],df),
    }

# FE-structure stability for H5, now under the same inference menu.
h5_fe = {
    "threeway_primary":"topic_id + company_id + entry_year",
    "topic_year":"topic_id + entry_year",
    "topic_firm":"topic_id + company_id",
}
h5_stability={}
for name,fe in h5_fe.items():
    f=f"y_h2 ~ early_entry * z_pre3_network_entropy + {common_no_entropy} | {fe}"
    h5_stability[name]={
        "cluster_inference":fit_inference(f,"early_entry:z_pre3_network_entropy",df,weighted=True),
        "firm_wild_bootstrap_unweighted":wild_company(f,"early_entry:z_pre3_network_entropy",df),
    }

# Leave-one-firm-out H5 under primary weighted three-way FE and topic CRV1.
loo=[]
for firm in sorted(df.company_id.unique()):
    d=df[df.company_id!=firm].copy()
    f=specs["H5"]["formula"]
    try:
        fit=pf.feols(f,data=d,weights="overlap_weight",weights_type="aweights",vcov={"CRV1":"topic_id"},fixef_rm="singleton",collin_tol=1e-9)
        rr=extract(fit,"early_entry:z_pre3_network_entropy")
    except Exception as exc:
        rr={"status":"failed","error":f"{type(exc).__name__}: {exc}"}
    loo.append({"left_out_firm":firm,**rr})
loo_df=pd.DataFrame(loo)
loo_df.to_csv(OUT/"h5_leave_one_firm_out.csv",index=False)

identified_loo=loo_df[loo_df.status=="identified"].copy()
if len(identified_loo):
    loo_summary={
        "identified_runs":int(len(identified_loo)),
        "estimate_min":float(identified_loo.estimate.min()),
        "estimate_max":float(identified_loo.estimate.max()),
        "positive_share":float((identified_loo.estimate>0).mean()),
        "p_lt_005_share":float((identified_loo.p<0.05).mean()),
        "p_lt_010_share":float((identified_loo.p<0.10).mean()),
    }
else:
    loo_summary={"identified_runs":0}

# Classification is intentionally conservative: H5 cannot be called robust from one CRV1 p-value alone.
def classify_h5():
    prim=h5_stability["threeway_primary"]
    crv1=prim["cluster_inference"].get("topic_crv1",{})
    crv3=prim["cluster_inference"].get("topic_crv3",{})
    tw=prim["cluster_inference"].get("two_way_crv1",{})
    wb=prim["firm_wild_bootstrap_unweighted"]
    if crv1.get("status")!="identified": return "unresolved_not_identified"
    positive=crv1.get("estimate",0)>0
    conventional=crv1.get("p",1)<0.05
    robust_p=[]
    if crv3.get("status")=="identified": robust_p.append(crv3.get("p",1))
    if tw.get("status")=="identified": robust_p.append(tw.get("p",1))
    if wb.get("status")=="ok" and wb.get("p") is not None: robust_p.append(wb["p"])
    fe_pos=[]
    for name,x in h5_stability.items():
        rr=x["cluster_inference"].get("topic_crv1",{})
        if rr.get("status")=="identified": fe_pos.append(rr.get("estimate",0)>0)
    if positive and conventional and robust_p and max(robust_p)<0.10 and all(fe_pos) and loo_summary.get("positive_share",0)>=0.90:
        return "robust_positive_association"
    if positive and conventional and all(fe_pos) and loo_summary.get("positive_share",0)>=0.80:
        return "positive_but_inference_sensitive"
    if positive:
        return "positive_but_specification_sensitive"
    return "no_positive_signal"

summary={
    "status":"INFERENCE_HARDENING_COMPLETE",
    "package_version":getattr(pf,"__version__","unknown"),
    "frozen_panel":{"n":int(len(df)),"topics":int(df.topic_id.nunique()),"firms":int(df.company_id.nunique())},
    "results":results,
    "h5_fe_stability":h5_stability,
    "h5_leave_one_firm_out":loo_summary,
    "h5_classification":classify_h5(),
    "interpretation":"associational only; endogenous entry timing; H3 unchanged and not forced",
}
(OUT/"inference_hardening.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")

md=[]
md.append("# Corporate Science Entry — Inference Hardening")
md.append("")
md.append("This checkpoint changes inference implementation only. Frozen sample, treatment, outcomes, and H1–H5 are unchanged.")
md.append("")
md.append("## H1/H2/H4/H5 primary inference")
md.append("| H | Estimate | Topic CRV1 p | Topic CRV3 p | Two-way CRV1 p | Firm wild p |")
md.append("|---|---:|---:|---:|---:|---:|")
for h in ["H1","H2","H4","H5"]:
    x=results[h]
    c=x["cluster_inference"]
    a=c.get("topic_crv1",{}); b=c.get("topic_crv3",{}); d=c.get("two_way_crv1",{}); w=x["firm_wild_bootstrap_unweighted"]
    est=a.get("estimate")
    def fmt(v): return "NA" if v is None else f"{float(v):.4f}"
    md.append(f"| {h} | {fmt(est)} | {fmt(a.get('p'))} | {fmt(b.get('p'))} | {fmt(d.get('p'))} | {fmt(w.get('p'))} |")
md.append("")
md.append("## H5 stability")
for name,x in h5_stability.items():
    a=x["cluster_inference"].get("topic_crv1",{}); w=x["firm_wild_bootstrap_unweighted"]
    md.append(f"- {name}: estimate={a.get('estimate')}, topic-CRV1 p={a.get('p')}, firm-wild p={w.get('p')}, wild-status={w.get('status')}.")
md.append(f"- Leave-one-firm-out: `{json.dumps(loo_summary)}`")
md.append(f"- Conservative H5 classification: **{summary['h5_classification']}**.")
md.append("")
md.append("## Decision rule")
md.append("H5 is not labeled robust merely because the primary topic-CRV1 p-value is below 0.05. Robustness requires inference and FE-structure stability plus leave-one-firm-out sign stability. H1–H4 are interpreted under the same conservative discipline. H3 remains governed by its frozen support rule.")
(OUT/"INFERENCE_HARDENING.md").write_text("\n".join(md)+"\n",encoding="utf-8")
print(json.dumps(summary,indent=2))
