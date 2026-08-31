from pathlib import Path

from gmsdl.analytics.google_patents import COLUMNS, TABLE, build_sql
from gmsdl.registry import load_registry


def test_google_patents_sql_is_bounded_and_explicit():
    sql = build_sql("US", 2025)
    assert f"FROM `{TABLE}`" in sql
    assert "SELECT *" not in sql.upper()
    assert "country_code = @country" in sql
    assert "publication_date BETWEEN @lo AND @hi" in sql
    for required in [
        "publication_number",
        "application_number",
        "family_id",
        "assignee_harmonized",
        "inventor_harmonized",
        "cpc",
        "citation",
    ]:
        assert required in COLUMNS
        assert required in sql


def test_patent_source_policy_is_nonblocking():
    registry_dir = Path(__file__).resolve().parents[1] / "registry"
    sources = {s.id: s for s in load_registry(registry_dir)}
    gp = sources["GOOGLE_PATENTS_PUBLIC"]
    epo = sources["EPO_OPS"]
    uspto = sources["USPTO_ODP"]
    pv = sources["PATENTSVIEW"]

    assert gp.enabled is False
    assert gp.params["table"] == TABLE
    assert gp.params["dedicated_workflow"] == "google-patents.yml"
    assert epo.enabled is False
    assert epo.params["role"] == "validation_enrichment"
    assert epo.params["free_weekly_bytes"] == 4 * 1024**3
    assert uspto.enabled is False
    assert pv.enabled is False
