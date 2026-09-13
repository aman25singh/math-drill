# Math Drill — Technical Report

**Date:** 2026-08-29
**Repository:** `github.com/xelaaaa999/math-drill`
**Scope:** code review, data-model assessment, defect list, and a plan for a web version

| | |
|---|---|
| **Language** | Python 3.11 |
| **Stack** | Tkinter (UI), pandas · matplotlib · seaborn (analysis) |
| **Size** | 3 source files, ~620 lines |
| **Git** | 1 commit (`b61735a`), `main` in sync with `origin/main` |
| **Tests** | None |
| **External services** | None — fully offline |

---

## Implementation review — 2026-09-13

The report below is a historical review of the original three-file app. The
current checkout already contains the `mathdrill` package, pure-logic tests,
pinned dependencies, MIT license, repository hygiene, and most desktop fixes.
Desktop verification is the agreed scope; web tasks W01–W08 remain deferred.

This follow-up closes gaps found against the current implementation:

- **T04:** use a monotonic deadline for countdown and answer acceptance; consume
  each question after submission; cancel pending callbacks and save only once.
  Per-question elapsed time also uses a monotonic clock while stored timestamps
  remain Unix wall-clock timestamps.
- **T08:** retain a distinct internal identity for each session even when names
  repeat; average individual session rates rather than pooling durations.
  This internal identity is not written to the JSON schema.
- **T01/T09:** handle a named filter on an all-empty log; add regressions for
  deadline callbacks, duplicate submissions, repeated names, and real headless
  chart rendering. Tests do not open a GUI or read the user's practice log.
- **T02:** constrain pyparsing for compatibility with pinned Matplotlib 3.10.1,
  whose older API calls otherwise fail the warnings-as-errors chart test.
- **T03/T11:** retain the historical screenshots, add a reproducible current
  overview explicitly labelled as synthetic, and correct the README's claim
  that a sample practice log is committed (it is gitignored).
- **T07:** display each feature group's sample count and its baseline count
  in the comparison chart, rather than leaving them only in the computed table.
- **T05/T06/T07/T10:** path handling, inline configuration errors, feature bins
  and sample thresholds, MIT license, and removal of tracked IDE/cache files
  were already implemented in this checkout.

Existing schema decision: the current app writes `operation` and accepts legacy
`question_type` on read. This predates this follow-up; no further persisted
schema change is introduced here.

Verification on Windows / Python 3.12: **97 tests pass**, including real PNG
rendering and fake-widget timer/save regression tests. Ruff lint, Ruff format,
and `git diff --check` pass. Runtime and development requirements installed in
a fresh `.venv-desktop-check` environment; editable package installation and
`pip check` passed. Both requirements-file audits reported no known
vulnerabilities. The regenerated synthetic overview was visually inspected.

Manual acceptance: the user played the launched desktop game, reported it was
working well, and approved committing the changes. Automated tests additionally
cover the callbacks without opening a window. Python 3.10 and 3.11 checks remain
covered by the existing CI matrix, not this local run.

## 1. Summary

A desktop app for timed mental-arithmetic drills that logs every answer with millisecond timing,
then analyses the results to show **which specific number patterns slow you down** — not just
"you're slow at multiplication," but "carry-additions cost you time" and "any operand containing a 9
takes 4.98s against 3.44s for a 1."

That feature-extraction idea is the strongest part of the project and the right thing to build a web
version around.

The app works end to end. There are three small bugs that break documented behaviour — a silently
ignored session filter, an uninstallable dependency, and two broken README images — plus a handful
of correctness issues in the game loop and the analysis. None are structural. The architecture is
sound and the data model is genuinely well designed.

---

## 2. Architecture

```
math_game_gui.py            SpeedDrillApp (tk.Tk)
  ├── ConfigFrame           operation toggles, number ranges, duration, session name
  │      └── on_start ──────► builds config dict
  ├── GameFrame  ───────────► game_frame.py
  │      ├── generate_question()   random operation, random operands
  │      ├── check_answer()        records timing + correctness
  │      └── end_game()            session stats, append to JSON
  └── launch_insight_after_session()
         └── subprocess ────► insights.py
                                ├── flatten sessions → DataFrame
                                ├── compute_insight_flags()   ← the interesting part
                                └── 2×6 matplotlib grid (8 used, 4 empty)
```

