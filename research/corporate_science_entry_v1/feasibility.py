from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb

PROJECT = "corporate_science_entry_v1"
OUT = Path("output")
OUT.mkdir(parents=True, exist_ok=True)

FILES = {
    "global_topic": "input/work_year_topic.parquet",
    "company_topic": "input/company_topic_year.parquet",
    "company_collab": "input/company_collaboration_year.parquet",
    "company_research": "input/company_research_year.parquet",
    "company_citation": "input/company_citation_year.parquet",
}

for name, path in FILES.items():
    if not Path(path).exists():
        raise FileNotFoundError(f"Missing required input {name}: {path}")

con = duckdb.connect()
con.execute("PRAGMA threads=4")

con.execute(
    """
    CREATE VIEW global_topic AS
    SELECT
        CAST(publication_year AS INTEGER) AS year,
        CAST(topic_id AS VARCHAR) AS topic_id,
        CAST(work_count AS DOUBLE) AS work_count,
        CAST(citation_sum AS DOUBLE) AS citation_sum,
        CAST(mean_citations AS DOUBLE) AS mean_citations,
        CAST(topic_score_sum AS DOUBLE) AS topic_score_sum
    FROM read_parquet(?)
    WHERE publication_year BETWEEN 1900 AND 2026
    """,
    [FILES["global_topic"]],
)

con.execute(
    """
    CREATE VIEW company_topic AS
    SELECT
        CAST(canonical_company_id AS VARCHAR) AS company_id,
        CAST(openalex_institution_id AS VARCHAR) AS openalex_institution_id,
        CAST(publication_year AS INTEGER) AS year,
        CAST(topic_id AS VARCHAR) AS topic_id,
        CAST(work_count AS DOUBLE) AS work_count,
        CAST(citation_sum AS DOUBLE) AS citation_sum,
        CAST(topic_score_sum AS DOUBLE) AS topic_score_sum
    FROM read_parquet(?)
    WHERE publication_year BETWEEN 1900 AND 2026
    """,
    [FILES["company_topic"]],
)

con.execute(
    """
    CREATE VIEW company_collab AS
    SELECT
        CAST(canonical_company_id AS VARCHAR) AS company_id,
        CAST(publication_year AS INTEGER) AS year,
        CAST(collaborator_country_code AS VARCHAR) AS collaborator_country_code,
        CAST(collaborative_work_count AS DOUBLE) AS collaborative_work_count,
        CAST(citation_sum AS DOUBLE) AS citation_sum
    FROM read_parquet(?)
    WHERE publication_year BETWEEN 1900 AND 2026
    """,
    [FILES["company_collab"]],
)

con.execute(
    """
    CREATE VIEW company_research AS
    SELECT
        CAST(canonical_company_id AS VARCHAR) AS company_id,
        CAST(company_name AS VARCHAR) AS company_name,
        CAST(publication_year AS INTEGER) AS year,
        CAST(work_count AS DOUBLE) AS work_count,
        CAST(citation_sum AS DOUBLE) AS citation_sum,
        CAST(mean_citations AS DOUBLE) AS mean_citations
    FROM read_parquet(?)
    WHERE publication_year BETWEEN 1900 AND 2026
    """,
    [FILES["company_research"]],
)

con.execute(
    """
    CREATE VIEW company_citation AS
    SELECT
        CAST(canonical_company_id AS VARCHAR) AS company_id,
        CAST(publication_year AS INTEGER) AS year,
        CAST(work_count AS DOUBLE) AS work_count,
        CAST(citation_sum AS DOUBLE) AS citation_sum,
        CAST(citations_per_work AS DOUBLE) AS citations_per_work
    FROM read_parquet(?)
    WHERE publication_year BETWEEN 1900 AND 2026
    """,
    [FILES["company_citation"]],
)

con.execute(
    """
    CREATE TEMP TABLE firm_topic_entry AS
    SELECT company_id, topic_id, MIN(year) AS entry_year
    FROM company_topic
    WHERE work_count > 0
    GROUP BY company_id, topic_id
    """
)

# Basic source diagnostics.
source_stats = {}
for name in ["global_topic", "company_topic", "company_collab", "company_research", "company_citation"]:
    rows, min_year, max_year = con.execute(
        f"SELECT COUNT(*), MIN(year), MAX(year) FROM {name}"
    ).fetchone()
    source_stats[name] = {"rows": int(rows), "min_year": int(min_year), "max_year": int(max_year)}

