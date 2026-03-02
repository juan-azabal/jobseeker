"""CV plan builder — deterministic, no LLM, instant.

Builds a structured generation plan from scored job data + reference files.
The plan is consumed by prompt.py (plan-aware prompting) and validator.py
(source-fidelity checks).

Usage:
    from api.cv.plan import build_cv_plan
    plan = build_cv_plan(job_dict, reference_files_dict)

Output schema: see _PLAN_SCHEMA docstring in build_cv_plan().
"""

import json
import re
from datetime import datetime

# ── Location → language hints (powered by babel + country-converter) ──────

# ── Known technical tools (for key_tools extraction) ─────────────────────

_KNOWN_TOOLS: frozenset[str] = frozenset(
    {
        "sql",
        "python",
        "r",
        "java",
        "scala",
        "go",
        "rust",
        "c++",
        "c#",
        "javascript",
        "typescript",
        "react",
        "node",
        "dbt",
        "kafka",
        "flink",
        "spark",
        "airflow",
        "luigi",
        "prefect",
        "dagster",
        "fivetran",
        "airbyte",
        "snowflake",
        "bigquery",
        "redshift",
        "databricks",
        "clickhouse",
        "postgresql",
        "mysql",
        "mongodb",
        "redis",
        "elasticsearch",
        "s3",
        "aws",
        "gcp",
        "azure",
        "docker",
        "kubernetes",
        "terraform",
        "tableau",
        "looker",
        "metabase",
        "superset",
        "power bi",
        "amplitude",
        "mixpanel",
        "segment",
        "snowplow",
        "ga4",
        "google analytics",
        "excel",
        "salesforce",
        "hubspot",
        "mlflow",
        "tensorflow",
        "pytorch",
        "scikit-learn",
        "pandas",
        "numpy",
        "datadog",
        "grafana",
        "prometheus",
        "git",
        "jira",
        "figma",
        "sap",
    }
)

# ── Dimension guidance (deterministic lookup) ─────────────────────────────

_DIMENSION_INSTRUCTIONS: dict[str, dict[str, str]] = {
    "domain_fit": {
        "high": "Lead with domain-proof bullets. Match terminology directly to JD.",
        "medium": "Surface domain experience; draw parallels to JD vertical.",
        "low": "Reframe adjacent experience; acknowledge domain gap honestly.",
    },
    "seniority_fit": {
        "high": "Maintain seniority level from source. Never downgrade title or years.",
        "medium": "Emphasize scope and ownership; avoid junior-sounding language.",
        "low": "Lead with strategic impact; minimize hands-on tactical details.",
    },
    "technical_depth": {
        "high": "Include technical mechanisms in bullets. Name the stack.",
        "medium": "Balance technical and business language.",
        "low": "Lead with outcomes. Technical details are secondary.",
    },
    "profile_evidence": {
        "high": "Emphasize concrete, verifiable evidence. Include metrics.",
        "medium": "Supplement every claim with a specific example.",
        "low": "Strengthen each claim with at least one concrete example.",
    },
    "strategic_impact": {
        "high": "Highlight platform-level and cross-functional strategic wins.",
        "medium": "Reframe tactical wins as strategic outcomes where honest.",
        "low": "Reframe as platform-level thinking; avoid task lists.",
    },
}

# ── Consultancy / in-house detection ─────────────────────────────────────

_CONSULTANCY_SIGNALS = [
    "consulting",
    "consultant",
    "our clients",
    "client engagements",
    "client projects",
    "embedded in client",
    "embedded at client",
    "client-facing",
    "client teams",
    "for our clients",
    "service to clients",
    "advisory",
    "outsource",
    "managed service",
    # weaker signals (need 2 hits to trigger on their own)
    "clients,",
    "clients.",
    "clients ",
    "our customers",
]
_IN_HOUSE_SIGNALS = [
    "we are building",
    "we build",
    "our platform",
    "our product",
    "our engineering team",
    "join our team",
    "our mission is",
    "we are a startup",
    "we are scaling",
    "product-led",
]


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════


