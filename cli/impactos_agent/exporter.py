"""Build the deterministic export set from contract records for one period.

Writes ``profile.json``, ``bai-v5.xlsx``, ``gaps.md`` and ``provenance.json`` (the
hashed set) plus ``run.json`` (excluded from the hash set — it may carry a wall
clock timestamp). Every populated workbook cell has a provenance entry tracing it
to a source file, sheet/column, row identity and the period's exported-at.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import contract, xlsx

# PacifiCan diverse group -> BAI Companies column.
GROUP_TO_BAI_COLUMN = {
    "Women": "Women",
    "Indigenous": "Indigenous Peoples",
    "Racialized": "Racialized Communities",
    "Persons with disabilities": "Persons with a Disability",
    "2SLGBTQ+": "2SLGBTQI+",
    "Youth": "Youth",
    "Immigrants": "Newcomers to Canada/Immigrants",
    "Official Language Minority Communities": "Official Language Minority Communities",
}

Cell = Tuple[Any, Optional[Dict[str, Any]]]


class ExportError(Exception):
    pass


def _index(records: Dict[str, List[Dict[str, Any]]], data_type: str) -> Dict[str, Dict[str, Any]]:
    return {r["identity"]: r for r in records.get(data_type, [])}


def _list(records: Dict[str, List[Dict[str, Any]]], data_type: str) -> List[Dict[str, Any]]:
    return records.get(data_type, [])


def _prov(record: Dict[str, Any], field: str, exported_at: str, data_type: str) -> Optional[Dict[str, Any]]:
    base = record.get("provenance", {}).get(field)
    if base is None:
        return None
    entry = dict(base)
    entry.update({"data_type": data_type, "field": field, "exported_at": exported_at})
    return entry


def _derived_prov(
    contributors: List[Tuple[str, Dict[str, Any], str]],
    exported_at: str,
    note: str,
) -> Dict[str, Any]:
    """Provenance for a value derived from one or more records."""
    sources = []
    for data_type, record, field in contributors:
        base = record.get("provenance", {}).get(field, {})
        sources.append({
            "data_type": data_type,
            "field": field,
            "row_identity": record.get("identity"),
            "source_file": base.get("source_file"),
            "sha256": base.get("sha256"),
            "sheet": base.get("sheet"),
            "column": base.get("column"),
        })
    return {"derivation": note, "exported_at": exported_at, "contributors": sources}


def _money_amount(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("amount")
    return value


class Exporter:
    def __init__(self, records_doc: Dict[str, Any]):
        self.doc = records_doc
        self.period = records_doc["period"]
        self.exported_at = self.period
        self.records = records_doc.get("records", {})
        self.company = _index(self.records, "company")
        self.person = _index(self.records, "person")
        self.program = _index(self.records, "program")
        self.cohort = _index(self.records, "cohort")
        self.company_person = _list(self.records, "company_person")
        self.company_update = _list(self.records, "company_update")
        self.membership = _list(self.records, "membership")
        self.milestone = _list(self.records, "milestone_position")
        self.funding = _list(self.records, "funding_event")
        self.export_contract = contract.bai_export_contract()

    # -- relationship helpers ------------------------------------------------ #
    def _company_persons(self, company_id: str) -> List[Dict[str, Any]]:
        return [cp for cp in self.company_person if cp["fields"].get("company_ref") == company_id]

    def _primary_person(self, company_id: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        links = self._company_persons(company_id)
        for cp in links:
            if cp["fields"].get("is_primary") in (True, "Yes", "yes"):
                person = self.person.get(cp["fields"].get("person_ref"))
                if person:
                    return person, cp
        for cp in links:
            person = self.person.get(cp["fields"].get("person_ref"))
            if person:
                return person, cp
        return None

    def _company_link_for_person(self, person_id: str) -> Optional[Dict[str, Any]]:
        for cp in self.company_person:
            if cp["fields"].get("person_ref") == person_id:
                return cp
        return None

    def _latest_milestone(self, company_id: str) -> Optional[Dict[str, Any]]:
        positions = [m for m in self.milestone if m["fields"].get("company_ref") == company_id]
        if not positions:
            return None
        return max(positions, key=lambda m: (m["fields"].get("as_of_date") or "", m["identity"]))

    def _memberships_for_company(self, company_id: str) -> List[Dict[str, Any]]:
        return [m for m in self.membership if m["fields"].get("company_ref") == company_id]

    def _programs_for_company(self, company_id: str) -> List[str]:
        names = []
        for membership in self._memberships_for_company(company_id):
            cohort = self.cohort.get(membership["fields"].get("cohort_ref"))
            if not cohort:
                continue
            program = self.program.get(cohort["fields"].get("program_ref"))
            if program and program["fields"].get("name"):
                names.append(program["fields"]["name"])
        return sorted(set(names))

    def _demographic_groups(self, company_id: str) -> Dict[str, Dict[str, Any]]:
        """group -> the person record that contributes it (first, deterministic)."""
        found: Dict[str, Dict[str, Any]] = {}
        for cp in sorted(self._company_persons(company_id), key=lambda c: c["identity"]):
            person = self.person.get(cp["fields"].get("person_ref"))
            if not person:
                continue
            for group in person["fields"].get("demographics", []) or []:
                found.setdefault(group, person)
        return found

    # -- sheet builders ------------------------------------------------------ #
    def build_companies(self) -> List[Dict[str, Cell]]:
        rows = []
        for company_id in sorted(self.company):
            company = self.company[company_id]
            f = company["fields"]
            primary = self._primary_person(company_id)
            person, link = primary if primary else (None, None)
            groups = self._demographic_groups(company_id)

            def demo_cell(group_key: str) -> Cell:
                if group_key in groups:
                    return "Yes", _derived_prov(
                        [("person", groups[group_key], "demographics")],
                        self.exported_at,
                        f"{group_key} reported by a person at the company",
                    )
                return "", None

            row: Dict[str, Cell] = {
                "Company ID": (f.get("source_id"), _prov(company, "source_id", self.exported_at, "company")),
                "Business Name": (f.get("legal_name"), _prov(company, "legal_name", self.exported_at, "company")),
                "Former Name": (f.get("former_name"), _prov(company, "former_name", self.exported_at, "company")),
                "Business Number": (f.get("business_number"), _prov(company, "business_number", self.exported_at, "company")),
                "Name of Ultimate Founder": self._founder_cell(person),
                "Address": ("", None),
                "City": (f.get("city"), _prov(company, "city", self.exported_at, "company")),
                "Province/Territory": (f.get("province"), _prov(company, "province", self.exported_at, "company")),
                "Phone Number": self._person_field_cell(person, "phone"),
                "Email": self._person_field_cell(person, "email"),
                "Website URL": (f.get("website"), _prov(company, "website", self.exported_at, "company")),
                "Industry Sector": (f.get("industry"), _prov(company, "industry", self.exported_at, "company")),
                "Underrepresented Group": self._underrepresented_cell(groups),
                "Indigenous Peoples": demo_cell("Indigenous"),
                "Black Communities": ("", None),
                "Racialized Communities": demo_cell("Racialized"),
                "Persons with a Disability": demo_cell("Persons with disabilities"),
                "Official Language Minority Communities": demo_cell("Official Language Minority Communities"),
                "Youth": demo_cell("Youth"),
                "Newcomers to Canada/Immigrants": demo_cell("Immigrants"),
                "2SLGBTQI+": demo_cell("2SLGBTQ+"),
                "Women": demo_cell("Women"),
                "Prefer Not to Disclose": ("", None),
                "Company Type": (f.get("company_type"), _prov(company, "company_type", self.exported_at, "company")),
            }
            rows.append(row)
        return rows

    def _founder_cell(self, person: Optional[Dict[str, Any]]) -> Cell:
        if not person:
            return "", None
        first = person["fields"].get("first_name")
        last = person["fields"].get("last_name")
        name = " ".join(p for p in (first, last) if p)
        if not name:
            return "", None
        return name, _derived_prov(
            [("person", person, "first_name"), ("person", person, "last_name")],
            self.exported_at,
            "primary contact name joined from first and last name",
        )

    def _person_field_cell(self, person: Optional[Dict[str, Any]], field: str) -> Cell:
        if not person or person["fields"].get(field) is None:
            return "", None
        return person["fields"][field], _prov(person, field, self.exported_at, "person")

    def _underrepresented_cell(self, groups: Dict[str, Dict[str, Any]]) -> Cell:
        if not groups:
            return "", None
        contributor = sorted(groups.items())[0]
        return "Yes", _derived_prov(
            [("person", contributor[1], "demographics")],
            self.exported_at,
            "at least one person reports a diverse-group membership",
        )

    def build_company_updates(self) -> List[Dict[str, Cell]]:
        rows = []
        for update in sorted(self.company_update, key=lambda u: u["identity"]):
            f = update["fields"]
            company_id = f.get("company_ref")
            company = self.company.get(company_id)
            programs = self._programs_for_company(company_id)
            milestone = self._latest_milestone(company_id)
            row: Dict[str, Cell] = {
                "Update ID": (f.get("source_id"), _prov(update, "source_id", self.exported_at, "company_update")),
                "Company ID": (f.get("company_ref"), _prov(update, "company_ref", self.exported_at, "company_update")),
                "Company Name": self._company_name_cell(company),
                "Update Date": (f.get("update_date"), _prov(update, "update_date", self.exported_at, "company_update")),
                "Support Programs Attended": self._programs_cell(company_id, programs),
                "Total Venture Capital": self._funding_cell(company_id, ("venture_capital",)),
                "Total Angel": self._funding_cell(company_id, ("angel",)),
                "Total Debt": self._funding_cell(company_id, ("debt", "bank_credit")),
                "Total Grants": self._funding_cell(company_id, ("government_grant",)),
                "Lifetime Revenue": (_money_amount(f.get("lifetime_revenue")),
                                     _prov(update, "lifetime_revenue", self.exported_at, "company_update")),
                "Revenue Disclosure": (f.get("revenue_disclosure"), _prov(update, "revenue_disclosure", self.exported_at, "company_update")),
                "Program": self._primary_program_cell(company_id, programs),
                "Stage of Growth": self._stage_cell(milestone),
                "Current FTEs": (f.get("current_ftes"), _prov(update, "current_ftes", self.exported_at, "company_update")),
                "Cost of Support (CAD)": ("", None),
                "Notes": (f.get("notes"), _prov(update, "notes", self.exported_at, "company_update")),
            }
            rows.append(row)
        return rows

    def _company_name_cell(self, company: Optional[Dict[str, Any]]) -> Cell:
        if not company:
            return "", None
        return company["fields"].get("legal_name"), _prov(company, "legal_name", self.exported_at, "company")

    def _programs_cell(self, company_id: str, programs: List[str]) -> Cell:
        if not programs:
            return "", None
        contributors = []
        for membership in self._memberships_for_company(company_id):
            contributors.append(("membership", membership, "cohort_ref"))
        return "; ".join(programs), _derived_prov(contributors, self.exported_at, "programs via cohort memberships")

    def _primary_program_cell(self, company_id: str, programs: List[str]) -> Cell:
        if not programs:
            return "", None
        memberships = self._memberships_for_company(company_id)
        contributors = [("membership", memberships[0], "cohort_ref")] if memberships else []
        return programs[0], _derived_prov(contributors, self.exported_at, "primary program via cohort membership")

    def _funding_cell(self, company_id: str, funding_types: Tuple[str, ...]) -> Cell:
        matches = [
            fe for fe in self.funding
            if fe["fields"].get("company_ref") == company_id
            and fe["fields"].get("funding_type") in funding_types
        ]
        if not matches:
            return "", None
        total = 0.0
        contributors = []
        for fe in matches:
            total += _money_amount(fe["fields"].get("amount")) or 0
            contributors.append(("funding_event", fe, "amount"))
        return total, _derived_prov(contributors, self.exported_at, f"sum of {'/'.join(funding_types)} funding")

    def _stage_cell(self, milestone: Optional[Dict[str, Any]]) -> Cell:
        if not milestone:
            return "", None
        track = milestone["fields"].get("track")
        rung = milestone["fields"].get("rung_order")
        stage = contract.funder_stage_for(track, rung) if track and rung is not None else None
        if stage is None:
            return "", None
        return stage, _derived_prov(
            [("milestone_position", milestone, "rung_order")],
            self.exported_at,
            f"funder stage from track {track!r} rung {rung}",
        )

    def build_contacts(self) -> List[Dict[str, Cell]]:
        rows = []
        for person_id in sorted(self.person):
            person = self.person[person_id]
            f = person["fields"]
            link = self._company_link_for_person(person_id)
            row: Dict[str, Cell] = {
                "Contact ID": (f.get("source_id"), _prov(person, "source_id", self.exported_at, "person")),
                "Company ID": self._link_cell(link, "company_ref", "company_person"),
                "First Name": (f.get("first_name"), _prov(person, "first_name", self.exported_at, "person")),
                "Last Name": (f.get("last_name"), _prov(person, "last_name", self.exported_at, "person")),
                "Title/Role": self._link_cell(link, "role", "company_person"),
                "Email": (f.get("email"), _prov(person, "email", self.exported_at, "person")),
                "Phone Number": (f.get("phone"), _prov(person, "phone", self.exported_at, "person")),
                "Primary Contact": self._primary_flag_cell(link),
                "Notes": ("", None),
            }
            rows.append(row)
        return rows

    def _link_cell(self, link: Optional[Dict[str, Any]], field: str, data_type: str) -> Cell:
        if not link or link["fields"].get(field) is None:
            return "", None
        return link["fields"][field], _prov(link, field, self.exported_at, data_type)

    def _primary_flag_cell(self, link: Optional[Dict[str, Any]]) -> Cell:
        if not link or "is_primary" not in link["fields"]:
            return "", None
        value = link["fields"]["is_primary"]
        text = "Yes" if value in (True, "Yes", "yes") else "No"
        return text, _prov(link, "is_primary", self.exported_at, "company_person")

    def build_programs(self) -> List[Dict[str, Cell]]:
        rows = []
        for program_id in sorted(self.program):
            program = self.program[program_id]
            f = program["fields"]
            rows.append({
                "Program ID": (f.get("source_id"), _prov(program, "source_id", self.exported_at, "program")),
                "Program Name": (f.get("name"), _prov(program, "name", self.exported_at, "program")),
                "Program Description": (f.get("description"), _prov(program, "description", self.exported_at, "program")),
                "Program Type": (f.get("program_type"), _prov(program, "program_type", self.exported_at, "program")),
                "Start Date": (f.get("start_date"), _prov(program, "start_date", self.exported_at, "program")),
                "End Date": (f.get("end_date"), _prov(program, "end_date", self.exported_at, "program")),
                "Status": (f.get("status"), _prov(program, "status", self.exported_at, "program")),
                "Notes": ("", None),
            })
        return rows

    def build_program_cohorts(self) -> List[Dict[str, Cell]]:
        rows = []
        for membership in sorted(self.membership, key=lambda m: m["identity"]):
            f = membership["fields"]
            cohort = self.cohort.get(f.get("cohort_ref"))
            cf = cohort["fields"] if cohort else {}
            rows.append({
                "Cohort ID": (f.get("source_id"), _prov(membership, "source_id", self.exported_at, "membership")),
                "Program ID": self._cohort_field_cell(cohort, "program_ref"),
                "Company ID": (f.get("company_ref"), _prov(membership, "company_ref", self.exported_at, "membership")),
                "Cohort Name": self._cohort_field_cell(cohort, "cohort_name"),
                "Start Date": self._cohort_field_cell(cohort, "start_date"),
                "End Date": self._cohort_field_cell(cohort, "end_date"),
                "Company Status": (f.get("status"), _prov(membership, "status", self.exported_at, "membership")),
                "Notes": ("", None),
            })
        return rows

    def _cohort_field_cell(self, cohort: Optional[Dict[str, Any]], field: str) -> Cell:
        if not cohort or cohort["fields"].get(field) is None:
            return "", None
        return cohort["fields"][field], _prov(cohort, field, self.exported_at, "cohort")

    # -- orchestration ------------------------------------------------------- #
    def _sheet_builders(self) -> Dict[str, Callable[[], List[Dict[str, Cell]]]]:
        return {
            "Companies": self.build_companies,
            "Company Updates": self.build_company_updates,
            "Contacts": self.build_contacts,
            "Programs": self.build_programs,
            "Program Cohorts": self.build_program_cohorts,
        }

    def build(self, out_dir: Path) -> Dict[str, Any]:
        from openpyxl.utils import get_column_letter

        out_dir.mkdir(parents=True, exist_ok=True)
        sheet_specs = self.export_contract["sheets"]
        sheet_rows_for_xlsx: Dict[str, List[List[Any]]] = {}
        provenance_cells: Dict[str, Any] = {}
        duplicate_errors: List[str] = []

        for sheet_name, builder in self._sheet_builders().items():
            columns = [c["column"] for c in sheet_specs[sheet_name]["columns"]]
            built_rows = builder()
            # Duplicate primary-key guard (first column is the sheet's id).
            key_col = columns[0]
            seen = {}
            for row in built_rows:
                key = row.get(key_col, ("", None))[0]
                if key in seen:
                    duplicate_errors.append(f"{sheet_name}: duplicate {key_col} {key!r}")
                seen[key] = True

            xlsx_rows: List[List[Any]] = []
            for row_offset, row in enumerate(built_rows, start=2):
                values = []
                for col_offset, column in enumerate(columns, start=1):
                    value, prov = row.get(column, ("", None))
                    value = "" if value is None else value
                    values.append(value)
                    if value != "" and prov is not None:
                        ref = f"{sheet_name}!{get_column_letter(col_offset)}{row_offset}"
                        provenance_cells[ref] = {"value": value, **prov}
                xlsx_rows.append(values)
            sheet_rows_for_xlsx[sheet_name] = xlsx_rows

        if duplicate_errors:
            raise ExportError("; ".join(duplicate_errors))

        workbook_path = out_dir / "bai-v5.xlsx"
        xlsx.build_workbook(sheet_rows_for_xlsx, workbook_path)

        profile = self._build_profile()
        provenance = {
            "period": self.period,
            "exported_at": self.exported_at,
            "workbook": "bai-v5.xlsx",
            "cell_count": len(provenance_cells),
            "cells": provenance_cells,
        }
        gaps_md = self._build_gaps_md(profile)

        _write_json(out_dir / "profile.json", profile)
        _write_json(out_dir / "provenance.json", provenance)
        (out_dir / "gaps.md").write_text(gaps_md, encoding="utf-8")

        template_problems = xlsx.validate_bai_template(workbook_path, self.export_contract)
        return {
            "period": self.period,
            "workbook": str(workbook_path),
            "hash_set": ["profile.json", "bai-v5.xlsx", "gaps.md", "provenance.json"],
            "template_problems": template_problems,
            "gap_count": len(profile["gaps"]),
            "populated_count": len(profile["populated"]),
            "provenance_cell_count": len(provenance_cells),
        }

    # -- profile / gaps ------------------------------------------------------ #
    def _build_profile(self) -> Dict[str, Any]:
        profile_spec = contract.reporting_profile()
        evaluated = []
        populated_keys = []
        gap_keys = []
        for field in profile_spec["fields"]:
            key = field["key"]
            count, reason = self._evaluate_profile_field(key)
            status = "populated" if count > 0 else "gap"
            entry = {
                "key": key,
                "label": field["label"],
                "anchor": field.get("anchor"),
                "contract_path": field.get("contract_path"),
                "status": status,
                "count": count,
            }
            if status == "gap":
                entry["reason"] = reason
                gap_keys.append(key)
            else:
                populated_keys.append(key)
            evaluated.append(entry)
        return {
            "period": self.period,
            "profile_name": profile_spec["profile_name"],
            "fields": evaluated,
            "populated": populated_keys,
            "gaps": gap_keys,
        }

    def _evaluate_profile_field(self, key: str) -> Tuple[int, str]:
        """Return ``(count, gap_reason)`` for a reporting-profile field."""
        updates = self.company_update
        companies = list(self.company.values())

        def count_update(field: str) -> int:
            return sum(1 for u in updates if _money_amount(u["fields"].get(field)) not in (None, ""))

        def count_company(field: str) -> int:
            return sum(1 for c in companies if c["fields"].get(field) not in (None, ""))

        if key == "legal_name":
            return count_company("legal_name"), "no company legal names"
        if key == "business_number":
            return count_company("business_number"), "no source column maps a CRA business number"
        if key == "year_incorporated":
            return count_company("year_incorporated"), "no source column maps year incorporated"
        if key == "year_of_first_sale":
            return count_company("year_of_first_sale"), "no source column maps year of first sale"
        if key == "industry":
            return count_company("industry"), "no source column maps industry"
        if key == "company_type":
            return count_company("company_type"), "company type is never inferred and no source column declares it"
        if key == "company_stage":
            n = sum(1 for c in self.company if self._latest_milestone(c))
            return n, "no milestone position maps to a funder stage"
        if key in ("founder_demographics", "diverse_groups"):
            n = sum(1 for p in self.person.values() if p["fields"].get("demographics"))
            return n, "demographics are never inferred and no source column declares them"
        if key == "employees_ft_canada":
            return count_update("ft_employees_canada"), "no source column maps full-time Canadian employees"
        if key == "employees_pt_canada":
            return count_update("pt_employees_canada"), "no source column maps part-time Canadian employees"
        if key == "employees_outside_canada":
            return count_update("employees_outside_canada"), "no source column maps employees outside Canada"
        if key == "annual_revenue":
            return count_update("annual_revenue"), "no source column maps annual revenue"
        if key == "export_revenue":
            return count_update("export_revenue"), "no source column maps export revenue"
        if key == "revenue_disclosure":
            return count_update("revenue_disclosure"), "no source column maps a revenue disclosure flag"
        if key in ("financing_by_source", "total_funding_received", "avg_funding_received"):
            n = len(self.funding)
            return n, "no funding events mapped (funding is reviewed, never inferred)"
        if key == "patents_applied":
            return count_update("patents_applied"), "no source column maps patents applied"
        if key == "patents_granted":
            return count_update("patents_granted"), "no source column maps patents granted"
        if key == "nps":
            return count_update("nps"), "no source column maps NPS"
        if key == "impact_rating":
            return count_update("impact_rating"), "no source column maps an impact rating"
        if key in ("support_programs_attended", "businesses_assisted"):
            n = len({m["fields"].get("company_ref") for m in self.membership if m["fields"].get("company_ref")})
            return n, "no cohort memberships mapped"
        if key == "coaching_hours_per_business":
            n = sum(1 for i in _list(self.records, "interaction") if i["fields"].get("duration_hours") is not None)
            return n, "no coaching interactions with duration mapped"
        if key == "jobs_created":
            return count_update("current_ftes"), "no source column maps current FTEs"
        if key == "jobs_maintained":
            n = sum(1 for t in _list(self.records, "team_member_period") if t["fields"].get("is_active"))
            return n, "no team-member-period roster mapped"
        if key == "total_sales":
            return count_update("lifetime_revenue"), "no source column maps lifetime revenue"
        if key == "survival_rate":
            return 0, "requires multi-period comparison (out of scope for a single export)"
        return 0, "no source mapping for this profile field"

    def _build_gaps_md(self, profile: Dict[str, Any]) -> str:
        lines = [
            f"# Reporting profile gaps — {self.period}",
            "",
            f"Profile: {profile['profile_name']}",
            f"Populated fields: {len(profile['populated'])} of {len(profile['fields'])}",
            "",
            "The fields below could not be filled from the mapped sources. Each is left "
            "blank in the workbook rather than inferred.",
            "",
            "| Field | Anchor | Reason |",
            "| --- | --- | --- |",
        ]
        for entry in profile["fields"]:
            if entry["status"] != "gap":
                continue
            reason = entry.get("reason", "").replace("|", "\\|")
            lines.append(f"| {entry['label']} | {entry.get('anchor', '')} | {reason} |")
        lines.append("")
        return "\n".join(lines)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
