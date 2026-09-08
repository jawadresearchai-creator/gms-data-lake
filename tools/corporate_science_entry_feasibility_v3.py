from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

OUT = Path("output")
OUT.mkdir(exist_ok=True)
INPUTS = {
    "global_topic": "input/work_year_topic.parquet",
    "company_topic": "input/company_topic_year.parquet",
    "company_collab": "input/company_collaboration_year.parquet",
    "company_research": "input/company_research_year.parquet",
    "company_citation": "input/company_citation_year.parquet",
}
for p in INPUTS.values():
    if not Path(p).exists():
        raise FileNotFoundError(p)

def qp(path: str) -> str:
    return path.replace("'", "''")

con = duckdb.connect()
con.execute("PRAGMA threads=4")

con.execute(f"""
CREATE VIEW global_topic AS
SELECT CAST(publication_year AS INTEGER) AS yr,
       CAST(topic_id AS VARCHAR) AS topic_id,
       CAST(work_count AS DOUBLE) AS work_count,
       CAST(citation_sum AS DOUBLE) AS citation_sum,
       CAST(mean_citations AS DOUBLE) AS mean_citations,
       CAST(topic_score_sum AS DOUBLE) AS topic_score_sum
FROM read_parquet('{qp(INPUTS['global_topic'])}')
WHERE publication_year BETWEEN 1900 AND 2026
""")
con.execute(f"""
CREATE VIEW company_topic AS
SELECT CAST(canonical_company_id AS VARCHAR) AS company_id,
       CAST(openalex_institution_id AS VARCHAR) AS openalex_institution_id,
       CAST(publication_year AS INTEGER) AS yr,
       CAST(topic_id AS VARCHAR) AS topic_id,
       CAST(work_count AS DOUBLE) AS work_count,
       CAST(citation_sum AS DOUBLE) AS citation_sum,
       CAST(topic_score_sum AS DOUBLE) AS topic_score_sum
FROM read_parquet('{qp(INPUTS['company_topic'])}')
WHERE publication_year BETWEEN 1900 AND 2026
""")
con.execute(f"""
CREATE VIEW company_collab AS
SELECT CAST(canonical_company_id AS VARCHAR) AS company_id,
       CAST(publication_year AS INTEGER) AS yr,
       CAST(collaborator_country_code AS VARCHAR) AS collaborator_country_code,
       CAST(collaborative_work_count AS DOUBLE) AS collaborative_work_count,
       CAST(citation_sum AS DOUBLE) AS citation_sum
FROM read_parquet('{qp(INPUTS['company_collab'])}')
WHERE publication_year BETWEEN 1900 AND 2026
""")
con.execute(f"""
CREATE VIEW company_research AS
SELECT CAST(canonical_company_id AS VARCHAR) AS company_id,
       CAST(company_name AS VARCHAR) AS company_name,
       CAST(publication_year AS INTEGER) AS yr,
       CAST(work_count AS DOUBLE) AS work_count,
       CAST(citation_sum AS DOUBLE) AS citation_sum,
       CAST(mean_citations AS DOUBLE) AS mean_citations
FROM read_parquet('{qp(INPUTS['company_research'])}')
WHERE publication_year BETWEEN 1900 AND 2026
""")
con.execute(f"""
CREATE VIEW company_citation AS
SELECT CAST(canonical_company_id AS VARCHAR) AS company_id,
       CAST(publication_year AS INTEGER) AS yr,
       CAST(work_count AS DOUBLE) AS work_count,
       CAST(citation_sum AS DOUBLE) AS citation_sum,
       CAST(citations_per_work AS DOUBLE) AS citations_per_work
FROM read_parquet('{qp(INPUTS['company_citation'])}')
WHERE publication_year BETWEEN 1900 AND 2026
""")

con.execute("""
CREATE TEMP TABLE firm_topic_entry AS
SELECT company_id, topic_id, MIN(yr) AS entry_year
FROM company_topic
WHERE work_count > 0
GROUP BY company_id, topic_id
""")
con.execute("""
CREATE TEMP TABLE company_names AS
SELECT company_id, ANY_VALUE(company_name) AS company_name
FROM company_research GROUP BY company_id
""")

source_stats = {}
for table in ["global_topic", "company_topic", "company_collab", "company_research", "company_citation"]:
    n, lo, hi = con.execute(f"SELECT COUNT(*), MIN(yr), MAX(yr) FROM {table}").fetchone()
    source_stats[table] = {"rows": int(n), "min_year": int(lo), "max_year": int(hi)}
