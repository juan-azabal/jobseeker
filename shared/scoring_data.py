"""Scoring data constants — pure data, no logic.

Extracted from scoring_core.py for maintainability.
Do NOT add functions here. Import path: scoring_core re-exports all public symbols.
"""

# Maps profile domain names → parser-emitted canonical domain names (v1.3).
DOMAIN_ALIASES: dict[str, str] = {
    # AI/ML consolidation
    "ia": "ai_ml",
    "ai": "ai_ml",
    "llm": "ai_ml",
    "ml": "ai_ml",
    # Adtech
    "martech": "adtech",
    # Automotive
    "mobility": "automotive",
    "ev": "automotive",
    # Biotech
    "pharma": "biotech",
    "life_sciences": "biotech",
    # Climate
    "greentech": "climate",
    "cleantech": "climate",
    # Construction
    "proptech": "construction",
    # Cybersecurity
    "security": "cybersecurity",
    "infosec": "cybersecurity",
    "devsecops": "cybersecurity",
    "cybersecurity": "cybersecurity",
    # Devtools
    "developer-tools": "devtools",
    # Edtech
    "ed-tech": "edtech",
    # Fintech
    "insurtech": "fintech",
    # Food & bev
    "agritech": "food_bev",
    "foodtech": "food_bev",
    # Gaming
    "game": "gaming",
    "esports": "gaming",
    "gaming": "gaming",
    # Healthcare (legacy parser value)
    "healthcare": "healthtech",
    # HR tech
    "hrtech": "hr_tech",
    # Legal tech
    "legaltech": "legal_tech",
    # Platform (old enum value not in v2 list)
    "platform": "infra",
    # Growth (old enum value not in v2 list)
    "growth": "saas",
}

# Frozenset of all valid canonical domain values (v1.3 — 30 entries).
VALID_DOMAINS: frozenset[str] = frozenset(
    {
        "adtech",
        "ai_ml",
        "automotive",
        "biotech",
        "climate",
        "construction",
        "cybersecurity",
        "data",
        "defense",
        "devtools",
        "ecommerce",
        "edtech",
        "energy",
        "fintech",
        "food_bev",
        "gaming",
        "govtech",
        "healthtech",
        "hr_tech",
        "infra",
        "legal_tech",
        "logistics",
        "manufacturing",
        "marketplace",
        "media",
        "retail",
        "saas",
        "telecom",
        "travel",
        "other",
    }
)

