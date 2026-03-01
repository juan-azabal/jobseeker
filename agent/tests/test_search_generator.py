"""Tests for search_generator.py — query generation from profile search_titles."""

import pytest

from search_generator import generate_queries, COUNTRY_INDEED_MAP, LINKEDIN_DELAY_SECS


def _profile(search_titles=None, home_locations=None):
    p = {}
    if search_titles is not None:
        p.setdefault("target", {})["search_titles"] = search_titles
    if home_locations is not None:
        p.setdefault("user", {})["home_locations"] = home_locations
    return p


class TestGenerateQueries:
    def test_five_titles_produce_ten_queries(self):
        titles = [
            "Senior Product Manager",
            "Principal Product Manager",
            "Staff Product Manager",
            "Product Owner",
            "Product Manager",
        ]
        result = generate_queries(_profile(search_titles=titles, home_locations=["barcelona", "spain"]))
        assert len(result) == 10

    def test_empty_search_titles_returns_empty(self):
        result = generate_queries(_profile(search_titles=[], home_locations=["barcelona", "spain"]))
        assert result == []

    def test_missing_search_titles_returns_empty(self):
        result = generate_queries({})
        assert result == []

    def test_missing_target_block_returns_empty(self):
        result = generate_queries({"user": {"home_locations": ["barcelona", "spain"]}})
        assert result == []

    def test_linkedin_params(self):
        result = generate_queries(_profile(search_titles=["Product Manager"], home_locations=["barcelona", "spain"]))
        linkedin = [q for q in result if q["site"] == "linkedin"]
        assert len(linkedin) == 1
        q = linkedin[0]
        assert q["results_wanted"] == 15
        assert q["is_remote"] is False
        assert q["linkedin_fetch_description"] is True

    def test_indeed_params(self):
        result = generate_queries(_profile(search_titles=["Product Manager"], home_locations=["barcelona", "spain"]))
        indeed = [q for q in result if q["site"] == "indeed"]
        assert len(indeed) == 1
        q = indeed[0]
        assert q["results_wanted"] == 25
        assert "is_remote" not in q
        assert q["country_indeed"] == "Spain"

    def test_indeed_comes_before_linkedin(self):
        result = generate_queries(_profile(search_titles=["Product Manager"], home_locations=["barcelona", "spain"]))
        sites = [q["site"] for q in result]
        assert sites.index("indeed") < sites.index("linkedin")

    def test_indeed_before_linkedin_with_multiple_titles(self):
        titles = ["Senior Product Manager", "Product Manager"]
        result = generate_queries(_profile(search_titles=titles, home_locations=["barcelona", "spain"]))
        # All indeed queries should come before all linkedin queries
        sites = [q["site"] for q in result]
        indeed_indices = [i for i, s in enumerate(sites) if s == "indeed"]
        linkedin_indices = [i for i, s in enumerate(sites) if s == "linkedin"]
        assert max(indeed_indices) < min(linkedin_indices)

    def test_paris_france_country_indeed(self):
        result = generate_queries(_profile(search_titles=["Product Manager"], home_locations=["paris", "france"]))
        indeed = [q for q in result if q["site"] == "indeed"][0]
        assert indeed["country_indeed"] == "France"
        assert indeed["location"] == "paris"

    def test_berlin_no_country_fallback(self):
        result = generate_queries(_profile(search_titles=["Product Manager"], home_locations=["berlin"]))
        indeed = [q for q in result if q["site"] == "indeed"][0]
        assert indeed["country_indeed"] == "Spain"
        assert indeed["location"] == "berlin"

    def test_no_home_locations_empty_city(self):
        result = generate_queries(_profile(search_titles=["Product Manager"]))
        indeed = [q for q in result if q["site"] == "indeed"][0]
        assert indeed["location"] == ""
        assert indeed["country_indeed"] == "Spain"

    def test_hours_old_set(self):
        result = generate_queries(_profile(search_titles=["Product Manager"], home_locations=["barcelona", "spain"]))
        for q in result:
            assert q["hours_old"] == 72

    def test_description_format_markdown(self):
        result = generate_queries(_profile(search_titles=["Product Manager"], home_locations=["barcelona", "spain"]))
        for q in result:
            assert q["description_format"] == "markdown"

    def test_term_matches_title(self):
        result = generate_queries(_profile(search_titles=["Senior PM"], home_locations=["barcelona", "spain"]))
        terms = {q["term"] for q in result}
        assert terms == {"Senior PM"}

    def test_country_indeed_map_has_expected_entries(self):
        assert COUNTRY_INDEED_MAP["spain"] == "Spain"
        assert COUNTRY_INDEED_MAP["france"] == "France"
        assert COUNTRY_INDEED_MAP["germany"] == "Germany"
        assert COUNTRY_INDEED_MAP["uk"] == "UK"
        assert COUNTRY_INDEED_MAP["usa"] == "USA"

    def test_linkedin_delay_constant_exists(self):
        assert isinstance(LINKEDIN_DELAY_SECS, int)
        assert LINKEDIN_DELAY_SECS > 0

    def test_espana_maps_to_spain(self):
        result = generate_queries(_profile(search_titles=["PM"], home_locations=["madrid", "españa"]))
        indeed = [q for q in result if q["site"] == "indeed"][0]
        assert indeed["country_indeed"] == "Spain"
