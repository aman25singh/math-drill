"""Tests for feature extraction and metrics.

These use hand-built session dictionaries, never the real data file.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from mathdrill import features
from mathdrill.features import NoDataError


def answer(
    operation="add",
    operand_1=1,
    operand_2=1,
    correct_answer=2,
    user_answer=2.0,
    time_taken_sec=1.0,
    correctness=True,
    timestamp=1000.0,
    question=None,
):
    symbol = {"add": "+", "sub": "-", "mul": "×", "div": "÷"}[operation]
    return {
        "timestamp": timestamp,
        "question": question or f"{operand_1} {symbol} {operand_2}",
        "operation": operation,
        "operand_1": operand_1,
        "operand_2": operand_2,
        "correct_answer": correct_answer,
        "user_answer": user_answer,
        "time_taken_sec": time_taken_sec,
        "correctness": correctness,
    }


def session(name="s1", duration=60, answers=None):
    return {"session_name": name, "duration": duration, "insights": answers or []}


def flagged(answers, **kwargs):
    df = features.to_dataframe([session(answers=answers, **kwargs)])
    return features.compute_insight_flags(df)


# ------------------------------------------------------------ carry / borrow


def test_is_carry_addition_true_for_17_plus_25():
    df = flagged([answer("add", 17, 25, correct_answer=42)])
    assert bool(df["is_carry_addition"].iloc[0]) is True


def test_is_carry_addition_false_for_12_plus_13():
    df = flagged([answer("add", 12, 13, correct_answer=25)])
    assert bool(df["is_carry_addition"].iloc[0]) is False


def test_is_carry_addition_is_false_for_non_addition():
    """A subtraction whose units digits sum past 10 is not a carry addition."""
    df = flagged([answer("sub", 17, 25, correct_answer=-8)])
    assert bool(df["is_carry_addition"].iloc[0]) is False


def test_carry_boundary_exactly_ten_counts_as_a_carry():
    df = flagged([answer("add", 15, 25, correct_answer=40)])
    assert bool(df["is_carry_addition"].iloc[0]) is True


def test_is_borrow_subtraction():
    rows = flagged(
        [
            answer("sub", 32, 17, correct_answer=15),  # 2 < 7 -> borrow
            answer("sub", 38, 12, correct_answer=26),  # 8 > 2 -> no borrow
        ]
    )
    assert list(rows["is_borrow_subtraction"]) == [True, False]


# ------------------------------------------------------------- digit flags


def test_digit_flags_cover_both_operands():
    df = flagged([answer("add", 19, 25, correct_answer=44)])
    row = df.iloc[0]
    for digit in (1, 9, 2, 5):
        assert bool(row[f"has_{digit}"]) is True, f"expected has_{digit}"
    for digit in (3, 4, 6, 7, 8):
        assert bool(row[f"has_{digit}"]) is False, f"unexpected has_{digit}"


def test_digit_flags_see_inside_multi_digit_operands():
    """A 7 in the tens place counts just as much as one in the units place."""
    df = flagged([answer("mul", 71, 4, correct_answer=284)])
    row = df.iloc[0]
    assert bool(row["has_7"]) is True
    assert bool(row["has_1"]) is True
    assert bool(row["has_4"]) is True
    assert bool(row["has_2"]) is False


def test_repeated_digit_is_still_a_single_flag():
    df = flagged([answer("add", 99, 11, correct_answer=110)])
    row = df.iloc[0]
    assert bool(row["has_9"]) is True
    assert bool(row["has_1"]) is True


# --------------------------------------------------------------- num_digits


@pytest.mark.parametrize(
    "value, expected",
    [(1, 1), (9, 1), (10, 2), (11, 2), (99, 2), (100, 3), (101, 3), (999, 3), (1000, 4)],
)
def test_num_digits_across_boundaries(value, expected):
    df = flagged([answer("add", value, 1, correct_answer=value + 1)])
    assert int(df["num_digits_op1"].iloc[0]) == expected


def test_num_digits_of_second_operand():
    df = flagged([answer("add", 1, 100, correct_answer=101)])
    assert int(df["num_digits_op2"].iloc[0]) == 3


def test_operand_diff_and_max_operand():
    df = flagged([answer("sub", 12, 100, correct_answer=-88)])
    assert int(df["operand_diff"].iloc[0]) == 88
    assert int(df["max_operand"].iloc[0]) == 100


def test_round_operand_flags():
    df = flagged([answer("mul", 40, 7, correct_answer=280)])
    assert bool(df["is_round_operand_1"].iloc[0]) is True
    assert bool(df["is_round_operand_2"].iloc[0]) is False


def test_dead_division_flags_are_gone():
    """Division is exact by construction, so both old flags were dead."""
    df = flagged([answer("div", 12, 4, correct_answer=3)])
    assert "is_decimal_division" not in df.columns
    assert "is_exact_division" not in df.columns


# ------------------------------------------------------- the filter regression


def test_compute_insight_flags_respects_a_prefiltered_dataframe():
    """Regression: the session filter used to be discarded.

    compute_insight_flags rebuilt its DataFrame from the module-level
    flattened_data, so `insights.py <session>` silently analysed every
    session. It must now operate only on the rows it is handed.
    """
    sessions = [
        session("morning", answers=[answer("add", 1, 1, correct_answer=2)] * 3),
        session("evening", answers=[answer("mul", 9, 9, correct_answer=81)] * 5),
    ]
    df = features.to_dataframe(sessions)
    assert len(df) == 8

    filtered = features.filter_session(df, "morning")
    flags = features.compute_insight_flags(filtered)

    assert len(flags) == 3
    assert set(flags["session_name"]) == {"morning"}
    assert not flags["has_9"].any()


def test_filter_session_rejects_an_unknown_name():
    df = features.to_dataframe(
        [session("morning", answers=[answer("add", 1, 1, correct_answer=2)])]
    )
    with pytest.raises(NoDataError, match="nope"):
        features.filter_session(df, "nope")


def test_filter_session_without_a_name_returns_everything():
    sessions = [
        session("a", answers=[answer()] * 2),
        session("b", answers=[answer()] * 3),
    ]
    df = features.to_dataframe(sessions)
    assert len(features.filter_session(df, None)) == 5


# ------------------------------------------------------- feature comparison


def test_boolean_feature_compares_true_against_false_subset():
    """The insight is the difference, not the absolute time."""
    slow = [answer("add", 9, 9, correct_answer=18, time_taken_sec=5.0)] * 6
    fast = [answer("add", 2, 2, correct_answer=4, time_taken_sec=1.0)] * 6
    df = flagged(slow + fast)

    comparison = features.feature_comparison(df, min_samples=5)
    row = comparison[comparison["feature"] == "has_9"].iloc[0]

    assert row["avg_time"] == pytest.approx(5.0)
    assert row["baseline_time"] == pytest.approx(1.0)
    assert row["delta"] == pytest.approx(4.0)
    assert row["n"] == 6
    assert row["baseline_n"] == 6


def test_numeric_features_are_binned_not_given_the_whole_frame():
    """Regression: numeric features used to report the global mean.

    The old code did `df[df[feat]] if df[feat].dtype == bool else df`, handing
    every numeric feature the entire DataFrame. Each such row then showed the
    overall average while claiming to describe that feature.
    """
    small = [answer("add", 2, 3, correct_answer=5, time_taken_sec=1.0) for _ in range(8)]
    large = [answer("add", 500, 400, correct_answer=900, time_taken_sec=6.0) for _ in range(8)]
    df = flagged(small + large)
    overall = df["time_taken_sec"].mean()

    comparison = features.feature_comparison(df, min_samples=5)
    numeric = comparison[comparison["feature"] == "num_digits_op1"]

    assert len(numeric) >= 2, "numeric feature should produce multiple bins"
    # No bin may simply restate the global mean over the whole frame.
    assert not (numeric["n"] == len(df)).any()
    assert numeric["avg_time"].min() < overall < numeric["avg_time"].max()


def test_feature_comparison_skips_groups_that_are_too_small():
    rows = [answer("add", 9, 9, correct_answer=18)] * 2 + [
        answer("add", 2, 2, correct_answer=4)
    ] * 20
    df = flagged(rows)
    comparison = features.feature_comparison(df, min_samples=5)
    assert "has_9" not in set(comparison["feature"])


def test_feature_comparison_raises_when_nothing_is_comparable():
    df = flagged([answer("add", 2, 3, correct_answer=5)])
    with pytest.raises(NoDataError):
        features.feature_comparison(df, min_samples=5)


# ------------------------------------------------------------------ summary


def test_questions_per_minute_uses_configured_duration():
    """9 answers in a 30s session is 18 Q/min, whatever the timestamps say."""
    rows = [answer(time_taken_sec=1.0, timestamp=1000.0 + i) for i in range(9)]
    df = flagged(rows, duration=30)
    summary = features.session_summary(df)
    assert summary["questions_per_min"] == pytest.approx(18.0)
    assert summary["total_duration_sec"] == pytest.approx(30.0)


def test_single_question_session_does_not_raise_zero_division():
    """Regression: the old formula divided by (timestamp.max - timestamp.min)."""
    df = flagged([answer(timestamp=1000.0)], duration=60)
    summary = features.session_summary(df)
    assert summary["total"] == 1
    assert summary["questions_per_min"] == pytest.approx(1.0)


def test_rate_across_sessions_ignores_the_gap_between_them():
    """Two sessions a week apart must not report a near-zero rate."""
    monday = session(
        "monday",
        duration=60,
        answers=[answer(timestamp=1000.0 + i) for i in range(10)],
    )
    friday = session(
        "friday",
        duration=60,
        answers=[answer(timestamp=1000.0 + 400_000 + i) for i in range(10)],
    )
    df = features.compute_insight_flags(features.to_dataframe([monday, friday]))

    summary = features.session_summary(df)
    assert summary["sessions"] == 2
    assert summary["total"] == 20
    # 20 questions over two 60s sessions = 10 Q/min, not 20/(400000/60).
    assert summary["questions_per_min"] == pytest.approx(10.0)
    assert summary["session_name"] == "2 sessions"


def test_summary_handles_a_zero_duration_session_without_crashing():
    df = flagged([answer()], duration=0)
    summary = features.session_summary(df)
    assert math.isnan(summary["questions_per_min"])


def test_digit_difficulty_ranks_slow_digits_first():
    rows = [answer("add", 9, 9, correct_answer=18, time_taken_sec=8.0)] * 3 + [
        answer("add", 1, 1, correct_answer=2, time_taken_sec=1.0)
    ] * 3
    df = flagged(rows)
    ranked = features.digit_difficulty(df)
    assert ranked.index[0] == 9
    assert ranked.loc[9, "avg_time"] == pytest.approx(8.0)
    assert ranked.loc[1, "avg_time"] == pytest.approx(1.0)


def test_accuracy_by_time_bucket():
    rows = [
        answer(time_taken_sec=1.0, correctness=True),
        answer(time_taken_sec=1.5, correctness=False),
        answer(time_taken_sec=7.0, correctness=False),
    ]
    df = flagged(rows)
    buckets = features.accuracy_by_time_bucket(df)
    assert buckets["<2s"] == pytest.approx(0.5)
    assert buckets["6s+"] == pytest.approx(0.0)


def test_error_counts_by_operation():
    rows = [
        answer("add", correctness=False),
        answer("add", correctness=False),
        answer("mul", correctness=True),
    ]
    df = flagged(rows)
    counts = features.error_counts_by_operation(df)
    assert counts["add"] == 2
    assert "mul" not in counts.index


# -------------------------------------------------------------- empty guards


def test_empty_dataframe_guard_is_preserved():
    """The old sys.exit guard became an exception, but it is still enforced."""
    empty = pd.DataFrame()
    for func in (
        features.compute_insight_flags,
        features.digit_difficulty,
        features.session_summary,
        features.accuracy_by_time_bucket,
        features.error_counts_by_operation,
        features.response_time_series,
    ):
        with pytest.raises(NoDataError):
            func(empty)


def test_missing_required_columns_is_reported_clearly():
    df = pd.DataFrame([{"session_name": "s", "duration": 60, "time_taken_sec": 1.0}])
    with pytest.raises(NoDataError, match="missing required column"):
        features.compute_insight_flags(df)


def test_flatten_tolerates_a_session_with_no_answers():
    assert features.flatten_sessions([session("empty", answers=[])]) == []
