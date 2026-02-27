"""
Synthetic RawJob fixtures for geo filtering regression baseline (15.2).

Covers the real distribution observed in production data:
- US jobs with location
- US jobs without location but with description signals
- EU onsite in Spain (target)
- EU onsite outside Spain (non-target)
- EU hybrid outside Spain
- Remote fulltime from US
- Remote fulltime global
- WTTJ partial-remote from France
- ATS with no location
- Indian city job
"""

from models import RawJob

GEO_TEST_JOBS: list[RawJob] = [
    # 1. US job with clear location — should be rejected by Layer 1
    RawJob(
        id="us-sf-loc",
        title="Senior Product Manager",
        company="US Corp",
        source="linkedin",
        location="San Francisco, CA",
        remote_type="no",
    ),
    # 2. US job with no location but US visa signals in description
    RawJob(
        id="us-desc-signal",
        title="Product Manager",
        company="US Corp 2",
        source="linkedin",
        location=None,
        remote_type="no",
        description="You must be authorized to work in the U.S. Salary up to $180k.",
    ),
    # 3. EU onsite in Spain (target country) — should pass
    RawJob(
        id="es-onsite",
        title="Product Manager",
        company="Barcelona Startup",
        source="wttj",
        location="Barcelona",
        remote_type="no",
        country="ES",
    ),
    # 4. EU onsite outside Spain (France) — should be rejected
    RawJob(
        id="fr-onsite",
        title="Product Manager",
        company="Paris Corp",
        source="wttj",
        location="Paris, France",
        remote_type="no",
        country="FR",
    ),
    # 5. EU hybrid outside Spain (France) — partial remote non-target
    RawJob(
        id="fr-hybrid",
        title="Product Manager",
        company="Lyon Tech",
        source="wttj",
        location="Lyon, France",
        remote_type="partial",
        country="FR",
    ),
    # 6. Remote fulltime from US — should pass (location-agnostic)
    RawJob(
        id="us-remote-ft",
        title="Remote Product Manager",
        company="Remote US Co",
        source="linkedin",
        location="United States",
        remote_type="fulltime",
    ),
    # 7. Remote fulltime global — should pass
    RawJob(
        id="global-remote",
        title="Product Manager",
        company="Fully Remote Inc",
        source="linkedin",
        location="Remote",
        remote_type="fulltime",
    ),
    # 8. WTTJ partial-remote from France — requires Paris presence
    RawJob(
        id="wttj-fr-partial",
        title="Head of Product",
        company="French Scale-up",
        source="wttj",
        location="Paris",
        remote_type="partial",
        country="FR",
    ),
    # 9. ATS with no location — should pass (conservative)
    RawJob(
        id="ats-no-loc",
        title="Senior Product Manager",
        company="Watchlist Corp",
        source="greenhouse",
        location=None,
        remote_type="no",
        description="We are building great things. Join our team. Competitive salary.",
    ),
    # 10. Spanish onsite with full location string — should pass
    RawJob(
        id="es-madrid-onsite",
        title="Product Manager",
        company="Madrid Corp",
        source="indeed",
        location="Madrid, Spain",
        remote_type="no",
    ),
    # 11. German onsite — should be rejected for ES user
    RawJob(
        id="de-onsite",
        title="Senior Product Manager",
        company="Berlin Co",
        source="linkedin",
        location="Berlin, Germany",
        remote_type="no",
    ),
    # 12. Job with null location, description mentions Berlin office
    RawJob(
        id="de-desc-mention",
        title="Product Manager",
        company="Berlin Remote",
        source="linkedin",
        location=None,
        remote_type="no",
        description="We are based in our Berlin office. Our team is growing rapidly.",
    ),
    # 13. Job with null location, no geo signals — should pass (conservative)
    RawJob(
        id="no-loc-no-signals",
        title="Product Manager",
        company="Mystery Corp",
        source="linkedin",
        location=None,
        remote_type="no",
        description="We are looking for a talented product manager to join our team.",
    ),
    # 14. Mumbai India job — should pass for IN target, fail for ES target
    RawJob(
        id="in-mumbai",
        title="Product Manager",
        company="India Tech",
        source="linkedin",
        location="Mumbai, India",
        remote_type="no",
    ),
    # 15. New York with US state abbreviation
    RawJob(
        id="us-ny-job",
        title="VP Product",
        company="NYC Fintech",
        source="linkedin",
        location="New York, NY",
        remote_type="no",
    ),
]
