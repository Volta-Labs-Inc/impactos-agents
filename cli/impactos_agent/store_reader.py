"""Read the store as the signed-in user and rebuild the file-route record shape.

The exporter (child 2) and the brief builder (child 5) both consume one
``records`` document: each data type is a list of ``{"identity", "fields"}``
records, and every cross-reference uses the *source id* of the parent (a
``company_ref``, ``cohort_ref`` …), not a database key. This module fetches the
store's fact tables over the per-user REST session, translates the database keys
back into source ids, and drops any fact a retraction row names, so exports and
briefs built from the store exclude retracted facts exactly as the file route
never contained them.

The REST layer is injectable so the reshaping can be proven without a live
cluster: pass ``get_rows(table, select)`` returning the parsed rows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import store as store_mod

GetRows = Callable[[str, str], List[Dict[str, Any]]]

# Columns fetched per table (explicit — never select *). Keys become record
# fields after database ids are translated to source-id references.
_SELECT: Dict[str, str] = {
    "company": ("id,source_system,source_id,legal_name,operating_name,former_name,"
                "business_number,industry,company_type,city,province,country,website,"
                "year_incorporated,year_of_first_sale"),
    "person": "id,source_system,source_id,first_name,last_name,email,phone,title",
    "person_demographics": "person_id,demographics",
    "program": "id,source_system,source_id,name,description,program_type,start_date,end_date,status",
    "cohort": "id,source_system,source_id,program_id,cohort_name,start_date,end_date",
    "company_person": "id,source_system,source_id,company_id,person_id,role,is_primary",
    "membership": "id,source_system,source_id,cohort_id,company_id,status",
    "company_update": ("id,source_system,source_id,company_id,update_date,current_ftes,"
                       "ft_employees_canada,pt_employees_canada,employees_outside_canada,"
                       "annual_revenue,export_revenue,lifetime_revenue,revenue_disclosure,"
                       "patents_applied,patents_granted,nps,impact_rating,notes"),
    "funding_event": ("id,source_system,source_id,company_id,funding_type,amount,close_date,"
                      "round_name,grant_program_name"),
    "team_member_period": ("id,source_system,source_id,company_id,person_id,period_month,"
                           "hours_per_week,is_founder,is_active"),
    "milestone_position": ("id,source_system,source_id,company_id,track,rung_order,status,"
                           "as_of_date,is_verified,notes"),
    "milestone_target": ("id,source_system,source_id,company_id,track,target_rung_order,"
                         "objective_signal,set_by,set_at"),
    "interaction": ("id,source_system,source_id,company_id,interaction_type,occurred_at,"
                    "subject,duration_hours,notes"),
    "retraction": "fact_table,fact_id",
}


class StoreReadError(Exception):
    pass


def _rest_get_rows(project_root: Path) -> GetRows:
    import json

    def get_rows(table: str, select: str) -> List[Dict[str, Any]]:
        status, body = store_mod.authed_request(
            project_root, "GET", f"/rest/v1/{table}?select={select}")
        if status != 200:
            raise StoreReadError(f"could not read {table} from the store (status {status}); sign in first")
        return json.loads(body)

    return get_rows


def _clean(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Drop null-valued keys so a store record matches a file-route record, which
    only carries the fields a source actually provided."""
    return {k: v for k, v in fields.items() if v is not None}


