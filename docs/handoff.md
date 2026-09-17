# Workspace handoff and transfer

This project keeps two kinds of material apart on purpose:

- **The repository** holds the tool, the data contract, mappings and operating
  notes. It is safe to clone and share; it contains no personal data.
- **The workspace** (`workspace/`) holds the organisation's own exports, the
  records built from them, the reports, provenance, the period baselines and the
  access record. It is git-ignored wholesale and never committed, because it
  holds personal data.

Because the two are separate, moving the work to another machine or another
person is a deliberate, two-part copy rather than a single push.

## Transfer the work to another machine

1. **Clone the repository** on the destination machine, the same way it was first
   obtained (`git clone`), and check out the same branch.
2. **Copy the `workspace/` folder** from the source machine to the destination,
   into the root of the clone, replacing the empty one. Use any private,
   encrypted channel your organisation approves for personal data (a managed
   drive, an encrypted archive, a direct secure copy). The workspace never goes
   through git.

That is the whole transfer: the clone provides the tool and the mappings, and the
copied workspace provides the sources, records, baselines, reports and the access
record.

## Confirm the transfer reproduced the same result

The tool is deterministic, so the same inputs must produce the same outputs on the
destination machine.

1. On the destination, run `impactos compare --period <period>`.
2. Compare the acknowledgement hash it prints (and the `compare.json` it writes)
   against the source machine's for the same period. They must match. A matching
   hash pair is the evidence that the workspace transferred intact and the tool
   reproduces the same comparison from it.

## The access record travels with the workspace

Who may reach a workspace is recorded in `workspace/access.json` and moves with the
folder. Keep it current at every handoff:

- **Granting access** to a new person:

  ```
  impactos access grant --name "Full Name" --email name@example.org \
      --scope helper --start 2026-06-01
  ```

  `--scope` is `helper` for a file-route helper or `staff` for the organisation's
  own staff.

- **Ending access** when a person hands the work back. This requires written
  confirmation that their copy of the workspace was deleted; without it the
  command refuses:

  ```
  impactos access end --name "Full Name" \
      --deletion-confirmed-by "Owner Name" --confirmed-at 2026-09-16 \
      --confirmation-text "Workspace copy deleted from the helper's laptop; confirmed in writing."
  ```

- **Reviewing** the record at any time:

  ```
  impactos access list
  ```

Ending access is a written control, not a technical deletion the tool performs:
the person still holds their copy until they delete it, and the confirmation text
is the record that they did.