source_stats["firm_topic_entry"] = {
    "rows": int(con.execute("SELECT COUNT(*) FROM firm_topic_entry").fetchone()[0]),
    "firms": int(con.execute("SELECT COUNT(DISTINCT company_id) FROM firm_topic_entry").fetchone()[0]),
    "topics": int(con.execute("SELECT COUNT(DISTINCT topic_id) FROM firm_topic_entry").fetchone()[0]),
}

def scalar(sql: str) -> int:
    return int(con.execute(sql).fetchone()[0])

grid = []
for scale in [10, 25, 50, 100]:
    em, ep = f"em_s{scale}", f"ep_s{scale}"
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE {em} AS
    WITH seq AS (
      SELECT topic_id, yr, work_count,
             LAG(work_count) OVER(PARTITION BY topic_id ORDER BY yr) AS prev_wc,
             LEAD(work_count) OVER(PARTITION BY topic_id ORDER BY yr) AS next_wc,
             AVG(work_count) OVER(PARTITION BY topic_id ORDER BY yr ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS prior3_avg
      FROM global_topic
    ), crossing AS (
      SELECT * FROM seq
      WHERE work_count >= {scale}
        AND COALESCE(next_wc,0) >= {scale}
        AND COALESCE(prev_wc,0) < {scale}
    )
    SELECT topic_id, MIN(yr) AS emergence_year,
           ARG_MIN(work_count,yr) AS work_count_at_emergence,
           ARG_MIN(prior3_avg,yr) AS prior3_avg_at_emergence
    FROM crossing GROUP BY topic_id
    """)
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE base AS
    SELECT f.company_id,f.topic_id,f.entry_year,e.emergence_year,
           f.entry_year-e.emergence_year AS entry_lag,
           e.work_count_at_emergence,e.prior3_avg_at_emergence,
           CASE WHEN f.entry_year-e.emergence_year BETWEEN -5 AND -1 THEN 'pioneer'
                WHEN f.entry_year-e.emergence_year BETWEEN 0 AND 2 THEN 'early'
                WHEN f.entry_year-e.emergence_year BETWEEN 3 AND 5 THEN 'middle'
                WHEN f.entry_year-e.emergence_year >= 6 THEN 'late'
                ELSE 'too_early' END AS entry_group
    FROM firm_topic_entry f JOIN {em} e USING(topic_id)
    WHERE e.emergence_year BETWEEN 2000 AND 2021
      AND f.entry_year <= 2024
      AND f.entry_year-e.emergence_year >= -5
    """)
    con.execute("""
    CREATE OR REPLACE TEMP TABLE net_country AS
    SELECT b.company_id,b.topic_id,c.collaborator_country_code,
           SUM(c.collaborative_work_count) AS collab_works
    FROM base b JOIN company_collab c
      ON c.company_id=b.company_id AND c.yr BETWEEN b.entry_year-3 AND b.entry_year-1
    WHERE c.collaborator_country_code IS NOT NULL
    GROUP BY b.company_id,b.topic_id,c.collaborator_country_code
    """)
    con.execute("""
    CREATE OR REPLACE TEMP TABLE net AS
    SELECT company_id,topic_id,COUNT(*) AS pre3_collab_countries,
           SUM(collab_works) AS pre3_collab_works,
           CASE WHEN SUM(collab_works)>0
             THEN 1.0-SUM(collab_works*collab_works)/(SUM(collab_works)*SUM(collab_works))
             ELSE NULL END AS pre3_network_diversity
    FROM net_country GROUP BY company_id,topic_id
    """)
    con.execute("""
    CREATE OR REPLACE TEMP TABLE pre AS
    SELECT b.company_id,b.topic_id,SUM(r.work_count) AS pre3_research_output,
           SUM(r.citation_sum) AS pre3_research_citations
    FROM base b JOIN company_research r
      ON r.company_id=b.company_id AND r.yr BETWEEN b.entry_year-3 AND b.entry_year-1
    GROUP BY b.company_id,b.topic_id
    """)
    con.execute("""
    CREATE OR REPLACE TEMP TABLE post AS
    SELECT b.company_id,b.topic_id,SUM(t.work_count) AS post3_topic_output,
           SUM(t.citation_sum) AS post3_topic_citations,
           COUNT(DISTINCT t.yr) AS post3_active_years
    FROM base b JOIN company_topic t
      ON t.company_id=b.company_id AND t.topic_id=b.topic_id
     AND t.yr BETWEEN b.entry_year+1 AND b.entry_year+3
    GROUP BY b.company_id,b.topic_id
    """)
    con.execute(f"""
    CREATE OR REPLACE TABLE {ep} AS
    SELECT b.*,n.pre3_collab_countries,n.pre3_collab_works,n.pre3_network_diversity,
           p.pre3_research_output,p.pre3_research_citations,
           o.post3_topic_output,o.post3_topic_citations,o.post3_active_years,
           (b.entry_year<=2021) AS has_full_3y_window
    FROM base b
    LEFT JOIN net n USING(company_id,topic_id)
    LEFT JOIN pre p USING(company_id,topic_id)
    LEFT JOIN post o USING(company_id,topic_id)
    """)

    con.execute(f"COPY (SELECT * FROM {em} WHERE emergence_year BETWEEN 2000 AND 2021 ORDER BY emergence_year,topic_id) TO 'output/topic_emergence_s{scale}.parquet' (FORMAT PARQUET)")
    con.execute(f"COPY (SELECT * FROM {ep} ORDER BY topic_id,entry_year,company_id) TO 'output/episodes_s{scale}.parquet' (FORMAT PARQUET)")

    emergence_topics = scalar(f"SELECT COUNT(*) FROM {em} WHERE emergence_year BETWEEN 2000 AND 2021")
    episodes = scalar(f"SELECT COUNT(*) FROM {ep}")
    firms = scalar(f"SELECT COUNT(DISTINCT company_id) FROM {ep}")
    topics = scalar(f"SELECT COUNT(DISTINCT topic_id) FROM {ep}")
    pioneers = scalar(f"SELECT COUNT(*) FROM {ep} WHERE entry_group='pioneer'")
    early = scalar(f"SELECT COUNT(*) FROM {ep} WHERE entry_group='early'")
    middle = scalar(f"SELECT COUNT(*) FROM {ep} WHERE entry_group='middle'")
    late = scalar(f"SELECT COUNT(*) FROM {ep} WHERE entry_group='late'")
    full3 = scalar(f"SELECT COUNT(*) FROM {ep} WHERE has_full_3y_window")
    network_n = scalar(f"SELECT COUNT(*) FROM {ep} WHERE pre3_collab_countries IS NOT NULL")
    research_n = scalar(f"SELECT COUNT(*) FROM {ep} WHERE pre3_research_output IS NOT NULL")
    comp_sql = f"""SELECT topic_id FROM {ep} GROUP BY topic_id
      HAVING COUNT(DISTINCT company_id)>=2
         AND SUM(CASE WHEN entry_lag<=2 THEN 1 ELSE 0 END)>=1
         AND SUM(CASE WHEN entry_lag>=3 THEN 1 ELSE 0 END)>=1"""
    comparable_topics = scalar(f"SELECT COUNT(*) FROM ({comp_sql}) q")
    comparable_episodes = scalar(f"SELECT COUNT(*) FROM {ep} e JOIN ({comp_sql}) c USING(topic_id)")
    earlyish, later = pioneers+early, middle+late
    net_pct = 100*network_n/episodes if episodes else 0.0
    res_pct = 100*research_n/episodes if episodes else 0.0
    balance = min(earlyish,later)/max(earlyish,later) if max(earlyish,later) else 0.0
    passed = (comparable_topics>=50 and comparable_episodes>=150 and firms>=15 and
              earlyish>=50 and later>=50 and full3>=100 and net_pct>=35.0)
    grid.append({
        "scale_threshold":scale,"emergence_topics_2000_2021":emergence_topics,
        "episode_topics":topics,"episodes":episodes,"firms":firms,
        "pioneers_m5_m1":pioneers,"early_0_2":early,"middle_3_5":middle,"late_6plus":late,
        "earlyish_pioneer_to_2":earlyish,"later_3plus":later,
        "early_late_balance":round(balance,4),"comparable_topics":comparable_topics,
        "comparable_episodes":comparable_episodes,"full_3y_window_episodes":full3,
        "pre3_network_coverage_n":network_n,"pre3_network_coverage_pct":round(net_pct,2),
        "pre3_research_coverage_n":research_n,"pre3_research_coverage_pct":round(res_pct,2),
        "passes_gate":passed})

