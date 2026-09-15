# Math Drill Web

The web frontend for Math Drill, built with Astro and TypeScript.

## Commands

Run these commands from `web/`:

```sh
npm install
npm run dev       # local development server
npm run check     # Astro/TypeScript diagnostics
npm test          # deterministic pure-logic tests
npm run build     # static production build in dist/
npm run preview   # preview the production build
```

## W00 decisions

- Astro provides the static site shell, file-based routes, layouts, and project
  documentation. The site is configured for static output; the hosting target is
  intentionally deferred until deployment is requested.
- TypeScript modules will hold the GUI-free drill and analytics logic. Browser
  behavior will live in explicit client-side islands or Astro component scripts;
  timers and `localStorage` will never run in server-rendered component code.
- The first milestone uses browser `localStorage`, with JSON import/export for
  the Python desktop session contract. No backend, account system, or database
  is required.
- W03 persistence lives in `src/lib/storage.ts`. It validates the full session
  array before use, preserves equal-name sessions as separate entries, accepts
  legacy `question_type`, and keeps browser-only IDs out of exported JSON.
- The first interactive implementation will use Astro components and standard
  TypeScript. A small framework integration may be added later only if the
  drill's stateful UI warrants it.
- The initial chart approach remains undecided until W05; choose it based on the
  four required views and accessibility needs rather than adding a library to
  the scaffold prematurely.
- The supported baseline is current evergreen Chrome, Edge, Firefox, and Safari
  on desktop and mobile widths. The drill uses `performance.now()` for elapsed
  timing and a single monotonic deadline. Hidden-tab behavior, minimum sample
  thresholds, and non-finite numeric input handling are explicit W02/W04 decisions.
- First-time users see an honest empty state until there is enough data for a
  comparison; the exact thresholds must match the ported Python metrics.

## W02 timed drill

The first browser workflow is complete: configure a session, answer generated
questions against a monotonic deadline, and review the score when time expires.
`src/lib/drill.ts` keeps timing and question consumption deterministic through
injected clocks, starts response timing only after the UI arms a rendered question,
and saves a finished session at most once through the W03 storage adapter. Blank
answers are ignored, invalid non-empty answers are recorded as incorrect, and a
submission at or after the deadline is rejected. Navigating away or closing the
tab abandons an active drill; hidden tabs continue against the same deadline and
the visible timer catches up when the tab returns.

## Import and export

Use the JSON picker to append desktop history. Every import appends all sessions,
including empty sessions and repeated names; importing the same file twice adds
duplicates. Export all history first for a backup. Export downloads the canonical
desktop array as `session_insights.json`; it includes no browser session IDs.
Legacy `question_type` is accepted and exported as `operation`.

History belongs to this browser and origin. Clearing browser data removes it;
there is no cloud backup. Avoid simultaneous edits from multiple tabs because
localStorage read/append/write is not a cross-tab transaction.

`npm test` includes a synthetic export checked by the real Python loader and
summary functions. Install the root Python development environment first. On
Windows it defaults to `../.venv/Scripts/python.exe`; elsewhere it uses `python3`.
Set `MATHDRILL_PYTHON` to override the interpreter. Tests never read practice logs.

## Planned structure

```text
src/
  components/   Astro shell and interactive drill/insight islands
  layouts/      shared document layout
  lib/          pure TypeScript generation, records, storage, and metrics
  pages/        file-based routes
  styles/       shared CSS
```
