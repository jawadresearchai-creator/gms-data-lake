from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import duckdb

OUT = Path("output_design")
OUT.mkdir(exist_ok=True)

FILES = {
    "global_topic": "input/work_year_topic.parquet",
    "company_topic": "input/company_topic_year.parquet",
    "company_collab": "input/company_collaboration_year.parquet",
    "company_research": "input/company_research_year.parquet",
    "company_citation": "input/company_citation_year.parquet",
    "issuer": "input/sec_issuer_metadata.parquet",
}
for name, path in FILES.items():
    if not Path(path).exists():
        raise FileNotFoundError(f"Missing {name}: {path}")


def qp(path: str) -> str:
    return path.replace("'", "''")


def mean(xs):
    xs = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return sum(xs) / len(xs) if xs else None


def variance(xs):
    xs = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def smd(a, b):
    a = [float(x) for x in a if x is not None and math.isfinite(float(x))]
    b = [float(x) for x in b if x is not None and math.isfinite(float(x))]
    if not a or not b:
        return None
    ma, mb = mean(a), mean(b)
    va, vb = variance(a), variance(b)
    if va is None or vb is None:
        return None
    pooled = math.sqrt(max((va + vb) / 2.0, 0.0))
    if pooled == 0:
        return 0.0 if ma == mb else None
    return (ma - mb) / pooled


con = duckdb.connect()
con.execute("PRAGMA threads=4")

con.execute(f"""
CREATE VIEW g AS
SELECT CAST(publication_year AS INTEGER) AS yr,
       CAST(topic_id AS VARCHAR) AS topic_id,
       CAST(work_count AS DOUBLE) AS work_count,
       CAST(citation_sum AS DOUBLE) AS citation_sum,
       CAST(mean_citations AS DOUBLE) AS mean_citations,
       CAST(topic_score_sum AS DOUBLE) AS topic_score_sum
FROM read_parquet('{qp(FILES['global_topic'])}')
WHERE publication_year BETWEEN 1900 AND 2026
""")
con.execute(f"""
CREATE VIEW t AS
SELECT CAST(canonical_company_id AS VARCHAR) AS company_id,
       CAST(openalex_institution_id AS VARCHAR) AS openalex_institution_id,
       CAST(publication_year AS INTEGER) AS yr,
       CAST(topic_id AS VARCHAR) AS topic_id,
       CAST(work_count AS DOUBLE) AS work_count,
       CAST(citation_sum AS DOUBLE) AS citation_sum,
       CAST(topic_score_sum AS DOUBLE) AS topic_score_sum
FROM read_parquet('{qp(FILES['company_topic'])}')
WHERE publication_year BETWEEN 1900 AND 2026
""")
con.execute(f"""
CREATE VIEW c AS
SELECT CAST(canonical_company_id AS VARCHAR) AS company_id,
       CAST(publication_year AS INTEGER) AS yr,
       CAST(collaborator_country_code AS VARCHAR) AS country,
       CAST(collaborative_work_count AS DOUBLE) AS collaborative_work_count,
       CAST(collaborator_institution_count AS DOUBLE) AS collaborator_institution_count,
       CAST(citation_sum AS DOUBLE) AS citation_sum
FROM read_parquet('{qp(FILES['company_collab'])}')
WHERE publication_year BETWEEN 1900 AND 2026
""")
con.execute(f"""
CREATE VIEW r AS
SELECT CAST(canonical_company_id AS VARCHAR) AS company_id,
       CAST(company_name AS VARCHAR) AS company_name,
       CAST(primary_ticker AS VARCHAR) AS primary_ticker,
       CAST(publication_year AS INTEGER) AS yr,
       CAST(work_count AS DOUBLE) AS work_count,
       CAST(citation_sum AS DOUBLE) AS citation_sum,
       CAST(mean_citations AS DOUBLE) AS mean_citations
FROM read_parquet('{qp(FILES['company_research'])}')
WHERE publication_year BETWEEN 1900 AND 2026
""")
con.execute(f"""
CREATE VIEW ci AS
SELECT CAST(canonical_company_id AS VARCHAR) AS company_id,
       CAST(publication_year AS INTEGER) AS yr,
       CAST(work_count AS DOUBLE) AS work_count,
       CAST(citation_sum AS DOUBLE) AS citation_sum,
       CAST(citations_per_work AS DOUBLE) AS citations_per_work
FROM read_parquet('{qp(FILES['company_citation'])}')
WHERE publication_year BETWEEN 1900 AND 2026
""")
con.execute(f"""
CREATE VIEW issuer AS
SELECT CAST(canonical_company_id AS VARCHAR) AS company_id,
       CAST(sic AS VARCHAR) AS sic,
       CAST(sic_description AS VARCHAR) AS sic_description,
       CAST(category AS VARCHAR) AS sec_category,
       CAST(business_country AS VARCHAR) AS business_country,
       CAST(business_state_or_country AS VARCHAR) AS business_state_or_country
FROM read_parquet('{qp(FILES['issuer'])}')
""")