**Entry point:** `python math_game_gui.py`
**Data sink:** `Data/session_insights.json` — append-only array of sessions
**Analysis:** separate process via `subprocess.run`; blocks the GUI until the plot window closes

The three-file split is sensible — UI shell, game loop, analysis — and the JSON file is a clean seam
between the game and the analytics. That seam is what makes a web port straightforward.

---

## 3. The Data Model

Every answered question produces one flat record:

```json
{
  "timestamp": 1754847942.753827,
  "question": "25 - 25",
  "question_type": "sub",
  "operation": "sub",
  "operand_1": 25,
  "operand_2": 25,
  "correct_answer": 0,
  "user_answer": 0.0,
  "time_taken_sec": 2.0723612308502197,
  "correctness": true
}
```

Wrapped per session as `{session_name, duration, insights[]}`.

**This schema should not change.** Storing operands separately from the rendered question string is
exactly what makes the downstream feature extraction possible — it is the reason the analysis can
ask questions about digits and carries at all. Treat it as the stable contract between the desktop
app, any web version, and any future storage.

One redundancy worth cleaning: `question_type` and `operation` are always identical
(`_build_question` sets both from the same `op`). Drop one.

**Current data volume: 1 session, 9 questions.** The demo charts in `Data/` show roughly 50 points,
so they were produced from data that no longer exists — `Data/session_insights.json` is gitignored
and was never committed. A few real sessions are needed before the analytics show anything
meaningful.

---

## 4. What Works Well

**The feature engineering (`insights.py:49-77`).** Deriving `is_carry_addition`, per-digit presence
flags, `is_round_operand`, digit counts, and `operand_diff` from raw operands — then measuring time
and error rate against each — is a real analytical instinct. Most drill apps report accuracy and
stop.

**It answers a question worth asking.** The digit heatmap shows digit 9 at 4.98s against digit 1 at
3.44s, and digit 8 carrying a 24% error rate. That is specific, personal, and immediately readable.

**Per-question timing.** `question_start_time` is set in `next_question` and diffed in
`check_answer`, so timing is per question rather than per session. Everything downstream depends on
this being right, and it is.

**A deliberate config surface.** Separate ranges for addition and multiplication, per-operation
toggles, duration presets, named sessions. Someone thought about how this would actually be used.

**A clear motivation.** The README's "Why I Built This" section connects the tool to quantitative
finance preparation. It is specific and true, and it is the strongest paragraph in the file.

---

## 5. Defects

Found by reading the source; nothing has been changed.

### Blocking

| # | Location | Defect |
|---|---|---|
| **D1** | `insights.py:50` | **`compute_insight_flags` rebuilds `df` from `flattened_data`, discarding the session filter** applied at lines 42-46. `python insights.py <session_name>` therefore always analyses *every* session, silently. The per-session feature the README documents does not work. Fix: delete line 50 and use the dataframe passed in. |
| **D2** | `requirements.txt:4` | **`tkinter` is not pip-installable** — it ships with CPython. `pip install -r requirements.txt` fails on that line, so the documented setup path is broken for anyone who clones the repo. |
| **D3** | `README.md:56-57` | **Screenshots reference `image.png` and `image-1.png`, which do not exist.** The real files are `Data/Demo_1.png` and `Data/Demo_2.png`. The README currently renders two broken images. |

### Correctness

