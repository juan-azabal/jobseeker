# File Copy Consistency Report

Generated: 2026-02-27

## Known dual-copy pairs

These files are intentionally duplicated between `api/` and `agent/`.
If one changes, both must be updated.

---

### `agent/geo.py` ↔ `api/geo.py`

**Status: Functionally identical. Cosmetic differences only.**

Differences found:
- Unicode `→` vs ASCII `->` in docstring comments (api/ uses ASCII)
- api/geo.py has an extra header note: "This is the API-side copy..."
- `españa` vs `espana` in one example comment (encoding)

Functional code (all functions, logic, constants): identical. ✅

---

### `agent/prompts/onboard-extraction.md` ↔ `api/prompts/onboard-extraction.md`

**Status: Identical.** ✅

---

### `_DOMAIN_KEYWORDS` in `agent/main.py` ↔ `api/scoring.py`

**Status: Identical.** ✅

---

### `_DOMAIN_ALIASES` in `agent/main.py` ↔ `api/scoring.py`

**Status: Identical.** ✅

---

### `api/onboard_utils.py` ↔ `agent/onboard.py`

**Status: Not compared** — these are parallel implementations (not exact copies).
They share the same extraction logic but have different I/O layers (HTTP vs CLI).
Functional equivalence maintained by convention, not byte comparison.

---

## Summary

All critical dual-copy pairs are in sync as of 2026-02-27.
