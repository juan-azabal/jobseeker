# File Copy Consistency Report

Updated: 2026-03-01 (Phase R1 — scoring core extracted to shared/)

## Eliminated dual-copy pairs (Phase R1)

These functions were previously duplicated and are now in `shared/scoring_core.py`.
Both `api/scoring.py` and `agent/main.py` import from shared — no sync needed.

| Function/Data | Previously in | Now in |
|---|---|---|
| `DOMAIN_KEYWORDS` | `api/scoring.py`, `agent/main.py` | `shared/scoring_core.py` |
| `DOMAIN_ALIASES` | `api/scoring.py`, `agent/main.py` | `shared/scoring_core.py` |
| `infer_domain()` | `api/scoring.py`, `agent/main.py` | `shared/scoring_core.py` |
| `grade_to_points()` / `_grade_to_points()` | `api/grade_mapping.py`, `agent/main.py` | `shared/scoring_core.py` |
| `is_pure_timezone()` | `api/geo.py`, `agent/main.py` | `shared/scoring_core.py` |
| `compute_eligibility_penalty()` | `api/scoring.py`, `agent/main.py` | `shared/scoring_core.py` |
| `heuristic_score()` (core) | `api/scoring.py`, `agent/main.py` | `shared/scoring_core.py` |
| `_CITY_TO_COUNTRY` | `api/scoring.py`, `agent/main.py` | `shared/scoring_core.py` |

---

## Remaining dual-copy pairs

### `agent/geo.py` ↔ `api/geo.py`

**Status: Functionally identical. Cosmetic differences only.**

Differences found:
- Unicode `→` vs ASCII `->` in docstring comments (api/ uses ASCII)
- api/geo.py has an extra header note: "This is the API-side copy..."
- `españa` vs `espana` in one example comment (encoding)

Functional code (all functions, logic, constants): identical. ✅

Note: `is_pure_timezone()` in geo.py is now superseded by `shared.scoring_core.is_pure_timezone()`.
The geo.py copies remain for non-scoring callers (reloc detection, prefilter).

---

### `agent/prompts/onboard-extraction.md` ↔ `api/prompts/onboard-extraction.md`

**Status: Identical.** ✅

---

### `api/onboard_utils.py` ↔ `agent/onboard.py`

**Status: Not compared** — these are parallel implementations (not exact copies).
They share the same extraction logic but have different I/O layers (HTTP vs CLI).
Functional equivalence maintained by convention, not byte comparison.

---

## Summary

Phase R1 (2026-03-01): Eliminated 8 dual-copy scoring functions/data structures.
Single source of truth is now `shared/scoring_core.py`.
Remaining dual copies: geo.py (non-scoring callers) + onboard prompts + onboard utils.