| # | Location | Defect |
|---|---|---|
| **D4** | `game_frame.py:240` | `self.answer_entry.pack_forget()` — the entry was placed with **`.grid()`** (line 88), so `pack_forget()` does nothing. The input box stays live after "Time's up". |
| **D5** | `game_frame.py:210` | `end_game` never cancels the pending `after(10, self.next_question)`. With D4, **the game keeps serving questions after the timer expires**; those answers append to `self.insights` *after* the JSON was written, so they change the score but are never saved. |
| **D6** | `insights.py:138` | `true_set = df[df[feat]] if df[feat].dtype == bool else df` — for numeric features (`num_digits_op1`, `num_digits_op2`, `operand_diff`) this assigns **the whole dataframe**, so those rows report the global mean time rather than anything feature-specific. The "Top Time-Consuming Features" chart mixes real subsets with meaningless whole-dataset rows. |
| **D7** | `insights.py:160` | `len(df) / (timestamp.max() - timestamp.min()) * 60` — **ZeroDivisionError on a single-question session**, and across multiple sessions the span includes the real-world gap between them, producing a nonsense questions-per-minute figure. |
| **D8** | `game_frame.py:143-147` | Division is built as `a = b * randint(...)`, so it is **always exact**. `is_decimal_division` (`insights.py:72`) can therefore never be `True` — a dead analytical feature. |
| **D9** | `math_game_gui.py:157` | `subprocess.run([sys.executable, "insights.py"])` uses a **relative path**, unlike line 147 which correctly resolves via `os.path.dirname(__file__)`. "View Overall Analysis" breaks whenever the working directory is not the project directory. |
| **D10** | `game_frame.py:246` | `file_path = "Data/session_insights.json"` is relative, and the directory is never created here — only `insights.py:8` does that. Working-directory-dependent write. |
| **D11** | `math_game_gui.py:95-103` | Unchecking all four operations makes `GameFrame.__init__` raise `ValueError` (line 31) with no handler — **an unhandled crash from ordinary UI input**. |

### Quality and hygiene

| # | Location | Defect |
|---|---|---|
| **D12** | git | `__pycache__/game_frame.cpython-311.pyc` **is tracked** despite `.gitignore` listing `__pycache__/` — committed before the ignore rule existed. |
| **D13** | git | `.idea/` (5 files) is tracked — machine-specific PyCharm config. The working tree also has an unstaged delete of `.idea/.gitignore` and an untracked `.idea/workspace.xml`. |
| **D14** | `README.md` | States "MIT License" but there is **no `LICENSE` file**. |
| **D15** | `requirements.txt` | No pinned versions. `seaborn`'s `palette=` without `hue=` (lines 147, 167) and the `groupby(observed=)` default (line 124) both emit deprecation warnings on current pandas/seaborn. |
| **D16** | `insights.py:81` | `plt.subplots(2, 6)` creates 12 axes for 8 charts; the other four render "More insights coming soon…", which reads as unfinished. |
| **D17** | `insights.py` | No `if __name__ == "__main__"` guard — the module runs on import, so none of the analysis is importable or testable. |
| **D18** | `math_game_gui.py:13-16` | `session_name` is parsed from `sys.argv` and **never used**. Unused imports across all three files (`ttk`, `random`, `json`, `time`). |
| **D19** | `game_frame.py:205` | Wrong answers subtract a point, and an empty Return submits `None` → counted wrong. Holding Return drives the score negative. The score is also never used in the end-of-session stats. |
| **D20** | `game_frame.py:137-142` | Subtraction draws from the addition ranges with a random swap, so **negative answers occur** (e.g. `2 - 100`). Defensible for drilling, but undocumented and not configurable. |

---

## 6. Security and Privacy

Clean. Nothing blocks publication.

| Check | Result |
|---|---|
| Secrets, credentials, tokens | ✅ None — no network calls anywhere in the codebase |
| External services | ✅ None; fully offline |
| Personal data | ✅ `session_insights.json` holds only timestamps and arithmetic performance, and is gitignored |
| Demo images | ✅ Both inspected — charts only, no paths or identifying content |
| Hard-coded personal paths | ✅ None (paths are relative — a bug, but not a leak) |
| Committed virtualenv | ✅ `Drill/` exists on disk but is correctly gitignored — 0 tracked files |
| Licence | ⚠️ MIT claimed in README, no `LICENSE` file (D14) |

---

## 7. Assessment