# Domain override keywords — all ≥2 words or known brand/product names.
# SYNC RULE: mirrors agent/main.py._DOMAIN_KEYWORDS until step 1.6 wires agent to shared.
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "adtech": [
        "ad tech",
        "programmatic advertising",
        "demand-side platform",
        "supply-side platform",
        "header bidding",
        "real-time bidding",
        "publisher monetization",
        "ad network",
        "ad exchange",
        "display advertising",
    ],
    "ai_ml": [
        "machine learning",
        "ml model",
        "ai agent",
        "large language model",
        "natural language processing",
        "computer vision",
        "deep learning",
        "neural network",
        "generative ai",
        "ml platform",
        "model training",
        "model inference",
    ],
    "automotive": [
        "autonomous driving",
        "electric vehicle",
        "ev charging",
        "connected car",
        "fleet management",
        "mobility platform",
        "adas system",
        "vehicle software",
    ],
    "biotech": [
        "drug discovery",
        "clinical trial",
        "life sciences",
        "genomics platform",
        "molecular biology",
        "bioinformatics pipeline",
    ],
    "climate": [
        "carbon offset",
        "carbon footprint",
        "renewable energy",
        "clean energy",
        "climate tech",
        "solar energy",
        "wind energy",
        "circular economy",
        "sustainability platform",
        "decarbonization",
    ],
    "construction": [
        "construction tech",
        "building information modeling",
        "property management",
        "real estate platform",
        "smart building",
        "architecture tech",
    ],
    "cybersecurity": [
        "information security",
        "identity management",
        "fraud prevention",
        "threat detection",
        "zero trust",
        "penetration testing",
        "security operations center",
        "vulnerability management",
    ],
    "data": [
        "data platform",
        "data pipeline",
        "data warehouse",
        "data lake",
        "data lakehouse",
        "data product",
        "data governance",
        "data quality",
        "data engineering",
        "business intelligence",
        "data analytics platform",
        "observability platform",
        "etl pipeline",
        "data modeling",
        "databricks",
        "snowflake",
        "clickhouse",
    ],
    "defense": [
        "defense contractor",
        "defense tech",
        "aerospace defense",
        "military technology",
        "government contractor",
    ],
    "devtools": [
        "developer tool",
        "developer experience",
        "ci/cd pipeline",
        "code review platform",
        "api platform",
        "sdk development",
        "source control",
        "build system",
        "package manager",
        "devops platform",
    ],
    "ecommerce": [
        "online retail",
        "e-commerce platform",
        "shopping platform",
        "direct-to-consumer",
        "online store",
        "product catalog",
        "shopify",
        "woocommerce",
    ],
    "edtech": [
        "e-learning",
        "learning management system",
        "education technology",
        "online education",
        "courseware platform",
        "student platform",
        "classroom technology",
        "tutoring platform",
    ],
    "energy": [
        "oil and gas",
        "energy management",
        "smart grid",
        "power generation",
        "energy trading",
        "utility company",
    ],
    "fintech": [
        "payment processing",
        "digital banking",
        "lending platform",
        "wealth management",
        "trading platform",
        "insurance technology",
        "credit platform",
        "neobank",
        "blockchain platform",
        "cryptocurrency exchange",
        "defi protocol",
        "financial institution",
        "financial services",
    ],
    "food_bev": [
        "food delivery",
        "restaurant tech",
        "meal kit",
        "food safety platform",
        "precision agriculture",
        "grocery platform",
        "agritech platform",
    ],
    "gaming": [
        "video game",
        "game engine",
        "game studio",
        "game development",
        "interactive entertainment",
        "mobile game",
        "esports platform",
        "unity developer",
        "unreal engine",
    ],
    "govtech": [
        "government technology",
        "civic tech",
        "public sector platform",
        "e-government",
        "regulatory technology",
    ],
    "healthtech": [
        "digital health",
        "telemedicine platform",
        "electronic health record",
        "patient platform",
        "medical device software",
        "telehealth",
        "health platform",
        "clinical software",
    ],
    "hr_tech": [
        "recruiting platform",
        "talent acquisition",
        "workforce management",
        "hr platform",
        "applicant tracking",
        "people analytics",
        "employee engagement",
        "payroll platform",
        "training management",
        "learning and development",
    ],
    "infra": [
        "cloud infrastructure",
        "container orchestration",
        "kubernetes",
        "terraform",
        "cloud platform",
        "infrastructure as code",
        "load balancer",
        "bare metal hosting",
        "cdn provider",
    ],
    "legal_tech": [
        "legal tech",
        "contract management",
        "compliance platform",
        "e-discovery",
        "case management",
        "document automation",
        "legal ai",
    ],
    "logistics": [
        "supply chain",
        "last mile delivery",
        "warehouse management",
        "freight platform",
        "transportation management",
        "fulfillment platform",
        "3pl platform",
    ],
    "manufacturing": [
        "industrial iot",
        "factory automation",
        "manufacturing tech",
        "quality control system",
        "production line",
        "robotics platform",
        "scada system",
    ],
    "marketplace": [
        "two-sided marketplace",
        "classifieds platform",
        "gig economy",
        "platform economy",
        "peer to peer",
        "rental platform",
        "buyer and seller",
    ],
    "media": [
        "content platform",
        "streaming platform",
        "digital media",
        "publishing platform",
        "video platform",
        "podcast platform",
        "content management system",
        "editorial platform",
        "media company",
    ],
    "retail": [
        "retail technology",
        "point of sale",
        "pos system",
        "in-store technology",
        "omnichannel retail",
        "inventory management",
        "store operations",
        "merchandising platform",
    ],
    "saas": [
        "b2b software",
        "b2b platform",
        "enterprise software",
        "subscription platform",
        "crm platform",
        "erp system",
        "productivity software",
    ],
    "telecom": [
        "telecommunications",
        "network operator",
        "mobile network",
        "fiber optic",
        "5g network",
        "voip platform",
        "connectivity platform",
    ],
    "travel": [
        "travel tech",
        "booking platform",
        "hospitality platform",
        "hotel management",
        "airline technology",
        "reservation system",
        "tourism platform",
    ],
}

