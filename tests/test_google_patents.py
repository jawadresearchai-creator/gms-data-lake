from pathlib import Path

from gmsdl.analytics.google_patents import COLUMN_FAMILIES, COLUMNS, TABLE, build_sql
from gmsdl.registry import load_registry


def test_google_patents_sql_is_bounded_and_explicit():
    sql = build_sql("US", 2025, "id_dates")
    assert f"FROM `{TABLE}`" in sql
    assert "SELECT *" not in sql.upper()
    assert "country_code = @country" in sql
    assert "publication_date BETWEEN @lo AND @hi" in sql
    for required in ["publication_number", "application_number", "family_id"]:
        assert required in COLUMN_FAMILIES["id_dates"]
        assert required in sql


def test_google_patents_column_families_cover_core_research_graph():
    expected = {
        "entities": ["assignee_harmonized", "inventor_harmonized"],
        "classes": ["cpc", "ipc"],
        "citations": ["citation"],
        "text": ["title_localized", "abstract_localized"],
    }
    for family, cols in expected.items():
        sql = build_sql("US", None, family)
        assert "publication_date BETWEEN" not in sql
        for col in cols:
            assert col in COLUMNS
            assert col in COLUMN_FAMILIES[family]
            assert col in sql


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
