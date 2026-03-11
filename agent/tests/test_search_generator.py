"""Tests for search_generator.py — query generation from profile search_titles."""

import pytest

from search_generator import generate_queries, generate_unified_queries, COUNTRY_INDEED_MAP, LINKEDIN_DELAY_SECS


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


class TestGenerateUnifiedQueries:
    def _juan(self):
        return _profile(
            search_titles=["Senior Product Manager", "Product Manager"],
            home_locations=["barcelona", "spain"],
        )

    def _noura(self):
        return _profile(
            search_titles=["Senior Product Manager", "Product Manager", "Product Owner"],
            home_locations=["barcelona", "spain"],
        )

    def test_empty_profiles_list(self):
        result = generate_unified_queries([])
        assert result == []

    def test_single_profile_matches_generate_queries(self):
        profile = _profile(search_titles=["Product Manager"], home_locations=["barcelona", "spain"])
        unified = generate_unified_queries([(1, "juan", profile)])
        direct = generate_queries(profile)
        assert unified == direct

    def test_shared_title_same_location_deduped(self):
        juan = self._juan()
        noura = self._noura()
        result = generate_unified_queries([(1, "juan", juan), (2, "noura", noura)])
        # "Senior Product Manager" + barcelona appears once per site, not twice
        senior_indeed = [q for q in result if q["term"] == "Senior Product Manager" and q["site"] == "indeed"]
        assert len(senior_indeed) == 1
        senior_li = [q for q in result if q["term"] == "Senior Product Manager" and q["site"] == "linkedin"]
        assert len(senior_li) == 1

    def test_noura_unique_title_not_deduped(self):
        juan = self._juan()
        noura = self._noura()
        result = generate_unified_queries([(1, "juan", juan), (2, "noura", noura)])
        owner = [q for q in result if q["term"] == "Product Owner"]
        # Product Owner is only in noura's profile, should appear once per site
        assert len(owner) == 2
        sites = {q["site"] for q in owner}
        assert sites == {"indeed", "linkedin"}

    def test_different_cities_not_deduped(self):
        bcn = _profile(search_titles=["Product Manager"], home_locations=["barcelona", "spain"])
        madrid = _profile(search_titles=["Product Manager"], home_locations=["madrid", "spain"])
        result = generate_unified_queries([(1, "u1", bcn), (2, "u2", madrid)])
        indeed = [q for q in result if q["site"] == "indeed"]
        assert len(indeed) == 2

    def test_indeed_before_linkedin_ordering(self):
        juan = self._juan()
        noura = self._noura()
        result = generate_unified_queries([(1, "juan", juan), (2, "noura", noura)])
        indeed_indices = [i for i, q in enumerate(result) if q["site"] == "indeed"]
        linkedin_indices = [i for i, q in enumerate(result) if q["site"] == "linkedin"]
        assert indeed_indices and linkedin_indices
        assert max(indeed_indices) < min(linkedin_indices)

    def test_total_count_juan_plus_noura(self):
        """Juan has 2 titles, Noura adds 1 unique title (Product Owner).
        3 unique titles × 2 sites = 6 queries."""
        juan = self._juan()
        noura = self._noura()
        result = generate_unified_queries([(1, "juan", juan), (2, "noura", noura)])
        assert len(result) == 6


class TestGenerateQueriesEdgeCases:
    """Edge cases for generate_queries() per Phase 2.5."""

    def test_empty_string_title_skipped(self):
        """Empty string entries in search_titles produce no queries."""
        result = generate_queries(
            _profile(search_titles=["", "Product Manager"], home_locations=["barcelona", "spain"])
        )
        assert all(q["term"] != "" for q in result)
        assert len(result) == 2  # 1 real title × 2 sites

    def test_whitespace_only_title_skipped(self):
        result = generate_queries(
            _profile(search_titles=["   ", "Product Manager"], home_locations=["barcelona", "spain"])
        )
        assert all(q["term"].strip() for q in result)
        assert len(result) == 2

    def test_duplicate_titles_within_profile_deduped(self):
        """Identical titles within one profile produce only one pair of queries."""
        result = generate_queries(
            _profile(
                search_titles=["Product Manager", "Product Manager"],
                home_locations=["barcelona", "spain"],
            )
        )
        assert len(result) == 2  # 1 unique title × 2 sites

    def test_case_insensitive_dedup_within_profile(self):
        """'product manager' and 'Product Manager' are the same title."""
        result = generate_queries(
            _profile(
                search_titles=["Product Manager", "product manager"],
                home_locations=["barcelona", "spain"],
            )
        )
        assert len(result) == 2

    def test_only_empty_titles_returns_empty(self):
        result = generate_queries(_profile(search_titles=["", "  "], home_locations=["barcelona", "spain"]))
        assert result == []

    def test_title_stripped_in_output(self):
        """Leading/trailing whitespace stripped from title in query term."""
        result = generate_queries(
            _profile(search_titles=["  Product Manager  "], home_locations=["barcelona", "spain"])
        )
        indeed = next(q for q in result if q["site"] == "indeed")
        assert indeed["term"] == "Product Manager"