source_stats["firm_topic_entry"] = {
    "rows": int(con.execute("SELECT COUNT(*) FROM firm_topic_entry").fetchone()[0]),
    "firms": int(con.execute("SELECT COUNT(DISTINCT company_id) FROM firm_topic_entry").fetchone()[0]),
    "topics": int(con.execute("SELECT COUNT(DISTINCT topic_id) FROM firm_topic_entry").fetchone()[0]),
}

thresholds = [10, 25, 50, 100]
grid = []

for scale in thresholds:
    emergence_table = f"topic_emergence_s{scale}"
    episode_table = f"episodes_s{scale}"

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE {emergence_table} AS
        WITH seq AS (
            SELECT
                topic_id,
                year,
                work_count,
                LAG(work_count) OVER (PARTITION BY topic_id ORDER BY year) AS prev_work_count,
                LEAD(work_count) OVER (PARTITION BY topic_id ORDER BY year) AS next_work_count,
                AVG(work_count) OVER (
                    PARTITION BY topic_id ORDER BY year
                    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
                ) AS prior3_avg
            FROM global_topic
        ), crossing AS (
            SELECT *
            FROM seq
            WHERE work_count >= {scale}
              AND COALESCE(next_work_count, 0) >= {scale}
              AND COALESCE(prev_work_count, 0) < {scale}
        )
        SELECT
            topic_id,
            MIN(year) AS emergence_year,
            ARG_MIN(work_count, year) AS work_count_at_emergence,
            ARG_MIN(prior3_avg, year) AS prior3_avg_at_emergence
        FROM crossing
        GROUP BY topic_id
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE episode_base AS
        SELECT
            e.company_id,
            e.topic_id,
            e.entry_year,
            m.emergence_year,
            e.entry_year - m.emergence_year AS entry_lag,
            m.work_count_at_emergence,
            m.prior3_avg_at_emergence,
            CASE
                WHEN e.entry_year - m.emergence_year BETWEEN -5 AND -1 THEN 'pioneer'
                WHEN e.entry_year - m.emergence_year BETWEEN 0 AND 2 THEN 'early'
                WHEN e.entry_year - m.emergence_year BETWEEN 3 AND 5 THEN 'middle'
                WHEN e.entry_year - m.emergence_year >= 6 THEN 'late'
                ELSE 'too_early'
            END AS entry_group
        FROM firm_topic_entry e
        JOIN {emergence_table} m USING (topic_id)
        WHERE m.emergence_year BETWEEN 2000 AND 2021
          AND e.entry_year <= 2024
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE pre_network_country AS
        SELECT
            e.company_id,
            e.topic_id,
            c.collaborator_country_code,
            SUM(c.collaborative_work_count) AS collab_works
        FROM episode_base e
        JOIN company_collab c
          ON c.company_id = e.company_id
         AND c.year BETWEEN e.entry_year - 3 AND e.entry_year - 1
        WHERE e.entry_lag >= -5
          AND c.collaborator_country_code IS NOT NULL
        GROUP BY e.company_id, e.topic_id, c.collaborator_country_code
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE pre_network AS
        SELECT
            company_id,
            topic_id,
            COUNT(*) AS pre3_collab_countries,
            SUM(collab_works) AS pre3_collab_works,
            CASE WHEN SUM(collab_works) > 0 THEN
                1.0 - SUM(collab_works * collab_works) / (SUM(collab_works) * SUM(collab_works))
            ELSE NULL END AS pre3_network_diversity
        FROM pre_network_country
        GROUP BY company_id, topic_id
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE pre_research AS
        SELECT
            e.company_id,
            e.topic_id,
            SUM(r.work_count) AS pre3_research_output,
            SUM(r.citation_sum) AS pre3_research_citations
        FROM episode_base e
        JOIN company_research r
          ON r.company_id = e.company_id
         AND r.year BETWEEN e.entry_year - 3 AND e.entry_year - 1
        WHERE e.entry_lag >= -5
        GROUP BY e.company_id, e.topic_id
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE post3 AS
        SELECT
            e.company_id,
            e.topic_id,
            SUM(t.work_count) AS post3_topic_output,
            SUM(t.citation_sum) AS post3_topic_citations,
            COUNT(DISTINCT t.year) AS post3_active_years
        FROM episode_base e
        JOIN company_topic t
          ON t.company_id = e.company_id
         AND t.topic_id = e.topic_id
         AND t.year BETWEEN e.entry_year + 1 AND e.entry_year + 3
        WHERE e.entry_lag >= -5
        GROUP BY e.company_id, e.topic_id
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE TABLE {episode_table} AS
        SELECT
            e.*,
            n.pre3_collab_countries,
            n.pre3_collab_works,
            n.pre3_network_diversity,
            r.pre3_research_output,
            r.pre3_research_citations,
            p.post3_topic_output,
            p.post3_topic_citations,
            p.post3_active_years,
            CASE WHEN e.entry_year <= 2021 THEN TRUE ELSE FALSE END AS has_full_3y_window
        FROM episode_base e
        LEFT JOIN pre_network n USING (company_id, topic_id)
        LEFT JOIN pre_research r USING (company_id, topic_id)
        LEFT JOIN post3 p USING (company_id, topic_id)
        WHERE e.entry_lag >= -5
        """
    )

    con.execute(
        f"""
        COPY (SELECT * FROM {emergence_table} WHERE emergence_year BETWEEN 2000 AND 2021 ORDER BY emergence_year, topic_id)
        TO 'output/topic_emergence_s{scale}.parquet' (FORMAT PARQUET)
        """
    )
    con.execute(
        f"""
        COPY (SELECT * FROM {episode_table} ORDER BY topic_id, entry_year, company_id)
        TO 'output/episodes_s{scale}.parquet' (FORMAT PARQUET)
        """
    )

    emergence_topics = int(con.execute(
        f"SELECT COUNT(*) FROM {emergence_table} WHERE emergence_year BETWEEN 2000 AND 2021"
    ).fetchone()[0])
    episodes = int(con.execute(f"SELECT COUNT(*) FROM {episode_table}").fetchone()[0])
    firms = int(con.execute(f"SELECT COUNT(DISTINCT company_id) FROM {episode_table}").fetchone()[0])
    topics = int(con.execute(f"SELECT COUNT(DISTINCT topic_id) FROM {episode_table}").fetchone()[0])
    pioneers = int(con.execute(f"SELECT COUNT(*) FROM {episode_table} WHERE entry_group='pioneer'").fetchone()[0])
    early = int(con.execute(f"SELECT COUNT(*) FROM {episode_table} WHERE entry_group='early'").fetchone()[0])
    middle = int(con.execute(f"SELECT COUNT(*) FROM {episode_table} WHERE entry_group='middle'").fetchone()[0])
    late = int(con.execute(f"SELECT COUNT(*) FROM {episode_table} WHERE entry_group='late'").fetchone()[0])
    full3 = int(con.execute(f"SELECT COUNT(*) FROM {episode_table} WHERE has_full_3y_window").fetchone()[0])
    network_n = int(con.execute(f"SELECT COUNT(*) FROM {episode_table} WHERE pre3_collab_countries IS NOT NULL").fetchone()[0])
    research_n = int(con.execute(f"SELECT COUNT(*) FROM {episode_table} WHERE pre3_research_output IS NOT NULL").fetchone()[0])

    comparable_topics = int(con.execute(
        f"""
        SELECT COUNT(*) FROM (
            SELECT topic_id
            FROM {episode_table}
            GROUP BY topic_id
            HAVING COUNT(DISTINCT company_id) >= 2
               AND SUM(CASE WHEN entry_lag <= 2 THEN 1 ELSE 0 END) >= 1
               AND SUM(CASE WHEN entry_lag >= 3 THEN 1 ELSE 0 END) >= 1
        ) x
        """
    ).fetchone()[0])

    comparable_episodes = int(con.execute(
        f"""
        SELECT COUNT(*)
        FROM {episode_table} e
        JOIN (
            SELECT topic_id
            FROM {episode_table}
            GROUP BY topic_id
            HAVING COUNT(DISTINCT company_id) >= 2
               AND SUM(CASE WHEN entry_lag <= 2 THEN 1 ELSE 0 END) >= 1
               AND SUM(CASE WHEN entry_lag >= 3 THEN 1 ELSE 0 END) >= 1
        ) c USING(topic_id)
        """
    ).fetchone()[0])

    earlyish = pioneers + early
    later = middle + late
    network_pct = (network_n / episodes * 100.0) if episodes else 0.0
    research_pct = (research_n / episodes * 100.0) if episodes else 0.0
    balance = (min(earlyish, later) / max(earlyish, later)) if max(earlyish, later) else 0.0

    passed = (
        comparable_topics >= 50
        and comparable_episodes >= 150
        and firms >= 15
        and earlyish >= 50
        and later >= 50
        and full3 >= 100
        and network_pct >= 35.0
    )

    grid.append({
        "scale_threshold": scale,
        "emergence_topics_2000_2021": emergence_topics,
        "episode_topics": topics,
        "episodes": episodes,
        "firms": firms,
        "pioneers_m5_m1": pioneers,
        "early_0_2": early,
        "middle_3_5": middle,
        "late_6plus": late,
        "earlyish_pioneer_to_2": earlyish,
        "later_3plus": later,
        "early_late_balance": round(balance, 4),
        "comparable_topics": comparable_topics,
        "comparable_episodes": comparable_episodes,
        "full_3y_window_episodes": full3,
        "pre3_network_coverage_n": network_n,
        "pre3_network_coverage_pct": round(network_pct, 2),
        "pre3_research_coverage_n": research_n,
        "pre3_research_coverage_pct": round(research_pct, 2),
        "passes_gate": passed,
    })

# Save grid as CSV and JSON.
fieldnames = list(grid[0].keys())
with (OUT / "feasibility_grid.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(grid)

with (OUT / "feasibility_grid.json").open("w", encoding="utf-8") as f:
    json.dump(grid, f, indent=2)

passes = [r for r in grid if r["passes_gate"]]
if passes:
    # Prefer stronger scientific scale while retaining within-topic comparison depth.
    preferred = sorted(
        passes,
        key=lambda r: (r["comparable_topics"], r["comparable_episodes"], r["early_late_balance"], r["scale_threshold"]),
        reverse=True,
    )[0]
    gate_status = "PASS"
else:
    preferred = sorted(
        grid,
        key=lambda r: (r["comparable_topics"], r["comparable_episodes"], r["early_late_balance"]),
        reverse=True,
    )[0]
    gate_status = "FAIL"

preferred_scale = preferred["scale_threshold"]
con.execute(
    f"""
    COPY (
        SELECT *
        FROM episodes_s{preferred_scale}
        WHERE topic_id IN (
            SELECT topic_id
            FROM episodes_s{preferred_scale}
            GROUP BY topic_id
            HAVING COUNT(DISTINCT company_id) >= 2
               AND SUM(CASE WHEN entry_lag <= 2 THEN 1 ELSE 0 END) >= 1
               AND SUM(CASE WHEN entry_lag >= 3 THEN 1 ELSE 0 END) >= 1
        )
        ORDER BY topic_id, entry_year, company_id
    ) TO 'output/preferred_comparable_episode_panel.parquet' (FORMAT PARQUET)
    """
)
con.execute(
    f"""
    COPY (
        SELECT *
        FROM episodes_s{preferred_scale}
        WHERE topic_id IN (
            SELECT topic_id
            FROM episodes_s{preferred_scale}
            GROUP BY topic_id
            HAVING COUNT(DISTINCT company_id) >= 2
               AND SUM(CASE WHEN entry_lag <= 2 THEN 1 ELSE 0 END) >= 1
               AND SUM(CASE WHEN entry_lag >= 3 THEN 1 ELSE 0 END) >= 1
        )
        ORDER BY topic_id, entry_year, company_id
        LIMIT 500
    ) TO 'output/preferred_episode_preview.csv' (HEADER, DELIMITER ',')
    """
)

# Firm-level diagnostic for the preferred scale.
top_firms = con.execute(
    f"""
    SELECT
        e.company_id,
        COALESCE(MAX(r.company_name), e.company_id) AS company_name,
        COUNT(*) AS episodes,
        COUNT(DISTINCT e.topic_id) AS topics,
        SUM(CASE WHEN e.entry_lag <= 2 THEN 1 ELSE 0 END) AS earlyish,
        SUM(CASE WHEN e.entry_lag >= 3 THEN 1 ELSE 0 END) AS later
    FROM episodes_s{preferred_scale} e
    LEFT JOIN company_research r ON r.company_id=e.company_id
    GROUP BY e.company_id
    ORDER BY episodes DESC
    """
).fetchall()

report = {
    "project": PROJECT,
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "gate_status": gate_status,
    "preferred_provisional_scale_threshold": preferred_scale,
    "preferred_metrics": preferred,
    "source_stats": source_stats,
    "threshold_grid": grid,
    "gate_criteria": {
        "comparable_topics_min": 50,
        "comparable_episodes_min": 150,
        "firms_min": 15,
        "earlyish_episodes_min": 50,
        "later_episodes_min": 50,
        "full_3y_window_min": 100,
        "pre3_network_coverage_pct_min": 35.0,
    },
}
with (OUT / "feasibility_report.json").open("w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

md = []
md.append("# Corporate Science Entry Timing — Empirical Feasibility Gate")
md.append("")
md.append(f"Generated: `{report['generated_at_utc']}`")
md.append("")
md.append(f"## Gate result: **{gate_status}**")
md.append("")
md.append("Research question: **Do firms that enter newly emerging scientific domains earlier develop a persistent scientific advantage, and does the diversity of their external international research networks condition that advantage?**")
md.append("")
md.append("This gate does not estimate the paper's hypotheses. It tests whether the frozen GMS data contain enough independent firm-topic entry episodes, early/late contrasts, follow-up windows, and pre-entry network information to justify full model construction.")
md.append("")
md.append("## Source diagnostics")
md.append("")
md.append("| Source | Rows | Min year | Max year |")
md.append("|---|---:|---:|---:|")
for name, s in source_stats.items():
    if name == "firm_topic_entry":
        continue
    md.append(f"| `{name}` | {s['rows']:,} | {s['min_year']} | {s['max_year']} |")
md.append("")
md.append(f"Firm-topic first-entry universe: **{source_stats['firm_topic_entry']['rows']:,}** entries across **{source_stats['firm_topic_entry']['firms']} firms** and **{source_stats['firm_topic_entry']['topics']:,} topics**.")
md.append("")
md.append("## Emergence-definition sensitivity grid")
md.append("")
md.append("A topic's provisional emergence year is the first year it crosses the stated global annual work-count threshold, remains at or above that threshold in the next year, and was below it in the previous year. Only emergence cohorts 2000–2021 are used at this gate.")
md.append("")
md.append("| Scale | Emergent topics | Episodes | Firms | Earlyish (-5..2) | Later (3+) | Comparable topics | Comparable episodes | Full 3y | Network cov. | Gate |")
md.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|")
for r in grid:
    md.append(
        f"| {r['scale_threshold']} | {r['emergence_topics_2000_2021']:,} | {r['episodes']:,} | {r['firms']} | "
        f"{r['earlyish_pioneer_to_2']:,} | {r['later_3plus']:,} | {r['comparable_topics']:,} | {r['comparable_episodes']:,} | "
        f"{r['full_3y_window_episodes']:,} | {r['pre3_network_coverage_pct']:.1f}% | {'PASS' if r['passes_gate'] else 'FAIL'} |"
    )
md.append("")
md.append(f"## Preferred provisional scale: **{preferred_scale} works/year**")
md.append("")
md.append("The preferred threshold is selected only for building the next analysis panel. It is **not** yet a final theoretical definition of field emergence; the manuscript analysis must retain the full sensitivity grid and preregister the final construct before hypothesis testing.")
md.append("")
md.append("## Firm coverage at preferred scale")
md.append("")
md.append("| Firm | Episodes | Topics | Earlyish | Later |")
md.append("|---|---:|---:|---:|---:|")
for company_id, company_name, episodes, topics, earlyish, later in top_firms:
    md.append(f"| {company_name} | {episodes:,} | {topics:,} | {earlyish:,} | {later:,} |")
md.append("")
md.append("## Interpretation")
md.append("")
if gate_status == "PASS":
    md.append("**The empirical feasibility gate passes.** The next phase is to freeze the modern sample, normalize citation outcomes by topic-year/age, formalize the emergence construct, construct within-topic early-vs-late comparisons, and estimate pre-trend/selection diagnostics before any substantive hypothesis claims.")
else:
    md.append("**The empirical feasibility gate does not pass under the preset thresholds.** Do not estimate the headline hypotheses yet. The next phase must diagnose which constraint fails (firm breadth, comparable topics, early/late balance, follow-up, or network coverage) and revise the design without relaxing criteria merely to manufacture significance.")
md.append("")
md.append("## Semantics / safeguards")
md.append("")
md.append("- Corporate topic rows are multi-label; topic-row sums are not described as unique publication totals.")
md.append("- Collaboration-country rows are used for country breadth/diversity. The collaborator-institution count is not treated as a globally distinct annual institution count.")
md.append("- Records after 8 September 2026 are not treated as observed outcomes; the current gate caps company entries at 2024 and emergence cohorts at 2021 to preserve follow-up.")
md.append("- Raw citations are not the primary outcome at this stage; citation-age and topic-year normalization is reserved for the next phase.")

(OUT / "FEASIBILITY_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
