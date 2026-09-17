---
name: brief
description: "Produce a company or portfolio brief from the file-route records and show it. Use when someone asks 'what's the state of <company>?', wants a one-page company summary (profile, track position and target, recent interactions, open flags), or a portfolio overview. Builds an A2UI blueprint plus a Markdown version; opens the static renderer when a browser is available, otherwise prints the Markdown."
---

# Brief

## Purpose

Answer "what's the state of Acme?" with a single, display-only brief built from the
records already produced for a reporting period. A company brief shows the profile,
the track position and target, the last three interactions, and any open flags. A
portfolio brief shows one row per company.

The brief never changes any record. It reads the file-route records only
(`workspace/state/<period>/records.json`) — it does not read a store or a source
system.

## When to use

- "What's the state of <company>?" / "Give me a brief on <company>."
- "Show me the portfolio." / "Portfolio overview."

## Prerequisites

- Records exist for the period: run the parse -> apply-mapping flow first so
  `workspace/state/<period>/records.json` is present. If none exist, the command
  says so; run `impactos apply-mapping` (see the CLI) before retrying.

## How it works

1. The deterministic CLI builds two equivalent files under `workspace/briefs/`:
   an A2UI v0.9.1 blueprint (`<name>.json`) for the renderer and a Markdown
   version (`<name>.md`). The blueprint uses only the eight catalogue components
   and is validated before it is written — an invalid brief is refused, never
   shown as a blank page.
2. The skill then shows the brief. If a browser is available it opens the
   committed static renderer (`renderer/dist/index.html`); the helper picks the
   blueprint file in the file dialog. If there is no browser (a terminal-only
   harness), it prints the Markdown instead.

## Steps

Run the helper, which does both the build and the display:

```sh
# A single company (use the record id, e.g. HL-001 or ACME-1):
skills/brief/show-brief.sh --company <company-id>

# The whole portfolio:
skills/brief/show-brief.sh --portfolio
```

Optional flags pass straight through to the CLI:

- `--period <label>` — read a specific period (default: the latest available).
- `--records <path>` — read a specific `records.json` (default: resolved from the
  workspace).
- Set `IMPACTOS_BRIEF_NO_BROWSER=1` to force the Markdown output even when a
  browser is present.

You can also drive the CLI directly:

```sh
impactos brief --company <company-id>     # writes workspace/briefs/company-<id>.json and .md
impactos brief --portfolio                # writes workspace/briefs/portfolio.json and .md
```

## Notes

- Display-only: nothing in the brief writes back into a record.
- Briefs contain personal data and are written under the git-ignored
  `workspace/briefs/`; never commit them.
- The renderer is a committed, pre-built static page. Helpers never need Node to
  view a brief; maintainers rebuild it from `renderer/src` (see `renderer/README.md`).
