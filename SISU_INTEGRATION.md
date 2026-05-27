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