GRADE_POINTS: dict[str, int] = {"A": 20, "B": 12, "C": 5}

# City → country lookup used by compute_eligibility_penalty + location scoring.
# SYNC RULE: also in agent/main.py._CITY_TO_COUNTRY — update both until step 1.6.
_CITY_TO_COUNTRY: dict[str, str] = {
    # Spain
    "barcelona": "spain",
    "madrid": "spain",
    "valencia": "spain",
    "bilbao": "spain",
    "seville": "spain",
    "sevilla": "spain",
    # France
    "paris": "france",
    "lyon": "france",
    "marseille": "france",
    "toulouse": "france",
    # Germany
    "berlin": "germany",
    "munich": "germany",
    "münchen": "germany",
    "hamburg": "germany",
    "frankfurt": "germany",
    "cologne": "germany",
    "köln": "germany",
    # Netherlands
    "amsterdam": "netherlands",
    "rotterdam": "netherlands",
    "utrecht": "netherlands",
    # UK
    "london": "uk",
    "manchester": "uk",
    "edinburgh": "uk",
    "bristol": "uk",
    # Portugal
    "lisbon": "portugal",
    "porto": "portugal",
    "lisboa": "portugal",
    # Italy
    "milan": "italy",
    "rome": "italy",
    "milano": "italy",
    "roma": "italy",
    # Sweden
    "stockholm": "sweden",
    "gothenburg": "sweden",
    # Denmark
    "copenhagen": "denmark",
    # Belgium
    "brussels": "belgium",
    "bruxelles": "belgium",
    # Ireland
    "dublin": "ireland",
    # Switzerland
    "zurich": "switzerland",
    "zürich": "switzerland",
    "geneva": "switzerland",
    # Austria
    "vienna": "austria",
    "wien": "austria",
    # Poland
    "warsaw": "poland",
    "krakow": "poland",
    # Czech Republic
    "prague": "czech republic",
    # Finland
    "helsinki": "finland",
    # Norway
    "oslo": "norway",
    # United States
    "new york": "us",
    "new york city": "us",
    "nyc": "us",
    "san francisco": "us",
    "los angeles": "us",
    "seattle": "us",
    "boston": "us",
    "chicago": "us",
    "austin": "us",
}

# Region alias mapping used in eligibility penalty.
_REGION_ALIASES: dict[str, list[str]] = {
    "eu": ["eu ", "eu/", "european union", "europe"],
    "eea": ["eea"],
}

# Language signals used by heuristic_score.
_LANG_SIGNALS: dict[str, list[str]] = {
    "fr": ["french", "français", "francais"],
    "de": ["german", "deutsch"],
    "pt": ["portuguese", "português", "portugues"],
    "nl": ["dutch", "flemish", "nederlands"],
    "es": ["spanish", "español", "espanol", "castellano"],
    "it": ["italian", "italiano"],
    "ca": ["catalan", "català", "catala", "valencian"],
    "ar": ["arabic", "árabe"],
    "zh": ["chinese", "mandarin"],
    "ja": ["japanese"],
    "ko": ["korean"],
    "pl": ["polish", "polski"],
    "sv": ["swedish", "svenska"],
    "da": ["danish", "dansk"],
    "fi": ["finnish", "suomi"],
    "no": ["norwegian", "norsk"],
}

# Null-value sentinels for red_flags used by heuristic_score.
_NULL_FLAG: frozenset[str] = frozenset(
    {"none mentioned", "none", "n/a", "null", "none noted", "no red flags", "none identified"}
)
