from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

OUT = Path("output_hypotheses")
OUT.mkdir(exist_ok=True)
PANEL = Path("input/primary_analysis_panel.csv")
RESEARCH = Path("input/company_research_year.parquet")
if not PANEL.exists() or not RESEARCH.exists():
    raise FileNotFoundError("Frozen design panel or company research mart missing")

np.random.seed(20260908)
df = pd.read_csv(PANEL)
r = pd.read_parquet(RESEARCH, columns=["canonical_company_id", "publication_year", "work_count"])
r = r.rename(columns={"canonical_company_id":"company_id", "publication_year":"yr"})
r["yr"] = r["yr"].astype(int)
r_lookup = {(str(a), int(y)): float(w) for a,y,w in r.itertuples(index=False, name=None)}

# Replicate the design-freeze episode slope exactly: [ln(1+y_-1)-ln(1+y_-3)]/2,
# treating absent firm-year rows as zero output.
def pretrend_slope(row):
    a = r_lookup.get((str(row.company_id), int(row.entry_year)-3), 0.0)
    b = r_lookup.get((str(row.company_id), int(row.entry_year)-1), 0.0)
    return (math.log1p(b)-math.log1p(a))/2.0

df["pretrend_slope"] = df.apply(pretrend_slope, axis=1)
df["sic2"] = df["sic"].astype(str).str.extract(r"(\d{2})", expand=False).fillna("UNK")
df["log_pre3_research_output"] = np.log1p(df["pre3_research_output"].fillna(0))
df["log_pre3_research_citations"] = np.log1p(df["pre3_research_citations"].fillna(0))
df["log_pre3_collab_works"] = np.log1p(df["pre3_collab_works"].fillna(0))
df["y_h1"] = np.log1p(df["post3_topic_output"].fillna(0))
df["y_h2"] = df["active_at_plus3"].astype(float)
df["y_h3"] = np.log1p(df["post3_field_year_norm_citation_ratio"])
df["y_h2_5"] = pd.to_numeric(df["active_at_plus5"], errors="coerce")

# Genuine pre-entry adjustment variables. Timing/maturity-at-entry variables are deliberately
# excluded because they are mechanically linked to relative entry timing and would over-control treatment.
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
    df["z_"+c] = (x-x.mean())/sd if sd > 0 else 0.0

# Regularized propensity model for overlap weighting. Industry is included; topic and entry-year
# are handled as fixed effects in outcome models rather than in the propensity score.
Xc = df[["z_"+c for c in adj]].to_numpy(float)
Xd = pd.get_dummies(df["sic2"], prefix="sic2", dtype=float)
X = np.column_stack([Xc, Xd.to_numpy(float)])
y = df["early_entry"].astype(int).to_numpy()
ps = LogisticRegression(C=1.0, max_iter=10000, solver="lbfgs").fit(X, y).predict_proba(X)[:,1]
ps = np.clip(ps, 0.03, 0.97)
df["propensity"] = ps
df["overlap_weight"] = np.where(y==1, 1-ps, ps)
df["overlap_weight"] /= df["overlap_weight"].mean()

def wmean(x,w):
    x=np.asarray(x,float); w=np.asarray(w,float)
    return float(np.sum(w*x)/np.sum(w)) if np.sum(w)>0 else None

def smd(a,b,wa=None,wb=None):
    a=np.asarray(a,float); b=np.asarray(b,float)
    if wa is None:
        ma,mb=float(np.mean(a)),float(np.mean(b)); va=float(np.var(a,ddof=1)); vb=float(np.var(b,ddof=1))
    else:
        wa=np.asarray(wa,float); wb=np.asarray(wb,float)
        ma,mb=wmean(a,wa),wmean(b,wb)
        va=float(np.sum(wa*(a-ma)**2)/np.sum(wa)); vb=float(np.sum(wb*(b-mb)**2)/np.sum(wb))
    den=math.sqrt(max((va+vb)/2,0))
    return 0.0 if den==0 else float((ma-mb)/den)

balance=[]
for c in adj:
    e=df[df.early_entry==1]; l=df[df.early_entry==0]
    balance.append({
        "covariate":c,
        "raw_smd":smd(e[c],l[c]),
        "weighted_smd":smd(e[c],l[c],e.overlap_weight,l.overlap_weight),
    })
pd.DataFrame(balance).to_csv(OUT/"overlap_balance.csv",index=False)

def ess(w):
    w=np.asarray(w,float); return float((w.sum()**2)/(w@w))