| Dimension | Score | Note |
|---|---|---|
| Technical depth | 7 | UI, game loop, and analysis across three layers |
| **Originality** | **9** | Digit-level difficulty profiling is uncommon |
| Problem-solving value | 7 | A real problem, honestly motivated |
| Engineering quality | 4 | Real bugs, no tests, script-style analysis module |
| **Understandability** | **9** | Graspable in one sentence, with a picture |
| Completeness | 6 | Runs end to end; the CLI feature silently does not |
| **Demo potential** | **9** | Interactive, visual, screenshots already exist |
| Documentation | 8 | README is already above average |
| **Release confidence** | **9** | No secrets, clean provenance |
| **Overall** | **7.3 / 10** | |

The gap between originality (9) and engineering quality (4) is the whole story: the idea is better
than its current execution, and closing that gap is cheap. Three small fixes address most of it.

---

## 8. Target State

"Ready to show" means: someone clones the repo, `pip install -r requirements.txt` succeeds, they
play a 60-second drill, the analysis window opens with correct charts, and the README screenshots
render.

**In scope:** D1–D3 fixed, D4–D11 fixed, tests on the pure logic, README corrected, `LICENSE` added.
**Out of scope:** rewriting the GUI, packaging as an executable, a database, user accounts.

---

## 9. Task List — Desktop

### T01 — Fix the session filter bug
**Type:** bug fix · **Size:** XS · **Priority:** Critical · **Depends on:** none

Delete `insights.py:50` and make `compute_insight_flags` operate on the dataframe passed to it.

**Acceptance criteria**
- `python insights.py <session_name>` analyses **only** that session — verify by comparing the
  summary panel's "Total:" against that session's question count.
- `python insights.py` with no argument still analyses all sessions.
- The empty-dataframe guard inside the function is preserved or relocated, not silently dropped.

### T02 — Repair the packaging
**Type:** packaging · **Size:** XS · **Priority:** Critical · **Depends on:** none · **Parallel-safe**

Remove `tkinter` from `requirements.txt`; pin `pandas`, `matplotlib`, `seaborn`.

**Acceptance criteria**
- `pip install -r requirements.txt` succeeds in a clean virtualenv.
- Versions pinned to what actually works.
- README notes Tkinter ships with CPython, and names `python3-tk` for Linux users.

### T03 — Fix the README screenshots
**Type:** docs · **Size:** XS · **Priority:** Critical · **Depends on:** none · **Parallel-safe**

Point the image links at `Data/Demo_1.png` and `Data/Demo_2.png`.

**Acceptance criteria**
- Both images render on GitHub.
- Alt text describes each chart rather than saying "alt text".
- Screenshots match the current 8-chart layout, or are regenerated.

### T04 — Stop the game when the timer expires
**Type:** bug fix · **Size:** S · **Priority:** High · **Depends on:** none · **Not parallel with T05**

Fix D4 and D5: use `grid_remove()` rather than `pack_forget()`, cancel the pending `after` callback,
disable the entry.

**Acceptance criteria**
- After "Time's up!", the input is disabled and no further questions appear.
- Answers submitted after expiry are neither scored nor appended to `insights`.
- The saved question count matches what was answered inside the timed window.
- Both timers (`update_timer` and the `after(duration*1000)` trigger) agree on when the session ends.

### T05 — Make file paths independent of the working directory
**Type:** bug fix · **Size:** S · **Priority:** High · **Depends on:** none · **Not parallel with T04**

Fix D9 and D10: resolve `Data/session_insights.json` and the `insights.py` subprocess path relative
to `__file__`, and create `Data/` if missing.

**Acceptance criteria**
- `python "path\to\math_game_gui.py"` works end to end from any working directory.
- "View Overall Analysis" launches correctly from any working directory.
- A missing `Data/` directory is created rather than raising.

### T06 — Handle invalid configuration
**Type:** bug fix · **Size:** XS · **Priority:** Medium · **Depends on:** none · **Parallel-safe**

**Acceptance criteria**
- Unchecking all four operations shows an inline message instead of crashing.
- Invalid ranges (min > max, non-numeric, empty) are reported rather than silently swallowed by the
  bare `except ValueError: return` at `math_game_gui.py:102`.