with (OUT/"feasibility_grid.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(grid[0].keys())); w.writeheader(); w.writerows(grid)
(OUT/"feasibility_grid.json").write_text(json.dumps(grid,indent=2),encoding="utf-8")

passes=[r for r in grid if r["passes_gate"]]
preferred=sorted(passes or grid,key=lambda r:(r["comparable_topics"],r["comparable_episodes"],r["early_late_balance"],r["scale_threshold"]),reverse=True)[0]
status="PASS" if passes else "FAIL"
s=preferred["scale_threshold"]
comp=f"""SELECT topic_id FROM ep_s{s} GROUP BY topic_id
HAVING COUNT(DISTINCT company_id)>=2
 AND SUM(CASE WHEN entry_lag<=2 THEN 1 ELSE 0 END)>=1
 AND SUM(CASE WHEN entry_lag>=3 THEN 1 ELSE 0 END)>=1"""
con.execute(f"COPY (SELECT * FROM ep_s{s} WHERE topic_id IN ({comp}) ORDER BY topic_id,entry_year,company_id) TO 'output/preferred_comparable_episode_panel.parquet' (FORMAT PARQUET)")
con.execute(f"COPY (SELECT * FROM ep_s{s} WHERE topic_id IN ({comp}) ORDER BY topic_id,entry_year,company_id LIMIT 500) TO 'output/preferred_episode_preview.csv' (HEADER,DELIMITER ',')")

firm_rows=con.execute(f"""
SELECT e.company_id,COALESCE(n.company_name,e.company_id) AS company_name,
       COUNT(*) AS episodes,COUNT(DISTINCT e.topic_id) AS topics,
       SUM(CASE WHEN e.entry_lag<=2 THEN 1 ELSE 0 END) AS earlyish,
       SUM(CASE WHEN e.entry_lag>=3 THEN 1 ELSE 0 END) AS later
FROM ep_s{s} e LEFT JOIN company_names n USING(company_id)
GROUP BY e.company_id,n.company_name ORDER BY episodes DESC
""").fetchall()

report={"project":"corporate_science_entry_v1","generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "gate_status":status,"preferred_provisional_scale_threshold":s,
        "preferred_metrics":preferred,"source_stats":source_stats,"threshold_grid":grid,
        "gate_criteria":{"comparable_topics_min":50,"comparable_episodes_min":150,"firms_min":15,
          "earlyish_episodes_min":50,"later_episodes_min":50,"full_3y_window_min":100,
          "pre3_network_coverage_pct_min":35.0}}
(OUT/"feasibility_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")

md=["# Corporate Science Entry Timing — Empirical Feasibility Gate","",
 f"Generated: `{report['generated_at_utc']}`","",f"## Gate result: **{status}**","",
 "Research question: **Do firms that enter newly emerging scientific domains earlier develop a persistent scientific advantage, and does the diversity of their external international research networks condition that advantage?**","",
 "This gate tests design feasibility, not the hypotheses.","","## Source diagnostics","",
 "| Source | Rows | Min year | Max year |","|---|---:|---:|---:|"]
for k,v in source_stats.items():
    if k!="firm_topic_entry": md.append(f"| `{k}` | {v['rows']:,} | {v['min_year']} | {v['max_year']} |")
md += ["",f"Firm-topic first-entry universe: **{source_stats['firm_topic_entry']['rows']:,}** entries across **{source_stats['firm_topic_entry']['firms']} firms** and **{source_stats['firm_topic_entry']['topics']:,} topics**.","",
 "## Emergence-definition sensitivity grid","",
 "| Scale | Emergent topics | Episodes | Firms | Earlyish | Later | Comparable topics | Comparable episodes | Full 3y | Network cov. | Gate |",
 "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|"]
for r in grid:
    md.append(f"| {r['scale_threshold']} | {r['emergence_topics_2000_2021']:,} | {r['episodes']:,} | {r['firms']} | {r['earlyish_pioneer_to_2']:,} | {r['later_3plus']:,} | {r['comparable_topics']:,} | {r['comparable_episodes']:,} | {r['full_3y_window_episodes']:,} | {r['pre3_network_coverage_pct']:.1f}% | {'PASS' if r['passes_gate'] else 'FAIL'} |")
md += ["",f"## Preferred provisional scale: **{s} works/year**","",
 "This threshold is provisional and remains subject to preregistration and sensitivity analysis.","",
 "## Firm coverage at preferred scale","","| Firm | Episodes | Topics | Earlyish | Later |","|---|---:|---:|---:|---:|"]
for _,name,n,t,e,l in firm_rows: md.append(f"| {name} | {n:,} | {t:,} | {e:,} | {l:,} |")
md += ["","## Interpretation","",
 ("**The empirical feasibility gate passes.** Proceed to modern-sample freeze, citation normalization, pre-trend/selection diagnostics, and model construction." if status=="PASS" else "**The empirical feasibility gate fails under the preset criteria.** Diagnose the binding constraint before estimating headline hypotheses."),"",
 "## Safeguards","",
 "- Topic rows are multi-label and are not treated as unique publication totals.",
 "- Collaboration-country rows support country breadth/diversity; collaborator-institution counts are not treated as globally distinct annual institutions.",
 "- Emergence cohorts stop at 2021 and firm entry at 2024 for follow-up; future-dated records are excluded.",
 "- Raw citations are not yet used as the primary impact outcome; age/topic normalization comes next."]
(OUT/"FEASIBILITY_REPORT.md").write_text("\n".join(md)+"\n",encoding="utf-8")
print(json.dumps(report,indent=2))