# Common fixed-effect adjustment. Entry-year FE is retained per the frozen design; topic and firm FE
# absorb stable field and firm heterogeneity. Network diversity remains a baseline control except where tested.
common = "z_log_pre3_research_output + z_log_pre3_research_citations + z_pretrend_slope + z_pre3_network_entropy + z_log_pre3_collab_works + z_pre3_network_observed"
fe = "C(topic_id) + C(company_id) + C(entry_year)"


def fit_wls(data, formula, param, weight="overlap_weight", cluster="topic_id"):
    d=data.dropna(subset=[param.split(':')[0] if ':' not in param else "early_entry"]).copy()
    m=smf.wls(formula, data=d, weights=d[weight]).fit(cov_type="cluster", cov_kwds={"groups":d[cluster],"use_correction":True})
    if param not in m.params.index:
        raise KeyError(f"Parameter {param} not identified")
    ci=m.conf_int().loc[param].tolist()
    return {"n":int(m.nobs),"estimate":float(m.params[param]),"se_topic_cluster":float(m.bse[param]),"p_topic_cluster":float(m.pvalues[param]),"ci95_topic_cluster":[float(ci[0]),float(ci[1])],"r2":float(getattr(m,"rsquared",np.nan))}, m


def wild_p(formula, data, param):
    try:
        from wildboottest.wildboottest import wildboottest
        model=smf.ols(formula, data=data)
        ans=wildboottest(model,param=param,cluster=data["company_id"],B=4999,bootstrap_type="31",seed=20260908)
        pcol=[c for c in ans.columns if "p" in str(c).lower()][-1]
        return float(ans.iloc[0][pcol])
    except Exception as exc:
        return None

results={}

# H1: early entry -> greater +1..+3 topic output.
f_h1=f"y_h1 ~ early_entry + {common} + {fe}"
r1,m1=fit_wls(df,f_h1,"early_entry")
r1["p_wild_firm"]=wild_p(f_h1,df,"early_entry")
results["H1"]=r1

# H2: early entry -> persistence at +3; +5 secondary where complete.
f_h2=f"y_h2 ~ early_entry + {common} + {fe}"
r2,m2=fit_wls(df,f_h2,"early_entry")
r2["p_wild_firm"]=wild_p(f_h2,df,"early_entry")
results["H2"]=r2

d5=df[df.y_h2_5.notna()].copy()
if len(d5)>=40 and d5.early_entry.nunique()==2:
    f_h25=f"y_h2_5 ~ early_entry + {common} + C(topic_id) + C(company_id) + C(entry_year)"
    try:
        results["H2_plus5_secondary"],_=fit_wls(d5,f_h25,"early_entry")
        results["H2_plus5_secondary"]["p_wild_firm"]=wild_p(f_h25,d5,"early_entry")
    except Exception as exc:
        results["H2_plus5_secondary"]={"status":"not_identified","error":str(exc),"n":len(d5)}

# H3: citation impact conditional on continued output. Restrict to topics with both exposure groups
# among rows with a defined field-year-normalized impact.
d3=df[df.y_h3.notna()].copy()
support=(d3.groupby("topic_id")["early_entry"].agg(["min","max","count"]))
support_topics=support[(support["min"]==0)&(support["max"]==1)].index
d3=d3[d3.topic_id.isin(support_topics)].copy()
if len(d3)>=30 and d3.topic_id.nunique()>=8 and d3.early_entry.nunique()==2:
    f_h3="y_h3 ~ early_entry + z_log_pre3_research_output + z_log_pre3_research_citations + z_pretrend_slope + z_pre3_network_entropy + z_log_pre3_collab_works + C(topic_id)"
    r3,m3=fit_wls(d3,f_h3,"early_entry")
    r3["p_wild_firm"]=wild_p(f_h3,d3,"early_entry")
    r3["conditional_on_continued_output"]=True
    r3["topics_with_within_topic_support"]=int(d3.topic_id.nunique())
    results["H3"]=r3
else:
    results["H3"]={"status":"insufficient_within_topic_support","n":int(len(d3)),"topics":int(d3.topic_id.nunique()),"conditional_on_continued_output":True}

