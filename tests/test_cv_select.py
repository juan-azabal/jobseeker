"""Unit tests for api/cv/select.py — Phase 4.1."""

from unittest.mock import patch

from api.cv.select import select_cv_content

_MASTER_CV = {
    "version": "1.0",
    "basics": {"name": "Alice"},
    "work": [
        {
            "id": "work_001",
            "company": "HealthTech",
            "position": "Senior PM",
            "start_date": "2021-01",
            "end_date": None,
            "highlights": ["Reduced patient wait time by 30%", "Launched EHR integration"],
            "skills_used": ["product management", "healthcare", "SQL"],
            "source": "cv_upload",
        },
        {
            "id": "work_002",
            "company": "Fintech Startup",
            "position": "PM",
            "start_date": "2018-01",
            "end_date": "2020-12",
            "highlights": ["Grew user base 3x", "Shipped payment API"],
            "skills_used": ["payments", "SQL", "A/B testing"],
            "source": "cv_upload",
        },
        {
            "id": "work_003",
            "company": "Early Career Co",
            "position": "Analyst",
            "start_date": "2015-01",
            "end_date": "2017-12",
            "highlights": ["Built reports"],
            "skills_used": ["Excel"],
            "source": "cv_upload",
        },
    ],
    "skills": [{"name": "product management"}],
    "education": [],
    "languages": [],
    "certifications": [],
    "projects": [],
}

_JOB = {
    "must_have_skills": ["product management", "healthcare"],
    "nice_to_have_skills": ["SQL"],
    "domain": "healthtech",
    "description": "Lead health product roadmap in a cross-functional team.",
}


def _mock_query_work(user_id, query_text, n_results=4):
    """Return work_001 as closest, work_002 second."""
    return [
        {"id": "work_001", "document": "HealthTech Senior PM", "distance": 0.1},
        {"id": "work_002", "document": "Fintech Startup PM", "distance": 0.4},
    ]


def _mock_query_highlights(user_id, query_text, n_results=10):
    """Return one highlight per work entry."""
    return [
        {"id": "work_001_hl_0", "document": "Reduced patient wait time by 30%", "distance": 0.1},
        {"id": "work_002_hl_0", "document": "Grew user base 3x", "distance": 0.5},
    ]


class TestSelectCvContent:
    @patch("api.cv.select.query_similar_highlights", side_effect=_mock_query_highlights)
    @patch("api.cv.select.query_similar_work", side_effect=_mock_query_work)
    def test_returns_dict_with_work_entries(self, mock_work, mock_hl):
        result = select_cv_content(_MASTER_CV, _JOB, user_id=1)
        assert result is not None
        assert "work" in result
        assert len(result["work"]) >= 1

    @patch("api.cv.select.query_similar_highlights", side_effect=_mock_query_highlights)
    @patch("api.cv.select.query_similar_work", side_effect=_mock_query_work)
    def test_most_relevant_entry_first(self, mock_work, mock_hl):
        result = select_cv_content(_MASTER_CV, _JOB, user_id=1)
        work_ids = [e["id"] for e in result["work"]]
        # work_001 has lower distance → higher relevance → comes first
        assert work_ids[0] == "work_001"

    @patch("api.cv.select.query_similar_highlights", side_effect=_mock_query_highlights)
    @patch("api.cv.select.query_similar_work", side_effect=_mock_query_work)
    def test_each_entry_has_selected_highlights(self, mock_work, mock_hl):
        result = select_cv_content(_MASTER_CV, _JOB, user_id=1)
        for entry in result["work"]:
            assert "selected_highlights" in entry
            assert isinstance(entry["selected_highlights"], list)

    @patch("api.cv.select.query_similar_highlights", side_effect=_mock_query_highlights)
    @patch("api.cv.select.query_similar_work", side_effect=_mock_query_work)
    def test_relevance_score_present(self, mock_work, mock_hl):
        result = select_cv_content(_MASTER_CV, _JOB, user_id=1)
        for entry in result["work"]:
            assert "relevance_score" in entry
            assert isinstance(entry["relevance_score"], float)

    @patch("api.cv.select.query_similar_highlights", side_effect=_mock_query_highlights)
    @patch("api.cv.select.query_similar_work", side_effect=_mock_query_work)
    def test_skill_intersection_present(self, mock_work, mock_hl):
        result = select_cv_content(_MASTER_CV, _JOB, user_id=1)
        assert "skill_intersection" in result
        assert "product management" in result["skill_intersection"]

    def test_returns_none_for_empty_work(self):
        empty_cv = {**_MASTER_CV, "work": []}
        result = select_cv_content(empty_cv, _JOB, user_id=1)
        assert result is None

    @patch("api.cv.select.query_similar_highlights", return_value=[])
    @patch("api.cv.select.query_similar_work", return_value=[])
    def test_chroma_empty_falls_back_to_first_entries(self, mock_work, mock_hl):
        """When ChromaDB returns nothing, fall back to original work order."""
        result = select_cv_content(_MASTER_CV, _JOB, user_id=1)
        # Should still return entries (from master_cv.work directly)
        assert result is not None
        assert len(result["work"]) >= 1
