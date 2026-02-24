# ADR-007: Library-Backed Geographic, Currency, and Language Detection

## Status: Accepted
## Date: 2026-02-24

## Context

The pipeline had three clusters of hardcoded lookup data:

1. **Geographic regions**: A manual list of EU-specific terms (`["eu", "europe", "emea", "eea", "schengen"]`) only worked for European users. A US-based user couldn't correctly detect "Americas" or "APAC" jobs as accessible. Adding a new user in a different region meant manually editing region lists.

2. **Currency conversion**: 8 hardcoded EUR exchange rates (e.g., USD=0.92, GBP=1.17) had drifted 2-8% from actual rates. Every new currency required a code change. No single source of truth.

3. **Location-to-language mapping**: A 60-entry dictionary in `api/cv/plan.py` mapping countries to languages for CV generation. Incomplete coverage, maintenance burden, and error-prone for multi-language countries.

Additionally, timezone abbreviation detection used 10 hardcoded abbreviations, missing many valid timezone terms that appear in job restriction fields.

## Decision

Replace all four hardcoded maps with library-backed equivalents, centralized in `geo.py` and `main.py`:

| Problem | Library | What it provides |
|---|---|---|
| Region detection | `country-converter` (coco) | Country resolution + group membership (EU27, EEA, Schengen, continent, UNregion, EMEA, APAC) |
| Currency conversion | `CurrencyConverter` | ECB reference rates, bundled offline, auto-updated on pip install |
| Language mapping | `babel` + `country-converter` | `get_official_languages(iso2)` for any country, returns language names |
| Timezone detection | `pytz` | 53 timezone abbreviations derived from all IANA timezones (vs 10 hardcoded) |

## Rationale

- **Multi-user correctness**: Region detection now works for any country. `derive_home_regions(["us"])` returns `["americas", "north america", "united states"]`. `derive_home_regions(["spain"])` returns `["eu", "eea", "schengen", "europe", "emea", ...]`. No manual config per user.

- **Word-boundary matching**: Region terms are matched via compiled regex with `\b` word boundaries. This prevents "eu" from matching inside "reuters", "deutsche", or "neural". Previous substring matching caused false positives.

- **Currency accuracy**: ECB reference rates are authoritative and bundled with the library. The previous hardcoded USD rate of 0.92 had drifted to ~0.85 (7.5% error). The library supports 40+ currencies; we now handle 18 explicitly detected currencies.

- **Zero config**: Adding a new user in Japan requires only `home_locations: ["tokyo", "japan"]` in their profile. Regions (Asia, APAC), currencies, languages, and timezone terms are all auto-derived.

- **Offline operation**: All four libraries work without network access. country-converter bundles its data, CurrencyConverter bundles ECB rates, babel bundles CLDR data, pytz bundles IANA timezone data.

## Implementation

All geographic utilities are centralized in `geo.py`:
- `derive_home_regions(home_locations)` — returns sorted list of region terms for a user
- `build_region_pattern(regions)` — compiles word-boundary regex for matching
- `matches_region(text, pattern)` — tests if text contains any region term
- `is_pure_timezone(restriction)` — checks if a restriction is timezone-only (not geographic)
- `location_to_languages(location_text)` — returns official language names for a location

Currency conversion lives in `main.py`:
- `_to_eur(amount, currency_code)` — converts to EUR via ECB rates
- `_detect_currency(salary_str, job)` — detects currency from text signals
- `_CURRENCY_SIGNALS` — maps text patterns to ISO 4217 codes (18 currencies)

## Consequences

- **New dependencies**: `country-converter`, `CurrencyConverter`, `babel`, `pycountry` added to requirements.txt. All are well-maintained, pure Python, and have no transitive heavy dependencies.
- **Import-time cost**: `_build_tz_abbreviations()` iterates all pytz timezones at import time (~0.3s). Acceptable for a batch pipeline; would need lazy loading if used in a request-hot-path.
- **ECB rate staleness**: CurrencyConverter rates are bundled at package build time. Rates may lag by weeks/months. Acceptable for salary display thresholds (not financial trading).
- **country-converter city limitations**: coco resolves country names but not cities ("barcelona" returns "not found"). Cities are still matched via direct substring in `home_locations`. This is by design — cities don't have region memberships.
