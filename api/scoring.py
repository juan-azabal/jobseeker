"""Per-user heuristic job scoring.

Ported from agent/main.py _heuristic_score(). Runs at query time for jobs
without RAG scores — no LLM calls, instant, free.
"""

import json
import os
from pathlib import Path

import yaml

import structlog
from api.skill_matcher import SkillMatch, match_skills

logger = structlog.get_logger(__name__)

# Maps profile domain names → parser-emitted domain names (canonical v1.3 enum).
# Parser enum (30 values): adtech|ai_ml|automotive|biotech|climate|construction|
#   cybersecurity|data|defense|devtools|ecommerce|edtech|energy|fintech|food_bev|
#   gaming|govtech|healthtech|hr_tech|infra|legal_tech|logistics|manufacturing|
#   marketplace|media|retail|saas|telecom|travel|other
_DOMAIN_ALIASES: dict[str, str] = {
    # AI/ML consolidation
    "ia": "ai_ml", "ai": "ai_ml", "llm": "ai_ml", "ml": "ai_ml",
    # Adtech
    "martech": "adtech",
    # Automotive
    "mobility": "automotive", "ev": "automotive",
    # Biotech
    "pharma": "biotech", "life_sciences": "biotech",
    # Climate
    "greentech": "climate", "cleantech": "climate",
    # Construction
    "proptech": "construction",
    # Cybersecurity
    "security": "cybersecurity", "infosec": "cybersecurity", "devsecops": "cybersecurity",
    "cybersecurity": "cybersecurity",
    # Devtools
    "developer-tools": "devtools",
    # Edtech
    "ed-tech": "edtech",
    # Fintech
    "insurtech": "fintech",
    # Food & bev
    "agritech": "food_bev", "foodtech": "food_bev",
    # Gaming
    "game": "gaming", "esports": "gaming", "gaming": "gaming",
    # Healthcare (legacy parser value)
    "healthcare": "healthtech",
    # HR tech
    "hrtech": "hr_tech",
    # Legal tech
    "legaltech": "legal_tech",
    # Platform (old enum value not in v2 list)
    "platform": "infra",
    # Growth (old enum value not in v2 list)
    "growth": "saas",
}

# Frozenset of all valid canonical domain values (v1.3 — 30 entries).
VALID_DOMAINS: frozenset[str] = frozenset({
    "adtech", "ai_ml", "automotive", "biotech", "climate", "construction",
    "cybersecurity", "data", "defense", "devtools", "ecommerce", "edtech",
    "energy", "fintech", "food_bev", "gaming", "govtech", "healthtech",
    "hr_tech", "infra", "legal_tech", "logistics", "manufacturing",
    "marketplace", "media", "retail", "saas", "telecom", "travel", "other",
})

# Seniority levels ordered from most junior to most senior
_SENIORITY_LEVELS = ["junior", "mid", "senior", "staff", "principal", "director", "vp"]
_LEVEL_IDX = {lvl: i for i, lvl in enumerate(_SENIORITY_LEVELS)}


def _compute_seniority_weights(level: str, track: str) -> dict[str, int]:
    """Compute seniority match weights from target.level + target.track.

    As per CLAUDE.md convention: seniority weights are computed at load time,
    never stored in YAML.

    Scoring:
      - Exact match: 15
      - 1 level off: 10
      - 2 levels off: 6
      - 3+ levels off: 0
      - director/vp capped at 4 for IC track (different career path)
    """
    level = (level or "senior").lower()
    track = (track or "ic").lower()
    target_idx = _LEVEL_IDX.get(level, 2)  # default to "senior" if unknown

    weights: dict[str, int] = {}
    for seniority, idx in _LEVEL_IDX.items():
        delta = abs(idx - target_idx)
        if delta == 0:
            weights[seniority] = 15
        elif delta == 1:
            weights[seniority] = 10
        elif delta == 2:
            weights[seniority] = 6
        else:
            weights[seniority] = 0

    # Management roles score poorly for IC track
    if track == "ic":
        weights["director"] = min(weights.get("director", 0), 4)
        weights["vp"] = min(weights.get("vp", 0), 4)

    return weights


