from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

OUT = Path("output")
OUT.mkdir(exist_ok=True)

def qp(p: str) -> str:
    return p.replace("'", "''")

paths = {
    "global": "input/work_year_topic.parquet",
    "topic": "input/company_topic_year.parquet",
    "collab": "input/company_collaboration_year.parquet",
    "research": "input/company_research_year.parquet",
}
for p in paths.values():
    if not Path(p).exists():
        raise FileNotFoundError(p)

con = duckdb.connect()
con.execute("PRAGMA threads=4")
con.execute(f"""
CREATE VIEW g AS
SELECT CAST(publication_year AS INTEGER) AS yr, CAST(topic_id AS VARCHAR) AS topic_id,
       CAST(work_count AS DOUBLE) AS work_count
FROM read_parquet('{qp(paths['global'])}')
WHERE publication_year BETWEEN 1900 AND 2026
""")
con.execute(f"""
CREATE VIEW t AS
SELECT CAST(canonical_company_id AS VARCHAR) AS company_id,
       CAST(publication_year AS INTEGER) AS yr, CAST(topic_id AS VARCHAR) AS topic_id,
       CAST(work_count AS DOUBLE) AS work_count, CAST(citation_sum AS DOUBLE) AS citation_sum
FROM read_parquet('{qp(paths['topic'])}')
WHERE publication_year BETWEEN 1900 AND 2026
""")
con.execute(f"""
CREATE VIEW c AS
SELECT CAST(canonical_company_id AS VARCHAR) AS company_id,
       CAST(publication_year AS INTEGER) AS yr,
       CAST(collaborator_country_code AS VARCHAR) AS country,
       CAST(collaborative_work_count AS DOUBLE) AS collaborative_work_count
FROM read_parquet('{qp(paths['collab'])}')
WHERE publication_year BETWEEN 1900 AND 2026
""")
con.execute(f"""
CREATE VIEW r AS
SELECT CAST(canonical_company_id AS VARCHAR) AS company_id,
       CAST(company_name AS VARCHAR) AS company_name,
       CAST(publication_year AS INTEGER) AS yr, CAST(work_count AS DOUBLE) AS work_count
FROM read_parquet('{qp(paths['research'])}')
WHERE publication_year BETWEEN 1900 AND 2026
""")
con.execute("CREATE TEMP TABLE names AS SELECT company_id, ANY_VALUE(company_name) company_name FROM r GROUP BY company_id")
con.execute("""
CREATE TEMP TABLE firm_entry AS
SELECT company_id, topic_id, MIN(yr) AS entry_year
FROM t WHERE work_count>0 AND yr<=2024
GROUP BY company_id,topic_id
""")
con.execute("""
CREATE TEMP TABLE global_maturity AS
SELECT topic_id,
       MIN(CASE WHEN work_count>=50 THEN yr END) AS first50,
       MIN(CASE WHEN work_count>=100 THEN yr END) AS first100,
       MIN(CASE WHEN work_count>=250 THEN yr END) AS first250,
       MAX(CASE WHEN yr<=2021 THEN work_count END) AS max_work_to_2021
FROM g GROUP BY topic_id
""")
con.execute("""
CREATE TEMP TABLE corporate_frontier AS
SELECT topic_id, MIN(entry_year) AS corp_first_year,
       MAX(entry_year) AS corp_last_year, COUNT(DISTINCT company_id) AS n_firms
FROM firm_entry GROUP BY topic_id
""")
con.execute("""
CREATE TEMP TABLE episodes AS
SELECT f.company_id,f.topic_id,f.entry_year,cf.corp_first_year,cf.n_firms,
       f.entry_year-cf.corp_first_year AS relative_entry_lag,
       gm.first50,gm.first100,gm.first250,gm.max_work_to_2021,
       CASE WHEN gm.first100 IS NOT NULL THEN cf.corp_first_year-gm.first100 END AS corp_frontier_lag_from_global100
FROM firm_entry f
JOIN corporate_frontier cf USING(topic_id)
LEFT JOIN global_maturity gm USING(topic_id)
WHERE cf.n_firms>=2 AND cf.corp_first_year BETWEEN 1990 AND 2021
""")

