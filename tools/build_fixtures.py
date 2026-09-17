"""Deterministically (re)build the synthetic Harbourline fixture.

Standard library only. Everything the fixture contains is invented; every email
is on ``@example.org``. The period-2-vs-1 deltas are computed here from the same
rows that are written to the CSVs, and written to ``expected/compare.json`` so
the encoded deltas cannot drift from the data. The test-suite independently
re-derives the deltas from the CSVs and checks them against ``compare.json``.

Run: python3 tools/build_fixtures.py
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIX = REPO_ROOT / "fixtures" / "harbourline"

# Fixed timestamp so generated workbooks are byte-stable.
ZIP_TIME = (2026, 9, 16, 0, 0, 0)

DEMOGRAPHIC_COLUMNS = [
    "dg_women",
    "dg_indigenous",
    "dg_youth",
    "dg_immigrants",
    "dg_racialized",
    "dg_2slgbtq",
    "dg_persons_with_disabilities",
    "dg_official_language_minority",
]

# record_id -> company facts, per period. record_id is stable across periods for
# the same company.
PERIOD1 = [
    {"record_id": "HL-001", "company_name": "Tidewater Robotics", "contact_first_name": "Ava", "contact_last_name": "Nguyen", "contact_email": "ava.nguyen@example.org", "employees": 12, "stage": "Growth", "city": "Halifax", "province": "NS"},
    {"record_id": "HL-002", "company_name": "Beacon Health Systems", "contact_first_name": "Liam", "contact_last_name": "Okafor", "contact_email": "liam.okafor@example.org", "employees": 8, "stage": "Early Adopters", "city": "Moncton", "province": "NB"},
    {"record_id": "HL-003", "company_name": "Saltmarsh Analytics", "contact_first_name": "Priya", "contact_last_name": "Sharma", "contact_email": "priya.sharma@example.org", "employees": 5, "stage": "MVP", "city": "Charlottetown", "province": "PE"},
    {"record_id": "HL-004", "company_name": "Nectar Foodworks", "contact_first_name": "Diego", "contact_last_name": "Alvarez", "contact_email": "diego.alvarez@example.org", "employees": 20, "stage": "Growth", "city": "St. John's", "province": "NL"},
    {"record_id": "HL-005", "company_name": "Kelp Bioscience", "contact_first_name": "Mei", "contact_last_name": "Tanaka", "contact_email": "mei.tanaka@example.org", "employees": 3, "stage": "Idea", "city": "Halifax", "province": "NS"},
    {"record_id": "HL-006", "company_name": "Granite Ledger", "contact_first_name": "Noah", "contact_last_name": "Bergeron", "contact_email": "noah.bergeron@example.org", "employees": 15, "stage": "Scale", "city": "Fredericton", "province": "NB"},
]

# Period 2 adds demographic columns. Deltas vs period 1:
#   HL-001 12 -> 14, HL-003 5 -> 9, HL-004 20 -> 18 (three changed employee counts)
#   HL-007 new company (new id, new name)
#   HL-006 absent
#   HL-008 new id whose name matches HL-001 (must be flagged unmatched, not merged)
PERIOD2 = [
    {"record_id": "HL-001", "company_name": "Tidewater Robotics", "contact_first_name": "Ava", "contact_last_name": "Nguyen", "contact_email": "ava.nguyen@example.org", "employees": 14, "stage": "Growth", "city": "Halifax", "province": "NS", "dg_women": "Yes"},
    {"record_id": "HL-002", "company_name": "Beacon Health Systems", "contact_first_name": "Liam", "contact_last_name": "Okafor", "contact_email": "liam.okafor@example.org", "employees": 8, "stage": "Growth", "city": "Moncton", "province": "NB", "dg_immigrants": "Yes"},
    {"record_id": "HL-003", "company_name": "Saltmarsh Analytics", "contact_first_name": "Priya", "contact_last_name": "Sharma", "contact_email": "priya.sharma@example.org", "employees": 9, "stage": "Early Adopters", "city": "Charlottetown", "province": "PE", "dg_women": "Yes", "dg_youth": "Yes"},
    {"record_id": "HL-004", "company_name": "Nectar Foodworks", "contact_first_name": "Diego", "contact_last_name": "Alvarez", "contact_email": "diego.alvarez@example.org", "employees": 18, "stage": "Growth", "city": "St. John's", "province": "NL", "dg_racialized": "Yes"},
    {"record_id": "HL-005", "company_name": "Kelp Bioscience", "contact_first_name": "Mei", "contact_last_name": "Tanaka", "contact_email": "mei.tanaka@example.org", "employees": 3, "stage": "MVP", "city": "Halifax", "province": "NS", "dg_immigrants": "Yes"},
    {"record_id": "HL-007", "company_name": "Harbour Freight Labs", "contact_first_name": "Sofia", "contact_last_name": "Martins", "contact_email": "sofia.martins@example.org", "employees": 6, "stage": "Idea", "city": "Sydney", "province": "NS", "dg_youth": "Yes"},
    {"record_id": "HL-008", "company_name": "Tidewater Robotics", "contact_first_name": "Omar", "contact_last_name": "Haddad", "contact_email": "omar.haddad@example.org", "employees": 4, "stage": "Idea", "city": "Dartmouth", "province": "NS"},
]

PERIOD1_DATE = "2026-03-31"
PERIOD2_DATE = "2026-06-30"

PERIOD1_COLUMNS = ["record_id", "company_name", "contact_first_name", "contact_last_name", "contact_email", "employees", "stage", "city", "province"]
PERIOD2_COLUMNS = PERIOD1_COLUMNS + DEMOGRAPHIC_COLUMNS


def _write_csv_with_bom(path: Path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        filled = {col: row.get(col, "") for col in columns}
        writer.writerow(filled)
    # UTF-8 BOM prefix, as CRM exports commonly emit.
    path.write_bytes(b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8"))


# ----- minimal, deterministic xlsx writer (inline strings) -----

def _col_letter(idx: int) -> str:
    letters = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _sheet_xml(rows) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>',
    ]
    for r_idx, row in enumerate(rows, start=1):
        parts.append(f'<row r="{r_idx}">')
        for c_idx, value in enumerate(row):
            ref = f"{_col_letter(c_idx)}{r_idx}"
            if value is None or value == "":
                parts.append(f'<c r="{ref}"/>')
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                parts.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                parts.append(
                    f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{_xml_escape(str(value))}</t></is></c>'
                )
        parts.append("</row>")
    parts.append("</sheetData></worksheet>")
    return "".join(parts)


def _write_xlsx(path: Path, sheets):
    path.parent.mkdir(parents=True, exist_ok=True)
    n = len(sheets)
    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
    ]
    for i in range(1, n + 1):
        content_types.append(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
    content_types.append("</Types>")

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    sheet_tags = "".join(
        f'<sheet name="{_xml_escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, (name, _) in enumerate(sheets, start=1)
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheet_tags}</sheets></workbook>"
    )

    rel_tags = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, n + 1)
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{rel_tags}</Relationships>"
    )

    files = {
        "[Content_Types].xml": "".join(content_types),
        "_rels/.rels": root_rels,
        "xl/workbook.xml": workbook_xml,
        "xl/_rels/workbook.xml.rels": workbook_rels,
    }
    for i, (_, rows) in enumerate(sheets, start=1):
        files[f"xl/worksheets/sheet{i}.xml"] = _sheet_xml(rows)

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, files[name])


# ----- transcripts -----

def _write_transcripts():
    tdir = FIX / "transcripts"
    tdir.mkdir(parents=True, exist_ok=True)

    fireflies = {
        "meeting_id": "ff-2026-0418-001",
        "title": "Harbourline coaching — Tidewater Robotics",
        "date": "2026-04-18",
        "duration_minutes": 45,
        "participants": [
            {"name": "Ava Nguyen", "email": "ava.nguyen@example.org"},
            {"name": "Jordan Lee", "email": "jordan.lee@example.org"},
        ],
        "transcript": [
            {"speaker": "Jordan Lee", "text": "How did the pilot with the port authority go this month?"},
            {"speaker": "Ava Nguyen", "text": "We closed the second paying customer and grew the team to fourteen."},
            {"speaker": "Jordan Lee", "text": "Great. Let's set the next milestone around repeatable sales."},
        ],
    }
    (tdir / "fireflies-tidewater-2026-04-18.json").write_text(
        json.dumps(fireflies, indent=2) + "\n", encoding="utf-8"
    )

    granola = """# Granola notes — Saltmarsh Analytics coaching