# Domain override keywords — mirrors agent/main.py _DOMAIN_KEYWORDS (dual-copy rule).
# All keywords are ≥2 words or known brand/product names to avoid false-match substrings.
_DOMAIN_KEYWORDS = {
    "adtech": ["ad tech", "programmatic advertising", "demand-side platform",
               "supply-side platform", "header bidding", "real-time bidding",
               "publisher monetization", "ad network", "ad exchange",
               "display advertising"],
    "ai_ml": ["machine learning", "ml model", "ai agent", "large language model",
              "natural language processing", "computer vision", "deep learning",
              "neural network", "generative ai", "ml platform",
              "model training", "model inference"],
    "automotive": ["autonomous driving", "electric vehicle", "ev charging",
                   "connected car", "fleet management", "mobility platform",
                   "adas system", "vehicle software"],
    "biotech": ["drug discovery", "clinical trial", "life sciences",
                "genomics platform", "molecular biology", "bioinformatics pipeline"],
    "climate": ["carbon offset", "carbon footprint", "renewable energy",
                "clean energy", "climate tech", "solar energy", "wind energy",
                "circular economy", "sustainability platform", "decarbonization"],
    "construction": ["construction tech", "building information modeling",
                     "property management", "real estate platform",
                     "smart building", "architecture tech"],
    "cybersecurity": ["information security", "identity management",
                      "fraud prevention", "threat detection", "zero trust",
                      "penetration testing", "security operations center",
                      "vulnerability management"],
    "data": ["data platform", "data pipeline", "data warehouse", "data lake",
             "data lakehouse", "data product", "data governance", "data quality",
             "data engineering", "business intelligence", "data analytics platform",
             "observability platform", "etl pipeline", "data modeling",
             "databricks", "snowflake", "clickhouse"],
    "defense": ["defense contractor", "defense tech", "aerospace defense",
                "military technology", "government contractor"],
    "devtools": ["developer tool", "developer experience", "ci/cd pipeline",
                 "code review platform", "api platform", "sdk development",
                 "source control", "build system", "package manager",
                 "devops platform"],
    "ecommerce": ["online retail", "e-commerce platform", "shopping platform",
                  "direct-to-consumer", "online store", "product catalog",
                  "shopify", "woocommerce"],
    "edtech": ["e-learning", "learning management system", "education technology",
               "online education", "courseware platform", "student platform",
               "classroom technology", "tutoring platform"],
    "energy": ["oil and gas", "energy management", "smart grid",
               "power generation", "energy trading", "utility company"],
    "fintech": ["payment processing", "digital banking", "lending platform",
                "wealth management", "trading platform", "insurance technology",
                "credit platform", "neobank", "blockchain platform",
                "cryptocurrency exchange", "defi protocol",
                "financial institution", "financial services"],
    "food_bev": ["food delivery", "restaurant tech", "meal kit",
                 "food safety platform", "precision agriculture",
                 "grocery platform", "agritech platform"],
    "gaming": ["video game", "game engine", "game studio", "game development",
               "interactive entertainment", "mobile game", "esports platform",
               "unity developer", "unreal engine"],
    "govtech": ["government technology", "civic tech", "public sector platform",
                "e-government", "regulatory technology"],
    "healthtech": ["digital health", "telemedicine platform", "electronic health record",
                   "patient platform", "medical device software", "telehealth",
                   "health platform", "clinical software"],
    "hr_tech": ["recruiting platform", "talent acquisition", "workforce management",
                "hr platform", "applicant tracking", "people analytics",
                "employee engagement", "payroll platform",
                "training management", "learning and development"],
    "infra": ["cloud infrastructure", "container orchestration", "kubernetes",
              "terraform", "cloud platform", "infrastructure as code",
              "load balancer", "bare metal hosting", "cdn provider"],
    "legal_tech": ["legal tech", "contract management", "compliance platform",
                   "e-discovery", "case management", "document automation",
                   "legal ai"],
    "logistics": ["supply chain", "last mile delivery", "warehouse management",
                  "freight platform", "transportation management",
                  "fulfillment platform", "3pl platform"],
    "manufacturing": ["industrial iot", "factory automation", "manufacturing tech",
                      "quality control system", "production line", "robotics platform",
                      "scada system"],
    "marketplace": ["two-sided marketplace", "classifieds platform", "gig economy",
                    "platform economy", "peer to peer", "rental platform",
                    "buyer and seller"],
    "media": ["content platform", "streaming platform", "digital media",
              "publishing platform", "video platform", "podcast platform",
              "content management system", "editorial platform",
              "media company"],
    "retail": ["retail technology", "point of sale", "pos system",
               "in-store technology", "omnichannel retail",
               "inventory management", "store operations",
               "merchandising platform"],
    "saas": ["b2b software", "b2b platform", "enterprise software",
             "subscription platform", "crm platform", "erp system",
             "productivity software"],
    "telecom": ["telecommunications", "network operator", "mobile network",
                "fiber optic", "5g network", "voip platform",
                "connectivity platform"],
    "travel": ["travel tech", "booking platform", "hospitality platform",
               "hotel management", "airline technology", "reservation system",
               "tourism platform"],
}

