"""Tests for the pure drill logic.

Nothing here opens a window or touches the real session file.
"""

from __future__ import annotations

import random

import pytest

from mathdrill import core
from mathdrill.core import ConfigError, DrillConfig, DrillSession

ALL_OPS = ("add", "sub", "mul", "div")


def make_config(**overrides) -> DrillConfig:
    params = {
        "session_name": "unit-test",
        "duration": 60,
        "operations": ALL_OPS,
        "add_range1": (2, 100),
        "add_range2": (2, 100),
        "mul_range1": (2, 12),
        "mul_range2": (2, 100),
    }
    params.update(overrides)
    return DrillConfig(**params)


EXPECTED = {
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "div": lambda a, b: a // b,
}


# --------------------------------------------------------------- generation


@pytest.mark.parametrize("operation", ALL_OPS)
def test_generated_answer_is_arithmetically_correct(operation):
    """Whatever we render, the stored answer must be the real answer."""
    config = make_config(operations=(operation,))
    rng = random.Random(1234)
    for _ in range(300):
        q = core.generate_question(config, rng)
        assert q.operation == operation
        assert q.answer == EXPECTED[operation](q.operand_1, q.operand_2)


def test_division_is_always_exact_and_integral():
    """Division is exact by construction, so the quotient is a whole number."""
    config = make_config(operations=("div",))
    rng = random.Random(7)
    for _ in range(500):
        q = core.generate_question(config, rng)
        assert q.operand_2 != 0
        assert q.operand_1 % q.operand_2 == 0
        assert isinstance(q.answer, int)
        assert q.operand_1 == q.operand_2 * q.answer


def test_addition_operands_respect_configured_ranges():
    config = make_config(operations=("add",), add_range1=(5, 9), add_range2=(50, 60))
    rng = random.Random(3)
    for _ in range(400):
        q = core.generate_question(config, rng)
        # The operands may be swapped for variety, so check as a pair.
        low, high = sorted((q.operand_1, q.operand_2))
        assert 5 <= low <= 9
        assert 50 <= high <= 60


def test_multiplication_operands_respect_configured_ranges():
    config = make_config(operations=("mul",), mul_range1=(2, 4), mul_range2=(70, 80))
    rng = random.Random(11)
    for _ in range(400):
        q = core.generate_question(config, rng)
        low, high = sorted((q.operand_1, q.operand_2))
        assert 2 <= low <= 4
        assert 70 <= high <= 80


def test_division_divisor_and_quotient_respect_their_ranges():
    """For division, operand_2 uses mul_range2 and the quotient uses mul_range1."""
    config = make_config(operations=("div",), mul_range1=(3, 6), mul_range2=(10, 20))
    rng = random.Random(19)
    for _ in range(400):
        q = core.generate_question(config, rng)
        assert 10 <= q.operand_2 <= 20
        assert 3 <= q.answer <= 6
        assert q.operand_1 == q.operand_2 * q.answer


def test_subtraction_allows_negative_answers_by_default():
    config = make_config(operations=("sub",), add_range1=(1, 3), add_range2=(90, 99))
    rng = random.Random(5)
    answers = [core.generate_question(config, rng).answer for _ in range(200)]
    assert any(a < 0 for a in answers), "negative answers should be reachable"


def test_subtraction_can_be_restricted_to_non_negative_answers():
    """The negative-answer behaviour is a documented, configurable choice."""
    config = make_config(
        operations=("sub",),
        add_range1=(1, 3),
        add_range2=(90, 99),
        allow_negative_answers=False,
    )
    rng = random.Random(5)
    for _ in range(300):
        q = core.generate_question(config, rng)
        assert q.answer >= 0
        assert q.answer == q.operand_1 - q.operand_2


def test_question_text_matches_operands():
    config = make_config()
    rng = random.Random(42)
    for _ in range(200):
        q = core.generate_question(config, rng)
        assert str(q.operand_1) in q.text
        assert str(q.operand_2) in q.text


# ------------------------------------------------------------- config errors


def test_no_operations_selected_is_a_clear_error():
    """Unchecking every operation must not crash the caller."""
    with pytest.raises(ConfigError, match="at least one operation"):
        make_config(operations=())


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"add_range1": (100, 2)}, "greater than its maximum"),
        ({"add_range2": (-5, 10)}, "cannot be negative"),
        ({"mul_range1": ("x", 10)}, "whole numbers"),
        ({"mul_range2": (5,)}, "must be a"),
        ({"duration": 0}, "greater than zero"),
        ({"duration": -30}, "greater than zero"),
        ({"duration": "soon"}, "whole number"),
        ({"operations": ("add", "log")}, "Unknown operation"),
    ],
)
def test_invalid_configuration_is_rejected(kwargs, message):
    with pytest.raises(ConfigError, match=message):
        make_config(**kwargs)


def test_division_requires_a_usable_divisor_range():
    with pytest.raises(ConfigError, match="divisor of at least 1"):
        make_config(operations=("div",), mul_range2=(0, 0))


