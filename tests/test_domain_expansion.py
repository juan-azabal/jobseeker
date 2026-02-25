"""
Tests for Phase 13.2: Expanded domain enum (30 values) and updated aliases.

Verifies:
(a) _infer_domain() correctly classifies text containing domain keywords.
(b) _DOMAIN_ALIASES maps alternate names to canonical enum values.
(c) VALID_DOMAINS frozenset contains all 30 canonical values.
"""

from api.scoring import _infer_domain, _DOMAIN_ALIASES, _DOMAIN_KEYWORDS, VALID_DOMAINS


class TestInferDomainExistingValues:
    """_infer_domain() returns canonical enum values for original domains."""

    def _parsed(self, text: str, domain: str = "other") -> dict:
        return {
            "domain": domain,
            "responsibilities_summary": text,
            "must_have_skills": [],
            "technical_stack": [],
        }

    def test_video_game_infers_gaming(self):
        parsed = self._parsed("video game development for mobile platforms")
        assert _infer_domain(parsed) == "gaming"

    def test_game_studio_infers_gaming(self):
        parsed = self._parsed("game studio building multiplayer experience")
        assert _infer_domain(parsed) == "gaming"

    def test_edtech_platform_infers_edtech(self):
        parsed = self._parsed("build learning management system for online courses")
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

    def test_cybersecurity_platform_infers_cybersecurity(self):
        parsed = self._parsed("cybersecurity platform for threat detection")
        assert _infer_domain(parsed) == "cybersecurity"

    def test_hr_infers_hr_tech(self):
        parsed = self._parsed("hr platform for talent management and payroll")
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


class TestInferDomainNewValues:
    """_infer_domain() handles the 9 new domains added in Phase 13.2."""

    def _parsed(self, text: str, domain: str = "other") -> dict:
        return {
            "domain": domain,
            "responsibilities_summary": text,
            "must_have_skills": [],
            "technical_stack": [],
        }

    def test_autonomous_driving_infers_automotive(self):
        parsed = self._parsed("autonomous driving and electric vehicle software platform")
        assert _infer_domain(parsed) == "automotive"

    def test_drug_discovery_infers_biotech(self):
        parsed = self._parsed("drug discovery platform for clinical trial management")
        assert _infer_domain(parsed) == "biotech"

    def test_construction_tech_infers_construction(self):
        parsed = self._parsed("construction tech and building information modeling platform")
        assert _infer_domain(parsed) == "construction"

    def test_defense_contractor_infers_defense(self):
        parsed = self._parsed("defense contractor building military technology systems")
        assert _infer_domain(parsed) == "defense"

    def test_oil_gas_infers_energy(self):
        parsed = self._parsed("oil and gas energy management and smart grid platform")
        assert _infer_domain(parsed) == "energy"

    def test_food_delivery_infers_food_bev(self):
        parsed = self._parsed("food delivery platform and restaurant tech solutions")
        assert _infer_domain(parsed) == "food_bev"

    def test_civic_tech_infers_govtech(self):
        parsed = self._parsed("government technology and civic tech for public sector")
        assert _infer_domain(parsed) == "govtech"

    def test_factory_automation_infers_manufacturing(self):
        parsed = self._parsed("factory automation and industrial iot manufacturing tech")
        assert _infer_domain(parsed) == "manufacturing"

    def test_retail_pos_infers_retail(self):
        parsed = self._parsed("retail technology and point of sale system for omnichannel retail")
        assert _infer_domain(parsed) == "retail"

    def test_telecom_network_infers_telecom(self):
        parsed = self._parsed("telecommunications and 5g network connectivity platform")
        assert _infer_domain(parsed) == "telecom"

    def test_booking_platform_infers_travel(self):
        parsed = self._parsed("travel tech and booking platform for hospitality")
        assert _infer_domain(parsed) == "travel"


