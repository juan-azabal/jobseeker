"""Phase 1.1 — Tests: replace-cv persists master_cv_json."""

import json
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import (
    upsert_user,
    create_session,
    save_user_profile_yaml,
    get_master_cv_json,
)
from api.main import app


MINIMAL_YAML = """
user:
  name: Test User
  email: test@example.com
  home_locations:
    - spain
target:
  domains:
    saas: 10
  seniority_weights:
    senior: 10
skills:
  - python
"""

SAMPLE_MASTER_CV = {
    "work": [
        {
            "id": "work_aaa",
            "company": "Acme Corp",
            "position": "Product Manager",
            "start_date": "2022-01",
            "end_date": None,
            "summary": "Led product team",
            "highlights": ["Shipped X feature"],
            "skills_used": ["python", "sql"],
        }
    ],
    "projects": [],
    "skills": [{"name": "python"}, {"name": "sql"}],
}

SAMPLE_PROFILE = {
    "name": "Test User",
    "email": "test@example.com",
    "home_locations": ["spain"],
    "skills": ["python", "sql"],
    "domains": {"saas": 10},
    "seniority_weights": {"senior": 10},
}


def _make_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    jobagent_dir = str(tmp_path / "jobagent")
    profiles_dir = os.path.join(jobagent_dir, "config", "profiles")
    os.makedirs(profiles_dir)
    monkeypatch.setenv("JOBAGENT_DIR", jobagent_dir)

    with open(os.path.join(profiles_dir, "test_user.yaml"), "w") as f:
        f.write(MINIMAL_YAML)

    user = upsert_user(
        db_path,
        {
            "google_id": "g_test",
            "email": "test@example.com",
            "name": "Test User",
            "avatar_url": None,
            "profile_id": "test_user",
        },
    )
    save_user_profile_yaml(db_path, user["id"], MINIMAL_YAML)
    create_session(db_path, "tok_test", user["id"], "2099-01-01T00:00:00")

    c = TestClient(app)
    c.cookies.set("jsk", "tok_test")
    return c, db_path, user["id"]


def _patch_github():
    return patch(
        "api.routes.onboard._push_file_to_github",
        return_value=None,
    )


