# Math Drill Web

The web frontend for Math Drill, built with Astro and TypeScript.

## Commands

Run these commands from `web/`:

```sh
npm install
npm run dev       # local development server
npm run check     # Astro/TypeScript diagnostics
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

## Planned structure

```text
src/
  components/   Astro shell and interactive drill/insight islands
  layouts/      shared document layout
  lib/          pure TypeScript generation, records, storage, and metrics
  pages/        file-based routes
  styles/       shared CSS
```
