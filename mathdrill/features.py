"""Feature extraction and metrics over answered questions.

This is the distinctive part of the project: it turns a log of answers into a
statement about *which number patterns cost you time*. It uses pandas but
imports no plotting library and no GUI toolkit, so it can be tested directly
and reused by any frontend.

Nothing here reads a file or calls ``sys.exit``; callers decide what to do
about missing data.
"""

from __future__ import annotations

import pandas as pd

#: Boolean features. Each is compared against its own false-subset, because
#: "carry additions took 4.9s" only means something next to "non-carry
#: additions took 3.4s".
BOOLEAN_FEATURES: tuple[str, ...] = (
    "is_carry_addition",
    "is_borrow_subtraction",
    "is_round_operand_1",
    "is_round_operand_2",
) + tuple(f"has_{d}" for d in range(1, 10))

#: Numeric features. These are binned before comparison; averaging a numeric
#: column's "true set" is meaningless.
NUMERIC_FEATURES: tuple[str, ...] = (
    "num_digits_op1",
    "num_digits_op2",
    "operand_diff",
    "max_operand",
)

#: Human-readable labels for the feature names above.
FEATURE_LABELS: dict[str, str] = {
    "is_carry_addition": "addition with a carry",
    "is_borrow_subtraction": "subtraction with a borrow",
    "is_round_operand_1": "first operand is a multiple of 10",
    "is_round_operand_2": "second operand is a multiple of 10",
    "num_digits_op1": "digits in first operand",
    "num_digits_op2": "digits in second operand",
    "operand_diff": "gap between operands",
    "max_operand": "larger operand",
    **{f"has_{d}": f"an operand containing {d}" for d in range(1, 10)},
}


class NoDataError(RuntimeError):
    """Raised when there is nothing to analyse.

    This replaces the old ``sys.exit(0)`` calls that lived inside the feature
    code, so the analysis logic stays importable and testable.
    """


def flatten_sessions(sessions: list[dict]) -> list[dict]:
    """Flatten stored sessions into one row per answered question.

    Each row carries its session's ``session_name`` and ``duration`` so
    per-session filtering and correct questions-per-minute both stay possible
    after flattening.
    """
    rows: list[dict] = []
    for session_index, session in enumerate(sessions):
        insights = session.get("insights") or []
        for i, insight in enumerate(insights):
            rows.append(
                {
                    "session_name": session.get("session_name", ""),
                    "duration": session.get("duration", 0),
                    "index": i + 1,
                    **insight,
                    "_session_index": session_index,
                }
            )
    return rows


def to_dataframe(sessions: list[dict]) -> pd.DataFrame:
    """Build a DataFrame of answered questions from stored sessions."""
    return pd.DataFrame(flatten_sessions(sessions))


def filter_session(df: pd.DataFrame, session_name: str | None) -> pd.DataFrame:
    """Restrict to one session by name.

    Historically the caller filtered here and then ``compute_insight_flags``
    silently rebuilt the DataFrame from the unfiltered rows, so
    ``insights.py <session>`` analysed every session. Keeping the filter and
    the feature computation as separate pure functions on an explicit
    DataFrame is what stops that from recurring.
    """
    if df is None or df.empty:
        raise NoDataError("No session data found. Play a session first.")
    if not session_name:
        return df
    filtered = df[df["session_name"] == session_name].copy()
    if filtered.empty:
        raise NoDataError(f"No data found for session {session_name!r}.")
    return filtered


