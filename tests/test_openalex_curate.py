from pathlib import Path

import duckdb

from gmsdl.analytics.openalex_curate import (
    curated_relpath,
    entity_from_key,
    is_scalar_duckdb_type,
    materialize_work_edges,
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


def test_materialize_work_edges_filters_and_deduplicates(tmp_path: Path):
    raw = tmp_path / "works.parquet"
    con = duckdb.connect()
    con.execute(f"""
      COPY (
        SELECT
          'W1'::VARCHAR AS id,
          ['W0','W0',NULL]::VARCHAR[] AS referenced_works,
          [
            struct_pack(id := 'T1', display_name := 'AI', score := 0.8),
            struct_pack(id := 'T1', display_name := 'AI', score := 0.9),
            struct_pack(id := NULL::VARCHAR, display_name := 'bad', score := 1.0)
          ] AS topics,
          [
            struct_pack(
              author := struct_pack(id := 'A1'), author_position := 'middle', is_corresponding := false,
              institutions := [struct_pack(id := 'I1', country_code := 'US')],
              countries := ['US','CA']
            ),
            struct_pack(
              author := struct_pack(id := 'A1'), author_position := 'first', is_corresponding := true,
              institutions := [struct_pack(id := 'I1', country_code := 'US')],
              countries := ['US','CA']
            ),
            struct_pack(
              author := struct_pack(id := NULL::VARCHAR), author_position := 'last', is_corresponding := false,
              institutions := [struct_pack(id := NULL::VARCHAR, country_code := 'US')],
              countries := ['US']
            )
          ] AS authorships
      ) TO '{raw.as_posix()}' (FORMAT PARQUET)
    """)
    con.close()

    outputs = materialize_work_edges(raw, tmp_path / "edges", "data/parquet/works/x.parquet")
    con = duckdb.connect()
    assert con.execute(f"SELECT COUNT(*) FROM read_parquet('{outputs['CITATION_EDGES'].as_posix()}')").fetchone()[0] == 1
    assert con.execute(f"SELECT COUNT(*) FROM read_parquet('{outputs['WORK_TOPIC_EDGES'].as_posix()}')").fetchone()[0] == 1
    assert float(con.execute(f"SELECT topic_score FROM read_parquet('{outputs['WORK_TOPIC_EDGES'].as_posix()}')").fetchone()[0]) == 0.9
    assert con.execute(f"SELECT COUNT(*) FROM read_parquet('{outputs['WORK_AUTHOR_EDGES'].as_posix()}')").fetchone()[0] == 1
    assert con.execute(f"SELECT author_position,is_corresponding FROM read_parquet('{outputs['WORK_AUTHOR_EDGES'].as_posix()}')").fetchone() == ('first', True)
    assert con.execute(f"SELECT COUNT(*) FROM read_parquet('{outputs['AUTHOR_INSTITUTION_EDGES'].as_posix()}')").fetchone()[0] == 1
    assert con.execute(f"SELECT COUNT(*) FROM read_parquet('{outputs['COUNTRY_COLLAB_EDGES'].as_posix()}')").fetchone()[0] == 1
    con.close()