def test_from_mapping_matches_the_gui_dict_shape():
    config = DrillConfig.from_mapping(
        {
            "session_name": "  spaced   name  ",
            "duration": 30,
            "use_add": True,
            "use_div": True,
            "use_sub": False,
            "use_mul": False,
            "add_range1": (1, 5),
        }
    )
    assert config.operations == ("add", "div")
    assert config.session_name == "spaced name"
    assert config.duration == 30


def test_session_name_is_normalised_but_not_used_as_a_path():
    dirty = "  drill\x00\n../../etc/passwd  "
    cleaned = core.clean_session_name(dirty)
    assert "\x00" not in cleaned
    assert "\n" not in cleaned
    # The traversal text survives as *text*; it is stored in JSON and never
    # used to build a path. This test documents that expectation.
    assert cleaned == "drill../../etc/passwd"


def test_session_name_length_is_capped():
    assert len(core.clean_session_name("x" * 500)) == core.MAX_SESSION_NAME_LENGTH


# ------------------------------------------------------------------ sessions


class FakeClock:
    """A clock that advances only when told to."""

    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_correct_answer_scores_and_records():
    clock = FakeClock()
    session = DrillSession(make_config(), rng=random.Random(1), clock=clock)
    question = session.next_question()
    clock.advance(2.5)

    result = session.submit(str(question.answer))

    assert result.accepted and result.correct
    assert session.score == 1
    assert len(session.records) == 1
    assert session.records[0]["time_taken_sec"] == pytest.approx(2.5)
    assert session.records[0]["correctness"] is True


def test_blank_submissions_are_ignored_entirely():
    """Holding Return used to drive the score negative and pollute the log."""
    session = DrillSession(make_config(), rng=random.Random(1), clock=FakeClock())
    session.next_question()

    for blank in ("", "   ", "\t"):
        result = session.submit(blank)
        assert result.accepted is False

    assert session.records == []
    assert session.score == 0


def test_wrong_answer_never_drives_the_score_below_zero():
    clock = FakeClock()
    session = DrillSession(make_config(), rng=random.Random(2), clock=clock)
    for _ in range(20):
        question = session.next_question()
        clock.advance(1.0)
        session.submit(str(question.answer + 1))

    assert session.score == 0
    assert len(session.records) == 20
    assert all(r["correctness"] is False for r in session.records)


def test_non_numeric_entry_counts_as_a_wrong_attempt():
    session = DrillSession(make_config(), rng=random.Random(3), clock=FakeClock())
    session.next_question()

    result = session.submit("banana")

    assert result.accepted is True
    assert result.correct is False
    assert session.records[0]["user_answer"] is None


def test_submissions_after_the_session_ends_are_dropped():
    """The pending next_question used to keep the drill alive past the timer."""
    clock = FakeClock()
    session = DrillSession(make_config(), rng=random.Random(4), clock=clock)
    question = session.next_question()
    clock.advance(1.0)
    session.submit(str(question.answer))

    session.finish()
    after = session.submit(str(question.answer))

    assert after.accepted is False
    assert session.next_question() is None
    assert len(session.records) == 1
    assert session.score == 1


def test_summary_reports_score_and_rate():
    clock = FakeClock()
    session = DrillSession(make_config(duration=60), rng=random.Random(5), clock=clock)
    for i in range(4):
        question = session.next_question()
        clock.advance(2.0)
        session.submit(str(question.answer if i < 3 else question.answer + 1))
    session.finish()

    summary = session.summary()
    assert summary["total"] == 4
    assert summary["correct"] == 3
    assert summary["incorrect"] == 1
    assert summary["score"] == 3
    assert summary["accuracy"] == pytest.approx(0.75)
    assert summary["avg_time_sec"] == pytest.approx(2.0)
    assert summary["questions_per_min"] == pytest.approx(4.0)


def test_summary_of_an_empty_session_does_not_divide_by_zero():
    session = DrillSession(make_config(), rng=random.Random(6), clock=FakeClock())
    session.finish()

    summary = session.summary()
    assert summary["total"] == 0
    assert summary["avg_time_sec"] == 0.0
    assert summary["accuracy"] == 0.0


def test_stored_record_matches_the_documented_schema():
    """The record shape is the contract; guard it against drift."""
    clock = FakeClock()
    session = DrillSession(make_config(), rng=random.Random(8), clock=clock)
    question = session.next_question()
    clock.advance(1.5)
    session.submit(str(question.answer))

    record = session.records[0]
    assert set(record) == {
        "timestamp",
        "question",
        "operation",
        "operand_1",
        "operand_2",
        "correct_answer",
        "user_answer",
        "time_taken_sec",
        "correctness",
    }
    # question_type was dropped; it was always identical to operation.
    assert "question_type" not in record
    assert isinstance(record["operand_1"], int)
    assert isinstance(record["operand_2"], int)

    wrapper = session.to_record()
    assert set(wrapper) == {"session_name", "duration", "insights"}
    assert wrapper["insights"][0] is record
