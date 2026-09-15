# Math Drill

A browser-based mental arithmetic trainer that helps you understand which number
patterns slow you down.

**Practice → record timings → identify weak patterns → target practice → track improvement.**

The web app is the only product under active development. The older Python desktop
app is frozen as source reference; it is not required to run, build or test the web
app. Historical instructions are in [DESKTOP_REFERENCE.md](DESKTOP_REFERENCE.md).

## Run locally

Requires **Node 24.21.0 or newer within Node 24**, plus npm. Older Node 24 versions
can fail during Astro's Windows build cleanup.

```sh
cd web
npm ci
npm run dev
```

Open the local URL printed by Astro. On Windows PowerShell use `npm.cmd` if script
execution policy prevents running `npm`.

## What works today

- Timed arithmetic drills with configurable operations and operand ranges.
- Exact division and optional negative subtraction.
- Per-answer timing, score and saved session history.
- Digit difficulty, operation timing, response sequence and session summary.
- Separate selection of sessions with identical names.
- JSON backup/import, including migration of old desktop records.

History stays in this browser and origin. There is no account, backend or cloud
backup. Export JSON before clearing browser data. Small samples are labelled as
early observations, not established weaknesses.

Cross-session progress and adaptive practice are the next product milestones after
browser acceptance. No public deployment is configured.

## Verify

```sh
cd web
npm run verify
npx playwright install chromium
npm run test:e2e
```

Verification runs lint/format checks, unit and fixed-fixture metric tests, Astro
type checking and the production build. Browser tests run against the built site
in isolated desktop/mobile Chromium contexts. No Python installation or real
practice history is used. CI performs the same checks.

See [web/README.md](web/README.md) for timing rules, data handling, architecture,
the browser verification scope, and preview commands.

## License

[MIT](LICENSE)
