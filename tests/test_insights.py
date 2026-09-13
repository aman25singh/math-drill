"""Render the real chart pipeline using synthetic data and a non-GUI backend."""

import json

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from mathdrill.insights import main


def test_cli_filters_and_renders_one_question(tmp_path, capsys):
    record = {
        "timestamp": 1000,
        "question": "1 + 1",
        "operation": "add",
        "operand_1": 1,
        "operand_2": 1,
        "correct_answer": 2,
        "user_answer": 2,
        "time_taken_sec": 1,
        "correctness": True,
    }
    source = tmp_path / "sessions.json"
    source.write_text(
        json.dumps(
            [
                {"session_name": "chosen", "duration": 60, "insights": [record]},
                {"session_name": "other", "duration": 60, "insights": [record] * 5},
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "chart.png"
    try:
        assert main(["chosen", "--file", str(source), "--save", str(output)]) == 0
        assert "only 1 answered question(s)" in capsys.readouterr().out
        assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        panels = plt.gcf().axes[:8]  # The heatmap also adds a colorbar axis.
        assert len(panels) == 8
        assert "Total: 1 |" in panels[6].texts[0].get_text()
    finally:
        plt.close("all")