# Pre-entry network/research context.
con.execute("""
CREATE TEMP TABLE net_country AS
SELECT e.company_id,e.topic_id,c.country,SUM(c.collaborative_work_count) AS w
FROM episodes e JOIN c
 ON c.company_id=e.company_id AND c.yr BETWEEN e.entry_year-3 AND e.entry_year-1
WHERE c.country IS NOT NULL
GROUP BY e.company_id,e.topic_id,c.country
""")
con.execute("""
CREATE TEMP TABLE net AS
SELECT company_id,topic_id,COUNT(*) AS pre3_countries,SUM(w) AS pre3_collab_works,
       CASE WHEN SUM(w)>0 THEN 1.0-SUM(w*w)/(SUM(w)*SUM(w)) ELSE NULL END AS pre3_network_diversity
FROM net_country GROUP BY company_id,topic_id
""")
con.execute("""
CREATE TEMP TABLE pre AS
SELECT e.company_id,e.topic_id,SUM(r.work_count) AS pre3_research_output
FROM episodes e JOIN r
 ON r.company_id=e.company_id AND r.yr BETWEEN e.entry_year-3 AND e.entry_year-1
GROUP BY e.company_id,e.topic_id
""")
con.execute("""
CREATE TEMP TABLE post AS
SELECT e.company_id,e.topic_id,SUM(t.work_count) AS post3_output,SUM(t.citation_sum) AS post3_citations,
       COUNT(DISTINCT t.yr) AS post3_active_years
FROM episodes e JOIN t
 ON t.company_id=e.company_id AND t.topic_id=e.topic_id AND t.yr BETWEEN e.entry_year+1 AND e.entry_year+3
GROUP BY e.company_id,e.topic_id
""")
con.execute("""
CREATE TABLE enriched AS
SELECT e.*,n.pre3_countries,n.pre3_collab_works,n.pre3_network_diversity,
       p.pre3_research_output,o.post3_output,o.post3_citations,o.post3_active_years,
       (e.entry_year<=2021) AS has_full_3y
FROM episodes e
LEFT JOIN net n USING(company_id,topic_id)
LEFT JOIN pre p USING(company_id,topic_id)
LEFT JOIN post o USING(company_id,topic_id)
""")

def scalar(sql: str):
    return con.execute(sql).fetchone()[0]

def as_int(x):
    return int(x or 0)

base_stats = {
    "all_firm_topic_entries": as_int(scalar("SELECT COUNT(*) FROM firm_entry")),
    "all_firms": as_int(scalar("SELECT COUNT(DISTINCT company_id) FROM firm_entry")),
    "all_topics": as_int(scalar("SELECT COUNT(DISTINCT topic_id) FROM firm_entry")),
    "shared_topics_2plus_firms": as_int(scalar("SELECT COUNT(*) FROM corporate_frontier WHERE n_firms>=2")),
    "shared_topics_3plus_firms": as_int(scalar("SELECT COUNT(*) FROM corporate_frontier WHERE n_firms>=3")),
    "modern_shared_topics": as_int(scalar("SELECT COUNT(DISTINCT topic_id) FROM enriched")),
    "modern_shared_episodes": as_int(scalar("SELECT COUNT(*) FROM enriched")),
    "modern_shared_firms": as_int(scalar("SELECT COUNT(DISTINCT company_id) FROM enriched")),
    "topics_with_global100": as_int(scalar("SELECT COUNT(DISTINCT topic_id) FROM enriched WHERE first100 IS NOT NULL AND first100<=2021")),
}

lag_stats = con.execute("""
SELECT COUNT(*) n,
       QUANTILE_CONT(corp_frontier_lag_from_global100,0.25) q25,
       QUANTILE_CONT(corp_frontier_lag_from_global100,0.50) median,
       QUANTILE_CONT(corp_frontier_lag_from_global100,0.75) q75
FROM (SELECT DISTINCT topic_id,corp_frontier_lag_from_global100 FROM enriched
      WHERE first100 IS NOT NULL AND first100<=2021)
""").fetchone()
base_stats["corporate_frontier_lag_from_global100"] = {
    "topics": as_int(lag_stats[0]), "q25_years": lag_stats[1], "median_years": lag_stats[2], "q75_years": lag_stats[3]
}