# H4: pre-entry international network diversity -> earlier entry. Topic FE keeps the comparison
# within the same scientific domain. Collaboration volume and research capacity control scale.
f_h4="early_entry ~ z_pre3_network_entropy + z_log_pre3_research_output + z_log_pre3_research_citations + z_pretrend_slope + z_log_pre3_collab_works + z_pre3_network_observed + C(topic_id) + C(sic2)"
r4,m4=fit_wls(df.assign(unit_weight=1.0),f_h4,"z_pre3_network_entropy",weight="unit_weight")
r4["p_wild_firm"]=wild_p(f_h4,df,"z_pre3_network_entropy")
results["H4"]=r4

# H5: network diversity strengthens early-entry persistence advantage. Persistence +3 is primary;
# output is a secondary moderator outcome. Overlap weighting plus outcome regression is doubly adjusted.
f_h5=f"y_h2 ~ early_entry * z_pre3_network_entropy + z_log_pre3_research_output + z_log_pre3_research_citations + z_pretrend_slope + z_log_pre3_collab_works + z_pre3_network_observed + {fe}"
r5,m5=fit_wls(df,f_h5,"early_entry:z_pre3_network_entropy")
r5["p_wild_firm"]=wild_p(f_h5,df,"early_entry:z_pre3_network_entropy")
results["H5"]=r5
f_h5o=f"y_h1 ~ early_entry * z_pre3_network_entropy + z_log_pre3_research_output + z_log_pre3_research_citations + z_pretrend_slope + z_log_pre3_collab_works + z_pre3_network_observed + {fe}"
try:
    results["H5_output_secondary"],_=fit_wls(df,f_h5o,"early_entry:z_pre3_network_entropy")
    results["H5_output_secondary"]["p_wild_firm"]=wild_p(f_h5o,df,"early_entry:z_pre3_network_entropy")
except Exception as exc:
    results["H5_output_secondary"]={"status":"not_identified","error":str(exc)}

# Within-topic nearest-neighbor propensity matching with replacement as mandatory robustness.
pairs=[]
for _,er in df[df.early_entry==1].iterrows():
    cand=df[(df.topic_id==er.topic_id)&(df.early_entry==0)]
    if cand.empty: continue
    j=(cand.propensity-er.propensity).abs().idxmin()
    lr=df.loc[j]
    pairs.append({"topic_id":er.topic_id,"early_company":er.company_id,"later_company":lr.company_id,"ps_distance":abs(er.propensity-lr.propensity),"h1_diff":er.y_h1-lr.y_h1,"h2_diff":er.y_h2-lr.y_h2})
match=pd.DataFrame(pairs)
match.to_csv(OUT/"within_topic_matches.csv",index=False)
matching={"pairs":int(len(match)),"median_ps_distance":float(match.ps_distance.median()) if len(match) else None,"mean_h1_diff":float(match.h1_diff.mean()) if len(match) else None,"mean_h2_diff":float(match.h2_diff.mean()) if len(match) else None}

# Leave-one-firm-out robustness for H1/H2 treatment coefficient.
loo=[]
for firm in sorted(df.company_id.unique()):
    d=df[df.company_id!=firm].copy()
    for hyp,formula in [("H1",f_h1),("H2",f_h2)]:
        try:
            rr,_=fit_wls(d,formula,"early_entry")
            loo.append({"left_out_firm":firm,"hypothesis":hyp,"estimate":rr["estimate"],"p_topic_cluster":rr["p_topic_cluster"],"n":rr["n"]})
        except Exception:
            pass
pd.DataFrame(loo).to_csv(OUT/"leave_one_firm_out.csv",index=False)

# Benjamini-Hochberg across the five primary hypothesis p-values that are estimable.
primary=[]
for h in ["H1","H2","H3","H4","H5"]:
    if "p_topic_cluster" in results.get(h,{}): primary.append((h,results[h]["p_topic_cluster"]))
if primary:
    order=sorted(range(len(primary)),key=lambda i:primary[i][1])
    m=len(primary); q=[None]*m; prev=1.0
    for rank_rev,i in enumerate(reversed(order),start=1):
        rank=m-rank_rev+1
        val=min(prev,primary[i][1]*m/rank); q[i]=val; prev=val
    for (h,_),qq in zip(primary,q): results[h]["bh_q_primary5"]=float(qq)

# Compact interpretation labels without causal language.
for h in ["H1","H2","H3","H4","H5"]:
    rr=results.get(h,{})
    if "estimate" not in rr:
        rr["evidence_label"]="not_estimable"
        continue
    p=rr.get("p_topic_cluster",1.0); qv=rr.get("bh_q_primary5",1.0); est=rr["estimate"]
    if est>0 and p<0.05 and qv<0.10: lab="positive_adjusted_association"
    elif est>0 and p<0.10: lab="positive_directional_signal"
    else: lab="no_positive_adjusted_signal"
    rr["evidence_label"]=lab