# City → country normalisation for country_weights scoring.
_CITY_TO_COUNTRY: dict[str, str] = {
    # Spain
    "barcelona": "spain", "madrid": "spain", "valencia": "spain",
    "bilbao": "spain", "seville": "spain", "sevilla": "spain",
    # France
    "paris": "france", "lyon": "france", "marseille": "france", "toulouse": "france",
    # Germany
    "berlin": "germany", "munich": "germany", "münchen": "germany",
    "hamburg": "germany", "frankfurt": "germany", "cologne": "germany", "köln": "germany",
    # Netherlands
    "amsterdam": "netherlands", "rotterdam": "netherlands", "utrecht": "netherlands",
    # UK
    "london": "uk", "manchester": "uk", "edinburgh": "uk", "bristol": "uk",
    # Portugal
    "lisbon": "portugal", "porto": "portugal", "lisboa": "portugal",
    # Italy
    "milan": "italy", "rome": "italy", "milano": "italy", "roma": "italy",
    # Sweden
    "stockholm": "sweden", "gothenburg": "sweden",
    # Denmark
    "copenhagen": "denmark",
    # Belgium
    "brussels": "belgium", "bruxelles": "belgium",
    # Ireland
    "dublin": "ireland",
    # Switzerland
    "zurich": "switzerland", "zürich": "switzerland", "geneva": "switzerland",
    # Austria
    "vienna": "austria", "wien": "austria",
    # Poland
    "warsaw": "poland", "krakow": "poland",
    # Czech Republic
    "prague": "czech republic",
    # Finland
    "helsinki": "finland",
    # Norway
    "oslo": "norway",
}

# ISO language code → text signals that appear in JDs.
# English is NOT listed here: it's the default language of most tech JDs so
# detecting it as a "required language" would produce false positives everywhere.
# All other signals use ≥5-char strings to avoid substring false-matches.
_LANG_SIGNALS: dict[str, list[str]] = {
    "fr": ["french", "français", "francais"],
    "de": ["german", "deutsch"],
    "pt": ["portuguese", "português", "portugues"],
    "nl": ["dutch", "flemish", "nederlands"],
    "es": ["spanish", "español", "espanol", "castellano"],
    "it": ["italian", "italiano"],
    "ca": ["catalan", "català", "catala", "valencian"],
    "ar": ["arabic", "árabe"],
    "zh": ["chinese", "mandarin"],
    "ja": ["japanese"],
    "ko": ["korean"],
    "pl": ["polish", "polski"],
    "sv": ["swedish", "svenska"],
    "da": ["danish", "dansk"],
    "fi": ["finnish", "suomi"],
    "no": ["norwegian", "norsk"],
}


