#!/usr/bin/env python3
"""Regenerate store/seed/tracks.sql from contract/tracks.json.

Deterministic: identical tracks.json produces identical tracks.sql. Run from the
repository root:

    python3 store/seed/generate_tracks.py > store/seed/tracks.sql
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKS = REPO_ROOT / "contract" / "tracks.json"


def q(value):
    if value is None:
        return "null"
    return "'" + value.replace("'", "''") + "'"


def main() -> None:
    tracks = json.loads(TRACKS.read_text(encoding="utf-8"))
    out = [
        "-- impactOS store seed: milestone tracks and rungs.",
        "-- Generated from contract/tracks.json (system tracks, D-07). Idempotent.",
        "-- Regenerate with: python3 store/seed/generate_tracks.py > store/seed/tracks.sql",
        "",
    ]
    for track in tracks["tracks"]:
        out.append("insert into public.milestone_track (slug, name, description)")
        out.append(f"values ({q(track['slug'])}, {q(track['name'])}, {q(track.get('description'))})")
        out.append(
            "on conflict (slug) do update set name = excluded.name, "
            "description = excluded.description, updated_at = now();"
        )
        out.append("")
    for track in tracks["tracks"]:
        for rung in track["rungs"]:
            out.append(
                "insert into public.milestone_definition "
                "(track_id, rung_order, name, evidence_description, objective_signal, funder_stage)"
            )
            out.append(
                f"select mt.id, {int(rung['order'])}, {q(rung['name'])}, "
                f"{q(rung.get('evidence_description'))}, {q(rung.get('objective_signal'))}, "
                f"{q(rung.get('funder_stage'))}"
            )
            out.append(f"from public.milestone_track mt where mt.slug = {q(track['slug'])}")
            out.append(
                "on conflict (track_id, rung_order) do update set name = excluded.name, "
                "evidence_description = excluded.evidence_description, "
                "objective_signal = excluded.objective_signal, "
                "funder_stage = excluded.funder_stage, updated_at = now();"
            )
            out.append("")
    print("\n".join(out))


if __name__ == "__main__":
    main()
