"""Exercise timer callbacks with fake widgets, without opening a GUI."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mathdrill import game_frame
from mathdrill.core import DrillConfig, DrillSession


@pytest.fixture
def frame(monkeypatch):
    monkeypatch.setattr(game_frame.time, "monotonic", lambda: 100.0)
    instance = SimpleNamespace(
        session=DrillSession(DrillConfig("test", 60, ("add",))),
        _deadline=160.0,
        _timer_job=None,
        timer_label=Mock(),
        after=Mock(return_value="timer"),
        end_game=Mock(),
        update_timer=Mock(),
    )
    return instance


def test_countdown_starts_at_full_duration(frame):
    game_frame.GameFrame.update_timer(frame)
    assert frame.remaining_time == 60
    frame.timer_label.config.assert_called_once_with(text="Time Remaining: 60s")


def test_delayed_tick_uses_elapsed_time(frame):
    frame._deadline = 142.2
    game_frame.GameFrame.update_timer(frame)
    assert frame.remaining_time == 43


@pytest.mark.parametrize("callback", ["update_timer", "check_answer", "next_question"])
def test_expired_callbacks_end_game_before_touching_input(frame, callback):
    frame._deadline = 100.0
    getattr(game_frame.GameFrame, callback)(frame)
    frame.end_game.assert_called_once_with()
    assert frame.session.records == []


def test_end_game_is_idempotent(frame):
    frame.session.finish()
    # No widget or storage calls should happen on a second end callback.
    game_frame.GameFrame.end_game(frame)


def test_end_game_cancels_jobs_disables_input_and_saves_once(frame, monkeypatch):
    saved = Mock(return_value="test.json")
    monkeypatch.setattr(game_frame, "append_session", saved)
    frame._timer_job = "timer"
    frame._next_question_job = "next"
    frame._end_job = "end"
    frame.after_cancel = Mock()
    frame._cancel_pending = lambda: game_frame.GameFrame._cancel_pending(frame)
    frame.question_label = Mock()
    frame.answer_entry = Mock()
    frame.stats_label = Mock()
    frame.close_btn = Mock()
    question = frame.session.next_question()
    frame.session.submit(str(question.answer))

    game_frame.GameFrame.end_game(frame)
    game_frame.GameFrame.end_game(frame)

    assert frame.after_cancel.call_count == 3
    frame.answer_entry.config.assert_called_once_with(state="disabled")
    frame.answer_entry.grid_remove.assert_called_once_with()
    saved.assert_called_once()
    assert len(saved.call_args.args[0]["insights"]) == 1
    assert not frame.session.submit(str(question.answer)).accepted
