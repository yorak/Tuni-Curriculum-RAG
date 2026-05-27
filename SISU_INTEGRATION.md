# SISU Kori Integration — Session Handoff

## What was done in this session

Replaced the synthetic dataset (`kori_synthetic_data.json`) with a live-data fetcher
targeting the TUNI SISU Kori API. The RAG pipeline itself was not changed; only the
data ingestion layer was updated.

### New file: `fetch_kori_data.py`

Standalone script that produces `kori_real_data.json` — a drop-in replacement for the
synthetic dataset, compatible with the existing `document_builder.py` schema.

**Run it locally** (not in a cloud sandbox — `sisu.tuni.fi` is not on the allowlist):

```bash
# Quick smoke test — 5 courses per prefix
python fetch_kori_data.py --limit 5

# Full fetch — all IT/ITC courses (COMP.*, DATA.*, SGN.*, ELT.*, MATH.*)
python fetch_kori_data.py

# Specific prefixes only
python fetch_kori_data.py --prefixes COMP DATA
```

Output: `kori_real_data.json` — place it in the project root. The app will pick it up
automatically on next start (no code change needed).

### Updated: `main.py` and `streamlit_app.py`

Both now auto-detect the data file in this priority order:

1. `$KORI_DATA_FILE` env var (explicit override)
2. `kori_real_data.json` (real data, if present)
3. `kori_synthetic_data.json` (fallback)

The Streamlit sidebar shows which file is active.

### Updated: `rag/document_builder.py`

`annualStudentCountEstimate` is `None` in real data (not in the public API) — the
`or "unknown"` fix prevents a crash when rendering the document text.

---

## Kori API — what we know

Base URL: `https://sisu.tuni.fi/kori`

Most GET endpoints are **publicly accessible** (no auth). Tested anonymously.

### OpenAPI specs

| Spec | Path | Notes |
|------|------|-------|
| Default | `/kori/v3/api-docs/default` | 102 paths — mostly `/import` + `/export` (SIS integration surface) |
| Internal | `/kori/v3/api-docs/internal` | 370 paths — what the Sisu UI itself uses; look here first |

Swagger UI: `https://sisu.tuni.fi/kori/swagger-ui/index.html`

### Worked example — COMP.CS.530 (Fine-tuning LLMs)

A known-good course to use as a test fixture:

- **Course unit id:** `otm-68424c80-193a-4f3e-a347-9c51809ef25e`
- **Organisation:** `tuni-org-1301000005` (Computing Sciences)
- **Credits:** 5–10 cr
- **Curriculum periods:** `uta-lvv-2024`, `uta-lvv-2025`, `uta-lvv-2026`
- **Spring 2026 realisations:**
  - Lectures `otm-1bd2266c-…_2025` — 7 Jan – 26 Feb 2026
  - Capstone `otm-9e9b00a6-…_2025` — 18 Feb – 1 Apr 2026
- **Responsible teachers:** Pekka Abrahamsson (Professor), Vaishnavi Bankhele, Jussi Rasku (Postdoctoral Research Fellow)

Quick fetch to inspect the raw API response:

```bash
curl -s "https://sisu.tuni.fi/kori/api/course-units/v1/otm-68424c80-193a-4f3e-a347-9c51809ef25e" | python3 -m json.tool | head -80
```

This is the fastest way to check field names if the fetcher produces unexpected output.

### IT/ITC course code prefixes (TUNI)

| Prefix | Faculty area |
|--------|-------------|
| `COMP` | Computing Sciences, Software Engineering, Signal Processing |
| `DATA` | Data Science |
| `SGN`  | Signal Processing (standalone) |
| `ELT`  | Electrical Engineering |
| `MATH` | Mathematics |

### Key endpoints used

```
GET /api/course-unit-search
    ?universityOrgId=tuni-university-root-id
    &codeQuery=COMP          # prefix filter
    &documentState=ACTIVE
    &start=0&limit=100       # pagination

GET /api/course-units/v1/{id}
    # Full details incl. content (description) and outcomes (learning outcomes)
    # search endpoint does NOT index these fields — must fetch individually

GET /api/persons/v1/{personId}
    # personId can be otm-... UUID or tuni-person-<username>
    # Returns firstName, lastName, title — NO email

GET /api/modules/v1/stream
    ?universityOrgId=tuni-university-root-id
    # Optional — may 404/403; script skips gracefully
```

### Gotchas (confirmed empirically)

- `fullTextQuery` / search only indexes **name, code, searchTags** — not
  `content`, `outcomes`, `tweetText`, `prerequisites`, `literature`.
  Descriptions/outcomes must be bulk-fetched via the individual endpoint.
- `name` field sometimes returns a plain string instead of `{en: ..., fi: ...}` dict.
- `responsibilityInfos[*].personId` mixes `otm-...` UUIDs and
  `tuni-person-<username>` strings in the same list.
- `credits` and `code` come back **null** on the realisation endpoint (`/course-unit-realisations/v1/{id}`) — use the course-unit endpoint instead.
- Add `universityOrgId=tuni-university-root-id` to restrict results to TUNI only
  (otherwise Aalto, JYU etc. are included).
- Known Computing Sciences org ID: `tuni-org-1301000005`

### Schema mapping (Kori API → RAG schema)

| RAG schema field       | Kori API field         |
|------------------------|------------------------|
| `description`          | `content`              |
| `learningOutcomes`     | `outcomes`             |
| `keywords`/`topicTags` | `searchTags`           |
| `responsibilityInfos`  | `responsibilityInfos[*].personId` |

