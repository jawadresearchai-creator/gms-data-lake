from gmsdl.analytics.openalex_curate import (
    curated_relpath,
    entity_from_key,
    is_scalar_duckdb_type,
    sql_ident,
    sql_literal,
)


def test_entity_from_key():
    assert entity_from_key("data/parquet/works/updated_date=2026-06-26/part_0001.parquet") == "works"
    assert entity_from_key("data/parquet/authors/manifest.json") == "authors"
    assert entity_from_key("other/path") is None


def test_curated_relpath():
    key = "data/parquet/works/updated_date=2026-06-26/part_0001.parquet"
    assert curated_relpath(key) == "WORK_MASTER/updated_date=2026-06-26/part_0001.parquet"
    assert curated_relpath("data/parquet/authors/manifest.json") is None
    assert curated_relpath("data/parquet/unknown/updated_date=2026-01-01/part.parquet") is None


def test_scalar_type_filter():
    for scalar in ["VARCHAR", "BIGINT", "BOOLEAN", "DATE", "TIMESTAMP", "DECIMAL(18,2)"]:
        assert is_scalar_duckdb_type(scalar)
    for nested in ["STRUCT(id VARCHAR)", "VARCHAR[]", "MAP(VARCHAR, BIGINT)", "INTEGER ARRAY"]:
        assert not is_scalar_duckdb_type(nested)


def test_sql_quoting():
    assert sql_ident('a"b') == '"a""b"'
    assert sql_literal("a'b") == "'a''b'"