def compute_tier(score: int) -> str:
    if score >= 50:
        return "A"
    if score >= 30:
        return "B"
    return "C"


def _load_profile_yaml_from_db(profile_id: str, profile_path: Path) -> dict | None:
    """Fetch profile YAML from the DB when the local file is missing.

    Writes the YAML back to disk so subsequent calls within the same process
    hit the filesystem (avoids repeated DB lookups per request).

    Returns the parsed YAML dict on success, None on any failure.
    """
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    try:
        from api.db.queries import get_profile_yaml_by_profile_id  # avoid circular import at module level
        stored_yaml = get_profile_yaml_by_profile_id(db_path, profile_id)
        if not stored_yaml:
            return None
        # Cache back to disk so the next call is a fast file read.
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(stored_yaml)
        logger.info(
            "Restored profile YAML from DB for profile_id=%r → %s",
            profile_id, profile_path,
        )
        return yaml.safe_load(stored_yaml)
    except Exception as exc:
        logger.error(
            "Failed to restore profile YAML from DB for profile_id=%r: %s",
            profile_id, exc,
        )
        return None


def load_profile_data(profile_id: str | None) -> dict | None:
    """Load profile YAML and return scoring-relevant fields.

    Returns dict with keys: domains, seniority, skills, home_locations,
    home_regions, languages, location_preference, country_weights,
    company_type_weights.
    Returns None if profile_id is missing or file not found.
    """
    if not profile_id:
        return None

    jobagent_dir = os.environ.get("JOBAGENT_DIR", "agent")
    profile_path = Path(jobagent_dir) / "config" / "profiles" / f"{profile_id}.yaml"

    try:
        raw = yaml.safe_load(profile_path.read_text())
    except FileNotFoundError:
        # Ephemeral filesystem (e.g. Railway redeploy): try to restore from DB.
        raw = _load_profile_yaml_from_db(profile_id, profile_path)
        if raw is None:
            logger.warning(
                "Profile YAML not found for profile_id=%r at %s and not in DB — "
                "heuristic scoring disabled for this user",
                profile_id, profile_path,
            )
            return None
    except Exception as exc:
        logger.error(
            "Failed to load profile YAML for profile_id=%r at %s: %s",
            profile_id, profile_path, exc,
        )
        return None

    user_block = raw.get("user", {})
    target_block = raw.get("target", {})
    home_locations = [loc.lower() for loc in user_block.get("home_locations", [])]

    # Auto-derive home regions via country-converter
    try:
        from api.geo import derive_home_regions
        home_regions = derive_home_regions(home_locations)
    except Exception as exc:
        logger.warning("derive_home_regions failed for profile_id=%r: %s", profile_id, exc)
        home_regions = []

    # Normalize domain names to match parser enum values, merging aliases.
    # e.g. ia→ml, llm→ml, martech→adtech  (takes max weight on collision)
    raw_domains = {k.lower(): v for k, v in (target_block.get("domains") or {}).items()}
    normalized_domains: dict[str, int] = {}
    for domain, weight in raw_domains.items():
        canonical = _DOMAIN_ALIASES.get(domain, domain)
        normalized_domains[canonical] = max(normalized_domains.get(canonical, 0), weight)

    # Prefer explicitly stored seniority_weights; fall back to computing from level+track
    # for backward compat with profiles that pre-date the seniority_weights feature.
    stored_sw = target_block.get("seniority_weights")
    if stored_sw:
        seniority_weights = {k.lower(): int(v) for k, v in stored_sw.items()}
    else:
        level = target_block.get("level", "")
        track = target_block.get("track", "ic")
        seniority_weights = _compute_seniority_weights(level, track)

    return {
        "domains": normalized_domains,
        "seniority": seniority_weights,
        "skills": [s.lower() for s in (raw.get("skills") or [])],
        "home_locations": home_locations,
        "home_regions": home_regions,
        "languages": [lang.lower() for lang in user_block.get("languages", [])],
        "location_preference": (user_block.get("location_preference") or "b").lower(),
        "country_weights": {
            k.lower(): int(v) for k, v in (target_block.get("country_weights") or {}).items()
        },
        "company_type_weights": {
            k.lower(): int(v) for k, v in (target_block.get("company_type_weights") or {}).items()
        },
    }