# Stable company metadata.
con.execute("""
CREATE TEMP TABLE company_meta AS
SELECT r.company_id,
       ANY_VALUE(r.company_name) AS company_name,
       ANY_VALUE(r.primary_ticker) AS primary_ticker,
       ANY_VALUE(i.sic) AS sic,
       ANY_VALUE(i.sic_description) AS sic_description,
       ANY_VALUE(i.sec_category) AS sec_category,
       ANY_VALUE(i.business_country) AS business_country,
       ANY_VALUE(i.business_state_or_country) AS business_state_or_country
FROM r
LEFT JOIN issuer i USING(company_id)
GROUP BY r.company_id
""")

# First observed corporate participation per firm-topic; stop at 2025 to avoid partial 2026 as an entry year.
con.execute("""
CREATE TEMP TABLE firm_entry AS
SELECT company_id, topic_id, MIN(yr) AS entry_year
FROM t
WHERE work_count > 0 AND yr <= 2025
GROUP BY company_id, topic_id
""")
con.execute("""
CREATE TEMP TABLE frontier AS
SELECT topic_id, MIN(entry_year) AS corp_first_year,
       COUNT(DISTINCT company_id) AS n_linked_firms
FROM firm_entry
GROUP BY topic_id
""")

# Consecutive-year global topic scale diagnostics. Missing calendar years do not count as persistence.
con.execute("""
CREATE TEMP TABLE gseq AS
SELECT topic_id, yr, work_count, citation_sum, mean_citations,
       LAG(work_count,1) OVER(PARTITION BY topic_id ORDER BY yr) AS prev_wc,
       LAG(yr,1) OVER(PARTITION BY topic_id ORDER BY yr) AS prev_yr,
       LEAD(work_count,1) OVER(PARTITION BY topic_id ORDER BY yr) AS next1_wc,
       LEAD(yr,1) OVER(PARTITION BY topic_id ORDER BY yr) AS next1_yr,
       LEAD(work_count,2) OVER(PARTITION BY topic_id ORDER BY yr) AS next2_wc,
       LEAD(yr,2) OVER(PARTITION BY topic_id ORDER BY yr) AS next2_yr,
       AVG(work_count) OVER(PARTITION BY topic_id ORDER BY yr ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS prior3_avg
FROM g
""")

SPEC_SQL = {
    "once100": "work_count>=100",
    "p2_100": "work_count>=100 AND next1_yr=yr+1 AND next1_wc>=100",
    "p3_100": "work_count>=100 AND next1_yr=yr+1 AND next1_wc>=100 AND next2_yr=yr+2 AND next2_wc>=100",
    "p2_50": "work_count>=50 AND next1_yr=yr+1 AND next1_wc>=50",
    "p2_250": "work_count>=250 AND next1_yr=yr+1 AND next1_wc>=250",
}

for spec, pred in SPEC_SQL.items():
    con.execute(f"""
    CREATE TEMP TABLE em_{spec} AS
    SELECT topic_id, MIN(yr) AS emergence_year
    FROM gseq
    WHERE {pred}
    GROUP BY topic_id
    """)