rows=[]
for eligibility, predicate in [
    ("all_modern_shared", "TRUE"),
    ("global100_by_2021", "first100 IS NOT NULL AND first100<=2021"),
    ("global100_1990_2021", "first100 BETWEEN 1990 AND 2021"),
]:
    for early_window in [0,1,2,3,5]:
        comp=f"""SELECT topic_id FROM enriched WHERE {predicate} GROUP BY topic_id
        HAVING SUM(CASE WHEN relative_entry_lag<={early_window} THEN 1 ELSE 0 END)>=1
           AND SUM(CASE WHEN relative_entry_lag>{early_window} THEN 1 ELSE 0 END)>=1"""
        topics=as_int(scalar(f"SELECT COUNT(*) FROM ({comp}) q"))
        episodes=as_int(scalar(f"SELECT COUNT(*) FROM enriched e JOIN ({comp}) q USING(topic_id) WHERE {predicate}"))
        firms=as_int(scalar(f"SELECT COUNT(DISTINCT company_id) FROM enriched e JOIN ({comp}) q USING(topic_id) WHERE {predicate}"))
        early=as_int(scalar(f"SELECT COUNT(*) FROM enriched e JOIN ({comp}) q USING(topic_id) WHERE {predicate} AND relative_entry_lag<={early_window}"))
        later=as_int(scalar(f"SELECT COUNT(*) FROM enriched e JOIN ({comp}) q USING(topic_id) WHERE {predicate} AND relative_entry_lag>{early_window}"))
        full3=as_int(scalar(f"SELECT COUNT(*) FROM enriched e JOIN ({comp}) q USING(topic_id) WHERE {predicate} AND has_full_3y"))
        netn=as_int(scalar(f"SELECT COUNT(*) FROM enriched e JOIN ({comp}) q USING(topic_id) WHERE {predicate} AND pre3_countries IS NOT NULL"))
        pren=as_int(scalar(f"SELECT COUNT(*) FROM enriched e JOIN ({comp}) q USING(topic_id) WHERE {predicate} AND pre3_research_output IS NOT NULL"))
        netpct=100*netn/episodes if episodes else 0.0
        prepct=100*pren/episodes if episodes else 0.0
        balance=min(early,later)/max(early,later) if max(early,later) else 0.0
        passed=(topics>=50 and episodes>=150 and firms>=15 and early>=50 and later>=50 and full3>=100 and netpct>=35)
        rows.append({"eligibility":eligibility,"early_window_years":early_window,
          "comparable_topics":topics,"comparable_episodes":episodes,"firms":firms,
          "early_episodes":early,"later_episodes":later,"early_late_balance":round(balance,4),
          "full_3y":full3,"network_coverage_n":netn,"network_coverage_pct":round(netpct,2),
          "prior_research_coverage_n":pren,"prior_research_coverage_pct":round(prepct,2),"passes_gate":passed})

passes=[x for x in rows if x["passes_gate"]]
preferred=sorted(passes or rows,key=lambda x:(x["comparable_topics"],x["comparable_episodes"],x["early_late_balance"]),reverse=True)[0]
status="PASS" if passes else "FAIL"