def _infer_domain(parsed: dict) -> str:
    """Override 'other' domain using keyword detection."""
    domain = parsed.get("domain", "other")
    if domain != "other":
        return domain

    all_text = " ".join([
        parsed.get("responsibilities_summary", ""),
        " ".join(parsed.get("must_have_skills") or []),
        " ".join(parsed.get("technical_stack") or []),
    ]).lower()

    best_domain = "other"
    best_count = 0
    for d, keywords in _DOMAIN_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in all_text)
        if count > best_count:
            best_count = count
            best_domain = d

    return best_domain if best_count >= 1 else "other"


_SEMANTIC_DOMAIN_THRESHOLD = 0.75
_SEMANTIC_DOMAIN_MAX = 15


def _semantic_domain_score(
    profile: dict, parsed: dict, job: dict, db_path: str | None
) -> int:
    """Semantic domain scoring when enum and keyword detection both fail.

    Fires only when _infer_domain() returns 'other' (cascade: enum → keywords → semantic).
    Uses embedding similarity between the job text and user domain labels.

    Returns a score in [-15, 15]. Returns 0 if no domain matches >= 0.75 threshold,
    no db_path, or no domains in profile.
    """
    if not db_path:
        return 0

    domains = profile.get("domains", {})
    if not domains:
        return 0

    # Build job domain text from stable signals
    job_text = " ".join(filter(None, [
        job.get("company", ""),
        parsed.get("domain", ""),
        job.get("title", ""),
    ])).strip()
    if not job_text:
        return 0

    domain_names = list(domains.keys())

    # Lazy import to avoid circular import at module level
    from api.embeddings import get_embeddings_batch, cosine_similarity

    all_texts = [job_text] + domain_names
    embeddings = get_embeddings_batch(all_texts, db_path)

    job_emb = embeddings.get(job_text.strip().lower())
    if job_emb is None:
        return 0

    best_sim = 0.0
    best_domain = None
    for domain_name in domain_names:
        domain_emb = embeddings.get(domain_name.strip().lower())
        if domain_emb is None:
            continue
        sim = cosine_similarity(job_emb, domain_emb)
        if sim > best_sim:
            best_sim = sim
            best_domain = domain_name

    if best_sim < _SEMANTIC_DOMAIN_THRESHOLD or best_domain is None:
        return 0

    weight = domains[best_domain]
    score = int(weight * best_sim)
    return max(-_SEMANTIC_DOMAIN_MAX, min(_SEMANTIC_DOMAIN_MAX, score))


def precompute_skill_lookup(
    profile_skills: list[str],
    all_job_skills: list[str],
    db_path: str,
) -> dict[str, SkillMatch]:
    """Match user skills against all unique job skills in one call.

    Returns dict keyed by normalized job skill for O(1) per-job lookup.
    """
    results = match_skills(profile_skills, all_job_skills, db_path)
    return {m.job_skill.strip().lower().replace("-", " "): m for m in results}