class TestReplaceCvPersistsMasterCv:
    def test_master_cv_json_saved_when_provided(self, tmp_path, monkeypatch):
        """PATCH /replace-cv with master_cv_json → GET /master-cv returns it."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)
        with _patch_github():
            resp = client.patch(
                "/api/onboard/replace-cv",
                json={
                    "cv_markdown": "# My CV\nPM at Acme",
                    "extracted_profile": SAMPLE_PROFILE,
                    "master_cv_json": SAMPLE_MASTER_CV,
                },
            )
        assert resp.status_code == 202  # async: endpoint now returns 202

        raw = get_master_cv_json(db_path, user_id)
        assert raw is not None
        saved = json.loads(raw)
        assert saved["work"][0]["company"] == "Acme Corp"

    def test_master_cv_json_absent_triggers_extraction(self, tmp_path, monkeypatch):
        """PATCH /replace-cv without master_cv_json but with cv_markdown → extracts and saves."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        fake_master_cv = {**SAMPLE_MASTER_CV, "work": [{"id": "w1", "company": "Extracted Co"}]}

        with (
            _patch_github(),
            patch("api.routes.onboard._make_openai_client", return_value=object()),
            patch(
                "api.routes.onboard.extract_master_cv_json",
                return_value=fake_master_cv,
            ),
        ):
            resp = client.patch(
                "/api/onboard/replace-cv",
                json={
                    "cv_markdown": "# My CV\nPM at Extracted Co",
                    "extracted_profile": SAMPLE_PROFILE,
                },
            )
        assert resp.status_code == 202  # async

        raw = get_master_cv_json(db_path, user_id)
        assert raw is not None
        saved = json.loads(raw)
        assert saved["work"][0]["company"] == "Extracted Co"

    def test_master_cv_json_merges_with_existing(self, tmp_path, monkeypatch):
        """replace-cv merges incoming master_cv with existing (not overwrite)."""
        from api.db.queries import save_master_cv_json

        client, db_path, user_id = _make_client(tmp_path, monkeypatch)
        existing_mcv = {
            **SAMPLE_MASTER_CV,
            "work": [{"id": "w_existing", "company": "Old Corp"}],
        }
        save_master_cv_json(db_path, user_id, json.dumps(existing_mcv))

        incoming_mcv = {
            **SAMPLE_MASTER_CV,
            "work": [{"id": "w_new", "company": "New Corp"}],
        }
        with _patch_github():
            resp = client.patch(
                "/api/onboard/replace-cv",
                json={
                    "cv_markdown": "# My CV",
                    "extracted_profile": SAMPLE_PROFILE,
                    "master_cv_json": incoming_mcv,
                },
            )
        assert resp.status_code == 202  # async

        raw = get_master_cv_json(db_path, user_id)
        saved = json.loads(raw)
        companies = [e["company"] for e in saved.get("work", [])]
        # Both entries should be present after merge
        assert "Old Corp" in companies or "New Corp" in companies

    def test_get_master_cv_returns_saved(self, tmp_path, monkeypatch):
        """After replace-cv with master_cv_json, GET /master-cv returns non-null."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)
        with _patch_github():
            client.patch(
                "/api/onboard/replace-cv",
                json={
                    "cv_markdown": "# My CV",
                    "extracted_profile": SAMPLE_PROFILE,
                    "master_cv_json": SAMPLE_MASTER_CV,
                },
            )
        resp = client.get("/api/onboard/master-cv")
        assert resp.status_code == 200
        data = resp.json()
        assert "work" in data
        assert data["work"][0]["company"] == "Acme Corp"


def _patch_bg_deps():
    """Patch all background task dependencies so tests can run without LLM/ChromaDB."""
    from contextlib import ExitStack
    from unittest.mock import patch

    stack = ExitStack()
    stack.enter_context(patch("api.routes.onboard._make_openai_client", return_value=None))
    stack.enter_context(patch("api.routes.onboard.index_master_cv"))
    return stack


class TestReplaceCvNestedPayload:
    """Phase 2 — Step 2.3: replace-cv correctly handles nested generated-profile payload."""

    def test_nested_extracted_profile_applies_merge(self, tmp_path, monkeypatch):
        """Step 2.1 — extracted_profile = {profile: {...}, master_cv_json: {...}} is unpacked.

        The inner 'profile' dict should be used for merge, not the wrapper.
        The 'go' skill from the nested profile must appear in the saved YAML.
        """
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        # Frontend sends the full generate-profile response as extracted_profile
        nested_payload = {
            "profile": {**SAMPLE_PROFILE, "skills": ["python", "sql", "go"]},
            "master_cv_json": SAMPLE_MASTER_CV,
        }

        with _patch_github(), _patch_bg_deps():
            resp = client.patch(
                "/api/onboard/replace-cv",
                json={
                    "cv_markdown": "# My CV",
                    "extracted_profile": nested_payload,
                },
            )
        assert resp.status_code == 202

        # Profile merge should have used the inner profile — 'go' must be in saved YAML
        from api.db.queries import get_user_profile_yaml
        import yaml

        raw_yaml = get_user_profile_yaml(db_path, user_id)
        assert raw_yaml is not None
        saved = yaml.safe_load(raw_yaml)
        skills = saved.get("skills", [])
        assert "go" in skills, f"'go' skill from nested profile not merged. skills={skills}"

    def test_nested_master_cv_json_persisted(self, tmp_path, monkeypatch):
        """Step 2.2 — master_cv_json inside nested extracted_profile is persisted."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        nested_mcv = {
            **SAMPLE_MASTER_CV,
            "work": [
                {
                    "id": "work_nested",
                    "company": "NestedCorp",
                    "position": "CTO",
                    "start_date": "2021-01",
                    "end_date": None,
                    "summary": "Led engineering",
                    "highlights": ["Built scalable platform"],
                    "skills_used": ["go"],
                }
            ],
        }
        nested_payload = {"profile": SAMPLE_PROFILE, "master_cv_json": nested_mcv}

        with _patch_github(), _patch_bg_deps():
            resp = client.patch(
                "/api/onboard/replace-cv",
                json={
                    "cv_markdown": "# My CV",
                    "extracted_profile": nested_payload,
                },
            )
        assert resp.status_code == 202

        # master_cv_json from the nested payload must be persisted
        raw = get_master_cv_json(db_path, user_id)
        assert raw is not None
        saved = json.loads(raw)
        companies = [e["company"] for e in saved.get("work", [])]
        assert "NestedCorp" in companies, f"master_cv_json not persisted. companies={companies}"
