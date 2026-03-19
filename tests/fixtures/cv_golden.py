"""Golden scenario fixtures for CV pipeline regression tests.

Each scenario is a plain constant (dict or string). No I/O, no randomness.
Tests import these to verify build_cv_plan, build_cv_prompts, and
validate_cv produce deterministic, expected output.
"""

import json

# ═══════════════════════════════════════════════════════════════════════════
# Scenario A — Senior Data PM at consultancy, fully enriched
# ═══════════════════════════════════════════════════════════════════════════

SCENARIO_A_JOB = {
    "title": "Senior Product Manager — Data Platform",
    "company": "DataConsult GmbH",
    "location": "Berlin, DE",
    "parsed": json.dumps(
        {
            "domain": "data",
            "seniority": "senior",
            "must_have_skills": ["SQL", "Python", "dbt"],
            "truly_required": ["SQL", "Python", "dbt", "Tableau"],
            "technical_stack": ["Snowflake", "Kafka", "Airflow"],
            "location_type": "hybrid",
            "locations_mentioned": ["Berlin, Germany"],
            "description": (
                "DataConsult is a consulting firm specialising in data platforms. "
                "We help enterprise clients modernise their data infrastructure. "
                "You will lead a cross-functional team of 6 engineers and analysts. "
                "Must have 10+ years of product management experience."
            ),
            "role_in_plain_english": "Lead data platform product strategy for enterprise consulting clients",
            "company_context": {
                "stage": "growth",
                "tone": "collaborative",
                "what_they_value": "client impact, technical depth",
            },
            "verbatim_for_cv": ["data infrastructure", "cross-functional", "enterprise clients"],
        }
    ),
    "scored": json.dumps(
        {
            "score": 78,
            "score_breakdown": {
                "domain_fit": 20,
                "seniority_fit": 15,
                "location_fit": 8,
                "skills_fit": 25,
                "red_flags": 0,
            },
            "strengths": ["Strong data domain background", "10+ years PM experience"],
            "gaps": ["No direct consulting experience mentioned"],
        }
    ),
}

SCENARIO_A_CV = """\
# Test User
Senior Product Manager | Data & Analytics
Barcelona, Spain | test@test.com | linkedin.com/in/test

## Summary
Senior Product Manager with 10+ years building data platforms at scale.
Experienced working in consulting environments, embedded with client teams.

## Core Skills
**Data Platforms & Tracking**
First-party tracking, event taxonomies, Snowplow, Kafka, dbt.

**Product Strategy**
Roadmapping, stakeholder management, OKR frameworks.

**AI and ML**
Recommendation systems, NLP, model monitoring.

## Languages
Spanish (native) | English (advanced) | German (basic)

## Work Experience

### Acme Analytics, Barcelona
Senior Product Manager | 2020–Present
- Built real-time data platform serving 2M daily active users
- Led migration from legacy warehouse to Snowflake, reducing query cost 60%
- Defined product strategy for analytics suite used by 50+ enterprise clients

### Beta Data Corp, Madrid
Product Manager | 2016–2020
- Managed team of 4 building internal BI tools
- Launched self-service analytics dashboard adopted by 200+ internal users
- Integrated machine learning pipeline for churn prediction

### Gamma Consulting, London
Associate Consultant | 2014–2016
- Delivered data strategy projects for 3 FTSE 100 clients
- Built ETL pipelines in Python and SQL for client reporting
"""

SCENARIO_A_PROFILE = {
    "domains": {"data": 15, "fintech": 10},
    "role_type": "Senior Product Manager",
    "role_function": "product",
    "skills": ["SQL", "Python", "dbt", "Snowflake", "Kafka"],
    "seniority_weights": {"senior": 15, "lead": 10, "mid": -5},
}


# ═══════════════════════════════════════════════════════════════════════════
# Scenario B — SaaS PM with sparse parsed data (no scored, no v1.5 fields)
# ═══════════════════════════════════════════════════════════════════════════

SCENARIO_B_JOB = {
    "title": "Product Manager",
    "company": "SaaSify Inc",
    "location": "Remote",
    "parsed": json.dumps(
        {
            "domain": "saas",
            "seniority": "mid",
            "must_have_skills": ["Jira", "SQL"],
            "location_type": "remote",
            "locations_mentioned": [],
            "description": "SaaSify builds workflow automation tools. Looking for a PM to own the integrations roadmap.",
        }
    ),
    "scored": None,
}

SCENARIO_B_CV = """\
# Test User
Product Manager
Barcelona, Spain | test@test.com

## Summary
Product Manager with 5+ years in SaaS.

## Core Skills
**Product Management**
Roadmapping, user research, A/B testing.

## Languages
Spanish (native) | English (advanced)

## Work Experience

### AlphaSaaS, Barcelona
Product Manager | 2019–Present
- Owned integrations roadmap for 15+ third-party connectors
- Ran 20+ A/B tests improving activation by 12%

### BetaStartup, Madrid
Junior PM | 2017–2019
- Launched MVP in 3 months with team of 3
"""

SCENARIO_B_PROFILE = {
    "domains": {"saas": 15},
    "role_type": "Product Manager",
    "skills": ["SQL", "Jira"],
}


# ═══════════════════════════════════════════════════════════════════════════
# Scenario C — Engineering role (tests role_function mismatch)
# ═══════════════════════════════════════════════════════════════════════════

SCENARIO_C_JOB = {
    "title": "Senior Software Engineer — Backend",
    "company": "TechCorp",
    "location": "Amsterdam, NL",
    "parsed": json.dumps(
        {
            "domain": "saas",
            "seniority": "senior",
            "must_have_skills": ["Go", "Kubernetes", "PostgreSQL"],
            "truly_required": ["Go", "Kubernetes", "PostgreSQL", "gRPC"],
            "technical_stack": ["Go", "Kubernetes", "Terraform"],
            "location_type": "hybrid",
            "locations_mentioned": ["Amsterdam, Netherlands"],
            "role_function": "engineering",
            "description": "TechCorp is hiring a senior backend engineer to build microservices infrastructure.",
        }
    ),
    "scored": json.dumps(
        {
            "score": 45,
            "score_breakdown": {
                "domain_fit": 15,
                "seniority_fit": 15,
                "location_fit": 8,
                "skills_fit": 5,
                "red_flags": -5,
            },
            "strengths": ["Senior level match"],
            "gaps": ["No backend engineering experience", "Missing Go/Kubernetes skills"],
        }
    ),
}