# Reusable pre-entry and post-entry feature components will be built per candidate design.
def build_panel(spec: str, early_window: int, table_name: str):
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE base AS
    SELECT fe.company_id, fe.topic_id, fe.entry_year,
           em.emergence_year, fr.corp_first_year, fr.n_linked_firms,
           fe.entry_year-fr.corp_first_year AS relative_entry_lag,
           fr.corp_first_year-em.emergence_year AS frontier_lag_from_emergence,
           CASE WHEN fe.entry_year-fr.corp_first_year <= {early_window} THEN 1 ELSE 0 END AS early_entry
    FROM firm_entry fe
    JOIN frontier fr USING(topic_id)
    JOIN em_{spec} em USING(topic_id)
    WHERE em.emergence_year BETWEEN 1990 AND 2021
      AND fr.corp_first_year BETWEEN 1990 AND 2021
      AND fr.n_linked_firms >= 2
      AND fe.entry_year <= 2022
    """)
    # Keep only topics with both early and later corporate entrants in the outcome-complete sample.
    con.execute("""
    CREATE OR REPLACE TEMP TABLE comp_topics AS
    SELECT topic_id
    FROM base
    GROUP BY topic_id
    HAVING SUM(CASE WHEN early_entry=1 THEN 1 ELSE 0 END)>=1
       AND SUM(CASE WHEN early_entry=0 THEN 1 ELSE 0 END)>=1
    """)
    con.execute("""
    CREATE OR REPLACE TEMP TABLE b AS
    SELECT x.* FROM base x JOIN comp_topics USING(topic_id)
    """)

    con.execute("""
    CREATE OR REPLACE TEMP TABLE net_country AS
    SELECT b.company_id,b.topic_id,c.country,
           SUM(c.collaborative_work_count) AS collab_works,
           SUM(c.collaborator_institution_count) AS collaborator_institution_sum
    FROM b JOIN c
      ON c.company_id=b.company_id AND c.yr BETWEEN b.entry_year-3 AND b.entry_year-1
    WHERE c.country IS NOT NULL
    GROUP BY b.company_id,b.topic_id,c.country
    """)
    con.execute("""
    CREATE OR REPLACE TEMP TABLE net_tot AS
    SELECT company_id,topic_id,
           COUNT(*) AS pre3_collab_countries,
           SUM(collab_works) AS pre3_collab_works,
           SUM(collaborator_institution_sum) AS pre3_collaborator_institution_sum,
           SUM(collab_works*collab_works) AS sumsq,
           SUM(collab_works) AS totalw
    FROM net_country
    GROUP BY company_id,topic_id
    """)
    con.execute("""
    CREATE OR REPLACE TEMP TABLE net_entropy AS
    SELECT n.company_id,n.topic_id,
           -SUM(CASE WHEN nt.totalw>0 AND n.collab_works>0
                     THEN (n.collab_works/nt.totalw)*LN(n.collab_works/nt.totalw)
                     ELSE 0 END) AS pre3_network_entropy
    FROM net_country n JOIN net_tot nt USING(company_id,topic_id)
    GROUP BY n.company_id,n.topic_id
    """)
    con.execute("""
    CREATE OR REPLACE TEMP TABLE net AS
    SELECT nt.company_id,nt.topic_id,nt.pre3_collab_countries,nt.pre3_collab_works,
           nt.pre3_collaborator_institution_sum,
           CASE WHEN nt.totalw>0 THEN 1.0-nt.sumsq/(nt.totalw*nt.totalw) ELSE 0 END AS pre3_network_hhi_complement,
           COALESCE(ne.pre3_network_entropy,0) AS pre3_network_entropy
    FROM net_tot nt LEFT JOIN net_entropy ne USING(company_id,topic_id)
    """)

    # Company-wide prior scientific capacity: absent annual rows are treated as zero output for that year.
    con.execute("""
    CREATE OR REPLACE TEMP TABLE pre_research AS
    SELECT b.company_id,b.topic_id,
           SUM(COALESCE(r.work_count,0)) AS pre3_research_output,
           SUM(COALESCE(r.citation_sum,0)) AS pre3_research_citations,
           COUNT(r.yr) AS pre3_research_observed_years
    FROM b
    CROSS JOIN (VALUES (-3),(-2),(-1)) off(k)
    LEFT JOIN r ON r.company_id=b.company_id AND r.yr=b.entry_year+off.k
    GROUP BY b.company_id,b.topic_id
    """)

    con.execute("""
    CREATE OR REPLACE TEMP TABLE entry_topic AS
    SELECT b.company_id,b.topic_id,
           COALESCE(t.work_count,0) AS entry_topic_output,
           COALESCE(t.citation_sum,0) AS entry_topic_citations
    FROM b LEFT JOIN t
      ON t.company_id=b.company_id AND t.topic_id=b.topic_id AND t.yr=b.entry_year
    """)

    con.execute("""
    CREATE OR REPLACE TEMP TABLE post3 AS
    SELECT b.company_id,b.topic_id,
           SUM(COALESCE(t.work_count,0)) AS post3_topic_output,
           SUM(COALESCE(t.citation_sum,0)) AS post3_topic_citations,
           COUNT(t.yr) AS post3_active_years,
           MAX(CASE WHEN t.yr=b.entry_year+3 AND t.work_count>0 THEN 1 ELSE 0 END) AS active_at_plus3,
           SUM(CASE WHEN t.work_count>0 AND g.mean_citations>0
                    THEN t.work_count*((t.citation_sum/t.work_count)/g.mean_citations)
                    ELSE 0 END)
             / NULLIF(SUM(CASE WHEN t.work_count>0 AND g.mean_citations>0 THEN t.work_count ELSE 0 END),0)
             AS post3_field_year_norm_citation_ratio
    FROM b
    CROSS JOIN (VALUES (1),(2),(3)) off(k)
    LEFT JOIN t ON t.company_id=b.company_id AND t.topic_id=b.topic_id AND t.yr=b.entry_year+off.k
    LEFT JOIN g ON g.topic_id=b.topic_id AND g.yr=b.entry_year+off.k
    GROUP BY b.company_id,b.topic_id
    """)

    con.execute("""
    CREATE OR REPLACE TEMP TABLE post5 AS
    SELECT b.company_id,b.topic_id,
           CASE WHEN b.entry_year<=2020 THEN SUM(COALESCE(t.work_count,0)) ELSE NULL END AS post5_topic_output,
           CASE WHEN b.entry_year<=2020 THEN MAX(CASE WHEN t.yr=b.entry_year+5 AND t.work_count>0 THEN 1 ELSE 0 END) ELSE NULL END AS active_at_plus5
    FROM b
    CROSS JOIN (VALUES (1),(2),(3),(4),(5)) off(k)
    LEFT JOIN t ON t.company_id=b.company_id AND t.topic_id=b.topic_id AND t.yr=b.entry_year+off.k
    GROUP BY b.company_id,b.topic_id,b.entry_year
    """)

    con.execute("""
    CREATE OR REPLACE TEMP TABLE field_features AS
    SELECT b.company_id,b.topic_id,
           COALESCE(gs.work_count,0) AS global_work_count_at_entry,
           COALESCE(gs.mean_citations,0) AS global_mean_citations_at_entry,
           COALESCE(gs.prior3_avg,0) AS global_prior3_avg_at_entry,
           CASE WHEN gs.prev_yr=b.entry_year-1 AND gs.prev_wc>0
                THEN (gs.work_count-gs.prev_wc)/gs.prev_wc ELSE NULL END AS global_yoy_growth_at_entry,
           b.entry_year-b.emergence_year AS field_age_at_entry
    FROM b LEFT JOIN gseq gs ON gs.topic_id=b.topic_id AND gs.yr=b.entry_year
    """)

    con.execute(f"""
    CREATE OR REPLACE TABLE {table_name} AS
    SELECT b.*,
           cm.company_name,cm.primary_ticker,cm.sic,cm.sic_description,cm.sec_category,
           cm.business_country,cm.business_state_or_country,
           COALESCE(n.pre3_collab_countries,0) AS pre3_collab_countries,
           COALESCE(n.pre3_collab_works,0) AS pre3_collab_works,
           COALESCE(n.pre3_collaborator_institution_sum,0) AS pre3_collaborator_institution_sum,
           COALESCE(n.pre3_network_hhi_complement,0) AS pre3_network_hhi_complement,
           COALESCE(n.pre3_network_entropy,0) AS pre3_network_entropy,
           CASE WHEN n.company_id IS NOT NULL THEN 1 ELSE 0 END AS pre3_network_observed,
           pr.pre3_research_output,pr.pre3_research_citations,pr.pre3_research_observed_years,
           et.entry_topic_output,et.entry_topic_citations,
           p3.post3_topic_output,p3.post3_topic_citations,p3.post3_active_years,p3.active_at_plus3,
           p3.post3_field_year_norm_citation_ratio,
           p5.post5_topic_output,p5.active_at_plus5,
           ff.global_work_count_at_entry,ff.global_mean_citations_at_entry,ff.global_prior3_avg_at_entry,
           ff.global_yoy_growth_at_entry,ff.field_age_at_entry
    FROM b
    LEFT JOIN company_meta cm USING(company_id)
    LEFT JOIN net n USING(company_id,topic_id)
    LEFT JOIN pre_research pr USING(company_id,topic_id)
    LEFT JOIN entry_topic et USING(company_id,topic_id)
    LEFT JOIN post3 p3 USING(company_id,topic_id)
    LEFT JOIN post5 p5 USING(company_id,topic_id)
    LEFT JOIN field_features ff USING(company_id,topic_id)
    """)


def summarize_panel(table_name: str):
    row = con.execute(f"""
    SELECT COUNT(*) AS episodes,COUNT(DISTINCT topic_id) AS topics,COUNT(DISTINCT company_id) AS firms,
           SUM(early_entry) AS early_n,SUM(1-early_entry) AS later_n,
           SUM(pre3_network_observed) AS network_observed,
           SUM(CASE WHEN sic IS NOT NULL AND sic<>'' THEN 1 ELSE 0 END) AS sic_n,
           SUM(CASE WHEN post3_field_year_norm_citation_ratio IS NOT NULL THEN 1 ELSE 0 END) AS norm_cite_n
    FROM {table_name}
    """).fetchone()
    episodes,topics,firms,early,later,network,sic_n,norm_cite_n = [int(x or 0) for x in row]
    return {
        "episodes":episodes,"topics":topics,"firms":firms,"early":early,"later":later,
        "early_late_balance":round(min(early,later)/max(early,later),4) if max(early,later) else 0,
        "network_observed_pct":round(100*network/episodes,2) if episodes else 0,
        "sic_coverage_pct":round(100*sic_n/episodes,2) if episodes else 0,
        "normalized_citation_outcome_pct":round(100*norm_cite_n/episodes,2) if episodes else 0,
    }

# Sensitivity grid on objective global-emergence definitions and corporate-relative entry windows.
grid=[]
for spec in SPEC_SQL:
    for early_window in [0,1,2,3]:
        tbl=f"p_{spec}_w{early_window}"
        build_panel(spec,early_window,tbl)
        s=summarize_panel(tbl)
        passed=(s["topics"]>=50 and s["episodes"]>=150 and s["firms"]>=15 and
                s["early"]>=50 and s["later"]>=50 and s["network_observed_pct"]>=90)
        grid.append({"emergence_spec":spec,"early_window":early_window,**s,"passes_gate":passed})

# Primary specification is fixed before looking at H1-H5 outcomes:
# two consecutive years >=100 global works; emergence 1990-2021; corporate-relative entry 0-2 years.
PRIMARY_SPEC="p2_100"
PRIMARY_WINDOW=2
PRIMARY_TABLE=f"p_{PRIMARY_SPEC}_w{PRIMARY_WINDOW}"
primary_summary=next(x for x in grid if x["emergence_spec"]==PRIMARY_SPEC and x["early_window"]==PRIMARY_WINDOW)
freeze_pass=bool(primary_summary["passes_gate"])

# Save sensitivity grid.
with (OUT/"design_sensitivity_grid.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(grid[0].keys()));w.writeheader();w.writerows(grid)
(OUT/"design_sensitivity_grid.json").write_text(json.dumps(grid,indent=2),encoding="utf-8")

# Primary panel and diagnostics are written even if gate fails, but are explicitly marked provisional.
con.execute(f"COPY (SELECT * FROM {PRIMARY_TABLE} ORDER BY topic_id,entry_year,company_id) TO 'output_design/primary_analysis_panel.parquet' (FORMAT PARQUET)")
con.execute(f"COPY (SELECT * FROM {PRIMARY_TABLE} ORDER BY topic_id,entry_year,company_id) TO 'output_design/primary_analysis_panel.csv' (HEADER,DELIMITER ',')")

# Firm and topic concentration.
firm_rows=con.execute(f"""
SELECT company_id,ANY_VALUE(company_name) AS company_name,COUNT(*) AS episodes,
       COUNT(DISTINCT topic_id) AS topics,SUM(early_entry) AS early,SUM(1-early_entry) AS later