def _score_skills(
    profile: dict, parsed: dict, db_path: str | None,
    skill_lookup: dict[str, SkillMatch] | None = None,
) -> int:
    """Score skills dimension (0-30).

    Must-have: 5 pts matched, 2 pts partial, cap 20.
    Nice-to-have + technical_stack: 3 pts matched, cap 10.

    Uses pre-computed skill_lookup when available, falls back to semantic
    matching when db_path is provided, substring fallback otherwise.
    """
    profile_skills = profile.get("skills", [])
    must_have_list = parsed.get("must_have_skills") or []
    nice_list = list(set(
        (parsed.get("nice_to_have_skills") or [])
        + (parsed.get("technical_stack") or [])
    ))

    if skill_lookup is not None:
        # Pre-computed batch lookup — O(1) per skill
        must_pts = sum(
            5 if (m := skill_lookup.get(s.strip().lower().replace("-", " "))) and m.status == "matched"
            else 2 if m and m.status == "partial"
            else 0
            for s in must_have_list
        )
        nice_pts = sum(
            3 if (m := skill_lookup.get(s.strip().lower().replace("-", " "))) and m.status == "matched"
            else 0
            for s in nice_list
        )
    elif db_path and profile_skills:
        # Semantic matching via embeddings
        must_results = match_skills(profile_skills, must_have_list, db_path)
        must_pts = sum(
            5 if m.status == "matched" else 2 if m.status == "partial" else 0
            for m in must_results
        )

        nice_results = match_skills(profile_skills, nice_list, db_path)
        nice_pts = sum(
            3 if m.status == "matched" else 0
            for m in nice_results
        )
    else:
        # Substring fallback (current behavior, also used when no db_path)
        norm_must = [s.lower().replace("-", " ") for s in must_have_list]
        nice_text = " ".join(
            [s.lower() for s in (parsed.get("nice_to_have_skills") or [])]
            + [s.lower() for s in (parsed.get("technical_stack") or [])]
            + [parsed.get("responsibilities_summary", "").lower()]
        ).replace("-", " ")
        norm_profile = [s.replace("-", " ") for s in profile_skills]

        must_pts = sum(5 for skill in norm_profile if skill in norm_must)
        nice_pts = sum(
            3 for skill in norm_profile
            if skill in nice_text and skill not in norm_must
        )

    return min(20, must_pts) + min(10, nice_pts)


