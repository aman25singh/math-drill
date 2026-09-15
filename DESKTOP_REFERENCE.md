> Frozen desktop reference. The supported product is now the web app in `web/`.
> The installation and screenshots below describe the historical Python app.

# Math Drill

**A timed arithmetic drill that tells you *which digits* are slowing you down.**

Most drill apps give you a score. This one logs every answer with millisecond
timing and keeps the operands as numbers, not just as a rendered string — so it
can go back and answer questions a score never can:

> Operands containing a **9** cost you **4.98s** on average.
> Operands containing a **1** cost you **3.44s**.

That is the point of the project. The drill exists to generate the data; the
feature extraction is what makes the data worth having. Both numbers above are
read straight off the first chart — it is the evidence for the claim, not an
illustration of it.

**Average time and error rate for every operand digit, 1–9:**

![Heatmap of average answer time and error rate per operand digit](Data/Demo_1.png)

**Answer time against the size of the larger operand, coloured by correctness:**

![Scatter plot of answer time versus larger operand](Data/Demo_2.png)

> **About those screenshots:** they are real measurements, but they are dated.
> Both were produced by an earlier version of the charting code against a much
> larger practice log that is no longer in this repo, so they do not match
> today's output: the tool now draws all eight panels as a single 2×4 figure,
> and the heatmap's second column is called `error_rate` rather than
> `incorrect_rate`. Session logs are local and gitignored; a fresh checkout has
> no practice data. See [How much data you need](#how-much-data-you-need).

---

## Why I Built This
As someone preparing for quantitative finance and data-intensive roles, I wanted a tool that not only drills arithmetic speed but also tracks and analyzes improvement over time.

This project combines my interests in Python development, data visualization, and performance optimization into a practical, interactive tool.

It’s designed to:
- Simulate high-pressure, time-bound calculations common in finance, analytics, and tech assessments
- Provide data-backed insights to identify strengths and weaknesses
- Demonstrate my ability to build complete, user-friendly applications with analytics capability

---

## What it measures

**Current eight-panel layout, using clearly labelled synthetic data:**

![Current analytics overview with eight panels, generated from synthetic demo sessions](Data/Demo_current.png)

Regenerate this illustration with `python -m scripts.render_demo` from the
project root. It does not read or modify your practice log.

Every answered question is scored against a set of derived features, and each
feature is compared **against its own opposite** — the difference is the
insight, not the absolute time.

| Feature | What it asks |
|---|---|
| `has_1` … `has_9` | Does either operand contain this digit, anywhere in it? |
| `is_carry_addition` | Does the addition carry into the tens? (17+25 yes, 12+13 no) |
| `is_borrow_subtraction` | Does the subtraction borrow? (32−17 yes, 38−12 no) |
| `is_round_operand_1/2` | Is that operand a multiple of 10? |
| `num_digits_op1/op2` | How long is each operand? |
| `operand_diff` | How far apart are the two operands? |
| `max_operand` | How big is the larger one? |

Boolean features compare their true set against their false set. Numeric
features are **binned**, and each bin is compared against the overall mean.

### What the charts show

`math-drill-insights` renders one 2×4 figure with these eight panels:

| Panel | |
|---|---|
| Avg Time by Operation | mean seconds per `add` / `sub` / `mul` / `div`, annotated with `n` |
| Digits That Trip You Up | the digit heatmap — avg time and error rate for `has_1`…`has_9` |
| Time vs Operand Size | answer time against `max_operand`, with a fitted line |
| Response Time (with Rolling Avg) | every answer in order, plus a 5-question rolling mean |
| Accuracy by Time Bucket | accuracy split into `<2s`, `2–4s`, `4–6s`, `6s+` |
| Slowest Patterns (vs baseline) | the top 8 features by how many seconds they cost **over baseline** |
| Session Summary | totals, accuracy, average time, questions per minute |
| Error Distribution by Operation | which operation your wrong answers came from |

Panels that do not have enough data yet say so in place rather than rendering an
empty or misleading chart.

## Install

Requires **Python 3.10+**.

```sh
git clone https://github.com/aman25singh/math-drill.git
cd math-drill
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

pip install -e .
```

Or, for the pinned set:

```sh
pip install -r requirements.txt
```

### A note on Tkinter

**Tkinter is not in `requirements.txt`, and must not be.** It ships with
CPython and is not installable from PyPI. It used to be listed there, which
made `pip install -r requirements.txt` fail for everyone who cloned the repo.

On most Debian/Ubuntu systems it is packaged separately:

```sh
sudo apt install python3-tk
```

The python.org installers for Windows and macOS include it already.

## Run

```sh
math-drill                          # the drill
math-drill-insights                 # analyse every session
math-drill-insights "<session>"     # analyse one session
```

Equivalently, without the console entry points:

```sh
python -m mathdrill.app
python -m mathdrill.insights
```

Useful flags:

```sh
math-drill-insights --file path/to/session_insights.json
math-drill-insights --save charts.png     # write a PNG instead of opening a window
```

## Where your data goes

Sessions are appended to `session_insights.json`, resolved in this order:

1. `$MATHDRILL_DATA_DIR`, if set.
2. `<repo>/Data/` when running from a source checkout.
3. A per-user data directory (`%LOCALAPPDATA%\math-drill` on Windows,
   `~/.local/share/math-drill` elsewhere) when pip-installed.

The path is always absolute. It used to be the bare relative string
`"Data/session_insights.json"`, so where a session got saved depended on
whatever directory you happened to launch the app from.

Writes are atomic — the file is written to a temporary file and moved into
place — so an interrupted save cannot truncate your history.

## Data contract

Every answered question produces one flat record. **Storing the operands
separately from the rendered question string is exactly what makes the
digit-level feature extraction possible.** Treat this as the stable contract
between the desktop app and any future frontend.

```json
{
  "timestamp": 1754847942.753827,
  "question": "25 - 25",
  "operation": "sub",
  "operand_1": 25,
  "operand_2": 25,
  "correct_answer": 0,
  "user_answer": 0.0,
  "time_taken_sec": 2.0723612308502197,
  "correctness": true
}
```

Wrapped per session:

```json
{ "session_name": "...", "duration": 120, "insights": [ ... ] }
```

`operation` is one of `add`, `sub`, `mul`, `div`. `user_answer` is `null` when
the entry was not a number.

> **Schema change:** records used to carry a `question_type` field that was
> always identical to `operation`. It is no longer written. Existing logs
> containing it still load — the reader maps it onto `operation` and drops it.

## How much data you need

The analytics are comparative, so they need volume before they say anything
true:

- **Under ~20 answers** — the charts render, but treat every comparison as
  noise. The tool prints a warning at this point.
- **A few hundred answers across several sessions** — digit and carry
  comparisons start to separate from noise.
- A boolean feature is skipped unless it has at least 5 questions on **both**
  sides of its comparison, and a numeric bin is skipped unless it holds at
  least 5. Skipping beats showing a confident-looking average built on two
  data points.

Session logs are not committed. Play several sessions to build your own dataset.
Overall questions per minute is the arithmetic mean of the individual session
rates, each calculated from its configured duration. Reusing a session name
keeps those sessions separate in the summary; filtering by name selects all
sessions with that name. Sessions with no answers do not enter these comparisons.

## Two deliberate design choices

**Division is always exact.** The dividend is built as `divisor × quotient`, so
there is never a remainder. Asking for a decimal quotient would change what you
have to type and what "correct" means. A consequence: the old
`is_decimal_division` feature flag could never be true, and `is_exact_division`
was always true for division rows. Both were dead, and both have been removed
rather than left in place looking meaningful.

**Subtraction can go negative.** Subtraction draws from the *addition* ranges
and may order the operands either way, so `2 - 100` is a legitimate question.
That is deliberate drilling practice, but it used to be an accident of the code
rather than a decision. It is now a checkbox on the setup screen
(`allow_negative_answers`), on by default.

## Project layout

```
mathdrill/
  __init__.py    package docstring and __version__
  core.py        drill logic: config, question generation, scoring, records
  features.py    feature extraction and metrics (pandas; no plotting)
  storage.py     session JSON load/save and validation
  app.py         Tkinter setup screen
  game_frame.py  Tkinter drill screen
  insights.py    matplotlib/seaborn charts
tests/
  test_core.py       question generation, scoring, config validation
  test_features.py   feature extraction, metrics, the session-filter regression
  test_storage.py    load/save, malformed input, legacy records
```

The tests open no GUI and never touch your real session file.

`core.py`, `features.py` and `storage.py` import **neither tkinter nor
matplotlib**. The drill logic and the analysis are usable from a CLI, a test,
or a future web port without dragging a GUI along.

## Development

```sh
pip install -e ".[dev]"

pytest
ruff check .
ruff format --check .

pip-audit -r requirements.txt        # runtime dependencies
pip-audit -r requirements-dev.txt    # dev dependencies
```

CI runs all of the above on every push, plus a clean-virtualenv install of
`requirements.txt` — the step that would have caught the unusable `tkinter`
line. Both requirements files are audited: checking only the runtime one is
how a known CVE in the pinned `pytest` went unnoticed.

`pytest` treats `FutureWarning` and `DeprecationWarning` as errors, so pandas
and seaborn deprecations surface as test failures rather than console noise.

## License

[MIT](LICENSE)
