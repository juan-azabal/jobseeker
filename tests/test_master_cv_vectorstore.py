"""Tests for api/master_cv_vectorstore.py — ChromaDB collection management."""

import tempfile

import pytest

from api.master_cv_vectorstore import get_collection, index_master_cv, query_similar_highlights, query_similar_work


@pytest.fixture()
def chroma_dir(tmp_path, monkeypatch):
    """Override CHROMA_DIR to an isolated temp directory."""
    import api.master_cv_vectorstore as vs

    monkeypatch.setattr(vs, "CHROMA_DIR", str(tmp_path / "chroma"))
    return str(tmp_path / "chroma")


def _sample_master_cv() -> dict:
    return {
        "version": "1.0",
        "work": [
            {
                "id": "work_001",
                "company": "Spotify",
                "position": "Senior PM",
                "summary": "Led music recommendation features.",
                "highlights": [
                    "Increased stream-start rate by 15%",
                    "Launched personalised playlist feature to 50M users",
                ],
                "skills_used": ["Product strategy", "A/B testing"],
                "source": "cv_upload",
            },
            {
                "id": "work_002",
                "company": "Fintech Startup",
                "position": "Product Manager",
                "summary": "Payments product.",
                "highlights": ["Reduced payment failure rate by 30%"],
                "skills_used": ["Payments", "SQL"],
                "source": "cv_upload",
            },
        ],
        "skills": [{"name": "Python", "level": "senior", "keywords": ["data analysis"], "source": "cv_upload"}],
        "education": [],
        "languages": [],
        "certifications": [],
        "projects": [],
    }


class TestGetCollection:
    def test_returns_collection(self, chroma_dir):
        col = get_collection(user_id=1)
        assert col is not None
        assert col.name == "master_cv_1"

    def test_same_collection_on_second_call(self, chroma_dir):
        col1 = get_collection(user_id=1)
        col2 = get_collection(user_id=1)
        assert col1.name == col2.name

    def test_different_users_different_collections(self, chroma_dir):
        col1 = get_collection(user_id=1)
        col2 = get_collection(user_id=2)
        assert col1.name != col2.name


class TestIndexMasterCv:
    def test_index_adds_work_entries(self, chroma_dir):
        cv = _sample_master_cv()
        index_master_cv(user_id=1, master_cv=cv)
        col = get_collection(user_id=1)
        results = col.get(where={"type": {"$eq": "work"}})
        assert len(results["ids"]) == 2
        assert "work_001" in results["ids"]
        assert "work_002" in results["ids"]

    def test_index_adds_highlights(self, chroma_dir):
        cv = _sample_master_cv()
        index_master_cv(user_id=1, master_cv=cv)
        col = get_collection(user_id=1)
        results = col.get(where={"type": {"$eq": "highlight"}})
        # 2 highlights in work_001 + 1 in work_002 = 3
        assert len(results["ids"]) == 3

    def test_index_adds_skills(self, chroma_dir):
        cv = _sample_master_cv()
        index_master_cv(user_id=1, master_cv=cv)
        col = get_collection(user_id=1)
        results = col.get(where={"type": {"$eq": "skill"}})
        assert len(results["ids"]) == 1
        assert "skill_000" in results["ids"]

    def test_reindex_clears_old_entries(self, chroma_dir):
        cv = _sample_master_cv()
        index_master_cv(user_id=1, master_cv=cv)
        # Remove one work entry and reindex
        cv2 = dict(cv)
        cv2["work"] = [cv["work"][0]]
        index_master_cv(user_id=1, master_cv=cv2)
        col = get_collection(user_id=1)
        results = col.get(where={"type": {"$eq": "work"}})
        assert len(results["ids"]) == 1


class TestQuerySimilarWork:
    def test_returns_relevant_work_entry(self, chroma_dir):
        cv = _sample_master_cv()
        index_master_cv(user_id=1, master_cv=cv)
        results = query_similar_work(user_id=1, query_text="music streaming product", n_results=1)
        assert len(results) >= 1
        assert results[0]["id"] == "work_001"

    def test_does_not_return_highlights_or_skills(self, chroma_dir):
        cv = _sample_master_cv()
        index_master_cv(user_id=1, master_cv=cv)
        results = query_similar_work(user_id=1, query_text="product", n_results=4)
        for r in results:
            assert r["id"].startswith("work_")
            assert "_hl_" not in r["id"]


class TestQuerySimilarHighlights:
    def test_returns_highlights(self, chroma_dir):
        cv = _sample_master_cv()
        index_master_cv(user_id=1, master_cv=cv)
        results = query_similar_highlights(user_id=1, query_text="reduced failure rate", n_results=3)
        assert len(results) >= 1
        for r in results:
            assert "_hl_" in r["id"]
