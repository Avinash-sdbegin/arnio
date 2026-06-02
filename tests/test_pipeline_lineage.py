"""Tests for row lineage metadata through filtering and drop steps.

Covers the ``track_lineage=True`` path added to :func:`arnio.pipeline` in
issue #648.  All fixtures use :func:`arnio.from_pandas` so no C++ CSV reader
is required.

Run with::

    pytest tests/test_pipeline_lineage.py -v
"""

from __future__ import annotations

import pandas as pd
import pytest

import arnio as ar
from arnio.pipeline import LineageReport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_frame(data: dict) -> ar.ArFrame:
    """Convenience wrapper for test frame construction."""
    return ar.from_pandas(pd.DataFrame(data))


# ---------------------------------------------------------------------------
# LineageReport: importability and type
# ---------------------------------------------------------------------------


class TestLineageReportImport:
    def test_importable_from_arnio_top_level(self):
        from arnio import LineageReport as LR  # noqa: F401

        assert LR is LineageReport

    def test_is_dataclass_frozen(self):
        """LineageReport must be immutable."""
        report = LineageReport(dropped_by_step={}, total_dropped=0)
        with pytest.raises((AttributeError, TypeError)):
            report.total_dropped = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# track_lineage type validation
# ---------------------------------------------------------------------------