def build_cv_plan(job: dict, user_cv_markdown: str = "") -> dict:
    """Build a CV generation plan from scored job data + the user's CV.

    Args:
        job: Full job dict from SQLite. `parsed` and `scored` fields may be
             JSON strings or already-decoded dicts.
        user_cv_markdown: The user's master CV text from the database
                          (users.cv_md).  Empty string → conservative defaults.

    Returns:
        Plan dict with keys: jd_context, score_summary, strengths, gaps,
        bullet_allocation, source_facts. Optionally: requirement_evidence,
        cv_strategy (when scorer v2.1 fields are present).

    This function never raises — missing data produces conservative defaults.
    """
    parsed, scored = _parse_job_blobs(job)
    cv_text = user_cv_markdown or ""

    jd_text = parsed.get("description", "") or ""
    location = (parsed.get("locations_mentioned") or [""])[0]

    # Scorer v2.1 enrichment fields (optional, graceful if absent)
    evidence_map = scored.get("requirement_evidence_map") or []
    cv_strategy = scored.get("cv_strategy")

    companies = _parse_companies_from_experience(cv_text)
    allocation = _build_bullet_allocation(companies, cv_text, parsed)
    _enrich_allocation_from_evidence(allocation, evidence_map)

    jd_ctx = _build_jd_context(parsed, jd_text, location)
    if cv_strategy:
        jd_ctx["cv_strategy"] = cv_strategy

    plan: dict = {
        "jd_context": jd_ctx,
        "score_summary": _build_score_summary(scored),
        "strengths": scored.get("strengths", []),
        "gaps": scored.get("gaps", []),
        "bullet_allocation": allocation,
        "source_facts": _extract_source_facts(cv_text),
    }
    if evidence_map:
        plan["requirement_evidence"] = evidence_map[:5]
    return plan


# ═══════════════════════════════════════════════════════════════════════════
# JD context
# ═══════════════════════════════════════════════════════════════════════════


def _parse_job_blobs(job: dict) -> tuple[dict, dict]:
    """Decode `parsed` and `scored` JSON fields from the job dict."""

    def _decode(value) -> dict:
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass
        return {}

    return _decode(job.get("parsed")), _decode(job.get("scored"))


def _build_jd_context(parsed: dict, jd_text: str, location: str) -> dict:
    ctx = {
        "company_type": _detect_company_type(jd_text),
        "business_model": _detect_business_model(parsed, jd_text),
        "vertical": parsed.get("domain", "unknown"),
        "location": location,
        "seniority_read": parsed.get("seniority", "unknown"),
        "key_tools": _extract_key_tools(parsed),
        "team_signals": _extract_team_signals(jd_text),
        "location_language_hints": _location_language_hints([location]),
    }
    role_summary = parsed.get("role_in_plain_english")
    if role_summary:
        ctx["role_summary"] = role_summary
    return ctx


def _detect_company_type(jd_text: str) -> str:
    """Heuristic: detect company type from JD keyword patterns."""
    text = jd_text.lower()
    consultancy_hits = sum(1 for s in _CONSULTANCY_SIGNALS if s in text)
    in_house_hits = sum(1 for s in _IN_HOUSE_SIGNALS if s in text)

    if consultancy_hits >= 2:
        return "consultancy"
    if in_house_hits >= 2:
        return "in_house"
    if consultancy_hits >= 1:
        return "consultancy"
    return "unknown"


def _detect_business_model(parsed: dict, jd_text: str) -> str:
    text = jd_text.lower()
    domain = (parsed.get("domain") or "").lower()
    if "marketplace" in text or "marketplace" in domain:
        return "marketplace"
    if "saas" in text or "saas" in domain:
        return "SaaS"
    if "b2b" in text:
        return "B2B"
    if "b2c" in text:
        return "B2C"
    if "platform" in text:
        return "platform"
    return "unknown"


def _location_language_hints(locations: list[str]) -> list[str]:
    """Return language hints for a list of location strings.

    Uses babel + country-converter to resolve locations to official languages.
    Skips English (assumed default) and returns unique names.
    """
    from api.geo import location_to_languages

    hints: list[str] = []
    for loc in locations:
        for lang in location_to_languages(loc):
            if lang not in hints and lang != "English":
                hints.append(lang)
    return hints


def _extract_key_tools(parsed: dict) -> list[str]:
    """Filter truly_required + technical_stack to known tool names."""
    raw: list[str] = (
        (parsed.get("truly_required") or parsed.get("must_have_skills") or [])
        + (parsed.get("technical_stack") or [])
        + (parsed.get("preferred_skills") or parsed.get("nice_to_have_skills") or [])
    )
    seen: set[str] = set()
    result: list[str] = []
    for item in raw:
        item_lower = item.lower().strip()
        for tool in _KNOWN_TOOLS:
            # Accept if the skill is a short phrase containing a known tool
            if tool in item_lower and len(item) < 50:
                # Normalise: use the known tool name as canonical form
                if tool not in seen:
                    seen.add(tool)
                    result.append(tool)
                break
    return result[:12]


def _extract_team_signals(jd_text: str) -> str:
    """Extract rough team-size / org-structure signals from JD text."""
    text_lower = jd_text.lower()
    signals = []
    for phrase in (
        "cross-functional",
        "embedded",
        "multi-team",
        "global team",
        "distributed team",
        "matrixed",
        "squad",
        "tribe",
    ):
        if phrase in text_lower:
            signals.append(phrase)
    return ", ".join(signals) if signals else ""


