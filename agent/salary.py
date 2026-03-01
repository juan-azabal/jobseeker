"""Salary extraction and currency conversion for job listings.

Extracts max salary from parsed job data and converts to EUR using ECB rates.
Pure functions with no dependency on agent pipeline globals.
"""

import re

from currency_converter import CurrencyConverter as _CurrencyConverter

_fx = _CurrencyConverter(fallback_on_missing_rate=True)

# Map text signals → ISO 4217 currency codes
_CURRENCY_SIGNALS: list[tuple[list[str], str]] = [
    (["cad"], "CAD"),
    (["usd", "$"], "USD"),
    (["pln", "zl", "zlot"], "PLN"),
    (["gbp", "£"], "GBP"),
    (["chf"], "CHF"),
    (["sek"], "SEK"),
    (["dkk"], "DKK"),
    (["nok"], "NOK"),
    (["inr", "₹", "lakh", "lpa"], "INR"),
    (["brl", "r$"], "BRL"),
    (["aud", "a$"], "AUD"),
    (["sgd", "s$"], "SGD"),
    (["czk", "kč"], "CZK"),
    (["huf", "ft"], "HUF"),
    (["ron", "lei"], "RON"),
    (["jpy", "¥", "yen"], "JPY"),
    (["ils", "₪", "shekel"], "ILS"),
    (["try", "₺", "tl"], "TRY"),
]


def _to_eur(amount: float, currency_code: str) -> float:
    """Convert amount to EUR using ECB rates. Returns amount unchanged if already EUR."""
    if currency_code == "EUR":
        return amount
    try:
        return _fx.convert(amount, currency_code, "EUR")
    except Exception:
        return amount  # unknown currency — assume EUR


def _detect_currency(salary_str: str, job: dict) -> str:
    """Detect currency from salary text and job metadata. Returns ISO code."""
    # CAD needs special handling: "$" + Canada location
    if "$" in salary_str and "canada" in (job.get("location") or "").lower():
        return "CAD"
    for signals, code in _CURRENCY_SIGNALS:
        if any(sig in salary_str for sig in signals):
            return code
    return "EUR"


def extract_max_salary_eur(job: dict) -> float:
    """Extract max salary as EUR equivalent. Returns 0 if not available."""
    p = job.get("parsed") or {}
    salary_str = (p.get("salary_mentioned") or "").lower()
    if not salary_str or salary_str == "null":
        max_amt = job.get("max_amount")
        if max_amt and max_amt == max_amt:  # not NaN
            try:
                val = float(max_amt)
                currency = (job.get("currency") or "").upper()
                if not currency or currency == "EUR":
                    return val
                return _to_eur(val, currency)
            except (ValueError, TypeError):
                return 0
        return 0

    # Normalize: remove spaces used as thousand separators (European style: "50 000")
    # and strip commas used as thousand separators (American style: "50,000")
    normalized = re.sub(r"(\d)[ \u00a0](\d)", r"\1\2", salary_str)  # "50 000" → "50000"
    normalized = normalized.replace(",", "")
    # Expand shorthand: "80k" → "80000", "100k" → "100000"
    normalized = re.sub(r"(\d+)\s*k\b", lambda m: str(int(m.group(1)) * 1000), normalized)

    # Extract salary-like numbers: ≥ 4 digits, but exclude years (1900-2099)
    raw_nums = [int(m) for m in re.findall(r"\d+", normalized)]
    vals = [n for n in raw_nums if n >= 1000 and not (1900 <= n <= 2099)]
    if not vals:
        return 0

    max_val = max(vals)
    if max_val < 20000:
        max_val *= 12  # monthly → annual

    # Currency conversion via ECB rates
    currency = _detect_currency(salary_str, job)
    max_val = _to_eur(max_val, currency)

    # Sanity cap: >250K EUR is almost certainly a parse error
    if max_val > 250000:
        return 0

    return max_val
