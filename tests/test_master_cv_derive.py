"""Tests for shared/master_cv_derive.py — deterministic profile derivation."""


def _master_cv_pm_music() -> dict:
    """A PM career in music/fintech."""
    return {
        "version": "1.0",
        "basics": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": None,
            "location": {"city": "Madrid", "country": "ES"},
            "url": None,
            "profiles": [],
        },
        "work": [
            {
                "id": "work_001",
                "company": "Spotify",
                "position": "Senior Product Manager",
                "location": None,
                "start_date": "2021-01",
                "end_date": None,
                "summary": "Led music streaming platform features.",
                "highlights": ["Launched feature to 10M users"],
                "skills_used": ["Product strategy", "SQL", "A/B testing"],
                "source": "cv_upload",
            },
            {
                "id": "work_002",
                "company": "Revolut",
                "position": "Product Manager",
                "location": None,
                "start_date": "2018-06",
                "end_date": "2020-12",
                "summary": "Payments product.",
                "highlights": ["Reduced failure rate by 30%"],
                "skills_used": ["Payments", "Figma"],
                "source": "cv_upload",
            },
            {
                "id": "work_003",
                "company": "Tech Startup",
                "position": "Junior Product Manager",
                "location": None,
                "start_date": "2016-01",
                "end_date": "2018-05",
                "summary": "Early career PM.",
                "highlights": ["Shipped 3 features"],
                "skills_used": ["User research"],
                "source": "cv_upload",
            },
        ],
        "education": [
            {
                "id": "edu_001",
                "institution": "MIT",
                "area": "Computer Science",
                "study_type": "Bachelor",
                "start_date": "2012",
                "end_date": "2016",
                "source": "cv_upload",
            }
        ],
        "skills": [
            {"name": "Analytics", "level": "senior", "keywords": ["Mixpanel", "Amplitude"], "source": "cv_upload"},
            {"name": "SQL", "level": "mid", "keywords": [], "source": "cv_upload"},
        ],
        "languages": [
            {"language": "English", "fluency": "native"},
            {"language": "Spanish", "fluency": "professional"},
        ],
        "certifications": [],
        "projects": [],
    }


class TestDeriveProfileFromMasterCv:
    def test_skills_union_from_work_and_skills(self):
        from shared.master_cv_derive import derive_profile_from_master_cv

        profile = derive_profile_from_master_cv(_master_cv_pm_music())
        skills = [s.lower() for s in profile["skills"]]
        assert "sql" in skills
        assert "product strategy" in skills
        assert "a/b testing" in skills
        assert "payments" in skills
        assert "mixpanel" in skills

    def test_skills_deduplicated(self):
        from shared.master_cv_derive import derive_profile_from_master_cv

        profile = derive_profile_from_master_cv(_master_cv_pm_music())
        lower_skills = [s.lower() for s in profile["skills"]]
        assert lower_skills.count("sql") == 1

    def test_languages_extracted(self):
        from shared.master_cv_derive import derive_profile_from_master_cv

        profile = derive_profile_from_master_cv(_master_cv_pm_music())
        # Languages returned as name strings (not fluency dicts)
        assert "English" in profile["languages"]
        assert "Spanish" in profile["languages"]

    def test_home_location_from_basics(self):
        from shared.master_cv_derive import derive_profile_from_master_cv

        profile = derive_profile_from_master_cv(_master_cv_pm_music())
        assert "Madrid" in profile["home_locations"] or "ES" in profile["home_locations"]

    def test_name_and_email_extracted(self):
        from shared.master_cv_derive import derive_profile_from_master_cv

        profile = derive_profile_from_master_cv(_master_cv_pm_music())
        assert profile["name"] == "Jane Doe"
        assert profile["email"] == "jane@example.com"

    def test_current_level_from_most_recent_senior_role(self):
        from shared.master_cv_derive import derive_profile_from_master_cv

        profile = derive_profile_from_master_cv(_master_cv_pm_music())
        assert profile["current_level"] == "senior"

    def test_role_type_from_most_recent_position(self):
        from shared.master_cv_derive import derive_profile_from_master_cv

        profile = derive_profile_from_master_cv(_master_cv_pm_music())
        assert "product manager" in profile["role_type"].lower()

    def test_track_ic_for_non_management_roles(self):
        from shared.master_cv_derive import derive_profile_from_master_cv

        profile = derive_profile_from_master_cv(_master_cv_pm_music())
        assert profile["track"] == "ic"

    def test_track_management_for_head_of(self):
        from shared.master_cv_derive import derive_profile_from_master_cv

        cv = _master_cv_pm_music()
        cv["work"][0]["position"] = "Head of Product"
        profile = derive_profile_from_master_cv(cv)
        assert profile["track"] == "management"

    def test_role_function_product(self):
        from shared.master_cv_derive import derive_profile_from_master_cv

        profile = derive_profile_from_master_cv(_master_cv_pm_music())
        assert profile["role_function"] == "product"

    def test_domains_dict_not_empty(self):
        from shared.master_cv_derive import derive_profile_from_master_cv

        profile = derive_profile_from_master_cv(_master_cv_pm_music())
        assert isinstance(profile["domains"], dict)
        assert len(profile["domains"]) > 0


class TestEnrichSkillsFromWork:
    def test_missing_skill_added_with_source_inferred(self):
        from shared.master_cv_derive import enrich_skills_from_work

        cv = {
            "work": [{"skills_used": ["Figma", "SQL"]}],
            "skills": [{"name": "SQL", "level": None, "keywords": [], "source": "cv_upload"}],
        }
        result = enrich_skills_from_work(cv)
        skill_names = [s["name"].lower() for s in result["skills"]]
        assert "figma" in skill_names
        inferred = [s for s in result["skills"] if s["name"].lower() == "figma"]
        assert inferred[0]["source"] == "inferred"

    def test_existing_skill_not_duplicated(self):
        from shared.master_cv_derive import enrich_skills_from_work

        cv = {
            "work": [{"skills_used": ["SQL"]}],
            "skills": [{"name": "SQL", "level": None, "keywords": [], "source": "cv_upload"}],
        }
        result = enrich_skills_from_work(cv)
        sql_entries = [s for s in result["skills"] if s["name"].lower() == "sql"]
        assert len(sql_entries) == 1

    def test_case_insensitive_dedup(self):
        from shared.master_cv_derive import enrich_skills_from_work

        cv = {
            "work": [{"skills_used": ["sql"]}],
            "skills": [{"name": "SQL", "level": None, "keywords": [], "source": "cv_upload"}],
        }
        result = enrich_skills_from_work(cv)
        sql_entries = [s for s in result["skills"] if s["name"].lower() == "sql"]
        assert len(sql_entries) == 1

    def test_does_not_mutate_input(self):
        from shared.master_cv_derive import enrich_skills_from_work

        cv = {
            "work": [{"skills_used": ["Figma"]}],
            "skills": [],
        }
        original_skills = list(cv["skills"])
        enrich_skills_from_work(cv)
        assert cv["skills"] == original_skills


class TestMinimalMasterCv:
    def test_empty_work_returns_default_profile(self):
        from shared.master_cv_derive import derive_profile_from_master_cv

        cv = {
            "version": "1.0",
            "basics": {
                "name": None,
                "email": None,
                "location": {"city": "", "country": ""},
                "profiles": [],
            },
            "work": [],
            "skills": [],
            "languages": [],
            "education": [],
            "certifications": [],
            "projects": [],
        }
        profile = derive_profile_from_master_cv(cv)
        assert isinstance(profile, dict)
        assert "skills" in profile
        assert "domains" in profile