class TestDomainAliases:
    """_DOMAIN_ALIASES maps common alternate names to canonical enum values."""

    def test_gaming_maps_to_gaming(self):
        assert _DOMAIN_ALIASES.get("gaming") == "gaming"

    def test_game_maps_to_gaming(self):
        assert _DOMAIN_ALIASES.get("game") == "gaming"

    def test_cybersecurity_maps_to_cybersecurity(self):
        assert _DOMAIN_ALIASES.get("cybersecurity") == "cybersecurity"

    def test_security_maps_to_cybersecurity(self):
        assert _DOMAIN_ALIASES.get("security") == "cybersecurity"

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

    def test_ml_maps_to_ai_ml(self):
        assert _DOMAIN_ALIASES.get("ml") == "ai_ml"

    def test_ai_maps_to_ai_ml(self):
        assert _DOMAIN_ALIASES.get("ai") == "ai_ml"

    def test_healthcare_maps_to_healthtech(self):
        assert _DOMAIN_ALIASES.get("healthcare") == "healthtech"

    def test_mobility_maps_to_automotive(self):
        assert _DOMAIN_ALIASES.get("mobility") == "automotive"

    def test_cleantech_maps_to_climate(self):
        assert _DOMAIN_ALIASES.get("cleantech") == "climate"

    def test_agritech_maps_to_food_bev(self):
        assert _DOMAIN_ALIASES.get("agritech") == "food_bev"

    def test_esports_maps_to_gaming(self):
        assert _DOMAIN_ALIASES.get("esports") == "gaming"

    def test_proptech_maps_to_construction(self):
        assert _DOMAIN_ALIASES.get("proptech") == "construction"

    def test_platform_maps_to_infra(self):
        assert _DOMAIN_ALIASES.get("platform") == "infra"

    def test_growth_maps_to_saas(self):
        assert _DOMAIN_ALIASES.get("growth") == "saas"


class TestNewDomainsInKeywords:
    """All 30 canonical domains exist in _DOMAIN_KEYWORDS with non-empty keyword lists."""

    CANONICAL_DOMAINS = [
        "adtech", "ai_ml", "automotive", "biotech", "climate", "construction",
        "cybersecurity", "data", "defense", "devtools", "ecommerce", "edtech",
        "energy", "fintech", "food_bev", "gaming", "govtech", "healthtech",
        "hr_tech", "infra", "legal_tech", "logistics", "manufacturing",
        "marketplace", "media", "retail", "saas", "telecom", "travel",
    ]

    def test_all_canonical_domains_have_keywords(self):
        for domain in self.CANONICAL_DOMAINS:
            assert domain in _DOMAIN_KEYWORDS, f"Missing domain: {domain}"
            assert len(_DOMAIN_KEYWORDS[domain]) >= 3, (
                f"Domain {domain} has fewer than 3 keywords"
            )

    def test_gaming_keywords_exist(self):
        assert "gaming" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["gaming"]) >= 3

    def test_cybersecurity_keywords_exist(self):
        assert "cybersecurity" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["cybersecurity"]) >= 3

    def test_ai_ml_keywords_exist(self):
        assert "ai_ml" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["ai_ml"]) >= 3

    def test_healthtech_keywords_exist(self):
        assert "healthtech" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["healthtech"]) >= 3

    def test_automotive_keywords_exist(self):
        assert "automotive" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["automotive"]) >= 3

    def test_biotech_keywords_exist(self):
        assert "biotech" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["biotech"]) >= 3

    def test_construction_keywords_exist(self):
        assert "construction" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["construction"]) >= 3

    def test_defense_keywords_exist(self):
        assert "defense" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["defense"]) >= 3

    def test_energy_keywords_exist(self):
        assert "energy" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["energy"]) >= 3

    def test_food_bev_keywords_exist(self):
        assert "food_bev" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["food_bev"]) >= 3

    def test_govtech_keywords_exist(self):
        assert "govtech" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["govtech"]) >= 3

    def test_manufacturing_keywords_exist(self):
        assert "manufacturing" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["manufacturing"]) >= 3

    def test_retail_keywords_exist(self):
        assert "retail" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["retail"]) >= 3

    def test_telecom_keywords_exist(self):
        assert "telecom" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["telecom"]) >= 3

    def test_travel_keywords_exist(self):
        assert "travel" in _DOMAIN_KEYWORDS
        assert len(_DOMAIN_KEYWORDS["travel"]) >= 3


class TestValidDomains:
    """VALID_DOMAINS frozenset contains all 30 canonical values."""

    def test_valid_domains_is_frozenset(self):
        assert isinstance(VALID_DOMAINS, frozenset)

    def test_valid_domains_has_30_entries(self):
        assert len(VALID_DOMAINS) == 30

    def test_valid_domains_includes_other(self):
        assert "other" in VALID_DOMAINS

    def test_all_new_domains_in_valid_domains(self):
        new_domains = [
            "automotive", "biotech", "construction", "cybersecurity", "defense",
            "energy", "food_bev", "gaming", "govtech", "healthtech",
            "manufacturing", "retail", "telecom", "travel",
        ]
        for d in new_domains:
            assert d in VALID_DOMAINS, f"Missing from VALID_DOMAINS: {d}"

    def test_old_canonical_names_not_in_valid_domains(self):
        """Old names (ml, game, security, healthcare) must not be in VALID_DOMAINS."""
        old_names = ["ml", "game", "security", "healthcare", "platform", "growth"]
        for old in old_names:
            assert old not in VALID_DOMAINS, f"Old name still in VALID_DOMAINS: {old}"