summary={
    "analysis_status":"COMPLETE",
    "estimand_language":"associational; endogenous relative entry; no causal claim",
    "frozen_panel":{"episodes":int(len(df)),"topics":int(df.topic_id.nunique()),"firms":int(df.company_id.nunique()),"early":int(df.early_entry.sum()),"later":int((1-df.early_entry).sum())},
    "overlap_weighting":{"propensity_min":float(df.propensity.min()),"propensity_max":float(df.propensity.max()),"ess":ess(df.overlap_weight),"max_abs_weighted_smd":float(max(abs(x["weighted_smd"]) for x in balance))},
    "matching":matching,
    "results":results,
}
(OUT/"hypothesis_results.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
df.to_csv(OUT/"analysis_panel_with_weights.csv",index=False)

md=[]
md.append("# Corporate Science Entry — Frozen H1–H5 Analysis")
md.append("")
md.append("This analysis uses the design-frozen primary panel. All estimates are associational because relative corporate entry timing is endogenous.")
md.append("")
md.append("## Selection adjustment")
md.append(f"- Frozen episodes: **{len(df)}**; topics: **{df.topic_id.nunique()}**; firms: **{df.company_id.nunique()}**.")
md.append(f"- Overlap-weight ESS: **{ess(df.overlap_weight):.1f}**.")
md.append(f"- Maximum absolute weighted SMD across genuine pre-entry adjustment covariates: **{max(abs(x['weighted_smd']) for x in balance):.3f}**.")
md.append(f"- Within-topic propensity matches: **{matching['pairs']}**.")
md.append("")
md.append("## Primary hypothesis estimates")
md.append("")
md.append("| Hypothesis | Primary coefficient | Estimate | Topic-cluster p | Firm wild-bootstrap p | BH q | Evidence label |")
md.append("|---|---|---:|---:|---:|---:|---|")
labels={"H1":"Early entry → +1..+3 output","H2":"Early entry → active at +3","H3":"Early entry → normalized impact","H4":"Network entropy → early entry","H5":"Early × network entropy → +3 persistence"}
for h in ["H1","H2","H3","H4","H5"]:
    rr=results[h]
    if "estimate" in rr:
        wb="NA" if rr.get("p_wild_firm") is None else f"{rr['p_wild_firm']:.4f}"
        qq="NA" if rr.get("bh_q_primary5") is None else f"{rr['bh_q_primary5']:.4f}"
        md.append(f"| {h}: {labels[h]} | {'early_entry' if h in ['H1','H2','H3'] else ('z_entropy' if h=='H4' else 'early×entropy')} | {rr['estimate']:.4f} | {rr['p_topic_cluster']:.4f} | {wb} | {qq} | {rr['evidence_label']} |")
    else:
        md.append(f"| {h}: {labels[h]} | — | — | — | — | — | {rr.get('evidence_label','not_estimable')} |")
md.append("")
md.append("## Robustness")
md.append(f"- Matched mean H1 log-output difference (early − later): **{matching['mean_h1_diff'] if matching['mean_h1_diff'] is not None else 'NA'}**.")
md.append(f"- Matched mean H2 persistence difference: **{matching['mean_h2_diff'] if matching['mean_h2_diff'] is not None else 'NA'}**.")
if "H2_plus5_secondary" in results: md.append(f"- +5 persistence secondary: `{json.dumps(results['H2_plus5_secondary'])}`")
if "H5_output_secondary" in results: md.append(f"- H5 output moderation secondary: `{json.dumps(results['H5_output_secondary'])}`")
md.append("")
md.append("## Interpretation discipline")
md.append("- Timing/maturity-at-entry variables were not used in the primary propensity adjustment because they are mechanically linked to the treatment definition.")
md.append("- H3 is conditional on continued output and is only interpreted if adequate within-topic support remains.")
md.append("- Topic-clustered uncertainty is primary; firm-level wild-cluster bootstrap p-values are reported where the implementation is available.")
md.append("- Matching and leave-one-firm-out files are retained for hostile-reviewer robustness checks.")
(OUT/"HYPOTHESIS_ANALYSIS.md").write_text("\n".join(md)+"\n",encoding="utf-8")
print(json.dumps(summary,indent=2))
