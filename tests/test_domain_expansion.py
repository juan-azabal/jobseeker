"""
Tests for Phase 13.2: Expanded domain enum (~20 values) and new aliases.

Verifies:
(a) _infer_domain() correctly classifies text containing new domain keywords.
(b) _DOMAIN_ALIASES maps new aliases to canonical values.
"""

from api.scoring import _infer_domain, _DOMAIN_ALIASES, _DOMAIN_KEYWORDS


class TestInferDomainNewValues:
    """_infer_domain() returns new enum values when matching keywords are found."""

    def _parsed(self, text: str, domain: str = "other") -> dict:
        return {
            "domain": domain,
            "responsibilities_summary": text,
            "must_have_skills": [],
            "technical_stack": [],
        }

    def test_video_game_infers_game(self):
        parsed = self._parsed("video game development for mobile platforms")
        assert _infer_domain(parsed) == "game"

    def test_gaming_infers_game(self):
        parsed = self._parsed("gaming studio building multiplayer experience")
        assert _infer_domain(parsed) == "game"

    def test_edtech_platform_infers_edtech(self):
        parsed = self._parsed("build learning platform for online courses")
        assert _infer_domain(parsed) == "edtech"

    def test_carbon_offset_infers_climate(self):
        parsed = self._parsed("carbon offset marketplace for sustainability")
        assert _infer_domain(parsed) == "climate"

    def test_developer_tools_infers_devtools(self):
        parsed = self._parsed("build developer tools and SDK for engineers")
        assert _infer_domain(parsed) == "devtools"

    def test_infrastructure_infers_infra(self):
        parsed = self._parsed("manage cloud infrastructure and kubernetes clusters")
        assert _infer_domain(parsed) == "infra"

    def test_cybersecurity_infers_security(self):
        parsed = self._parsed("cybersecurity platform for threat detection")
        assert _infer_domain(parsed) == "security"

    def test_hr_infers_hr_tech(self):
        parsed = self._parsed("human resources platform for talent management and payroll")
        assert _infer_domain(parsed) == "hr_tech"

    def test_logistics_infers_logistics(self):
        parsed = self._parsed("supply chain and last mile delivery logistics")
        assert _infer_domain(parsed) == "logistics"

    def test_known_domain_not_overridden(self):
        # domain != 'other' should not be overridden by _infer_domain
        parsed = self._parsed("video game studio", domain="data")
        assert _infer_domain(parsed) == "data"

    def test_no_match_returns_other(self):
        parsed = self._parsed("generic consulting advisory services")
        assert _infer_domain(parsed) == "other"


class TestDomainAliases:
    """_DOMAIN_ALIASES maps common alternate names to canonical enum values."""

    def test_gaming_maps_to_game(self):
        assert _DOMAIN_ALIASES.get("gaming") == "game"

    def test_cybersecurity_maps_to_security(self):
        assert _DOMAIN_ALIASES.get("cybersecurity") == "security"

    def test_hrtech_maps_to_hr_tech(self):
        assert _DOMAIN_ALIASES.get("hrtech") == "hr_tech"

    def test_legaltech_maps_to_legal_tech(self):
        assert _DOMAIN_ALIASES.get("legaltech") == "legal_tech"

    def test_greentech_maps_to_climate(self):
        assert _DOMAIN_ALIASES.get("greentech") == "climate"

    def test_developer_tools_maps_to_devtools(self):
        assert _DOMAIN_ALIASES.get("developer-tools") == "devtools"

    def test_edtech_hyphen_maps_to_edtech(self):
        assert _DOMAIN_ALIASES.get("ed-tech") == "edtech"


class TestNewDomainsInKeywords:
    """New domains exist in _DOMAIN_KEYWORDS with non-empty keyword lists."""

    def test_game_keywords_exist(self):
        assert "game" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["game"]) >= 3

    def test_edtech_keywords_exist(self):
        assert "edtech" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["edtech"]) >= 3

    def test_climate_keywords_exist(self):
        assert "climate" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["climate"]) >= 3

    def test_devtools_keywords_exist(self):
        assert "devtools" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["devtools"]) >= 3

    def test_infra_keywords_exist(self):
        assert "infra" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["infra"]) >= 3

    def test_security_keywords_exist(self):
        assert "security" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["security"]) >= 3

    def test_logistics_keywords_exist(self):
        assert "logistics" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["logistics"]) >= 3

    def test_hr_tech_keywords_exist(self):
        assert "hr_tech" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["hr_tech"]) >= 3