---

## What still needs to be done

### High priority

- [ ] **Run the fetcher** locally and commit `kori_real_data.json`
      (or `.gitignore` it and document that it must be generated).
- [ ] **Validate** the fetched data — check that `content`/`outcomes` are populated
      for a sample of courses (some older courses may have empty fields).
- [ ] **Study modules** — the `/api/modules/v1/stream` endpoint was not confirmed
      to work. Investigate whether degree-programme / study-module data is accessible
      and how to link courses to modules.

### Medium priority

- [ ] **Staff research areas** — not available from the public Kori API. Consider
      scraping the TUNI staff pages or manually curating for key faculty members,
      since research-area queries are a common use case.
- [ ] **Realisations** (scheduled offerings) — `/api/course-unit-realisations/search`
      can add `activityPeriod` and enrolment-period data so users can ask
      "what courses are running this semester".
- [ ] **Incremental refresh** — re-running the full fetcher is slow (~10–20 min).
      Add a `--since` / `--update` mode that only re-fetches courses modified after
      a given date (Kori has a `modificationDate` field on course units).

### Low priority / nice-to-have

- [ ] Cache the fetched JSON in git (with a scheduled refresh action) so the app
      can be deployed without needing to run the fetcher first.
- [ ] Surface `curriculumPeriodIds` to allow filtering by academic year.
- [ ] Handle Finnish-language queries — `document_builder.py` currently picks `en`
      over `fi`; a bilingual index would need separate documents or a combined text.

---

## How to continue

1. `git pull` to get the latest changes.
2. `pip install -r requirements.txt` if needed.
3. Run `python fetch_kori_data.py --limit 10` to verify the fetcher works.
4. Run `python fetch_kori_data.py` for the full dataset.
5. Run `python main.py` or `streamlit run streamlit_app.py` to test with real data.

---

## Testing, triage & fix guide

The fetcher was written but **never run against the real API** (network was blocked in
the authoring session). Treat the first run as exploratory — expect to find and fix at
least one or two issues before the data is clean.

### Step 1 — smoke-test the fetcher

```bash
python fetch_kori_data.py --prefixes COMP --limit 5 --output kori_test.json
```

Expected output:
- `[1/5]` org names: should find > 0 organisations
- `[2/5]` search: should find results for `COMP.*` — if 0, see triage below
- `[3/5]` course units: each line shows a course code like `COMP.CS.530`
- `[4/5]` persons: lines like `Pekka Abrahamsson (tuni-person-pabraha)`
- `[5/5]` modules: likely 0 or skipped — that's fine

### Step 2 — validate the JSON

```python
import json
data = json.load(open("kori_test.json"))

# Check counts
print(len(data["courses"]), "courses")
print(len(data["staff"]), "staff")

# Check that descriptions actually have text (not empty dicts)
empty_desc = [c["code"] for c in data["courses"] if not c.get("description")]
print("Empty descriptions:", empty_desc)

# Check learning outcomes
empty_out = [c["code"] for c in data["courses"] if not c.get("learningOutcomes")]
print("Empty outcomes:", empty_out)

# Check a course in full
print(json.dumps(data["courses"][0], indent=2, ensure_ascii=False))
```

**Good:** descriptions and outcomes are multilang dicts with `en` or `fi` text.  
**Bad:** empty dicts `{}` — see triage below.

### Step 3 — end-to-end RAG test

```bash
GPTLAB_API_KEY=<your-key> python main.py
# Enter: "What courses cover machine learning?"
# Enter: "Who teaches software testing?"
# Enter: "What are the learning outcomes of COMP.CS.530?"
```

A good answer cites course codes and names from the fetched data. If answers are vague
or say "I don't know", check that retrieval is returning nodes (add a `print(nodes)`
in `main.py` temporarily).

### Triage: common failure modes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Search returns 0 results for `COMP` | `codeQuery` param name changed | Check Swagger UI at `/kori/swagger-ui` and update param name in `_search_page()` |
| Search response has unexpected shape | Response envelope differs from expected | Print raw response and update `.get("searchResults")` key in `_search_page()` |
| `description` / `learningOutcomes` always empty | Kori field names changed (`content`→`description`) | Fetch one course manually and inspect: `python -c "import requests,json; print(json.dumps(requests.get('https://sisu.tuni.fi/kori/api/course-units/v1/otm-68424c80-193a-4f3e-a347-9c51809ef25e').json(), indent=2))"` |
| All person fetches return 404 | `otm-...` IDs not valid for `/persons/v1/` | Only `tuni-person-<username>` IDs work; filter in `_extract_person_ids()` to skip `otm-` prefixed IDs |
| Credits come back as `{"min": 5, "max": 5}` for everything | `credits` null on course-unit (shouldn't happen, but if so) | Check raw response — credits should be on course unit, not realisation |
| RAG answers are wrong / hallucinated | `content`/`outcomes` fields empty so index has no substance | Fix empty descriptions first; the RAG quality is entirely dependent on this |

### Acceptance criteria — when is the data good enough?

- [ ] > 80% of fetched courses have non-empty `description` (the `content` field)
- [ ] > 50% of fetched courses have non-empty `learningOutcomes` (the `outcomes` field)
- [ ] Staff records resolve for the majority of `tuni-person-*` IDs
- [ ] RAG correctly answers "What does COMP.CS.530 cover?" with content from the
      real course description (verifiable at `https://sisu.tuni.fi/kori/swagger-ui`)