FROM {PRIMARY_TABLE} GROUP BY company_id ORDER BY episodes DESC
""").fetchall()
firm_total=sum(int(x[2]) for x in firm_rows) or 1
firm_hhi=sum((int(x[2])/firm_total)**2 for x in firm_rows)
with (OUT/"firm_concentration.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.writer(f);w.writerow(["company_id","company_name","episodes","topics","early","later","episode_share"])
    for row in firm_rows:
        w.writerow([*row,round(int(row[2])/firm_total,6)])

topic_rows=con.execute(f"""
SELECT topic_id,COUNT(*) AS episodes,COUNT(DISTINCT company_id) AS firms,
       SUM(early_entry) AS early,SUM(1-early_entry) AS later,
       MIN(emergence_year) AS emergence_year,MIN(corp_first_year) AS corp_first_year
FROM {PRIMARY_TABLE} GROUP BY topic_id ORDER BY episodes DESC,topic_id
""").fetchall()
with (OUT/"topic_concentration.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.writer(f);w.writerow(["topic_id","episodes","firms","early","later","emergence_year","corp_first_year"]);w.writerows(topic_rows)

# Pre-entry company-wide output trajectories at -3,-2,-1.
pretrend = []
for off in [-3,-2,-1]:
    rows=con.execute(f"""
    SELECT p.early_entry,COALESCE(r.work_count,0) AS output
    FROM {PRIMARY_TABLE} p
    LEFT JOIN r ON r.company_id=p.company_id AND r.yr=p.entry_year+({off})
    """).fetchall()
    early=[math.log1p(float(v)) for e,v in rows if int(e)==1]
    later=[math.log1p(float(v)) for e,v in rows if int(e)==0]
    pretrend.append({"relative_year":off,"early_mean_log1p_output":mean(early),"later_mean_log1p_output":mean(later),"smd_log1p_output":smd(early,later),"early_n":len(early),"later_n":len(later)})

# Episode-level pretrend slope from -3 to -1.
slope_rows=con.execute(f"""
SELECT p.early_entry,
       LN(1+COALESCE(r1.work_count,0))-LN(1+COALESCE(r3.work_count,0)) AS two_year_change_log1p
