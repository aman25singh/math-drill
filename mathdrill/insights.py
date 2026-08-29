"""Charts for a drill log.

Plotting only. Every number shown here is computed by
:mod:`mathdrill.features`, which is importable and testable on its own.

This module used to run its whole body at import time, with no
``if __name__ == "__main__"`` guard, so importing it opened a chart window and
could call ``sys.exit``. Nothing here executes on import any more.
"""

from __future__ import annotations

import argparse
import sys

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from . import features
from .features import NoDataError
from .storage import SessionDataError, data_file, load_sessions


def build_figure(df: pd.DataFrame):
    """Draw the analysis grid for the already-flagged rows in ``df``."""
    sns.set_style("whitegrid")
    fig, axes = plt.subplots(2, 4, figsize=(22, 9))
    axes = axes.flatten()

    # 1. Average time by operation.
    avg_op = df.groupby("operation", observed=True).agg(
        avg_time=("time_taken_sec", "mean"), count=("operation", "count")
    )
    avg_op = avg_op.sort_values("avg_time")
    axes[0].bar(avg_op.index, avg_op["avg_time"], color="skyblue")
    axes[0].set_title("Avg Time by Operation")
    axes[0].set_ylabel("Seconds")
    for i, (_, row) in enumerate(avg_op.iterrows()):
        axes[0].text(
            i,
            row["avg_time"],
            f"n={int(row['count'])}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    # 2. The headline: which digits cost you time.
    try:
        digits = features.digit_difficulty(df)
        sns.heatmap(
            digits[["avg_time", "error_rate"]],
            annot=True,
            fmt=".2f",
            cmap="YlOrRd",
            ax=axes[1],
        )
        axes[1].set_title("Digits That Trip You Up")
    except NoDataError as exc:
        _placeholder(axes[1], "Digits That Trip You Up", str(exc))

    # 3. Time against operand size.
    sns.regplot(
        data=df,
        x="max_operand",
        y="time_taken_sec",
        scatter_kws={"alpha": 0.5},
        line_kws={"color": "blue"},
        ax=axes[2],
    )
    axes[2].set_title("Time vs Operand Size")

    # 4. Response time over the session.
    ordered = features.response_time_series(df)
    sns.lineplot(
        data=ordered,
        x="question_number",
        y="time_taken_sec",
        ax=axes[3],
        label="Time",
        color="gray",
    )
    sns.lineplot(
        data=ordered,
        x="question_number",
        y="rolling",
        ax=axes[3],
        label="Rolling Avg",
        color="purple",
    )
    axes[3].set_title("Response Time (with Rolling Avg)")

    # 5. Accuracy by how long the answer took.
    time_perf = features.accuracy_by_time_bucket(df)
    axes[4].bar(time_perf.index.astype(str), time_perf.values, color="salmon")
    axes[4].set_ylim(0, 1)
    axes[4].set_title("Accuracy by Time Bucket")

    # 6. What actually slows you down, as a difference from baseline.
    try:
        comparison = features.feature_comparison(df).head(8)
        # hue= is set explicitly; passing palette= without it is deprecated in
        # seaborn 0.14 and warns on current versions.
        sns.barplot(
            data=comparison,
            x="delta",
            y="description",
            hue="description",
            palette="coolwarm",
            legend=False,
            ax=axes[5],
        )
        axes[5].set_title("Slowest Patterns (vs baseline)")
        axes[5].set_xlabel("Extra seconds vs baseline")
        axes[5].set_ylabel("")
    except NoDataError as exc:
        _placeholder(axes[5], "Slowest Patterns (vs baseline)", str(exc))

    # 7. Session summary text.
    axes[6].axis("off")
    summary = features.session_summary(df)
    qpm = summary["questions_per_min"]
    qpm_text = "n/a" if pd.isna(qpm) else f"{qpm:.1f}"
    axes[6].text(
        0,
        0.5,
        (
            f"Session: {summary['session_name']}\n"
            f"Total: {summary['total']} | "
            f"Correct: {summary['correct']} | "
            f"Incorrect: {summary['incorrect']}\n"
            f"Accuracy: {summary['accuracy'] * 100:.0f}%\n"
            f"Avg Time: {summary['avg_time_sec']:.2f}s\n"
            f"Speed: {qpm_text} Q/min"
        ),
        fontsize=12,
        verticalalignment="center",
    )
    axes[6].set_title("Session Summary")

    # 8. Where the errors are.
    errors = features.error_counts_by_operation(df)
    if errors.empty:
        _placeholder(axes[7], "Error Distribution by Operation", "No wrong answers.")
    else:
        sns.barplot(
            x=errors.index,
            y=errors.values,
            hue=errors.index,
            palette="Reds",
            legend=False,
            ax=axes[7],
        )
        axes[7].set_title("Error Distribution by Operation")
        axes[7].set_ylabel("Count")

    fig.tight_layout()
    return fig


def _placeholder(ax, title, message):
    ax.axis("off")
    ax.set_title(title)
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=9, wrap=True)


def main(argv: list[str] | None = None) -> int:
    """Load, analyse, and show. Returns a process exit code."""
    parser = argparse.ArgumentParser(
        prog="math-drill-insights",
        description="Analyse Math Drill sessions and show the charts.",
    )
    parser.add_argument(
        "session_name",
        nargs="?",
        help="Only analyse this session. Omit to analyse every session.",
    )
    parser.add_argument("--file", dest="path", default=None, help="Path to a session JSON file.")
    parser.add_argument(
        "--save",
        metavar="PNG",
        default=None,
        help="Write the figure to a PNG instead of opening a window.",
    )
    args = parser.parse_args(argv)

    try:
        sessions = load_sessions(args.path)
    except SessionDataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not sessions:
        print(f"No session data found in {args.path or data_file()}. Play a session first.")
        return 0

    df = features.to_dataframe(sessions)

    try:
        df = features.filter_session(df, args.session_name)
        df = features.compute_insight_flags(df)
    except NoDataError as exc:
        print(exc)
        return 0

    if len(df) < 20:
        print(
            f"Note: only {len(df)} answered question(s) available. "
            "The per-feature comparisons need several sessions before they "
            "mean much."
        )

    figure = build_figure(df)
    if args.save:
        figure.savefig(args.save, dpi=110)
        print(f"Saved {args.save}")
    else:
        plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
