"""Generate the README overview from explicitly synthetic, reproducible data.

Run from the project root: python -m scripts.render_demo
"""

import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from mathdrill.core import DrillConfig, build_answer_record, generate_question
from mathdrill.features import compute_insight_flags, to_dataframe
from mathdrill.insights import build_figure


def main():
    rng = random.Random(42)
    config = DrillConfig("Synthetic demo", 120, ("add", "sub", "mul", "div"))
    sessions = []
    for index in range(4):
        records = []
        for number in range(40):
            question = generate_question(config, rng)
            seconds = rng.uniform(0.5, 4.5)
            correct = rng.random() > 0.15
            records.append(
                build_answer_record(
                    question,
                    question.answer if correct else question.answer + 1,
                    seconds,
                    1_700_000_000 + index * 86400 + number * 3,
                )
            )
        sessions.append({"session_name": config.session_name, "duration": 120, "insights": records})
    figure = build_figure(compute_insight_flags(to_dataframe(sessions)))
    figure.suptitle("SYNTHETIC DEMO — illustrative data, not measured performance", fontsize=16)
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    target = Path(__file__).resolve().parents[1] / "Data" / "Demo_current.png"
    figure.savefig(target, dpi=110)
    plt.close(figure)
    print(target)


if __name__ == "__main__":
    main()
