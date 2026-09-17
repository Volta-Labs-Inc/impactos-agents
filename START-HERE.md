# Start here (for helpers)

This folder is a work kit for helping an incubator or accelerator get their data into the funder spreadsheet. You do **not** need to be technical. You open this folder in an AI app that can see files on your computer, and the app walks you through it.

You are the helper. The organisation keeps ownership of their data. Nothing they give you should be committed back to GitHub.

---

## Before you begin (once)

1. **Get access to this repository** — ask Matt for a GitHub invite (private repo). Accept the email invite, then ask the AI app to clone it, or clone it yourself.
2. **Use an AI app that can reach a folder** — Claude Code, Cursor, or Claude Cowork with folder access. Chat-only Claude (no files) will not work.
3. **Have Python 3.9+ installed** — on Mac, if unsure, ask the app to check. If it is missing, install from [python.org](https://www.python.org/downloads/) or `brew install python@3.12`, then come back.

**First thing to say to the app** (copy/paste):

> Open this impactOS Agents folder. Run preflight. If anything fails, tell me exactly what to fix. When preflight is green, start onboarding for [organisation name]. Ask me one question at a time.

Replace `[organisation name]` with the org you are helping (for example `WorkSource Alliance`).

---

## What “done” looks like for crawl

Crawl = inventory only. You succeed when:

- You know **where** each kind of data lives (companies, people, programs, funding, meetings).
- You have a **source map** (what systems, who owns them by name/role — not their email).
- For each data type you have recorded whether it **stays** in their current system or would later move to an optional store.
- You have **not** invented missing demographics, company type, or funding amounts.

You do **not** need a finished spreadsheet to finish crawl. Getting to the spreadsheet is the next phase (walk), after crawl.

---

## How a typical session goes

1. **Preflight** — the app checks Python and this folder. Fix anything it flags.
2. **Onboarding** — one question at a time. When it asks for exports, point it at real files the org shared (CSV/Excel). It reads them and confirms what it found before moving on.
3. **Routes** — it recommends stay vs store per data type; you (with the org contact) choose; it records the choice.
4. **Stop when crawl is complete** — you can pause anytime and resume later, even in a different AI app, as long as you keep the same folder.

When the org is ready for the spreadsheet, say:

> Map the companies export for this period, then run the period export when I confirm.

---

## Rules (do not skip)

- **Never write into the org’s systems** — HubSpot, Airtable, their live sheets. Read exports only.
- **Never guess** demographics, company type, or funding. Leave blank and flag for a person.
- **Do not put personal data in git** — exports and reports stay under `workspace/` (ignored). Only mappings and operating notes that pass the privacy check may be committed, and only if Matt says so.
- **Record people by name or role**, not email or phone, in notes you might share.
- **One main contact at the org** — without someone who will spend ~2 hours a week for a few weeks, pause and revisit fit with Matt.

---

## When you hit a bump

Tell the app what went wrong in plain language, or ping Matt with:

- which org
- which step (preflight / onboarding / mapping / export)
- the exact message the app showed

Matt will adjust the kit and you pull the update (`git pull`, or ask the app to update the folder).

---

## Out of scope for this kit (for now)

- Setting up a live database / Supabase for the org  
- Founder self-serve portals  
- Replacing systems the org already likes  

Those come later, only if crawl and walk prove useful.
