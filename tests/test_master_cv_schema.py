"""Tests for shared/master_cv.py — schema validation and ID generators."""

from shared.master_cv import (
    MASTER_CV_SCHEMA_VERSION,
    generate_cert_id,
    generate_edu_id,
    generate_proj_id,
    generate_work_id,
    validate_master_cv,
)


def _valid_cv() -> dict:
    return {
        "version": "1.0",
        "updated_at": "2024-01-01T00:00:00Z",
        "sources": ["cv_upload"],
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
                "company": "Acme Corp",
                "position": "Product Manager",
                "location": "Madrid",
                "start_date": "2021-01",
                "end_date": None,
                "summary": "Led product development.",
                "highlights": ["Launched 3 features that increased retention by 20%"],
                "skills_used": ["Product strategy", "SQL"],
                "source": "cv_upload",
            }
        ],
        "education": [
            {
                "id": "edu_001",
                "institution": "Universidad Complutense",
                "area": "Computer Science",
                "study_type": "Bachelor",
                "start_date": "2015",
                "end_date": "2019",
                "source": "cv_upload",
            }
        ],
        "skills": [{"name": "Python", "level": "senior", "keywords": [], "source": "cv_upload"}],
        "languages": [{"language": "Spanish", "fluency": "native"}],
        "certifications": [],
        "projects": [],
    }


class TestValidateMasterCv:
    def test_valid_cv_returns_no_errors(self):
        errors = validate_master_cv(_valid_cv())
        assert errors == []

    def test_empty_dict_returns_errors(self):
        errors = validate_master_cv({})
        assert len(errors) > 0

    def test_missing_version_returns_error(self):
        cv = _valid_cv()
        del cv["version"]
        errors = validate_master_cv(cv)
        assert any("version" in e for e in errors)

    def test_work_missing_id_returns_error(self):
        cv = _valid_cv()
        del cv["work"][0]["id"]
        errors = validate_master_cv(cv)
        assert any("id" in e for e in errors)

    def test_work_missing_company_returns_error(self):
        cv = _valid_cv()
        del cv["work"][0]["company"]
        errors = validate_master_cv(cv)
        assert any("company" in e for e in errors)

    def test_work_missing_position_returns_error(self):
        cv = _valid_cv()
        del cv["work"][0]["position"]
        errors = validate_master_cv(cv)
        assert any("position" in e for e in errors)

    def test_work_highlights_not_list_returns_error(self):
        cv = _valid_cv()
        cv["work"][0]["highlights"] = "not a list"
        errors = validate_master_cv(cv)
        assert any("highlights" in e for e in errors)

    def test_education_missing_id_returns_error(self):
        cv = _valid_cv()
        del cv["education"][0]["id"]
        errors = validate_master_cv(cv)
        assert any("id" in e for e in errors)

    def test_education_missing_institution_returns_error(self):
        cv = _valid_cv()
        del cv["education"][0]["institution"]
        errors = validate_master_cv(cv)
        assert any("institution" in e for e in errors)

    def test_education_missing_area_returns_error(self):
        cv = _valid_cv()
        del cv["education"][0]["area"]
        errors = validate_master_cv(cv)
        assert any("area" in e for e in errors)

    def test_skill_missing_name_returns_error(self):
        cv = _valid_cv()
        del cv["skills"][0]["name"]
        errors = validate_master_cv(cv)
        assert any("name" in e for e in errors)

    def test_work_list_not_list_returns_error(self):
        cv = _valid_cv()
        cv["work"] = "not a list"
        errors = validate_master_cv(cv)
        assert any("work" in e for e in errors)


class TestSchemaVersion:
    def test_version_constant(self):
        assert MASTER_CV_SCHEMA_VERSION == "1.0"


class TestIdGenerators:
    def test_generate_work_id_zero(self):
        assert generate_work_id(0) == "work_000"

    def test_generate_work_id_one(self):
        assert generate_work_id(1) == "work_001"

    def test_generate_work_id_large(self):
        assert generate_work_id(42) == "work_042"

    def test_generate_edu_id(self):
        assert generate_edu_id(3) == "edu_003"

    def test_generate_cert_id(self):
        assert generate_cert_id(7) == "cert_007"

    def test_generate_proj_id(self):
        assert generate_proj_id(12) == "proj_012"
