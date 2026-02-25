// Canonical domain list — mirrors parser-prompt.md v1.3 enum (30 values + other)
// This is the single source of truth for all domain-related UI in the frontend.
// Keep in sync with api/scoring.py VALID_DOMAINS and _DOMAIN_KEYWORDS.

export const VALID_DOMAINS = [
  "adtech", "ai_ml", "automotive", "biotech", "climate", "construction",
  "cybersecurity", "data", "defense", "devtools", "ecommerce", "edtech",
  "energy", "fintech", "food_bev", "gaming", "govtech", "healthtech",
  "hr_tech", "infra", "legal_tech", "logistics", "manufacturing",
  "marketplace", "media", "retail", "saas", "telecom", "travel", "other",
] as const;

export type Domain = typeof VALID_DOMAINS[number];

/** Human-readable display labels for each domain key. */
export const DOMAIN_LABELS: Record<Domain, string> = {
  adtech:       "AdTech",
  ai_ml:        "AI / ML",
  automotive:   "Automotive",
  biotech:      "Biotech",
  climate:      "Climate Tech",
  construction: "PropTech / Construction",
  cybersecurity:"Cybersecurity",
  data:         "Data",
  defense:      "Defense",
  devtools:     "Dev Tools",
  ecommerce:    "E-commerce",
  edtech:       "EdTech",
  energy:       "Energy",
  fintech:      "Fintech",
  food_bev:     "Food & Bev",
  gaming:       "Gaming",
  govtech:      "GovTech",
  healthtech:   "HealthTech",
  hr_tech:      "HR Tech",
  infra:        "Infra / Cloud",
  legal_tech:   "Legal Tech",
  logistics:    "Logistics",
  manufacturing:"Manufacturing",
  marketplace:  "Marketplace",
  media:        "Media",
  retail:       "Retail",
  saas:         "SaaS",
  telecom:      "Telecom",
  travel:       "Travel",
  other:        "Other",
};

/** Grouped layout for the domain selector dropdown in job detail (13.4b). */
export const DOMAIN_GROUPS: { label: string; domains: Domain[] }[] = [
  {
    label: "Tech Infrastructure",
    domains: ["infra", "cybersecurity", "devtools", "data", "ai_ml", "telecom"],
  },
  {
    label: "Industry Verticals",
    domains: ["fintech", "healthtech", "edtech", "biotech", "automotive", "energy", "defense"],
  },
  {
    label: "Commerce & Services",
    domains: ["ecommerce", "marketplace", "retail", "saas", "adtech", "logistics"],
  },
  {
    label: "Lifestyle & Media",
    domains: ["gaming", "media", "travel", "food_bev"],
  },
  {
    label: "Specialized",
    domains: ["climate", "construction", "govtech", "hr_tech", "legal_tech", "manufacturing"],
  },
  {
    label: "Other",
    domains: ["other"],
  },
];

/** Ordered flat list for quick-add chips: all domains except "other", grouped order. */
export const DOMAIN_CHIP_ORDER: Domain[] = DOMAIN_GROUPS
  .flatMap((g) => g.domains)
  .filter((d) => d !== "other");

/** Look up a display label for any domain key, including unknown/custom keys. */
export const domainLabel = (key: string): string =>
  (DOMAIN_LABELS as Record<string, string>)[key] ?? key;