class TestTrackLineageTypeValidation:
    def test_track_lineage_wrong_type_raises_type_error(self):
        frame = _make_frame({"x": [1, 2, 3]})
        with pytest.raises(TypeError, match="track_lineage"):
            ar.pipeline(frame, [("strip_whitespace",)], track_lineage="yes")  # type: ignore[arg-type]

    def test_track_lineage_int_raises_type_error(self):
        frame = _make_frame({"x": [1, 2, 3]})
        with pytest.raises(TypeError, match="track_lineage"):
            ar.pipeline(frame, [("strip_whitespace",)], track_lineage=1)  # type: ignore[arg-type]

    def test_track_lineage_none_raises_type_error(self):
        frame = _make_frame({"x": [1, 2, 3]})
        with pytest.raises(TypeError, match="track_lineage"):
            ar.pipeline(frame, [("strip_whitespace",)], track_lineage=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Default behaviour unchanged
# ---------------------------------------------------------------------------


class TestDefaultBehaviourUnchanged:
    def test_track_lineage_false_returns_arframe(self):
        frame = _make_frame({"name": ["Alice", None, "Charlie"]})
        result = ar.pipeline(frame, [("drop_nulls",)], track_lineage=False)
        assert isinstance(result, ar.ArFrame)

    def test_track_lineage_false_no_sentinel_column_in_output(self):
        frame = _make_frame({"name": ["Alice", "Bob"]})
        result = ar.pipeline(frame, [("strip_whitespace",)], track_lineage=False)
        df = ar.to_pandas(result)
        assert "__arnio_lineage_id__" not in df.columns

    def test_track_lineage_default_is_false(self):
        """Omitting track_lineage entirely must behave like track_lineage=False."""
        frame = _make_frame({"name": ["Alice", None]})
        result = ar.pipeline(frame, [("drop_nulls",)])
        assert isinstance(result, ar.ArFrame)


# ---------------------------------------------------------------------------
# Sentinel column stripped from output
# ---------------------------------------------------------------------------


class TestSentinelColumnStripped:
    def test_sentinel_column_not_present_in_output(self):
        frame = _make_frame({"score": [1.0, None, 3.0]})
        result, _ = ar.pipeline(frame, [("drop_nulls",)], track_lineage=True)
        df = ar.to_pandas(result)
        assert "__arnio_lineage_id__" not in df.columns

    def test_sentinel_column_not_present_after_non_dropping_step(self):
        frame = _make_frame({"name": ["  Alice  ", "  Bob  "]})
        result, _ = ar.pipeline(frame, [("strip_whitespace",)], track_lineage=True)
        df = ar.to_pandas(result)
        assert "__arnio_lineage_id__" not in df.columns

    def test_output_shape_excludes_sentinel(self):
        """Result must have the same number of columns as the original frame."""
        frame = _make_frame({"a": [1, None, 3], "b": ["x", "y", "z"]})
        original_col_count = len(ar.to_pandas(frame).columns)
        result, _ = ar.pipeline(frame, [("drop_nulls",)], track_lineage=True)
        result_col_count = len(ar.to_pandas(result).columns)
        assert result_col_count == original_col_count


# ---------------------------------------------------------------------------
# drop_nulls lineage
# ---------------------------------------------------------------------------


class TestLineageDropNulls:
    def test_drop_nulls_records_correct_indices(self):
        #  Row 0: Alice 30   — kept
        #  Row 1: None  25   — dropped (null name)
        #  Row 2: Charlie 35 — kept
        frame = _make_frame({"name": ["Alice", None, "Charlie"], "age": [30, 25, 35]})
        _, lineage = ar.pipeline(frame, [("drop_nulls",)], track_lineage=True)
        assert lineage.dropped_by_step["drop_nulls"] == [1]

    def test_drop_nulls_subset_records_only_subset_drops(self):
        #  Row 0: score=None — kept (age column is the subset, age=30 is fine)
        #  Row 1: age=None   — dropped
        frame = _make_frame({"score": [None, 9.0], "age": [30, None]})
        _, lineage = ar.pipeline(
            frame, [("drop_nulls", {"subset": ["age"]})], track_lineage=True
        )
        assert lineage.dropped_by_step["drop_nulls"] == [1]

    def test_drop_nulls_multiple_null_rows(self):
        frame = _make_frame({"x": [1, None, None, 4]})
        _, lineage = ar.pipeline(frame, [("drop_nulls",)], track_lineage=True)
        assert lineage.dropped_by_step["drop_nulls"] == [1, 2]

    def test_drop_nulls_no_nulls_empty_drop_list(self):
        frame = _make_frame({"x": [1, 2, 3]})
        _, lineage = ar.pipeline(frame, [("drop_nulls",)], track_lineage=True)
        assert lineage.dropped_by_step["drop_nulls"] == []


# ---------------------------------------------------------------------------
# drop_duplicates lineage
# ---------------------------------------------------------------------------


class TestLineageDropDuplicates:
    def test_drop_duplicates_records_correct_indices(self):
        #  Row 0: Alice 30  — kept (first occurrence)
        #  Row 1: Bob   25  — kept
        #  Row 2: Alice 30  — dropped (duplicate of row 0)
        frame = _make_frame({"name": ["Alice", "Bob", "Alice"], "age": [30, 25, 30]})
        _, lineage = ar.pipeline(frame, [("drop_duplicates",)], track_lineage=True)
        assert lineage.dropped_by_step["drop_duplicates"] == [2]

    def test_drop_duplicates_keep_last_drops_first(self):
        frame = _make_frame({"name": ["Alice", "Bob", "Alice"], "age": [30, 25, 30]})
        _, lineage = ar.pipeline(
            frame, [("drop_duplicates", {"keep": "last"})], track_lineage=True
        )
        assert lineage.dropped_by_step["drop_duplicates"] == [0]

    def test_drop_duplicates_no_dupes_empty_drop_list(self):
        frame = _make_frame({"name": ["Alice", "Bob", "Charlie"]})
        _, lineage = ar.pipeline(frame, [("drop_duplicates",)], track_lineage=True)
        assert lineage.dropped_by_step["drop_duplicates"] == []


# ---------------------------------------------------------------------------
# filter_rows lineage
# ---------------------------------------------------------------------------


class TestLineageFilterRows:
    def test_filter_rows_records_correct_indices(self):
        #  Row 0: age=30 — dropped (not > 25 is False; 30 > 25 so KEPT)
        #  Wait: filter_rows keeps rows WHERE condition is True.
        #  age > 25: rows 0 (30>25=True), 2 (35>25=True) kept; row 1 (25>25=False) dropped.
        frame = _make_frame({"age": [30, 25, 35]})
        _, lineage = ar.pipeline(
            frame,
            [("filter_rows", {"column": "age", "op": ">", "value": 25})],
            track_lineage=True,
        )
        assert lineage.dropped_by_step["filter_rows"] == [1]

    def test_filter_rows_equality_drops_non_matching(self):
        #  Only row 0 (Alice) matches == "Alice"; rows 1 and 2 are dropped.
        frame = _make_frame({"name": ["Alice", "Bob", "Charlie"]})
        _, lineage = ar.pipeline(
            frame,
            [("filter_rows", {"column": "name", "op": "==", "value": "Alice"})],
            track_lineage=True,
        )
        assert lineage.dropped_by_step["filter_rows"] == [1, 2]

    def test_filter_rows_no_rows_dropped_empty_list(self):
        frame = _make_frame({"age": [30, 35, 40]})
        _, lineage = ar.pipeline(
            frame,
            [("filter_rows", {"column": "age", "op": ">", "value": 20})],
            track_lineage=True,
        )
        assert lineage.dropped_by_step["filter_rows"] == []


# ---------------------------------------------------------------------------
# Multi-step accumulation
# ---------------------------------------------------------------------------


class TestLineageMultiStep:
    def test_multi_step_each_step_records_only_its_own_drops(self):
        #  Row 0: Alice 30   — kept through all steps
        #  Row 1: None  25   — dropped by drop_nulls
        #  Row 2: Alice 30   — dropped by drop_duplicates (dup of row 0)
        frame = _make_frame({"name": ["Alice", None, "Alice"], "age": [30, 25, 30]})
        _, lineage = ar.pipeline(
            frame,
            [("drop_nulls",), ("drop_duplicates",)],
            track_lineage=True,
        )
        assert lineage.dropped_by_step["drop_nulls"] == [1]
        assert lineage.dropped_by_step["drop_duplicates"] == [2]

    def test_multi_step_indices_refer_to_original_rows(self):
        """Indices in dropped_by_step are always original-frame row indices."""
        #  Original: rows 0,1,2,3
        #  After drop_nulls:  rows 0,2,3 survive (row 1 has null)
        #  After filter_rows(age>28): from {0,2,3}, row 2 (age=25) is dropped
        #  So drop_nulls drops original row 1; filter_rows drops original row 2.
        frame = _make_frame(
            {"name": ["Alice", None, "Bob", "Charlie"], "age": [30, 25, 25, 35]}
        )
        _, lineage = ar.pipeline(
            frame,
            [
                ("drop_nulls",),
                ("filter_rows", {"column": "age", "op": ">", "value": 28}),
            ],
            track_lineage=True,
        )
        assert lineage.dropped_by_step["drop_nulls"] == [1]
        assert lineage.dropped_by_step["filter_rows"] == [2]

    def test_multi_step_total_dropped_matches_sum(self):
        frame = _make_frame({"name": ["Alice", None, "Alice"], "age": [30, 25, 30]})
        _, lineage = ar.pipeline(
            frame,
            [("drop_nulls",), ("drop_duplicates",)],
            track_lineage=True,
        )
        expected = sum(len(v) for v in lineage.dropped_by_step.values())
        assert lineage.total_dropped == expected
        assert lineage.total_dropped == 2

    def test_three_step_pipeline_accumulates(self):
        #  Row 0: "Alice" age=30
        #  Row 1: None    age=25  → dropped by drop_nulls
        #  Row 2: "Alice" age=30  → dropped by drop_duplicates
        #  Row 3: " Bob " age=40  → strip_whitespace does NOT drop it
        frame = _make_frame(
            {"name": ["Alice", None, "Alice", " Bob "], "age": [30, 25, 30, 40]}
        )
        _, lineage = ar.pipeline(
            frame,
            [("drop_nulls",), ("strip_whitespace",), ("drop_duplicates",)],
            track_lineage=True,
        )
        assert lineage.dropped_by_step["drop_nulls"] == [1]
        assert lineage.dropped_by_step["strip_whitespace"] == []
        assert lineage.dropped_by_step["drop_duplicates"] == [2]
        assert lineage.total_dropped == 2


# ---------------------------------------------------------------------------
# Non-dropping step produces empty entry
# ---------------------------------------------------------------------------


class TestLineageNonDroppingStep:
    def test_non_dropping_step_has_empty_entry(self):
        frame = _make_frame({"name": ["  Alice  ", "  Bob  "]})
        _, lineage = ar.pipeline(frame, [("strip_whitespace",)], track_lineage=True)
        assert "strip_whitespace" in lineage.dropped_by_step
        assert lineage.dropped_by_step["strip_whitespace"] == []

    def test_non_dropping_step_total_dropped_is_zero(self):
        frame = _make_frame({"name": ["Alice", "Bob"]})
        _, lineage = ar.pipeline(frame, [("strip_whitespace",)], track_lineage=True)
        assert lineage.total_dropped == 0

    def test_rename_columns_has_empty_entry(self):
        frame = _make_frame({"old_name": [1, 2, 3]})
        _, lineage = ar.pipeline(
            frame,
            [("rename_columns", {"old_name": "new_name"})],
            track_lineage=True,
        )
        assert lineage.dropped_by_step.get("rename_columns", []) == []


# ---------------------------------------------------------------------------
# LineageReport.total_dropped
# ---------------------------------------------------------------------------


class TestLineageTotalDropped:
    def test_total_dropped_matches_sum_of_dropped_by_step(self):
        frame = _make_frame({"x": [1, None, None, 4, None]})
        _, lineage = ar.pipeline(frame, [("drop_nulls",)], track_lineage=True)
        assert lineage.total_dropped == sum(
            len(v) for v in lineage.dropped_by_step.values()
        )

    def test_total_dropped_zero_when_nothing_dropped(self):
        frame = _make_frame({"x": [1, 2, 3]})
        _, lineage = ar.pipeline(frame, [("strip_whitespace",)], track_lineage=True)
        assert lineage.total_dropped == 0

    def test_total_dropped_all_rows(self):
        frame = _make_frame({"x": [None, None, None]})
        _, lineage = ar.pipeline(frame, [("drop_nulls",)], track_lineage=True)
        assert lineage.total_dropped == 3


# ---------------------------------------------------------------------------
# LineageReport.to_pandas()
# ---------------------------------------------------------------------------


class TestLineageReportToPandas:
    def test_to_pandas_returns_dataframe(self):
        frame = _make_frame({"x": [1, None, 3]})
        _, lineage = ar.pipeline(frame, [("drop_nulls",)], track_lineage=True)
        df = lineage.to_pandas()
        assert isinstance(df, pd.DataFrame)

    def test_to_pandas_schema_has_correct_columns(self):
        frame = _make_frame({"x": [1, None, 3]})
        _, lineage = ar.pipeline(frame, [("drop_nulls",)], track_lineage=True)
        df = lineage.to_pandas()
        assert list(df.columns) == ["original_index", "step"]

    def test_to_pandas_correct_rows(self):
        #  Rows 1 and 2 are null → dropped by drop_nulls
        frame = _make_frame({"x": [1, None, None, 4]})
        _, lineage = ar.pipeline(frame, [("drop_nulls",)], track_lineage=True)
        df = lineage.to_pandas()
        assert set(df["original_index"].tolist()) == {1, 2}
        assert set(df["step"].tolist()) == {"drop_nulls"}

    def test_to_pandas_empty_when_nothing_dropped(self):
        frame = _make_frame({"x": [1, 2, 3]})
        _, lineage = ar.pipeline(frame, [("drop_nulls",)], track_lineage=True)
        df = lineage.to_pandas()
        assert len(df) == 0
        assert list(df.columns) == ["original_index", "step"]

    def test_to_pandas_multi_step_all_drops_present(self):
        frame = _make_frame({"name": ["Alice", None, "Alice"], "age": [30, 25, 30]})
        _, lineage = ar.pipeline(
            frame,
            [("drop_nulls",), ("drop_duplicates",)],
            track_lineage=True,
        )
        df = lineage.to_pandas()
        assert len(df) == 2
        assert set(df["step"].tolist()) == {"drop_nulls", "drop_duplicates"}
        null_row = df[df["step"] == "drop_nulls"]
        assert null_row["original_index"].iloc[0] == 1
        dup_row = df[df["step"] == "drop_duplicates"]
        assert dup_row["original_index"].iloc[0] == 2

    def test_to_pandas_row_count_equals_total_dropped(self):
        frame = _make_frame({"x": [1, None, 3, None, 5]})
        _, lineage = ar.pipeline(frame, [("drop_nulls",)], track_lineage=True)
        df = lineage.to_pandas()
        assert len(df) == lineage.total_dropped


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


class TestLineageReturnType:
    def test_track_lineage_true_returns_tuple(self):
        frame = _make_frame({"x": [1, 2]})
        out = ar.pipeline(frame, [("strip_whitespace",)], track_lineage=True)
        assert isinstance(out, tuple)
        assert len(out) == 2

    def test_track_lineage_true_first_element_is_arframe(self):
        frame = _make_frame({"x": [1, 2]})
        result, _ = ar.pipeline(frame, [("strip_whitespace",)], track_lineage=True)
        assert isinstance(result, ar.ArFrame)

    def test_track_lineage_true_second_element_is_lineage_report(self):
        frame = _make_frame({"x": [1, 2]})
        _, lineage = ar.pipeline(frame, [("strip_whitespace",)], track_lineage=True)
        assert isinstance(lineage, LineageReport)

    def test_empty_steps_with_track_lineage_returns_clean_frame(self):
        frame = _make_frame({"x": [1, 2, 3]})
        result, lineage = ar.pipeline(frame, [], track_lineage=True)
        assert isinstance(result, ar.ArFrame)
        assert lineage.total_dropped == 0
        df = ar.to_pandas(result)
        assert "__arnio_lineage_id__" not in df.columns
