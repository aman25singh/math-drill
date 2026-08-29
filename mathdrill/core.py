"""Pure drill logic: configuration, question generation, and session records.

This module imports nothing outside the standard library -- no tkinter, no
pandas, no matplotlib. Everything here is deterministic when handed an
explicit ``random.Random`` and clock, which is what makes it testable.

Two deliberate design decisions are encoded here and documented in the README:

Division is always exact.
    ``operand_1`` is constructed as ``operand_2 * quotient``, so division never
    produces a remainder. This is a drill for mental arithmetic; asking for a
    decimal quotient would change what the user has to type and what
    "correct" means. The historical ``is_decimal_division`` feature flag could
    therefore never be true, and has been removed rather than left dead.

Subtraction may produce negative answers.
    Subtraction draws from the *addition* ranges and may order the operands
    either way, so "2 - 100" is a legitimate question. That is useful drilling
    but it surprised people, so it is now controlled by
    ``allow_negative_answers`` instead of being an accident of the code.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

OPERATIONS: tuple[str, ...] = ("add", "sub", "mul", "div")

OP_SYMBOL: dict[str, str] = {"add": "+", "sub": "-", "mul": "×", "div": "÷"}

#: Durations offered by the GUI, in seconds.
DURATION_CHOICES: tuple[int, ...] = (30, 60, 120, 180, 300)

MAX_SESSION_NAME_LENGTH = 120


class ConfigError(ValueError):
    """Raised when a drill configuration cannot be used to generate questions."""


def _validate_range(name: str, value: Sequence[int]) -> tuple[int, int]:
    """Coerce and check a (min, max) operand range."""
    try:
        low, high = value
    except (TypeError, ValueError):
        raise ConfigError(f"{name} must be a (min, max) pair.") from None
    if isinstance(low, bool) or isinstance(high, bool):
        raise ConfigError(f"{name} bounds must be whole numbers.")
    try:
        low, high = int(low), int(high)
    except (TypeError, ValueError):
        raise ConfigError(f"{name} bounds must be whole numbers.") from None
    if low > high:
        raise ConfigError(f"{name} minimum ({low}) is greater than its maximum ({high}).")
    if low < 0:
        raise ConfigError(f"{name} cannot be negative (got {low}).")
    return low, high


def clean_session_name(raw: str) -> str:
    """Normalise a user-supplied session name.

    The name is stored in JSON and displayed; it is deliberately *not* used to
    build any filesystem path. Control characters are stripped so a pasted name
    cannot smuggle newlines into printed output, and the length is capped so
    stored records stay readable.
    """
    if raw is None:
        return ""
    text = "".join(ch for ch in str(raw) if ch.isprintable())
    text = " ".join(text.split())
    return text[:MAX_SESSION_NAME_LENGTH]


@dataclass(frozen=True)
class DrillConfig:
    """A validated, immutable description of one drill session."""

    session_name: str
    duration: int
    operations: tuple[str, ...]
    add_range1: tuple[int, int] = (2, 100)
    add_range2: tuple[int, int] = (2, 100)
    mul_range1: tuple[int, int] = (2, 12)
    mul_range2: tuple[int, int] = (2, 100)
    allow_negative_answers: bool = True

    def __post_init__(self) -> None:
        ops = tuple(dict.fromkeys(self.operations))
        if not ops:
            raise ConfigError("Select at least one operation.")
        unknown = [op for op in ops if op not in OPERATIONS]
        if unknown:
            raise ConfigError(f"Unknown operation(s): {', '.join(map(str, unknown))}.")
        object.__setattr__(self, "operations", ops)

        if isinstance(self.duration, bool):
            raise ConfigError("Duration must be a whole number of seconds.")
        try:
            duration = int(self.duration)
        except (TypeError, ValueError):
            raise ConfigError("Duration must be a whole number of seconds.") from None
        if duration <= 0:
            raise ConfigError(f"Duration must be greater than zero (got {duration}).")
        object.__setattr__(self, "duration", duration)

        for name in ("add_range1", "add_range2", "mul_range1", "mul_range2"):
            object.__setattr__(self, name, _validate_range(name, getattr(self, name)))

        object.__setattr__(self, "session_name", clean_session_name(self.session_name))

        # Division builds operand_1 as operand_2 * quotient. A zero divisor is
        # unusable and a zero quotient makes every answer 0, so both ranges
        # must be able to supply at least one positive value.
        if "div" in ops:
            if self.mul_range2[1] < 1:
                raise ConfigError(
                    "Division needs a divisor of at least 1; widen the multiplication range."
                )
            if self.mul_range1[1] < 1:
                raise ConfigError(
                    "Division needs a quotient of at least 1; widen the multiplication range."
                )

    @classmethod
    def from_mapping(cls, data: dict) -> DrillConfig:
        """Build a config from the flat dict shape the GUI produces."""
        ops = tuple(op for op in OPERATIONS if data.get(f"use_{op}", False))
        return cls(
            session_name=data.get("session_name", ""),
            duration=data.get("duration", 0),
            operations=ops,
            add_range1=data.get("add_range1", (2, 100)),
            add_range2=data.get("add_range2", (2, 100)),
            mul_range1=data.get("mul_range1", (2, 12)),
            mul_range2=data.get("mul_range2", (2, 100)),
            allow_negative_answers=data.get("allow_negative_answers", True),
        )


@dataclass(frozen=True)
class Question:
    """One generated question, with operands kept separate from the text."""

    text: str
    answer: int
    operation: str
    operand_1: int
    operand_2: int


def _positive_randint(rng: random.Random, low: int, high: int) -> int:
    """Draw from [low, high], avoiding 0 when a positive value is available."""
    if high < 1:
        return rng.randint(low, high)
    return rng.randint(max(low, 1), high)


def generate_question(config: DrillConfig, rng: random.Random | None = None) -> Question:
    """Generate a single question from ``config``.

    ``rng`` is injectable so tests can be deterministic.
    """
    rng = rng or random
    op = rng.choice(config.operations)

    if op == "add":
        a = rng.randint(*config.add_range1)
        b = rng.randint(*config.add_range2)
        if rng.choice((True, False)):
            a, b = b, a
        return Question(f"{a} + {b}", a + b, op, a, b)

    if op == "sub":
        a = rng.randint(*config.add_range1)
        b = rng.randint(*config.add_range2)
        if rng.choice((True, False)):
            a, b = b, a
        if not config.allow_negative_answers and b > a:
            a, b = b, a
        return Question(f"{a} - {b}", a - b, op, a, b)

    if op == "div":
        # Build the dividend from the divisor so the quotient is whole.
        # operand_2 respects mul_range2; the *quotient* respects mul_range1,
        # and operand_1 is their product.
        b = _positive_randint(rng, *config.mul_range2)
        quotient = _positive_randint(rng, *config.mul_range1)
        a = b * quotient
        return Question(f"{a} {OP_SYMBOL['div']} {b}", quotient, op, a, b)

    a = rng.randint(*config.mul_range1)
    b = rng.randint(*config.mul_range2)
    if rng.choice((True, False)):
        a, b = b, a
    return Question(f"{a} {OP_SYMBOL['mul']} {b}", a * b, op, a, b)


def build_answer_record(
    question: Question,
    user_answer: float | None,
    time_taken_sec: float,
    timestamp: float,
) -> dict:
    """Build one flat answer record.

    This is the stable data contract between the app and any analysis. Keeping
    ``operand_1`` / ``operand_2`` alongside the rendered ``question`` string is
    the whole reason digit-level feature extraction is possible.

    ``question_type`` used to be stored here too; it was always identical to
    ``operation`` and has been dropped. Readers still accept it (see
    ``storage.load_sessions``) so older files keep working.
    """
    return {
        "timestamp": timestamp,
        "question": question.text,
        "operation": question.operation,
        "operand_1": question.operand_1,
        "operand_2": question.operand_2,
        "correct_answer": question.answer,
        "user_answer": user_answer,
        "time_taken_sec": time_taken_sec,
        "correctness": user_answer is not None and user_answer == question.answer,
    }


def build_session_record(session_name: str, duration: int, records: Sequence[dict]) -> dict:
    """Wrap answer records as one stored session."""
    return {
        "session_name": session_name,
        "duration": duration,
        "insights": list(records),
    }


def parse_user_answer(raw: str) -> tuple[bool, float | None]:
    """Interpret what the user typed.

    Returns ``(submitted, value)``.

    An empty or whitespace-only entry is *not* a submission: it returns
    ``(False, None)`` and the caller ignores it. That is what stops a held-down
    Return key from racing through questions. A non-empty entry that is not a
    number *is* a real attempt, and is recorded as a wrong answer with a
    ``user_answer`` of ``None``.
    """
    if raw is None:
        return False, None
    text = raw.strip()
    if not text:
        return False, None
    try:
        return True, float(text)
    except ValueError:
        return True, None


@dataclass
class SubmitResult:
    """Outcome of handing one entry to :meth:`DrillSession.submit`."""

    accepted: bool
    correct: bool = False
    record: dict | None = None


@dataclass
class DrillSession:
    """Drives one drill: generates questions, times them, scores them.

    Holds no widgets and draws nothing. The Tkinter frame owns the display and
    delegates every decision here, which is what makes the scoring and timing
    rules testable without opening a window.
    """

    config: DrillConfig
    rng: random.Random = field(default_factory=random.Random)
    clock: Callable[[], float] = time.time

    records: list[dict] = field(default_factory=list, init=False)
    score: int = field(default=0, init=False)
    current: Question | None = field(default=None, init=False)
    finished: bool = field(default=False, init=False)
    _question_started_at: float | None = field(default=None, init=False)

    def next_question(self) -> Question | None:
        """Generate and arm the next question, unless the session has ended."""
        if self.finished:
            return None
        self.current = generate_question(self.config, self.rng)
        self._question_started_at = self.clock()
        return self.current

    def submit(self, raw: str) -> SubmitResult:
        """Score one entry.

        Blank entries, and anything arriving after the session ended, are
        ignored so neither can pollute the record or move the score.
        """
        if self.finished or self.current is None:
            return SubmitResult(accepted=False)

        submitted, value = parse_user_answer(raw)
        if not submitted:
            return SubmitResult(accepted=False)

        now = self.clock()
        started = self._question_started_at
        if started is None:
            started = now
        record = build_answer_record(self.current, value, now - started, now)
        self.records.append(record)

        # Score counts correct answers only. It used to subtract a point for a
        # wrong answer, which -- combined with blank submissions counting as
        # wrong -- let a held-down Return key drive the score negative.
        if record["correctness"]:
            self.score += 1

        return SubmitResult(accepted=True, correct=record["correctness"], record=record)

    def finish(self) -> None:
        """Close the session. Later submissions are ignored."""
        self.finished = True
        self.current = None

    def summary(self) -> dict:
        """End-of-session statistics."""
        total = len(self.records)
        correct = sum(1 for r in self.records if r["correctness"])
        avg_time = sum(r["time_taken_sec"] for r in self.records) / total if total else 0.0
        minutes = self.config.duration / 60
        return {
            "session_name": self.config.session_name,
            "duration": self.config.duration,
            "total": total,
            "correct": correct,
            "incorrect": total - correct,
            "score": self.score,
            "accuracy": correct / total if total else 0.0,
            "avg_time_sec": avg_time,
            "questions_per_min": total / minutes if minutes else 0.0,
        }

    def slowest(self, limit: int = 5) -> list[dict]:
        """The slowest answers of the session, slowest first."""
        return sorted(self.records, key=lambda r: r["time_taken_sec"], reverse=True)[:limit]

    def to_record(self) -> dict:
        """This session in the stored JSON shape."""
        return build_session_record(self.config.session_name, self.config.duration, self.records)