Date: 2026-05-06
Attendees: Priya Sharma (priya.sharma@example.org), Jordan Lee (jordan.lee@example.org)

## Summary
- Headcount grew from five to nine over the quarter.
- Moved from MVP to early adopters after two signed pilots.

## Action items
- Draft an ideal-customer-profile one-pager.
- Prepare the next funding conversation (angel round).
"""
    (tdir / "granola-saltmarsh-2026-05-06.md").write_text(granola, encoding="utf-8")

    fathom = """Fathom Transcript
Meeting: Nectar Foodworks check-in
Date: 2026-05-20
Participants: Diego Alvarez (diego.alvarez@example.org), Jordan Lee (jordan.lee@example.org)

00:00:04 Jordan Lee: Revenue held steady but you trimmed to eighteen staff, right?
00:00:11 Diego Alvarez: Yes, we restructured operations after the winter season.
00:00:19 Jordan Lee: Understood. We'll note the headcount change for the update.
"""
    (tdir / "fathom-nectar-2026-05-20.txt").write_text(fathom, encoding="utf-8")


# ----- programs + BAI workbook -----

def _write_programs():
    programs_rows = [
        ["Program ID", "Program Name", "Program Type", "Start Date", "End Date", "Status"],
        ["PRG-01", "Harbourline Accelerator 2026", "Accelerator", "2026-01-15", "2026-06-30", "Active"],
        ["PRG-02", "Coastal Founders Workshop", "Workshop", "2026-02-10", "2026-02-11", "Completed"],
    ]
    cohorts_rows = [
        ["Cohort ID", "Program ID", "Company ID", "Cohort Name", "Start Date", "End Date", "Company Status"],
        ["COH-01", "PRG-01", "HL-001", "Spring 2026", "2026-01-15", "2026-06-30", "Active"],
        ["COH-02", "PRG-01", "HL-003", "Spring 2026", "2026-01-15", "2026-06-30", "Active"],
        ["COH-03", "PRG-01", "HL-007", "Spring 2026", "2026-04-01", "2026-06-30", "Active"],
    ]
    _write_xlsx(
        FIX / "programs" / "harbourline-programs.xlsx",
        [("Programs", programs_rows), ("Cohorts", cohorts_rows)],
    )


def _write_bai_workbook():
    companies_header = [
        "Company ID", "Business Name", "Former Name", "Business Number",
        "Name of Ultimate Founder", "Address", "City", "Province/Territory",
        "Phone Number", "Email", "Website URL", "Industry Sector",
        "Underrepresented Group", "Indigenous Peoples", "Black Communities",
        "Racialized Communities", "Persons with a Disability",
        "Official Language Minority Communities", "Youth",
        "Newcomers to Canada/Immigrants", "2SLGBTQI+", "Women",
        "Prefer Not to Disclose", "Company Type",
    ]
    companies_rows = [companies_header]
    companies_rows.append([
        "HL-001", "Tidewater Robotics", "", "", "Ava Nguyen", "", "Halifax", "NS",
        "", "info@example.org", "https://tidewater.example.org",
        "Robotics and drones", "Yes", "No", "No", "No", "No", "No", "No", "No",
        "No", "Yes", "No", "Startup",
    ])
    companies_rows.append([
        "HL-002", "Beacon Health Systems", "", "", "Liam Okafor", "", "Moncton", "NB",
        "", "hello@example.org", "https://beacon.example.org",
        "Digital health", "Yes", "No", "No", "No", "No", "No", "No", "Yes",
        "No", "No", "No", "Startup",
    ])

    updates_header = [
        "Update ID", "Company ID", "Company Name", "Update Date",
        "Support Programs Attended", "Total Venture Capital", "Total Angel",
        "Total Debt", "Total Grants", "Lifetime Revenue", "Revenue Disclosure",
        "Program", "Stage of Growth", "Current FTEs", "Cost of Support (CAD)",
        "Notes",
    ]
    updates_rows = [updates_header]
    # Cost of Support (CAD) column (index 14) is intentionally left blank.
    updates_rows.append([
        "UPD-001", "HL-001", "Tidewater Robotics", "2026-06-30",
        "Harbourline Accelerator 2026", 0, 250000, 0, 50000, 400000, "Disclosed",
        "Harbourline Accelerator 2026", "Growth", 14, "", "Grew to 14 staff.",
    ])
    updates_rows.append([
        "UPD-002", "HL-003", "Saltmarsh Analytics", "2026-06-30",
        "Harbourline Accelerator 2026", 0, 100000, 0, 0, 90000, "Disclosed",
        "Harbourline Accelerator 2026", "Early Adopters", 9, "", "Two pilots signed.",
    ])
    _write_xlsx(
        FIX / "bai-workbook" / "harbourline-bai-v5.xlsx",
        [("Companies", companies_rows), ("Company Updates", updates_rows)],
    )


# ----- compare.json (computed from the two periods) -----

def _compute_compare():
    p1 = {r["record_id"]: r for r in PERIOD1}
    p2 = {r["record_id"]: r for r in PERIOD2}
    p1_names = {r["company_name"] for r in PERIOD1}
    name_to_p1_id = {r["company_name"]: r["record_id"] for r in PERIOD1}

    changed = []
    for rid in p1:
        if rid in p2 and int(p1[rid]["employees"]) != int(p2[rid]["employees"]):
            changed.append({
                "record_id": rid,
                "from_employees": int(p1[rid]["employees"]),
                "to_employees": int(p2[rid]["employees"]),
            })

    new_companies = [
        {"record_id": rid, "company_name": p2[rid]["company_name"]}
        for rid in p2
        if rid not in p1 and p2[rid]["company_name"] not in p1_names
    ]
    absent = [
        {"record_id": rid, "company_name": p1[rid]["company_name"]}
        for rid in p1
        if rid not in p2
    ]
    unmatched = [
        {
            "record_id": rid,
            "company_name": p2[rid]["company_name"],
            "matches_existing_record_id": name_to_p1_id[p2[rid]["company_name"]],
            "resolution": "unmatched",
            "reason": "New identifier whose name matches an existing company; a name match never authorises a merge.",
        }
        for rid in p2
        if rid not in p1 and p2[rid]["company_name"] in p1_names
    ]

    return {
        "fixture": "harbourline",
        "period_1": {"label": PERIOD1_DATE, "file": "crm/period-2026-03-31/companies.csv", "company_count": len(PERIOD1)},
        "period_2": {"label": PERIOD2_DATE, "file": "crm/period-2026-06-30/companies.csv", "company_count": len(PERIOD2)},
        "changed_employee_counts": sorted(changed, key=lambda x: x["record_id"]),
        "new_companies": sorted(new_companies, key=lambda x: x["record_id"]),
        "absent_companies": sorted(absent, key=lambda x: x["record_id"]),
        "unmatched_name_collisions": sorted(unmatched, key=lambda x: x["record_id"]),
        "demographic_columns_added": DEMOGRAPHIC_COLUMNS,
        "cost_of_support_present": False,
        "notes": "Deltas are computed by tools/build_fixtures.py from the two CRM CSVs; tests re-derive them independently.",
    }


def main() -> int:
    _write_csv_with_bom(FIX / "crm" / "period-2026-03-31" / "companies.csv", PERIOD1_COLUMNS, PERIOD1)
    _write_csv_with_bom(FIX / "crm" / "period-2026-06-30" / "companies.csv", PERIOD2_COLUMNS, PERIOD2)
    _write_programs()
    _write_bai_workbook()
    _write_transcripts()

    compare = _compute_compare()
    expected_dir = FIX / "expected"
    expected_dir.mkdir(parents=True, exist_ok=True)
    (expected_dir / "compare.json").write_text(json.dumps(compare, indent=2) + "\n", encoding="utf-8")

    summary = {
        "fixture": "harbourline",
        "period_1_companies": len(PERIOD1),
        "period_2_companies": len(PERIOD2),
        "changed_employee_counts": len(compare["changed_employee_counts"]),
        "new_companies": len(compare["new_companies"]),
        "absent_companies": len(compare["absent_companies"]),
        "unmatched_name_collisions": len(compare["unmatched_name_collisions"]),
    }
    (expected_dir / "period-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("Fixture built:")
    for line in json.dumps(summary, indent=2).splitlines():
        print("  " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