### T07 — Fix the feature-comparison chart
**Type:** analysis · **Size:** S · **Priority:** High · **Depends on:** T01

Fix D6. Boolean features compare their true-subset against their false-subset; numeric features are
binned (e.g. `operand_diff` into quartiles) rather than defaulting to the whole dataframe.

**Acceptance criteria**
- No chart row is computed from the entire dataset while claiming to describe a feature.
- Each row reports its own sample size; rows below the `n >= 5` threshold are excluded.
- Boolean features show the *difference* between true and false groups — that is the actual insight.
- The chart title states what is being compared.

### T08 — Fix the speed calculation
**Type:** bug fix · **Size:** XS · **Priority:** Medium · **Depends on:** T01 · **Parallel-safe**

**Acceptance criteria**
- A one-question session does not raise `ZeroDivisionError`.
- Multi-session speed is computed per session and averaged, not across the wall-clock span between
  sessions.
- Matches the in-app calculation at `game_frame.py:221`, or the divergence is deliberate and
  commented.

### T09 — Extract and test the pure logic
**Type:** refactor + tests · **Size:** M · **Priority:** High · **Depends on:** T01, T07 · **Parallel-safe**

Move question generation and feature extraction into importable modules with a `__main__` guard,
then test them. **This is also the prerequisite for the web version** — see §10.

**Acceptance criteria**
- `pytest` passes from a clean install.
- Question generation covered: every operation produces a mathematically correct answer; division
  always yields an integer; operands respect the configured ranges.
- `compute_insight_flags` covered: `is_carry_addition` true for `17+25`, false for `12+13`; digit
  flags correct for multi-digit operands; `num_digits` correct across boundaries.
- A regression test for the session-filter bug (D1).
- At least one failure-path test. No test opens a GUI or reads the real data file.

### T10 — Repository hygiene
**Type:** housekeeping · **Size:** S · **Priority:** Medium · **Depends on:** none · **Parallel-safe**

**Acceptance criteria**
- `__pycache__/game_frame.cpython-311.pyc` and `.idea/` untracked (`git rm --cached`).
- `.gitignore` covers `.idea/`, `__pycache__/`, `Drill/`, `.env*`.
- `LICENSE` file added matching the README's MIT claim.
- **No history rewrite** — one commit, nothing sensitive in it; removing files going forward is enough.

### T11 — README refresh
**Type:** docs · **Size:** S · **Priority:** High · **Depends on:** T01–T08

**Acceptance criteria**
- **Leads with the digit-difficulty insight**, not the feature list — that is the distinctive part.
- Documents the JSON schema (§3) as the data contract.
- Every setup step verified from a clean clone.
- The existing "Why I Built This" narrative is preserved.
- States honestly that the analytics need several sessions before they mean anything.

---

## 10. Web Version — Game Section With Analytics

### Why the port is straightforward

The valuable logic is **already independent of Tkinter and matplotlib**:

| Piece | Location | Lines | Depends on the GUI? |
|---|---|---|---|
| Question generation | `game_frame.py:129-163` | ~35 | No |
| Session record shape | `game_frame.py:189-200` | ~12 | No |
| Feature extraction | `insights.py:49-77` | ~29 | No — pure pandas |
| Metric computation | `insights.py:86-169` | ~85 | Only for rendering |

**Roughly 160 lines of portable logic.** Everything else is UI chrome and plotting plumbing, neither
of which survives the port anyway.

### Recommended shape

```
Browser
  ├── Drill screen         config → timed loop → per-question timing
  │      └── emits records in the EXISTING schema (§3)
  ├── Storage              localStorage first; a real table later
  └── Insights screen      the same charts, client-side
```

**Keep the schema byte-identical.** Then desktop and web sessions are interchangeable, the web
analytics can be seeded with real desktop data on day one, and the Python analysis stays usable as a
cross-check. That compatibility is worth more than any refactor it might tempt you into.

### Which charts to port, in priority order

