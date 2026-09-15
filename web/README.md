# Math Drill Web

The supported Math Drill app, built with Astro and TypeScript. The Python desktop
source is frozen; web development and CI do not require Python.

## Setup and commands

Use Node **24.21.0** (`.node-version`) or a later Node 24 patch, with npm. Verification
uses this runtime; Node 24.11.1 exhibited a Windows libuv cleanup crash.
Make sure both `node --version` and npm's child processes use this runtime.
On Windows, an older system `npm.cmd` may select its adjacent Node executable;
updating PATH alone does not necessarily change the runtime npm uses.

Windows can also briefly lock generated files on the newer runtime. The Astro
launcher retries removal/rename operations only within `.astro/vite-cache` and
`dist/.prerender`, up to eight times. Persistent failures still fail the command;
source files and browser history are outside this workaround.

Run from `web/` (use `npm.cmd`/`npx.cmd` in Windows PowerShell):

```sh
npm ci
npm run dev           # local development server
npm run format        # format source
npm run lint          # ESLint and format validation
npm test              # pure logic + fixed metric fixtures; no Python
npm run check         # Astro/TypeScript diagnostics
npm run build         # static production files in dist/
npm run verify        # lint -> tests -> check -> build, stops on failure
npx playwright install chromium
npm run test:e2e       # production preview + isolated desktop/mobile browsers
npm run preview       # playable production preview
```

CI runs audit, verification and browser tests on every push/PR. Failed checks remain
failures; no deployment step is configured. The old desktop workflow is manual-only.

## Drill behavior

Configuration selects operations, duration and operand ranges. Division constructs
an exact dividend from divisor × quotient. Subtraction can be negative; the sign
button supports keyboards that lack a minus key. Unsafe numeric configurations
are rejected before play.

Response timing uses `performance.now()`, separate from stored Unix timestamps.
The total session has one deadline. After rendering each question, the UI waits
for two animation frames before enabling input and arming response timing. This
defines a presentation boundary after a paint opportunity, not an exact physical
display measurement. Blank submissions are ignored; nonempty invalid decimal
input is recorded as incorrect with a null answer. Held Return events are ignored.

The deadline continues when a tab is hidden. A pending unseen question is not
armed until the tab can render; an already shown question's response time includes
time spent away. Expiry is checked on submit even if timer callbacks arrive late.
Leaving/reloading the page discards an unfinished drill and cancels callbacks.
Returning via browser history starts at setup. A completed session saves once.
If saving fails, its records remain available as a separate JSON download.

## Insights

The four views are a session summary, digit difficulty, average time per operation,
and the complete response sequence with a five-answer rolling mean. Tables expose
values, units and counts without relying on colour; long tables scroll locally on
small screens. Session numbers distinguish repeated names and unnamed sessions.

Under 20 answers, the UI explains that comparisons are early observations. Digit
groups with fewer than five answers are marked as small samples. Feature
comparisons require five answers on both sides for booleans; numeric groups use
quantile bins with an equal-width fallback and compare with the overall mean.

Speed averages individual configured-duration rates. Sessions without answers
are excluded. Zero-duration sessions still contribute answers but not speed;
if no duration is usable, the UI says “Unavailable”. Equal timestamps preserve
input order. Metric sort keys use 10 decimal places to avoid insignificant
floating-point differences; displayed values are rounded for readability.

## History and migration

History belongs to this browser and origin. There is no cloud backup. Clearing
browser data removes it; export JSON regularly. Avoid simultaneous writes in
multiple tabs: localStorage read/append/write is not a cross-tab transaction.

Import validates the entire array before appending it. It preserves repeated
names and empty sessions. Importing the same file twice deliberately adds
duplicates. Blank or malformed files and storage failures preserve existing data.

Export downloads all history as `session_insights.json`. Its snake_case record
format also supports migration from the old desktop app. Legacy `question_type`
is normalized to `operation`; browser IDs are not exported. This compatibility
is a migration convenience, not a permanent restriction on future web features.

## Tests and scope

`src/lib/fixtures/metrics.json` stores the synthetic inputs and Python-verified
expected results captured at `3dcf5fb`. All 29 scenarios now run without Python,
with numerical tolerance 1e-10. Expected values must not be regenerated from the
implementation under test.

Playwright tests use isolated profiles and synthetic imports, never personal
history. They check a full timed drill, held Return, expiry, reload, navigation
cleanup, storage failure recovery, import/export, safe repeated-name selection,
empty data, and desktop/mobile widths. They use Chromium at 1440×1000 and an
emulated Pixel 7. Physical mobile devices and Firefox/Safari are not yet verified.
User playthrough is the final M1 acceptance step.

## Structure

- `src/lib/`: configuration, generation, timing, storage and metric logic/tests.
- `src/scripts/app.ts`: drill UI lifecycle and import/export controls.
- `src/scripts/analytics.ts`: safe DOM rendering of the four analytics views.
- `src/pages/index.astro`: static page and accessible form controls.
- `src/styles/app.css`: responsive layout and shared visual styles.
- `e2e/`: production browser regression tests.

After M1 acceptance: cross-session progress (W07), then explainable adaptive
practice (W08). Hosting/deployment remains a separate user-directed step.