FROM {PRIMARY_TABLE} p
LEFT JOIN r r3 ON r3.company_id=p.company_id AND r3.yr=p.entry_year-3
LEFT JOIN r r1 ON r1.company_id=p.company_id AND r1.yr=p.entry_year-1
""").fetchall()
e_slope=[float(v)/2 for e,v in slope_rows if int(e)==1]
l_slope=[float(v)/2 for e,v in slope_rows if int(e)==0]
slope_diag={"early_mean_annualized_log_slope":mean(e_slope),"later_mean_annualized_log_slope":mean(l_slope),"smd_slope":smd(e_slope,l_slope)}

with (OUT/"pretrend_diagnostics.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(pretrend[0].keys()));w.writeheader();w.writerows(pretrend)

# Baseline standardized mean differences. These are design diagnostics, not hypothesis tests.
cols={
    "log1p_pre3_research_output":"LN(1+pre3_research_output)",
    "log1p_pre3_research_citations":"LN(1+pre3_research_citations)",
    "pre3_collab_countries":"pre3_collab_countries",
    "pre3_network_hhi_complement":"pre3_network_hhi_complement",
    "pre3_network_entropy":"pre3_network_entropy",
    "field_age_at_entry":"field_age_at_entry",
    "frontier_lag_from_emergence":"frontier_lag_from_emergence",
    "log1p_global_work_count_at_entry":"LN(1+global_work_count_at_entry)",
    "global_yoy_growth_at_entry":"global_yoy_growth_at_entry",
    "log1p_entry_topic_output":"LN(1+entry_topic_output)",
}
balance=[]
for name,expr in cols.items():
    rows=con.execute(f"SELECT early_entry,{expr} AS v FROM {PRIMARY_TABLE}").fetchall()
    a=[float(v) for e,v in rows if int(e)==1 and v is not None and math.isfinite(float(v))]
    b=[float(v) for e,v in rows if int(e)==0 and v is not None and math.isfinite(float(v))]
    balance.append({"covariate":name,"early_mean":mean(a),"later_mean":mean(b),"smd":smd(a,b),"early_n":len(a),"later_n":len(b)})
with (OUT/"baseline_balance.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(balance[0].keys()));w.writeheader();w.writerows(balance)

max_abs_smd=max(abs(x["smd"]) for x in balance if x["smd"] is not None) if balance else None
pretrend_max_abs=max(abs(x["smd_log1p_output"]) for x in pretrend if x["smd_log1p_output"] is not None) if pretrend else None
selection_flag=(max_abs_smd is not None and max_abs_smd>0.25) or (pretrend_max_abs is not None and pretrend_max_abs>0.25)

report={
    "generated_at_utc":datetime.now(timezone.utc).isoformat(),
    "freeze_status":"PASS" if freeze_pass else "FAIL",
    "research_question":"Among objectively emerging scientific topics, do firms that enter earlier relative to the corporate adoption frontier develop more persistent scientific advantage, and is this relationship conditioned by pre-entry international scientific-network diversity?",
    "primary_design":{
        "emergence_spec":"first year in 1990-2021 with >=100 global works and >=100 again in the immediately following calendar year",
        "emergence_spec_code":PRIMARY_SPEC,
        "corporate_frontier":"first observed linked-firm entry into the qualifying topic, restricted to frontier years 1990-2021",
        "early_entry":"firm entry within 0-2 years of the corporate frontier",
        "later_entry":"firm entry more than 2 years after the corporate frontier",
        "latest_entry_year_primary":2022,
        "outcome_years_latest":2025,
        "partial_2026_excluded":True,
        "estimand_language":"associational first-mover advantage; no causal claim without stronger identification",
    },
    "primary_summary":primary_summary,
    "firm_episode_hhi":firm_hhi,
    "top_firm_share":round(int(firm_rows[0][2])/firm_total,4) if firm_rows else None,
    "top_two_firm_share":round(sum(int(x[2]) for x in firm_rows[:2])/firm_total,4) if firm_rows else None,
    "max_abs_baseline_smd":max_abs_smd,
    "max_abs_pretrend_smd":pretrend_max_abs,
    "pretrend_slope":slope_diag,
    "selection_adjustment_required":selection_flag,
    "sensitivity_grid":grid,
    "gate_criteria":{"topics_min":50,"episodes_min":150,"firms_min":15,"early_min":50,"later_min":50,"network_observed_pct_min":90},
}
(OUT/"design_freeze.json").write_text(json.dumps(report,indent=2),encoding="utf-8")

md=[]
md.append("# Corporate Science Entry Timing — Design Freeze")
md.append("")
md.append(f"Generated: `{report['generated_at_utc']}`")
md.append("")
md.append(f"## Freeze status: **{report['freeze_status']}**")
md.append("")
md.append("## Frozen research question")
md.append("")
md.append(report["research_question"])
md.append("")
md.append("## Primary construct definitions")
md.append("")
md.append("- **Objectively emerging scientific topic:** first reaches at least 100 global OpenAlex works in a year during 1990–2021 and remains at or above 100 in the immediately following calendar year. This persistence rule prevents a one-year spike from defining emergence.")
md.append("- **Corporate adoption frontier:** first observed entry by any production-linked firm into that qualifying topic, restricted to 1990–2021.")
md.append("- **Early corporate entrant:** enters within 0–2 years of the corporate adoption frontier.")
md.append("- **Later entrant:** enters more than 2 years after the corporate adoption frontier.")
md.append("- **Primary outcome-complete sample:** firm entry no later than 2022, so the three-year post-entry window ends by 2025. Calendar year 2026 is excluded from primary follow-up because it is incomplete as of 8 September 2026.")
md.append("")
md.append("## Primary sample")
md.append("")
for k in ["topics","episodes","firms","early","later","early_late_balance","network_observed_pct","sic_coverage_pct","normalized_citation_outcome_pct"]:
    md.append(f"- `{k}`: **{primary_summary[k]}**")
md.append("")
md.append("## Primary outcomes to be estimated in the next phase")
md.append("")
md.append("1. Post-entry topic output over years +1 to +3.")
md.append("2. Persistence: active in the same topic at +3; +5 as a secondary outcome where a complete window exists.")
md.append("3. Scientific impact conditional on continued output: firm citations-per-work normalized by the global mean for the same topic and publication year, aggregated over +1 to +3. This controls citation age and field-year differences without using raw citations as the primary impact metric.")
md.append("")
md.append("## Pre-entry network variables")
md.append("")
md.append("- distinct collaborator-country breadth over t−3…t−1;")
md.append("- collaboration-volume HHI complement;")
md.append("- Shannon entropy of collaborator-country distribution;")
md.append("- collaboration work volume;")
md.append("- collaborator-institution counts are retained only as additive source aggregates and are not described as globally distinct institution counts.")
md.append("")
md.append("## Identification discipline")
md.append("")
md.append("The primary design is **not frozen as causal**. Relative entry is endogenous. Main models must use within-topic comparisons, firm and calendar-year controls/fixed effects where identifiable, strong pre-entry capacity/network controls, and explicit selection diagnostics. Matching/weighting and leave-one-firm-out checks are mandatory robustness steps. With approximately 20 firms, inference should include firm-aware small-cluster methods (e.g., wild-cluster bootstrap) in addition to topic-clustered uncertainty.")
md.append("")
md.append("## Selection and pre-trend diagnostics")
md.append("")
md.append("| Relative year | Early mean log(1+company output) | Later mean | SMD |")
md.append("|---:|---:|---:|---:|")
for x in pretrend:
    md.append(f"| {x['relative_year']} | {x['early_mean_log1p_output']:.4f} | {x['later_mean_log1p_output']:.4f} | {x['smd_log1p_output']:.4f} |")
md.append("")
md.append(f"Annualized pre-entry output-slope SMD: **{slope_diag['smd_slope']:.4f}**" if slope_diag['smd_slope'] is not None else "Annualized pre-entry output-slope SMD: unavailable")
md.append(f"Maximum absolute baseline-covariate SMD: **{max_abs_smd:.4f}**" if max_abs_smd is not None else "Maximum baseline SMD unavailable")
md.append(f"Selection-adjustment flag: **{'YES' if selection_flag else 'NO'}**")
md.append("")
md.append("A selection flag does not invalidate the study; it determines that adjusted/matched specifications must be primary rather than optional.")
md.append("")
md.append("## Sample concentration")
md.append("")
md.append(f"- Firm-level episode HHI: **{firm_hhi:.4f}**")
md.append(f"- Largest firm's episode share: **{report['top_firm_share']:.1%}**" if report['top_firm_share'] is not None else "- Largest firm share unavailable")
md.append(f"- Top two firms' episode share: **{report['top_two_firm_share']:.1%}**" if report['top_two_firm_share'] is not None else "- Top-two share unavailable")
md.append("")
md.append("## Sensitivity plan frozen before hypothesis estimation")
md.append("")
md.append("- global emergence: one-year 100 threshold; two-year persistent 100 (primary); three-year persistent 100; two-year persistent 50; two-year persistent 250;")
md.append("- corporate early window: exact first entrant, 0–1, 0–2 (primary), and 0–3 years;")
md.append("- alternative output windows +1…+2, +1…+3 (primary), and +1…+5 where complete;")
md.append("- leave-one-firm-out and industry-stratified checks;")
md.append("- topic and firm concentration diagnostics;")
md.append("- no result-driven change to the primary treatment definition after this freeze.")
md.append("")
md.append("## Decision")
md.append("")
if freeze_pass:
    md.append("**DESIGN FREEZE PASSED.** The next phase may estimate selection-adjusted baseline models and robustness diagnostics on the frozen primary panel. H1–H5 have not yet been tested in this file.")
else:
    md.append("**DESIGN FREEZE FAILED.** Do not estimate H1–H5. The persistent-emergence primary definition does not retain the preset minimum sample and must be reconsidered transparently before analysis.")
md.append("")
md.append("## Reproducibility safeguards")
md.append("")
md.append("- Topic rows are multi-label and are never summed as unique publication totals.")
md.append("- Primary three-year outcomes use publication years through 2025 only.")
md.append("- Field-year citation normalization compares each firm-topic publication year with the same global topic-year baseline.")
md.append("- All treatment definitions and sensitivity variants are computed from the frozen GMS release without manually selecting favorable topics or firms.")

(OUT/"DESIGN_FREEZE.md").write_text("\n".join(md)+"\n",encoding="utf-8")
print(json.dumps(report,indent=2))