| # | Chart | Value on the web | Difficulty |
|---|---|---|---|
| **1** | **Digit difficulty heatmap** | ⭐ Highest — the signature visual | Low |
| **2** | Accuracy by response-time bucket | High — "you rush and miss" | Low |
| 3 | Average time by operation | High — instantly legible | Trivial |
| 4 | Response time with rolling average | High — shows warm-up and fatigue | Low |
| 5 | Time vs. operand size | Medium — needs a regression line | Medium |
| 6 | Feature comparison | High **after T07** — currently misleading | Medium |
| 7 | Session summary tiles | High — cheap, anchors the page | Trivial |
| 8 | Error distribution by operation | Medium — overlaps #3 | Trivial |

Start with 1, 3, 4, and 7. That is a complete, honest analytics view; add the rest as data
accumulates.

### What the web version can do that the desktop cannot

- **Progress across sessions.** Every chart today is within-session or naively pooled. Trending
  accuracy and speed over weeks is the obvious missing view, and the `timestamp` field already
  supports it.
- **Targeted practice.** The analysis identifies weak digit patterns, but nothing feeds that back
  into question generation. Weighting generation toward weak spots closes the loop and turns an
  analytics demo into an actual training tool. **This is the highest-value feature available** —
  measure, analyse, adapt.
- **Shareable results.** A session summary card is natural on the web and impossible on the desktop.

### Web tasks

Assumes T09 has landed — it is the real prerequisite.

| ID | Task | Size | Notes |
|---|---|---|---|
| **W01** | Port question generation to TypeScript | S | Direct translation of `generate_question`; keep the operand-range semantics exactly. |
| **W02** | Drill UI — config → timed loop → results | M | Time each question with `performance.now()`; do not derive it from render timestamps. |
| **W03** | Session recorder emitting the §3 schema | S | Byte-identical field names. `localStorage` first. |
| **W04** | Port `compute_insight_flags` to TypeScript | S | Pure function; port the T09 tests alongside it. |
| **W05** | Charts 1, 3, 4, 7 | M | The heatmap is the one to get right. |
| **W06** | Import desktop `session_insights.json` | S | Launches the web version with real data instead of an empty state. |
| **W07** | Cross-session progress view | M | New capability — accuracy and speed over time. |
| **W08** | Adaptive question weighting | M | Feeds weak-spot analysis back into generation. The differentiating feature. |

### Two things to get right

**Timing fidelity.** The entire dataset's value rests on `time_taken_sec` being accurate. Use
`performance.now()`, start the clock when the question paints rather than when state updates, and
stop it on submit. If timing is noisy, every chart downstream is decorative.

**Empty states.** With 9 questions on record, most charts are visually meaningless at first. Decide
deliberately what a first-time visitor sees — either seed with demo data clearly labelled as such,
or show a "play three sessions to unlock" state. Do not ship charts that render noise.

---

## 11. Suggested Sequencing

**Phase 1 — about an hour, unblocks everything:** T01, T02, T03. Three small fixes that repair the
silently broken CLI feature, the broken install path, and the broken README images.

**Phase 2 — solid desktop:** T04, T05, T06, T07, T08, T10 → then T09 (tests) → T11 (README).

**Phase 3 — web version:** W01–W06 for a working game section with analytics; W07–W08 for the
features that make it more than a port.

**Parallelism:** T02, T03, T06, and T10 are independent. T04 and T05 both edit `game_frame.py` and
must run sequentially. T01 gates T07 and T08.

---

## 12. Open Questions

1. **Is the repository public?** Determines how urgent T03 (broken README images) and T10 (tracked
   `.idea/`) are.
   ANSWER : Yes 
2. **Where did the demo-chart data go?** `Data/Demo_*.png` show ~50 questions; the JSON holds 9, and
   it is gitignored. Regenerating equivalent screenshots needs a few real sessions.
   ANSWER : Unsure
3. **Should negative subtraction answers stay?** (D20) Defensible for drilling, surprising for a
   casual player. A config toggle costs little.
   ANSWER : Sure
4. **Working copy location.** The project currently lives inside a OneDrive-synced folder. Sync can
   race with in-place edits during a batch of changes; consider working from a local path and syncing
   back, or pausing sync while making bulk edits.
   ANSWER : Moved to a local copy already. 
