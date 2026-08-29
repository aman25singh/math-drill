"""Tests for reading and writing the session log.

Every test writes into pytest's tmp_path. The real session file is never
opened.
"""

from __future__ import annotations

import json

import pytest

from mathdrill import storage
from mathdrill.storage import SessionDataError


def valid_record(name="s1"):
    return {
        "session_name": name,
        "duration": 60,
        "insights": [
            {
                "timestamp": 1754847942.75,
                "question": "25 - 25",
                "operation": "sub",
                "operand_1": 25,
                "operand_2": 25,
                "correct_answer": 0,
                "user_answer": 0.0,
                "time_taken_sec": 2.07,
                "correctness": True,
            }
        ],
    }


# ------------------------------------------------------------------ loading


def test_missing_file_means_nothing_played_yet(tmp_path):
    assert storage.load_sessions(tmp_path / "absent.json") == []


def test_empty_file_is_not_an_error(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("", encoding="utf-8")
    assert storage.load_sessions(path) == []


def test_round_trip(tmp_path):
    path = tmp_path / "s.json"
    storage.append_session(valid_record("first"), path)
    storage.append_session(valid_record("second"), path)

    loaded = storage.load_sessions(path)
    assert [s["session_name"] for s in loaded] == ["first", "second"]
    assert loaded[0]["insights"][0]["operation"] == "sub"


def test_append_creates_the_directory(tmp_path):
    path = tmp_path / "nested" / "deeper" / "s.json"
    storage.append_session(valid_record(), path)
    assert path.exists()
    assert len(storage.load_sessions(path)) == 1


def test_legacy_question_type_is_accepted_and_normalised(tmp_path):
    """Older logs stored question_type; they must keep working."""
    legacy = valid_record()
    record = legacy["insights"][0]
    record["question_type"] = record.pop("operation")
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps([legacy]), encoding="utf-8")

    loaded = storage.load_sessions(path)
    answer = loaded[0]["insights"][0]
    assert answer["operation"] == "sub"
    assert "question_type" not in answer


# --------------------------------------------------- untrusted / malformed


def test_malformed_json_gives_a_clear_error_not_a_traceback(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('[{"session_name": "x",,}]', encoding="utf-8")

    with pytest.raises(SessionDataError) as excinfo:
        storage.load_sessions(path)

    message = str(excinfo.value)
    assert "not valid JSON" in message
    assert "line" in message


def test_top_level_object_instead_of_list_is_rejected(tmp_path):
    path = tmp_path / "obj.json"
    path.write_text('{"session_name": "x"}', encoding="utf-8")
    with pytest.raises(SessionDataError, match="list of sessions"):
        storage.load_sessions(path)


def test_session_that_is_not_an_object_is_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("[42]", encoding="utf-8")
    with pytest.raises(SessionDataError, match="should be an object"):
        storage.load_sessions(path)


def test_insights_that_are_not_a_list_are_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('[{"session_name": "x", "insights": "oops"}]', encoding="utf-8")
    with pytest.raises(SessionDataError, match="should be a list"):
        storage.load_sessions(path)


def test_answer_missing_a_required_field_is_named(tmp_path):
    broken = valid_record()
    del broken["insights"][0]["operand_2"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([broken]), encoding="utf-8")

    with pytest.raises(SessionDataError, match="operand_2"):
        storage.load_sessions(path)


def test_invalid_utf8_is_reported_clearly(tmp_path):
    path = tmp_path / "bad.json"
    path.write_bytes(b"\xff\xfe\x00 not utf-8")
    with pytest.raises(SessionDataError, match="not valid UTF-8"):
        storage.load_sessions(path)


def test_append_refuses_to_silently_discard_a_corrupt_log(tmp_path):
    """A hand-broken file must not be quietly replaced with a fresh list."""
    path = tmp_path / "bad.json"
    original = "{ this is not json"
    path.write_text(original, encoding="utf-8")

    with pytest.raises(SessionDataError):
        storage.append_session(valid_record(), path)

    assert path.read_text(encoding="utf-8") == original


def test_failed_append_leaves_no_temporary_files(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("nonsense", encoding="utf-8")
    with pytest.raises(SessionDataError):
        storage.append_session(valid_record(), path)
    assert list(tmp_path.glob(".session_insights.*")) == []


# ------------------------------------------------------------ path resolution


def test_data_dir_honours_the_environment_override(tmp_path, monkeypatch):
    monkeypatch.setenv(storage.DATA_DIR_ENV, str(tmp_path / "custom"))
    assert storage.data_dir() == tmp_path / "custom"
    assert storage.data_file() == tmp_path / "custom" / storage.FILENAME


def test_data_file_is_absolute(monkeypatch):
    """Regression: the path used to be the relative string "Data/...".

    That made the save location depend on the working directory the app was
    launched from.
    """
    monkeypatch.delenv(storage.DATA_DIR_ENV, raising=False)
    assert storage.data_file().is_absolute()
