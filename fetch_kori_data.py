#!/usr/bin/env python3
"""
fetch_kori_data.py — Fetch real TUNI IT/ITC curriculum data from the Kori API.

Usage:
    python fetch_kori_data.py [--output kori_real_data.json] [--prefixes COMP DATA] [--limit 20]

Run this locally (not in the cloud sandbox — sisu.tuni.fi requires internet access).
The output file is then used by the RAG pipeline in place of the synthetic dataset.

API notes (from empirical testing):
 - Most GET endpoints are publicly accessible (no auth required).
 - fullTextQuery only indexes name, code, searchTags — NOT descriptions/outcomes.
 - Descriptions/outcomes must be fetched individually via /course-units/v1/{id}.
 - responsibilityInfos[*].personId mixes otm-... UUIDs and tuni-person-<username>.
 - Persons endpoint returns title/name but no email.
"""

import argparse
import json
import sys
import time
from collections import defaultdict

import requests

BASE_URL = "https://sisu.tuni.fi/kori"
TUNI_ROOT_ORG = "tuni-university-root-id"

# IT/ITC faculty course code prefixes
IT_CODE_PREFIXES = ["COMP", "DATA", "SGN", "ELT", "MATH"]

HEADERS = {
    "User-Agent": "TuniCurriculumRAG/1.0 (research prototype)",
    "Accept": "application/json",
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(path: str, params: dict = None, retries: int = 4) -> dict | list | None:
    url = BASE_URL + path
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if r.status_code == 429:
                wait = 2 ** attempt
                print(f"    rate-limited — waiting {wait}s", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code in (404, 403):
                return None  # not found / not public — skip silently
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
        except requests.exceptions.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    return None


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------

def _name(v) -> str:
    """Extract English (or Finnish) string from a multilang dict or plain string."""
    if isinstance(v, dict):
        return v.get("en") or v.get("fi") or v.get("sv") or ""
    return str(v) if v else ""


def _extract_keywords(search_tags) -> list[str]:
    """
    searchTags can come back as:
      [{tag: "...", lang: "en"}, ...]   — documented form
      [{en: "..."}, ...]                — alternative observed form
      ["plain string", ...]             — simplified form
    """
    if not search_tags:
        return []
    tags = []
    for t in search_tags:
        if isinstance(t, str):
            tags.append(t)
        elif isinstance(t, dict):
            if "tag" in t:
                tags.append(t["tag"])
            else:
                tags.extend(v for v in t.values() if isinstance(v, str) and v)
    # deduplicate, preserve order
    seen: set[str] = set()
    out = []
    for tag in tags:
        tag = tag.strip()
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return out


def _extract_person_ids(responsibility_infos: list) -> list[str]:
    pids = []
    for ri in responsibility_infos or []:
        if isinstance(ri, dict):
            pid = ri.get("personId") or (ri.get("person") or {}).get("id")
        else:
            pid = ri
        if pid:
            pids.append(pid)
    return pids


def _credits(cu: dict) -> dict:
    c = cu.get("credits", {})
    if isinstance(c, dict):
        return {"min": c.get("min") or 5, "max": c.get("max") or 5}
    if isinstance(c, (int, float)):
        return {"min": int(c), "max": int(c)}
    return {"min": 5, "max": 5}


# ---------------------------------------------------------------------------
# Phase 1 — search for course IDs by code prefix
# ---------------------------------------------------------------------------

def _search_page(prefix: str, start: int, limit: int) -> tuple[list, int]:
    """Returns (items, total)."""
    result = _get("/api/course-unit-search", params={
        "universityOrgId": TUNI_ROOT_ORG,
        "codeQuery": prefix,
        "documentState": "ACTIVE",
        "ignoreValidityPeriod": "false",
        "start": start,
        "limit": limit,
    })
    if result is None:
        return [], 0
    if isinstance(result, list):
        return result, len(result)
    items = result.get("searchResults") or result.get("results") or []
    total = result.get("total") or result.get("totalCount") or len(items)
    return items, int(total)


def fetch_course_ids_for_prefix(prefix: str, cap: int = 0) -> list[str]:
    ids: list[str] = []
    start = 0
    limit = 100
    while True:
        print(f"    {prefix}.* — searching (start={start}) …", end="", flush=True)
        items, total = _search_page(prefix, start, limit)
        print(f" {len(items)} results (total={total})")
        for item in items:
            cid = item.get("id") or item.get("courseUnitId") or item.get("groupId")
            if cid and cid not in ids:
                ids.append(cid)
        start += limit
        if not items or start >= total:
            break
        if cap and len(ids) >= cap:
            break
        time.sleep(0.25)
    return ids[:cap] if cap else ids


# ---------------------------------------------------------------------------
# Phase 2 — fetch full course unit details
# ---------------------------------------------------------------------------

def fetch_course_unit(course_id: str) -> dict | None:
    return _get(f"/api/course-units/v1/{course_id}")


# ---------------------------------------------------------------------------
# Phase 3 — fetch person details
# ---------------------------------------------------------------------------

def fetch_person(person_id: str) -> dict | None:
    return _get(f"/api/persons/v1/{person_id}")


# ---------------------------------------------------------------------------
# Phase 4 — optional: fetch study modules
# ---------------------------------------------------------------------------

def try_fetch_modules(prefix: str) -> list[dict]:
    """
    Study modules (majors/minors/specialisations) live under /api/modules/v1/.
    Try stream endpoint first; fall back to search-style pagination.
    Not guaranteed to succeed — skip gracefully if 404/403.
    """
    result = _get("/api/modules/v1/stream", params={
        "universityOrgId": TUNI_ROOT_ORG,
        "documentState": "ACTIVE",
    })
    if isinstance(result, list):
        return result
    return []


# ---------------------------------------------------------------------------
# Org name map
# ---------------------------------------------------------------------------

def build_org_name_map() -> dict[str, str]:
    result = _get("/api/organisations/search", params={
        "universityOrgId": TUNI_ROOT_ORG,
        "limit": 500,
    })
    org_map: dict[str, str] = {}
    items = []
    if isinstance(result, list):
        items = result
    elif isinstance(result, dict):
        items = result.get("searchResults") or result.get("results") or []
    for o in items:
        if isinstance(o, dict) and o.get("id"):
            org_map[o["id"]] = _name(o.get("name")) or o["id"]
    return org_map


# ---------------------------------------------------------------------------
# Schema mapping
# ---------------------------------------------------------------------------

def map_course(cu: dict, org_name_map: dict) -> dict:
    person_ids = _extract_person_ids(cu.get("responsibilityInfos", []))

    # organisations → names
    cu_orgs = cu.get("organisations") or cu.get("organizationRoles") or []
    org_names: list[str] = []
    for o in cu_orgs:
        if isinstance(o, dict):
            oid = o.get("organisationId") or o.get("id")
            org_names.append(org_name_map.get(oid) or _name(o.get("name")) or oid or "")
    if not org_names:
        org_names = ["Tampere University"]

    keywords = _extract_keywords(cu.get("searchTags", []))

    return {
        "id": cu.get("id", ""),
        "groupId": cu.get("groupId", ""),
        "documentState": cu.get("documentState", "ACTIVE"),
        "code": cu.get("code", ""),
        "lang": "en",
        "name": cu.get("name") or {},
        "credits": _credits(cu),
        # Kori uses 'content' for description and 'outcomes' for learning outcomes
        "description": cu.get("content") or {},
        "learningOutcomes": cu.get("outcomes") or {},
        "keywords": keywords,
        "topicTags": keywords,
        "moduleCodes": [],        # populated from modules if available
        "degreeProgrammes": [],   # not directly available via public API
        "organisations": [o for o in org_names if o],
        "responsibilityInfos": person_ids,
        "annualStudentCountEstimate": None,
    }


def map_module(m: dict, org_name_map: dict) -> dict:
    keywords = _extract_keywords(m.get("searchTags", []))
    return {
        "id": m.get("id", ""),
        "groupId": m.get("groupId", ""),
        "documentState": m.get("documentState", "ACTIVE"),
        "code": m.get("code", ""),
        "name": m.get("name") or {},
        "description": m.get("content") or m.get("description") or {},
        "topicTags": keywords,
        "courseCodes": [],
        "degreeProgrammes": [],
        "annualStudentVolumeEstimate": None,
    }


def map_staff(pid: str, person: dict, course_codes: list[str]) -> dict:
    first = person.get("firstName", "")
    last = person.get("lastName", "")
    name = f"{first} {last}".strip() or pid
    title = _name(person.get("title") or person.get("employerTitle") or "")
    return {
        "id": pid,
        "groupId": person.get("groupId", ""),
        "documentState": "ACTIVE",
        "name": name,
        "title": title,
        "email": "",  # not exposed by the public API
        "researchAreas": [],
        "keywords": [],
        "relatedModuleCodes": [],
        "relatedCourseCodes": sorted(course_codes),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch TUNI ITC curriculum data from Kori API")
    parser.add_argument("--output", default="kori_real_data.json")
    parser.add_argument("--prefixes", nargs="+", default=IT_CODE_PREFIXES,
                        help="Course code prefixes (default: COMP DATA SGN ELT MATH)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max courses per prefix, 0 = all (use a small number for testing)")
    args = parser.parse_args()

    print("=" * 60)
    print("TUNI Kori Curriculum Fetcher")
    print(f"Prefixes : {args.prefixes}")
    print(f"Limit    : {args.limit or 'unlimited'}")
    print(f"Output   : {args.output}")
    print("=" * 60)

    # Org name map (best-effort)
    print("\n[1/5] Fetching organisation names …")
    try:
        org_name_map = build_org_name_map()
        print(f"      {len(org_name_map)} organisations found")
    except Exception as e:
        print(f"      Could not fetch orgs ({e}) — org names will be left as IDs")
        org_name_map = {}

    # Collect course IDs
    print("\n[2/5] Searching for course IDs …")
    all_ids: list[str] = []
    for prefix in args.prefixes:
        ids = fetch_course_ids_for_prefix(prefix, cap=args.limit)
        print(f"      {prefix}.* → {len(ids)} courses")
        all_ids.extend(ids)

    # Deduplicate preserving order
    seen: set[str] = set()
    unique_ids = [x for x in all_ids if not (x in seen or seen.add(x))]
    print(f"\n      Total unique course IDs: {len(unique_ids)}")

    # Fetch full course unit details
    print("\n[3/5] Fetching full course unit details …")
    raw_courses: list[dict] = []
    failures = 0
    for i, cid in enumerate(unique_ids, 1):
        suffix = f"[{i}/{len(unique_ids)}]"
        try:
            cu = fetch_course_unit(cid)
            if cu:
                raw_courses.append(cu)
                print(f"  {suffix} {cu.get('code', cid)}")
            else:
                print(f"  {suffix} {cid} — empty response (skipped)")
                failures += 1
        except Exception as e:
            print(f"  {suffix} {cid} — ERROR: {e}")
            failures += 1
        time.sleep(0.15)

    print(f"\n      Fetched {len(raw_courses)} courses, {failures} failed")

    # Collect unique responsible person IDs
    print("\n[4/5] Fetching responsible persons …")
    person_to_courses: dict[str, set[str]] = defaultdict(set)
    for cu in raw_courses:
        code = cu.get("code", "")
        for pid in _extract_person_ids(cu.get("responsibilityInfos", [])):
            person_to_courses[pid].add(code)

    all_person_ids = list(person_to_courses.keys())
    print(f"      {len(all_person_ids)} unique persons to fetch")

    persons: dict[str, dict] = {}
    for i, pid in enumerate(all_person_ids, 1):
        try:
            p = fetch_person(pid)
            if p:
                persons[pid] = p
                name = f"{p.get('firstName','')} {p.get('lastName','')}".strip()
                print(f"  [{i}/{len(all_person_ids)}] {name} ({pid})")
            else:
                print(f"  [{i}/{len(all_person_ids)}] {pid} — not found")
        except Exception as e:
            print(f"  [{i}/{len(all_person_ids)}] {pid} — ERROR: {e}")
        time.sleep(0.1)

    print(f"\n      Retrieved {len(persons)} person records")

    # Optional: study modules
    print("\n[5/5] Attempting to fetch study modules (optional) …")
    raw_modules: list[dict] = []
    try:
        raw_modules = try_fetch_modules("COMP")
        print(f"      {len(raw_modules)} modules fetched")
    except Exception as e:
        print(f"      Modules not available ({e}) — skipping")

    # Map to output schema
    print("\nMapping to output schema …")
    mapped_courses = [map_course(cu, org_name_map) for cu in raw_courses]
    mapped_modules = [map_module(m, org_name_map) for m in raw_modules]
    mapped_staff = [
        map_staff(pid, persons[pid], list(person_to_courses[pid]))
        for pid in all_person_ids
        if pid in persons
    ]

    output = {
        "metadata": {
            "datasetType": "real",
            "source": "TUNI SISU Kori API — https://sisu.tuni.fi/kori",
            "note": (
                "Real curriculum data for TUNI IT/ITC faculty. "
                f"Code prefixes: {args.prefixes}. "
                "Staff email and research areas are not available via the public API."
            ),
            "counts": {
                "courses": len(mapped_courses),
                "modules": len(mapped_modules),
                "staff": len(mapped_staff),
            },
        },
        "courses": mapped_courses,
        "modules": mapped_modules,
        "staff": mapped_staff,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSaved → {args.output}")
    print(f"  Courses : {len(mapped_courses)}")
    print(f"  Modules : {len(mapped_modules)}")
    print(f"  Staff   : {len(mapped_staff)}")
    print("\nDone! Copy kori_real_data.json to the project root and run the app.")


if __name__ == "__main__":
    main()