def compute_insight_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add the derived feature columns used by the analysis.

    Operates on the DataFrame it is given -- it does not reach back to any
    module-level data. Returns a copy; the input is left alone.
    """
    if df is None or df.empty:
        raise NoDataError("No session data found. Play a session first.")

    missing = {"operation", "operand_1", "operand_2"} - set(df.columns)
    if missing:
        raise NoDataError(
            f"Session data is missing required column(s): {', '.join(sorted(missing))}."
        )

    df = df.copy()
    op1 = df["operand_1"].astype(int)
    op2 = df["operand_2"].astype(int)

    df["is_carry_addition"] = (df["operation"] == "add") & ((op1 % 10 + op2 % 10) >= 10)
    df["is_borrow_subtraction"] = (df["operation"] == "sub") & ((op1 % 10) < (op2 % 10))

    op1_str = op1.abs().astype(str)
    op2_str = op2.abs().astype(str)
    for d in range(1, 10):
        df[f"has_{d}"] = op1_str.str.contains(str(d)) | op2_str.str.contains(str(d))

    df["is_round_operand_1"] = op1 % 10 == 0
    df["is_round_operand_2"] = op2 % 10 == 0
    df["num_digits_op1"] = op1_str.str.len()
    df["num_digits_op2"] = op2_str.str.len()
    df["operand_diff"] = (op1 - op2).abs()
    df["max_operand"] = df[["operand_1", "operand_2"]].max(axis=1)

    # ``is_exact_division`` and ``is_decimal_division`` used to live here.
    # Division is generated exact by construction (see core.generate_question),
    # so the first was always true for div rows -- a restatement of
    # ``operation == "div"`` -- and the second could never be true at all.
    # Operation-level timing already covers this, so both were removed.
    return df


def digit_difficulty(df: pd.DataFrame, min_samples: int = 1) -> pd.DataFrame:
    """Average time and error rate for questions containing each digit 1-9.

    This is the headline metric: it is what lets the app say a 9 in an operand
    costs you materially more than a 1.
    """
    if df is None or df.empty:
        raise NoDataError("No session data found. Play a session first.")

    rows = []
    for d in range(1, 10):
        column = f"has_{d}"
        mask = df[column] if column in df.columns else None
        if mask is None:
            continue
        subset = df[mask]
        if len(subset) < min_samples:
            continue
        rows.append(
            {
                "digit": d,
                "avg_time": subset["time_taken_sec"].mean(),
                "error_rate": 1 - subset["correctness"].mean(),
                "n": len(subset),
            }
        )
    if not rows:
        raise NoDataError("Not enough data to compare digits yet.")
    return (
        pd.DataFrame(rows)
        .set_index("digit")
        .sort_values("avg_time", ascending=False, kind="stable", key=lambda s: s.round(10))
    )


def _numeric_bins(series: pd.Series, max_bins: int = 4) -> pd.Series | None:
    """Bin a numeric feature, preferring quantiles and falling back to cuts."""
    distinct = series.nunique(dropna=True)
    if distinct < 2:
        return None
    bins = min(max_bins, distinct)
    try:
        binned = pd.qcut(series, q=bins, duplicates="drop")
    except (ValueError, IndexError):
        binned = None
    if binned is None or binned.nunique(dropna=True) < 2:
        try:
            binned = pd.cut(series, bins=bins, duplicates="drop")
        except (ValueError, IndexError):
            return None
    if binned.nunique(dropna=True) < 2:
        return None
    return binned


def feature_comparison(df: pd.DataFrame, min_samples: int = 5) -> pd.DataFrame:
    """Compare answer time across feature groups.

    Boolean features compare their true-subset against their false-subset --
    the *difference* is the insight, not the absolute time. Numeric features
    are binned and each bin is compared against the overall mean.

    The old implementation did ``df[df[feat]] if df[feat].dtype == bool else df``,
    which handed the *entire* DataFrame to every numeric feature. Those rows
    then reported the global mean while claiming to describe a feature.

    Returns columns: ``feature``, ``label``, ``group``, ``avg_time``,
    ``baseline_time``, ``delta``, ``accuracy``, ``n``, ``baseline_n``.
    """
    if df is None or df.empty:
        raise NoDataError("No session data found. Play a session first.")

    rows: list[dict] = []

    for feature in BOOLEAN_FEATURES:
        if feature not in df.columns:
            continue
        mask = df[feature].astype(bool)
        true_set = df[mask]
        false_set = df[~mask]
        # Both sides must be substantial: a comparison against two rows is noise.
        if len(true_set) < min_samples or len(false_set) < min_samples:
            continue
        true_time = true_set["time_taken_sec"].mean()
        false_time = false_set["time_taken_sec"].mean()
        rows.append(
            {
                "feature": feature,
                "label": FEATURE_LABELS.get(feature, feature),
                "group": "true",
                "avg_time": true_time,
                "baseline_time": false_time,
                "delta": true_time - false_time,
                "accuracy": true_set["correctness"].mean(),
                "n": len(true_set),
                "baseline_n": len(false_set),
            }
        )

    overall_time = df["time_taken_sec"].mean()
    for feature in NUMERIC_FEATURES:
        if feature not in df.columns:
            continue
        binned = _numeric_bins(df[feature])
        if binned is None:
            continue
        for interval, subset in df.groupby(binned, observed=True):
            if len(subset) < min_samples:
                continue
            avg_time = subset["time_taken_sec"].mean()
            rows.append(
                {
                    "feature": feature,
                    "label": FEATURE_LABELS.get(feature, feature),
                    "group": str(interval),
                    "avg_time": avg_time,
                    "baseline_time": overall_time,
                    "delta": avg_time - overall_time,
                    "accuracy": subset["correctness"].mean(),
                    "n": len(subset),
                    "baseline_n": len(df),
                }
            )

    if not rows:
        raise NoDataError(
            "Not enough data yet to compare features. "
            f"Each group needs at least {min_samples} questions."
        )

    result = pd.DataFrame(rows)
    result["description"] = result.apply(
        lambda r: r["label"] if r["group"] == "true" else f"{r['label']} {r['group']}",
        axis=1,
    )
    return result.sort_values(
        "delta", ascending=False, kind="stable", key=lambda s: s.round(10)
    ).reset_index(drop=True)


def accuracy_by_time_bucket(df: pd.DataFrame) -> pd.Series:
    """Accuracy split by how long the answer took."""
    if df is None or df.empty:
        raise NoDataError("No session data found. Play a session first.")
    bins = [0, 2, 4, 6, float("inf")]
    labels = ["<2s", "2-4s", "4-6s", "6s+"]
    bucket = pd.cut(df["time_taken_sec"], bins=bins, labels=labels, include_lowest=True)
    # observed=True is explicit: the default flipped in pandas 2.x and emits a
    # FutureWarning when grouping on a categorical.
    return df.groupby(bucket, observed=True)["correctness"].mean().reindex(labels)


def error_counts_by_operation(df: pd.DataFrame) -> pd.Series:
    """How many wrong answers each operation accounts for."""
    if df is None or df.empty:
        raise NoDataError("No session data found. Play a session first.")
    return df[~df["correctness"].astype(bool)]["operation"].value_counts()


def session_summary(df: pd.DataFrame) -> dict:
    """Headline numbers for the rows in ``df``.

    Questions-per-minute is computed from the sessions' *configured durations*,
    not from the span between the first and last timestamp. The old formula,
    ``len(df) / (timestamp.max() - timestamp.min()) * 60``, raised
    ZeroDivisionError on a single-question session and, across sessions,
    included the real-world gaps between them -- so a drill played on Monday
    and another on Friday reported a rate near zero.
    """
    if df is None or df.empty:
        raise NoDataError("No session data found. Play a session first.")

    total = len(df)
    correct = int(df["correctness"].astype(bool).sum())
    names = df["session_name"].unique()

    # Names are labels, not identities: two drills may share a name.
    key = "_session_index" if "_session_index" in df.columns else "session_name"
    groups = df.groupby(key, observed=True)
    durations = groups["duration"].first()
    total_seconds = float(durations.sum())
    rates = groups.size() * 60 / durations.where(durations > 0)
    session_count = len(durations)

    return {
        "session_name": names[0] if session_count == 1 else f"{session_count} sessions",
        "sessions": int(session_count),
        "total": total,
        "correct": correct,
        "incorrect": total - correct,
        "accuracy": correct / total,
        "avg_time_sec": float(df["time_taken_sec"].mean()),
        "total_duration_sec": total_seconds,
        "questions_per_min": float(rates.mean()),
    }


def response_time_series(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """Answer times in order, with a rolling average."""
    if df is None or df.empty:
        raise NoDataError("No session data found. Play a session first.")
    ordered = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
    ordered["question_number"] = ordered.index + 1
    ordered["rolling"] = ordered["time_taken_sec"].rolling(window, min_periods=1).mean()
    return ordered