with (OUT/"relative_entry_grid.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
report={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"diagnostic_status":status,
        "base_stats":base_stats,"preferred_design":preferred,"grid":rows}
(OUT/"relative_entry_diagnostic.json").write_text(json.dumps(report,indent=2),encoding="utf-8")

pred={"all_modern_shared":"TRUE","global100_by_2021":"first100 IS NOT NULL AND first100<=2021","global100_1990_2021":"first100 BETWEEN 1990 AND 2021"}[preferred["eligibility"]]
w=preferred["early_window_years"]
comp=f"""SELECT topic_id FROM enriched WHERE {pred} GROUP BY topic_id
HAVING SUM(CASE WHEN relative_entry_lag<={w} THEN 1 ELSE 0 END)>=1
 AND SUM(CASE WHEN relative_entry_lag>{w} THEN 1 ELSE 0 END)>=1"""
con.execute(f"COPY (SELECT * FROM enriched WHERE {pred} AND topic_id IN ({comp}) ORDER BY topic_id,entry_year,company_id) TO 'output/relative_entry_preferred_panel.parquet' (FORMAT PARQUET)")
con.execute(f"COPY (SELECT * FROM enriched WHERE {pred} AND topic_id IN ({comp}) ORDER BY topic_id,entry_year,company_id LIMIT 1000) TO 'output/relative_entry_preview.csv' (HEADER,DELIMITER ',')")

firm_rows=con.execute(f"""SELECT e.company_id,COALESCE(n.company_name,e.company_id) company_name,
 COUNT(*) episodes,COUNT(DISTINCT e.topic_id) topics,
 SUM(CASE WHEN e.relative_entry_lag<={w} THEN 1 ELSE 0 END) early,
 SUM(CASE WHEN e.relative_entry_lag>{w} THEN 1 ELSE 0 END) later
FROM enriched e LEFT JOIN names n USING(company_id)
WHERE {pred} AND e.topic_id IN ({comp})
GROUP BY e.company_id,n.company_name ORDER BY episodes DESC""").fetchall()

md=["# Relative Corporate Entry Timing — Diagnostic","",f"Generated: `{report['generated_at_utc']}`","",
 f"## Redesigned gate: **{status}**","",
 "The original global-emergence timing gate failed because linked firms overwhelmingly entered scientific topics long after global academic emergence. This diagnostic tests a theory-consistent alternative: **relative corporate entry timing within each topic**, while global topic maturity remains a control/eligibility variable.","",
 "## Base coverage","",
 f"- Firm-topic entry records: **{base_stats['all_firm_topic_entries']:,}** across **{base_stats['all_firms']} firms** and **{base_stats['all_topics']:,} topics**.",
 f"- Topics shared by at least 2 linked firms: **{base_stats['shared_topics_2plus_firms']:,}**.",
 f"- Topics shared by at least 3 linked firms: **{base_stats['shared_topics_3plus_firms']:,}**.",
 f"- Modern shared-topic episodes (corporate frontier 1990–2021): **{base_stats['modern_shared_episodes']:,}** across **{base_stats['modern_shared_topics']:,} topics** and **{base_stats['modern_shared_firms']} firms**.","",
 "## Why the original definition failed","",
 f"Among shared topics that reached 100 global works/year by 2021, the first linked corporate entrant lagged that global threshold by a median of **{base_stats['corporate_frontier_lag_from_global100']['median_years']} years** (IQR {base_stats['corporate_frontier_lag_from_global100']['q25_years']} to {base_stats['corporate_frontier_lag_from_global100']['q75_years']}).","",
 "## Preferred redesigned specification","",
 f"- Eligibility: **{preferred['eligibility']}**",
 f"- Early corporate entrant window: **0–{preferred['early_window_years']} years from the first linked corporate entry into that topic**",
 f"- Comparable topics: **{preferred['comparable_topics']:,}**",
 f"- Comparable episodes: **{preferred['comparable_episodes']:,}**",
 f"- Firms: **{preferred['firms']}**",
 f"- Early episodes: **{preferred['early_episodes']:,}**; later episodes: **{preferred['later_episodes']:,}**",
 f"- Full 3-year follow-up episodes: **{preferred['full_3y']:,}**",
 f"- Pre-entry network coverage: **{preferred['network_coverage_pct']:.1f}%**",
 f"- Pre-entry research-capacity coverage: **{preferred['prior_research_coverage_pct']:.1f}%**","",
 "## Firm coverage","","| Firm | Episodes | Topics | Early | Later |","|---|---:|---:|---:|---:|"]
for _,name,n,t,e,l in firm_rows: md.append(f"| {name} | {n:,} | {t:,} | {e:,} | {l:,} |")
md += ["","## Decision","",
 ("**PROCEED WITH THE RELATIVE-CORPORATE-ENTRY DESIGN.** The sample clears the same preset feasibility thresholds. Global scientific emergence should be retained as a field-age/maturity control rather than used to define treatment." if status=="PASS" else "**DO NOT PROCEED YET.** Even the relative corporate-entry design does not clear the preset sample-balance thresholds; the topic should be reconsidered rather than weakening the gate."),"",
 "## Safeguards","",
 "- This diagnostic tests feasibility only; it does not test H1–H5.",
 "- Relative entry is measured within topic, which reduces field-level comparability problems but does not remove endogenous firm selection.",
 "- Global field maturity remains observable through first-50/100/250-work thresholds and should enter controls/stratification.",
 "- Citation-age normalization and selection/pre-trend diagnostics remain mandatory before substantive inference."]
(OUT/"RELATIVE_ENTRY_DIAGNOSTIC.md").write_text("\n".join(md)+"\n",encoding="utf-8")
print(json.dumps(report,indent=2))
