"""Quality report layout. Counts only; no real Chama data is used."""
import pandas as pd

from chama.validation.report import as_tables


def test_one_table_per_chama_with_a_column_per_year():
    report = pd.DataFrame(
        {
            "chama_id": ["chama_a", "chama_a", "chama_a", "chama_b"],
            "year": [2014, 2015, 2014, 2014],
            "table_name": ["statements", "statements", "statements", "statements"],
            "measure_order": [10, 10, 11, 10],
            "measure": ["lines", "lines", "flagged", "lines"],
            "value": [167, 150, 2, 90],
        }
    )
    tables = as_tables(report)
    assert set(tables) == {"chama_a", "chama_b"}
    a = tables["chama_a"]
    assert list(a.columns) == [2014, 2015]
    assert a.loc[("statements", "lines"), 2015] == 150
    assert a.loc[("statements", "flagged"), 2015] == 0  # missing years show 0
    assert list(a.index.get_level_values("measure")) == ["lines", "flagged"]  # report order kept