def read_records(project_root: Path, period: str, get_rows: Optional[GetRows] = None) -> Dict[str, Any]:
    """Build the file-route ``records`` document from the store for ``period``."""
    get_rows = get_rows or _rest_get_rows(project_root)

    raw: Dict[str, List[Dict[str, Any]]] = {
        table: get_rows(table, select) for table, select in _SELECT.items()
    }

    # id -> source_id maps for every referenced parent.
    def id_map(table: str) -> Dict[str, str]:
        return {r["id"]: r["source_id"] for r in raw[table] if r.get("id") and r.get("source_id")}

    companies = id_map("company")
    people = id_map("person")
    programs = id_map("program")
    cohorts = id_map("cohort")

    # Retracted (fact_table, fact_id) pairs — only rows that name a specific fact.
    retracted: set[Tuple[str, str]] = {
        (r["fact_table"], r["fact_id"]) for r in raw["retraction"]
        if r.get("fact_table") and r.get("fact_id")
    }

    demographics_by_person: Dict[str, List[str]] = {
        r["person_id"]: r.get("demographics") or [] for r in raw["person_demographics"]
    }

    records: Dict[str, List[Dict[str, Any]]] = {}

    def emit(data_type: str, table: str, build: Callable[[Dict[str, Any]], Dict[str, Any]],
             identity: Callable[[Dict[str, Any]], str]) -> None:
        rows = []
        for row in raw[table]:
            if (table, row.get("id")) in retracted:
                continue
            rows.append({"identity": identity(row), "fields": _clean(build(row))})
        records[data_type] = rows

    emit("company", "company",
         lambda r: {
             "source_system": r.get("source_system"), "source_id": r.get("source_id"),
             "legal_name": r.get("legal_name"), "operating_name": r.get("operating_name"),
             "former_name": r.get("former_name"), "business_number": r.get("business_number"),
             "industry": r.get("industry"), "company_type": r.get("company_type"),
             "city": r.get("city"), "province": r.get("province"), "country": r.get("country"),
             "website": r.get("website"), "year_incorporated": r.get("year_incorporated"),
             "year_of_first_sale": r.get("year_of_first_sale"),
         },
         lambda r: r["source_id"])

    emit("person", "person",
         lambda r: {
             "source_system": r.get("source_system"), "source_id": r.get("source_id"),
             "first_name": r.get("first_name"), "last_name": r.get("last_name"),
             "email": r.get("email"), "phone": r.get("phone"), "title": r.get("title"),
             "demographics": demographics_by_person.get(r["id"]) or None,
         },
         lambda r: r["source_id"])

    emit("program", "program",
         lambda r: {
             "source_system": r.get("source_system"), "source_id": r.get("source_id"),
             "name": r.get("name"), "description": r.get("description"),
             "program_type": r.get("program_type"), "start_date": r.get("start_date"),
             "end_date": r.get("end_date"), "status": r.get("status"),
         },
         lambda r: r["source_id"])

    emit("cohort", "cohort",
         lambda r: {
             "source_system": r.get("source_system"), "source_id": r.get("source_id"),
             "program_ref": programs.get(r.get("program_id")),
             "cohort_name": r.get("cohort_name"), "start_date": r.get("start_date"),
             "end_date": r.get("end_date"),
         },
         lambda r: r["source_id"])

    emit("company_person", "company_person",
         lambda r: {
             "source_system": r.get("source_system"), "source_id": r.get("source_id"),
             "company_ref": companies.get(r.get("company_id")),
             "person_ref": people.get(r.get("person_id")),
             "role": r.get("role"), "is_primary": r.get("is_primary"),
         },
         lambda r: r["source_id"])

    emit("membership", "membership",
         lambda r: {
             "source_system": r.get("source_system"), "source_id": r.get("source_id"),
             "cohort_ref": cohorts.get(r.get("cohort_id")),
             "company_ref": companies.get(r.get("company_id")),
             "status": r.get("status"),
         },
         lambda r: r["source_id"])

    emit("company_update", "company_update",
         lambda r: {
             "source_system": r.get("source_system"), "source_id": r.get("source_id"),
             "company_ref": companies.get(r.get("company_id")),
             "update_date": r.get("update_date"), "current_ftes": r.get("current_ftes"),
             "ft_employees_canada": r.get("ft_employees_canada"),
             "pt_employees_canada": r.get("pt_employees_canada"),
             "employees_outside_canada": r.get("employees_outside_canada"),
             "annual_revenue": r.get("annual_revenue"), "export_revenue": r.get("export_revenue"),
             "lifetime_revenue": r.get("lifetime_revenue"),
             "revenue_disclosure": r.get("revenue_disclosure"),
             "patents_applied": r.get("patents_applied"), "patents_granted": r.get("patents_granted"),
             "nps": r.get("nps"), "impact_rating": r.get("impact_rating"), "notes": r.get("notes"),
         },
         lambda r: r["source_id"])

    emit("funding_event", "funding_event",
         lambda r: {
             "source_system": r.get("source_system"), "source_id": r.get("source_id"),
             "company_ref": companies.get(r.get("company_id")),
             "funding_type": r.get("funding_type"), "amount": r.get("amount"),
             "close_date": r.get("close_date"), "round_name": r.get("round_name"),
             "grant_program_name": r.get("grant_program_name"),
         },
         lambda r: r["source_id"])

    emit("team_member_period", "team_member_period",
         lambda r: {
             "source_system": r.get("source_system"), "source_id": r.get("source_id"),
             "company_ref": companies.get(r.get("company_id")),
             "person_ref": people.get(r.get("person_id")),
             "period_month": r.get("period_month"), "hours_per_week": r.get("hours_per_week"),
             "is_founder": r.get("is_founder"), "is_active": r.get("is_active"),
         },
         lambda r: r["source_id"])

    emit("milestone_position", "milestone_position",
         lambda r: {
             "source_system": r.get("source_system"), "source_id": r.get("source_id"),
             "company_ref": companies.get(r.get("company_id")),
             "track": r.get("track"), "rung_order": r.get("rung_order"),
             "status": r.get("status"), "as_of_date": r.get("as_of_date"),
             "is_verified": r.get("is_verified"), "notes": r.get("notes"),
         },
         lambda r: r["source_id"])

    emit("milestone_target", "milestone_target",
         lambda r: {
             "source_system": r.get("source_system"), "source_id": r.get("source_id"),
             "company_ref": companies.get(r.get("company_id")),
             "track": r.get("track"), "target_rung_order": r.get("target_rung_order"),
             "objective_signal": r.get("objective_signal"), "set_by": r.get("set_by"),
             "set_at": r.get("set_at"),
         },
         lambda r: r["source_id"])

    emit("interaction", "interaction",
         lambda r: {
             "source_system": r.get("source_system"), "source_id": r.get("source_id"),
             "company_ref": companies.get(r.get("company_id")),
             "interaction_type": r.get("interaction_type"), "occurred_at": r.get("occurred_at"),
             "subject": r.get("subject"), "duration_hours": r.get("duration_hours"),
             "notes": r.get("notes"),
         },
         lambda r: r["source_id"])

    return {
        "period": period,
        "source_route": "store",
        "sources": [{"source": "store", "route": "store"}],
        "flags": [],
        "records": records,
    }