# ═══════════════════════════════════════════════════════════════════════════
# Score summary
# ═══════════════════════════════════════════════════════════════════════════


def _classify_score_level(score: int | float) -> str:
    if score >= 16:
        return "high"
    if score >= 10:
        return "medium"
    return "low"


def _build_score_summary(scored: dict) -> dict:
    breakdown = scored.get("score_breakdown", {})
    dimension_guidance: dict[str, dict] = {}
    for dim, score in breakdown.items():
        level = _classify_score_level(score)
        dim_instructions = _DIMENSION_INSTRUCTIONS.get(dim, {})
        dimension_guidance[dim] = {
            "score": score,
            "level": level,
            "instruction": dim_instructions.get(level, ""),
        }
    return {
        "total": scored.get("score", 0),
        "breakdown": breakdown,
        "dimension_guidance": dimension_guidance,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Source facts
# ═══════════════════════════════════════════════════════════════════════════


def _extract_source_facts(cv_text: str) -> dict:
    """Extract source facts from the user's full CV markdown.

    The same cv_text is searched for all facts — the parsers are tolerant
    of format variation and return empty values when the section is absent.
    """
    return {
        "title": _extract_title(cv_text),
        "years_experience": _extract_years(cv_text),
        "languages": _extract_languages(cv_text),
        "core_skills_themes": _extract_core_skills_themes(cv_text),
    }


def _extract_title(profile: str) -> str:
    """Extract professional title from the Contact section.

    Looks for a line matching 'Title | ...' pattern (containing a "|" and
    a seniority keyword).
    """
    SENIORITY_KEYWORDS = (
        "Product Manager",
        "Director",
        "VP",
        "Head of",
        "Lead",
        "Engineer",
        "Analyst",
        "Consultant",
        "Designer",
    )
    in_contact = False
    for line in profile.splitlines():
        stripped = line.strip()
        if stripped == "## Contact":
            in_contact = True
            continue
        if in_contact and stripped.startswith("## "):
            break
        if in_contact and "|" in stripped:
            # "Senior Product Manager | Data, Personalization & Monetization"
            for kw in SENIORITY_KEYWORDS:
                if kw in stripped:
                    return stripped.split("|")[0].strip()

    # Fallback: scan entire file for first line with title pattern
    for line in profile.splitlines()[:30]:
        stripped = line.strip()
        if "|" in stripped:
            for kw in SENIORITY_KEYWORDS:
                if kw in stripped:
                    return stripped.split("|")[0].strip()
    return ""


def _extract_years(experience: str) -> str:
    """Compute years of relevant experience from PM-role dates in experience file.

    Finds the earliest role line containing 'Product Manager' (or equivalent),
    extracts the start year, and returns 'N+' bucketed.
    """
    # Match lines like "Senior Product Manager | 07/2022 - ..."
    role_pattern = re.compile(
        r"(?:Product Manager|Director|Head of|VP|Lead).*?\|\s*(\d{2})/(\d{4})",
        re.IGNORECASE,
    )
    earliest_year: int | None = None
    for line in experience.splitlines():
        m = role_pattern.search(line)
        if m:
            year = int(m.group(2))
            if earliest_year is None or year < earliest_year:
                earliest_year = year

    if earliest_year is None:
        return ""

    years = datetime.now().year - earliest_year
    if years >= 15:
        return "15+"
    if years >= 10:
        return "10+"
    if years >= 5:
        return "5+"
    return f"{years}+"


def _extract_languages(profile: str) -> list[str]:
    """Extract language list from the Languages section of the profile.

    Handles both '| '-separated lines and '- ' list lines.
    """
    in_languages = False
    list_langs: list[str] = []
    for line in profile.splitlines():
        stripped = line.strip()
        if re.match(r"^## Languages?\s*$", stripped, re.IGNORECASE):
            in_languages = True
            continue
        if in_languages and stripped.startswith("## "):
            break
        if in_languages and stripped and not stripped.startswith("#"):
            if "|" in stripped:
                return [lang.strip() for lang in stripped.split("|") if lang.strip()]
            if stripped.startswith("- "):
                list_langs.append(stripped[2:].strip())
    return list_langs


def _extract_core_skills_themes(profile: str) -> list[str]:
    """Extract Core Skills theme names from '**Theme Name**' headers."""
    themes: list[str] = []
    in_skills = False
    for line in profile.splitlines():
        stripped = line.strip()
        if re.match(r"^## Core Skills?\s*$", stripped, re.IGNORECASE):
            in_skills = True
            continue
        if in_skills and stripped.startswith("## "):
            break
        if in_skills:
            # Phase 5 style: **Theme Name**
            m = re.match(r"^\*\*(.+?)\*\*$", stripped)
            if m:
                themes.append(m.group(1).strip())
            # Phase 6 style: "Theme Name: prose"
            elif re.match(r"^[A-Za-z][^:*\n]{0,50}:\s+\S", stripped):
                theme = stripped.split(":")[0].strip()
                if theme and len(theme) < 60:
                    themes.append(theme)
    return themes


# ═══════════════════════════════════════════════════════════════════════════
# Bullet allocation
# ═══════════════════════════════════════════════════════════════════════════


def _parse_companies_from_experience(experience: str) -> list[str]:
    """Extract company names from '### Company, City' section headers."""
    companies: list[str] = []
    for line in experience.splitlines():
        if line.startswith("### "):
            content = line[4:].strip()
            # "Gartner Digital Markets, Barcelona, Spain" → "Gartner Digital Markets"
            # "Grupo Godo (LaVanguardia.com), Barcelona" → "Grupo Godo (LaVanguardia.com)"
            # Split at first comma that is NOT inside parentheses
            company = re.split(r",\s*(?![^(]*\))", content)[0].strip()
            if company:
                companies.append(company)
    return companies


def _build_required_tokens(parsed: dict) -> frozenset[str]:
    """Build a set of meaningful tokens from JD requirements."""
    raw = (parsed.get("truly_required") or parsed.get("must_have_skills") or []) + (parsed.get("technical_stack") or [])
    tokens: set[str] = set()
    for item in raw:
        for token in item.lower().split():
            if len(token) > 3 and token.isalpha():
                tokens.add(token)
    return frozenset(tokens)


def _get_company_text(company_name: str, experience: str) -> str:
    """Extract the text block for a given company from the experience file."""
    lines = experience.splitlines()
    collecting = False
    block: list[str] = []
    company_lower = company_name.lower()
    for line in lines:
        if line.startswith("### "):
            if collecting:
                break  # reached next company
            if company_lower in line.lower():
                collecting = True
                block.append(line)
        elif collecting:
            block.append(line)
    return " ".join(block).lower()


def _compute_company_relevance(
    company_name: str,
    experience: str,
    required_tokens: frozenset[str],
) -> tuple[str, str]:
    """Return (relevance_level, reason) for a company vs JD requirements."""
    if not required_tokens:
        return "medium", "no JD requirements to compare"

    company_text = _get_company_text(company_name, experience)
    matched = sum(1 for t in required_tokens if t in company_text)
    ratio = matched / len(required_tokens)

    if ratio >= 0.12:
        return "high", f"{matched} JD skills/tools found in role"
    if ratio >= 0.05:
        return "medium", f"{matched} JD skills/tools found in role"
    return "low", "limited overlap with JD requirements"


def _enrich_allocation_from_evidence(
    allocation: dict,
    evidence_map: list[dict],
) -> None:
    """Add cv_hints to allocation entries where evidence mentions the company.

    Mutates allocation in-place. Graceful: no-op when either arg is empty.
    """
    if not evidence_map or not allocation:
        return
    for company in allocation:
        hints: list[str] = []
        for entry in evidence_map:
            ev_text = (entry.get("best_evidence") or "").lower()
            cv_hint = entry.get("cv_bullet_hint") or ""
            if company.lower() in ev_text and cv_hint:
                hints.append(cv_hint)
        if hints:
            allocation[company]["cv_hints"] = hints


def _build_bullet_allocation(
    companies: list[str],
    experience: str,
    parsed: dict,
) -> dict:
    """Assign a bullet budget per company based on JD relevance.

    Total budget is capped at 12 to satisfy the 2-page soft cap.
    Budget by relevance tier:
        high   → 3-4 bullets (capped by remaining budget)
        medium → 2-3 bullets
        low    → 1 bullet
    """
    if not companies:
        return {}

    required_tokens = _build_required_tokens(parsed)

    # Score each company
    scored: list[tuple[str, str, str]] = []  # (company, relevance, reason)
    for company in companies:
        relevance, reason = _compute_company_relevance(company, experience, required_tokens)
        scored.append((company, relevance, reason))

    # Sort: high first, then medium, then low (preserve order within tier)
    _ORDER = {"high": 0, "medium": 1, "low": 2}
    scored.sort(key=lambda x: _ORDER[x[1]])

    # Assign budgets with total cap
    _BASE_BUDGET = {"high": 3, "medium": 2, "low": 1}
    _MAX_TOTAL = 12
    total = 0
    allocation: dict[str, dict] = {}

    for company, relevance, reason in scored:
        remaining = _MAX_TOTAL - total
        if remaining <= 0:
            budget = 0
        else:
            budget = min(_BASE_BUDGET[relevance], remaining)
        allocation[company] = {
            "budget": budget,
            "relevance": relevance,
            "because": reason,
        }
        total += budget

    return allocation
