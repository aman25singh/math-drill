"""Reading and writing the session log.

``Data/session_insights.json`` is treated as untrusted input. It is a plain
text file a user can hand-edit, and a malformed one should produce a sentence
explaining the problem rather than a stack trace from somewhere inside pandas.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

DATA_DIR_ENV = "MATHDRILL_DATA_DIR"
FILENAME = "session_insights.json"

REQUIRED_RECORD_FIELDS = (
    "timestamp",
    "question",
    "operation",
    "operand_1",
    "operand_2",
    "correct_answer",
    "time_taken_sec",
    "correctness",
)


class SessionDataError(ValueError):
    """Raised when the session file exists but is not usable."""


def _project_root() -> Path | None:
    """The checkout this package was imported from, if it is a checkout.

    Running from a source tree keeps writing to ``<repo>/Data``, which is what
    the project has always done. Once pip-installed there is no such tree, and
    the caller falls through to a per-user directory instead of writing into
    site-packages.
    """
    root = Path(__file__).resolve().parent.parent
    if (root / "pyproject.toml").exists() or (root / ".git").exists():
        return root
    return None


def data_dir() -> Path:
    """Directory holding the session log.

    Resolution order:

    1. ``$MATHDRILL_DATA_DIR`` if set.
    2. ``<repo>/Data`` when running from a source checkout.
    3. A per-user data directory.

    Previously the path was the bare relative string ``"Data/..."``, so where
    a session got saved depended on the working directory the app happened to
    be launched from.
    """
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser()

    root = _project_root()
    if root is not None:
        return root / "Data"

    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "math-drill"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "math-drill"


def data_file() -> Path:
    """Full path to the session log."""
    return data_dir() / FILENAME


def _validate(payload: object, path: Path) -> list[dict]:
    """Check the parsed JSON has the shape the analysis expects."""
    where = f"Session file {path}"

    if payload is None:
        return []
    if not isinstance(payload, list):
        raise SessionDataError(
            f"{where} should contain a list of sessions, "
            f"but its top level is {type(payload).__name__}."
        )

    sessions: list[dict] = []
    for i, session in enumerate(payload):
        label = f"{where}, session {i + 1}"
        if not isinstance(session, dict):
            raise SessionDataError(
                f"{label} should be an object, but it is {type(session).__name__}."
            )
        insights = session.get("insights")
        if insights is None:
            insights = []
        if not isinstance(insights, list):
            raise SessionDataError(
                f"{label} has an 'insights' field that is "
                f"{type(insights).__name__}, but it should be a list."
            )

        cleaned: list[dict] = []
        for j, record in enumerate(insights):
            if not isinstance(record, dict):
                raise SessionDataError(
                    f"{label}, answer {j + 1} should be an object, "
                    f"but it is {type(record).__name__}."
                )
            record = dict(record)
            # Older files stored question_type alongside an always-identical
            # operation. Accept either so existing logs keep working.
            if "operation" not in record and "question_type" in record:
                record["operation"] = record["question_type"]
            record.pop("question_type", None)

            absent = [f for f in REQUIRED_RECORD_FIELDS if f not in record]
            if absent:
                raise SessionDataError(
                    f"{label}, answer {j + 1} is missing required field(s): "
                    f"{', '.join(absent)}."
                )
            cleaned.append(record)

        sessions.append(
            {
                "session_name": str(session.get("session_name", "")),
                "duration": session.get("duration", 0),
                "insights": cleaned,
            }
        )
    return sessions


def load_sessions(path: Path | str | None = None) -> list[dict]:
    """Load stored sessions.

    A missing or empty file means "nothing played yet" and returns ``[]``.
    Anything present but malformed raises :class:`SessionDataError` carrying a
    message worth showing to a person.
    """
    target = Path(path) if path is not None else data_file()

    try:
        text = target.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise SessionDataError(f"Could not read {target}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise SessionDataError(
            f"Session file {target} is not valid UTF-8 text: {exc}"
        ) from exc

    if not text:
        return []

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SessionDataError(
            f"Session file {target} is not valid JSON "
            f"(line {exc.lineno}, column {exc.colno}): {exc.msg}."
        ) from exc

    return _validate(payload, target)


def append_session(record: dict, path: Path | str | None = None) -> Path:
    """Append one session to the log and return the path written.

    Writes to a temporary file in the same directory and replaces the original,
    so an interrupted write cannot leave a half-truncated log behind. The old
    code opened the real file ``r+``, seeked to 0 and truncated, which was
    exactly the pattern that could destroy previous sessions.

    A log that is already unreadable is preserved: rather than silently
    starting a fresh list and dropping the user's history, the error is raised.
    """
    target = Path(path) if path is not None else data_file()
    target.parent.mkdir(parents=True, exist_ok=True)

    sessions = load_sessions(target)
    sessions.append(record)

    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=".session_insights.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(sessions, handle, indent=4)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return target