def heuristic_score(
    profile: dict, parsed: dict, job: dict, is_reloc: bool,
    db_path: str | None = None,
    skill_lookup: dict[str, SkillMatch] | None = None,
    domain_override: str | None = None,
) -> int:
    """Compute heuristic fit score 0-100 from parsed job data + user profile.

    Score budget:
      Domain          0-15
      Seniority       0-15
      Skills          0-30  (must-have 5×cap20 + nice-to-have 3×cap10)
      Location        0-10
      Country bonus   ±10
      Language bonus  0-10
      Company type    ±15
      Red flags       0 to -15

    Args:
        profile: dict from load_profile_data()
        parsed: job's parsed JSON blob (dict)
        job: raw job row (for location field)
        is_reloc: unused — kept for API compatibility
        db_path: SQLite path for embedding cache; None → substring fallback
        skill_lookup: pre-computed batch skill matches; None → per-job matching
        domain_override: user-provided domain correction; skips cascade when set
    """
    if not parsed:
        return 0

    score = 0

    # ── Domain (0-15) ───────────────────────────────────────────────────────
    # Cascade: domain_override → enum match → keyword override → semantic fallback
    if domain_override is not None:
        # User-corrected domain: use directly, skip all inference
        score += profile["domains"].get(domain_override, 0)
    else:
        domain = _infer_domain(parsed)
        if domain != "other":
            score += profile["domains"].get(domain, 0)
        else:
            # Both enum and keyword detection failed — use semantic similarity
            score += _semantic_domain_score(profile, parsed, job, db_path)

    # ── Seniority (0-15) ────────────────────────────────────────────────────
    score += profile["seniority"].get(parsed.get("seniority", "unknown"), 0)

    # ── Skills (0-30) ───────────────────────────────────────────────────────
    # Must-have: 5 pts matched, 2 pts partial, cap 20.
    # Nice-to-have + technical_stack: 3 pts matched, cap 10.
    score += _score_skills(profile, parsed, db_path, skill_lookup=skill_lookup)

    # ── Location (0-10) ─────────────────────────────────────────────────────
    loc_pref = profile.get("location_preference", "b")
    loc_type = parsed.get("location_type", "unknown")
    job_loc = (job.get("location") or "").lower()
    home_locations = profile.get("home_locations", [])
    home_regions = profile.get("home_regions", [])

    if loc_pref == "a":
        # Remote-only: remote full score, hybrid partial, onsite nothing
        if loc_type == "remote":
            score += 10
        elif loc_type == "hybrid":
            score += 4
    elif loc_pref == "b":
        # Remote + home city (default legacy behaviour)
        if loc_type == "remote":
            score += 10
        elif loc_type == "hybrid" and any(c in job_loc for c in home_locations):
            score += 8
        elif loc_type == "onsite" and any(c in job_loc for c in home_locations):
            score += 6
    elif loc_pref == "c":
        # Anywhere in same country
        all_home = home_locations + home_regions
        if loc_type == "remote":
            score += 10
        elif loc_type in ("hybrid", "onsite") and any(c in job_loc for c in all_home):
            score += 8
        elif loc_type == "hybrid":
            score += 3  # partial credit: hybrid is flexible even without country match
    elif loc_pref == "d":
        # Anywhere in Europe — onsite/hybrid everywhere is fine
        if loc_type == "remote":
            score += 10
        elif loc_type == "hybrid":
            score += 10
        elif loc_type == "onsite":
            score += 8

    # ── Country weights (±10) ───────────────────────────────────────────────
    country_weights = profile.get("country_weights", {})
    if country_weights:
        locations_mentioned = [
            loc.lower() for loc in (parsed.get("locations_mentioned") or [])
        ]
        # Normalise city names → country names
        normalized_locs = {
            _CITY_TO_COUNTRY.get(loc, loc) for loc in locations_mentioned
        }
        # Remote jobs are accessible from any preferred location
        if loc_type == "remote":
            normalized_locs.add("remote")
        if normalized_locs:
            best = max(country_weights.get(loc, 0) for loc in normalized_locs)
            score += max(-10, min(10, best))

    # ── Language bonus (0-10) ───────────────────────────────────────────────
    languages = profile.get("languages", [])
    if languages:
        exp_req = parsed.get("experience_requirements") or ""
        if isinstance(exp_req, list):
            exp_req = " ".join(exp_req)
        lang_text = " ".join([
            exp_req,
            parsed.get("responsibilities_summary") or "",
            job.get("title") or "",
            (job.get("description") or "")[:1000],
        ]).lower()
        lang_bonus = 0
        for lang in languages:
            signals = _LANG_SIGNALS.get(lang.lower())
            if signals is None:
                # Unknown ISO code — skip; too short to safely use as substring
                continue
            if any(s in lang_text for s in signals):
                lang_bonus += 5
        score += min(10, lang_bonus)

    # ── Company type (±15) ──────────────────────────────────────────────────
    company_type_weights = profile.get("company_type_weights", {})
    if company_type_weights:
        company_type = (parsed.get("company_type") or "").lower()
        if company_type:
            ct_score = company_type_weights.get(company_type, 0)
            score += max(-15, min(15, ct_score))

    # ── Red flags (-5 each, max -15) ────────────────────────────────────────
    # Filter out placeholder strings the LLM emits when there are no real red flags.
    _NULL_FLAG = {"none mentioned", "none", "n/a", "null", "none noted", "no red flags", "none identified"}
    real_flags = [f for f in (parsed.get("red_flags") or []) if f.strip().lower() not in _NULL_FLAG]
    score -= min(15, len(real_flags) * 5)

    return max(0, min(100, score))
