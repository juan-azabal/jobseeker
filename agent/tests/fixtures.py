"""
Shared test fixtures for scoring/rubric tests.

Uses a FIXED profile that does NOT load from config/profiles/juan.yaml so
that baseline regression tests remain stable regardless of personal profile
tuning. Update this fixture only when the scoring algorithm changes.

Design constraints (must satisfy all baseline assertions):
  strong_fit  → 66  = domain(data=15) + seniority(principal=15) + location(remote=10) + country_weights(remote=10) + skills(4×4=16)
  medium_fit  → 30  = domain(saas=10) + seniority(senior=8)    + location(hybrid,barcelona=8) + skills(1×4=4)
  low_fit     →  0  = domain(healthtech=0) + seniority(mid=0) + location(onsite,NYC=0) - red_flags(5) → clamped
  rubric core domains      → "data, adtech"
  rubric adjacent domains  → "Adjacent domains (saas, martech, ia, llm)"
  rubric target levels     → "principal/staff"
"""

BASELINE_PROFILE: dict = {
    "user": {
        "id": "juan",
        "name": "Juan Azabal",
        "home_locations": ["barcelona", "spain"],
    },
    "target": {
        "level": "principal",
        "track": "ic",
        "role_type": "Product Manager",
        "geography": "EU or remote",
        "seniority_weights": {
            "principal": 15,
            "staff": 12,
            "senior": 8,
        },
        "country_weights": {
            "spain": 10,
            "remote": 10,
        },
        # Insertion order determines the display order in the rubric.
        # core  (>= 12): data, adtech
        # adjacent (6–11): saas, martech, ia, llm  → "Adjacent domains (saas, martech, ia, llm)"
        "domains": {
            "data": 15,
            "adtech": 12,
            "saas": 10,
            "martech": 10,
            "ia": 10,
            "llm": 10,
        },
    },
    # Skills chosen so that:
    #   JOB_STRONG_FIT matches: snowplow, kafka, dbt, snowflake (4 matches → 16 pts)
    #   JOB_MEDIUM_FIT matches: analytics only               (1 match  →  4 pts)
    "skills": ["snowplow", "kafka", "dbt", "snowflake", "analytics"],
}
