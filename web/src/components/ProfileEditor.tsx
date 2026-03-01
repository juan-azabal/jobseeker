import { useState } from 'react';
import { DOMAIN_CHIP_ORDER, domainLabel } from '../constants/domains';

const SENIORITY_OPTIONS = ['junior', 'mid', 'senior', 'staff', 'principal', 'director', 'vp', 'unknown'];
const COMPANY_TYPE_OPTIONS = ['startup', 'scaleup', 'enterprise', 'consultancy', 'agency', 'ngo'];
const COMMON_COUNTRIES = ['spain', 'germany', 'netherlands', 'france', 'uk', 'portugal', 'remote'];
const ROLE_FUNCTION_OPTIONS = ['product', 'engineering', 'design', 'data', 'marketing', 'sales', 'ops', 'support', 'other'];
const ROLE_FUNCTION_LABELS: Record<string, string> = {
  product: 'Product (PM/PO)', engineering: 'Engineering', design: 'Design/UX',
  data: 'Data/Analytics', marketing: 'Marketing', sales: 'Sales', ops: 'Operations',
  support: 'Support/Success', other: 'Other',
};

interface Profile {
  name: string;
  email: string | null;
  languages: string[];
  home_locations: string[];
  current_level: string;
  track: string;
  target_level: string;
  seniority_weights?: Record<string, number>;
  domains: Record<string, number>;
  country_weights?: Record<string, number>;
  company_type_weights?: Record<string, number>;
  skills: string[];
  search_titles: string[];
  exclude_companies: string[];
  salary_min?: number;
  location_preference?: string;
  role_type?: string;
  role_function?: string;
}

interface Props {
  profile: Profile;
  cvMarkdown: string;
  onSaved: () => void;
  /** If true, we're reviewing a freshly extracted profile (first-time / CV replace).
   *  The save button calls POST /save-profile instead of PATCH /profile. */
  isNew?: boolean;
}

export default function ProfileEditor({ profile, cvMarkdown, onSaved, isNew = false }: Props) {
  const [name, setName] = useState(profile.name);
  const [skills, setSkills] = useState<string[]>(profile.skills);
  const [locations, setLocations] = useState<string[]>(profile.home_locations);
  const [domains, setDomains] = useState<Record<string, number>>(profile.domains);
  const [seniorityWeights, setSeniorityWeights] = useState<Record<string, number>>(
    profile.seniority_weights ?? {}
  );
  const [salaryMin, setSalaryMin] = useState(profile.salary_min ?? 60000);
  const [locationPref, setLocationPref] = useState(profile.location_preference ?? 'b');
  const [countryWeights, setCountryWeights] = useState<Record<string, number>>(profile.country_weights ?? {});
  const [companyTypeWeights, setCompanyTypeWeights] = useState<Record<string, number>>(profile.company_type_weights ?? {});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newDomain, setNewDomain] = useState('');
  const [newSkill, setNewSkill] = useState('');
  const [newLocation, setNewLocation] = useState('');
  const [newSeniority, setNewSeniority] = useState('');
  const [newCountry, setNewCountry] = useState('');
  const [newCompanyType, setNewCompanyType] = useState('');
  const [roleType, setRoleType] = useState(profile.role_type ?? '');
  const [roleFunction, setRoleFunction] = useState(profile.role_function ?? '');
  const [track, setTrack] = useState(profile.track ?? 'ic');
  const [searchTitles, setSearchTitles] = useState<string[]>(profile.search_titles ?? []);
  const [newSearchTitle, setNewSearchTitle] = useState('');

  const handleSave = async () => {
    setError(null);
    setSaving(true);

    let resp: Response;
    if (isNew) {
      // First-time onboarding: POST to save-profile (creates YAML + links profile)
      resp = await fetch('/api/onboard/save-profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cv_markdown: cvMarkdown,
          profile: { ...profile, name, skills, home_locations: locations, domains, seniority_weights: seniorityWeights, country_weights: countryWeights, company_type_weights: companyTypeWeights, search_titles: searchTitles, role_type: roleType || undefined, role_function: roleFunction || undefined },
          salary_min: salaryMin,
          location_preference: locationPref,
        }),
      });
    } else {
      // Existing user: PATCH — surgically update editable fields, preserve stories etc.
      resp = await fetch('/api/onboard/profile', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          home_locations: locations,
          domains,
          seniority_weights: seniorityWeights,
          country_weights: countryWeights,
          company_type_weights: companyTypeWeights,
          skills,
          search_titles: searchTitles,
          salary_min: salaryMin,
          location_preference: locationPref,
          ...(roleType ? { role_type: roleType } : {}),
          ...(roleFunction ? { role_function: roleFunction } : {}),
          track,
        }),
      });
    }

    setSaving(false);
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      setError(data.detail || 'Save failed. Please try again.');
      return;
    }
    onSaved();
  };

  const removeSkill = (s: string) => setSkills(skills.filter((x) => x !== s));
  const removeLocation = (l: string) => setLocations(locations.filter((x) => x !== l));

  const addDomain = () => {
    const key = newDomain.trim().toLowerCase();
    if (!key || key in domains) return;
    setDomains({ ...domains, [key]: 10 });
    setNewDomain('');
  };

  const removeDomain = (key: string) => {
    const next = { ...domains };
    delete next[key];
    setDomains(next);
  };

  const addSeniority = (raw?: string) => {
    const key = (raw ?? newSeniority).trim().toLowerCase();
    if (!key || key in seniorityWeights) return;
    setSeniorityWeights({ ...seniorityWeights, [key]: 10 });
    setNewSeniority('');
  };

  const removeSeniority = (key: string) => {
    const next = { ...seniorityWeights };
    delete next[key];
    setSeniorityWeights(next);
  };

  const addCountry = (raw?: string) => {
    const key = (raw ?? newCountry).trim().toLowerCase();
    if (!key || key in countryWeights) return;
    setCountryWeights({ ...countryWeights, [key]: 5 });
    setNewCountry('');
  };

  const removeCountry = (key: string) => {
    const next = { ...countryWeights };
    delete next[key];
    setCountryWeights(next);
  };

  const addCompanyType = (raw?: string) => {
    const key = (raw ?? newCompanyType).trim().toLowerCase();
    if (!key || key in companyTypeWeights) return;
    setCompanyTypeWeights({ ...companyTypeWeights, [key]: 5 });
    setNewCompanyType('');
  };

  const removeCompanyType = (key: string) => {
    const next = { ...companyTypeWeights };
    delete next[key];
    setCompanyTypeWeights(next);
  };

  const addSkill = () => {
    const s = newSkill.trim().toLowerCase();
    if (!s || skills.includes(s)) return;
    setSkills([...skills, s]);
    setNewSkill('');
  };

  const addLocation = () => {
    const l = newLocation.trim().toLowerCase();
    if (!l || locations.includes(l)) return;
    setLocations([...locations, l]);
    setNewLocation('');
  };

  const addSearchTitle = () => {
    const t = newSearchTitle.trim();
    if (!t) return;
    if (searchTitles.some((s) => s.toLowerCase() === t.toLowerCase())) return;
    setSearchTitles([...searchTitles, t]);
    setNewSearchTitle('');
  };

  const removeSearchTitle = (title: string) =>
    setSearchTitles(searchTitles.filter((s) => s !== title));

  return (
    <div className="space-y-6">
      {/* Name */}
      <div>
        <label className="block text-zinc-300 text-sm font-medium mb-1">Name</label>
        <input
          className="w-full bg-zinc-800 text-white rounded px-3 py-2 text-sm"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      {/* Role */}
      <div className="flex gap-3">
        <div className="flex-1">
          <label className="block text-zinc-300 text-sm font-medium mb-1">Role title</label>
          <input
            className="w-full bg-zinc-800 text-white rounded px-3 py-2 text-sm"
            value={roleType}
            placeholder="e.g. Product Manager"
            onChange={(e) => setRoleType(e.target.value)}
          />
        </div>
        <div className="flex-1">
          <label className="block text-zinc-300 text-sm font-medium mb-1" htmlFor="role-function-select">Role function</label>
          <select
            id="role-function-select"
            aria-label="Role function"
            className="w-full bg-zinc-800 text-white rounded px-3 py-2 text-sm"
            value={roleFunction}
            onChange={(e) => setRoleFunction(e.target.value)}
          >
            <option value="">— not set —</option>
            {ROLE_FUNCTION_OPTIONS.map((rf) => (
              <option key={rf} value={rf}>{ROLE_FUNCTION_LABELS[rf] ?? rf}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Track */}
      <div>
        <label className="block text-zinc-300 text-sm font-medium mb-1" htmlFor="track-select">Career track</label>
        <select
          id="track-select"
          aria-label="Career track"
          className="w-full bg-zinc-800 text-white rounded px-3 py-2 text-sm"
          value={track}
          onChange={(e) => setTrack(e.target.value)}
        >
          <option value="ic">Individual Contributor (IC)</option>
          <option value="management">Management</option>
        </select>
      </div>

      {/* Search titles */}
      <div>
        <label className="block text-zinc-300 text-sm font-medium mb-1">Job titles to search</label>
        <p className="text-zinc-500 text-xs mb-3">
          These exact titles are searched on LinkedIn and Indeed every day. Add titles you want to monitor — they don't affect scoring.
        </p>
        <div className="flex flex-wrap gap-2">
          {searchTitles.map((t) => (
            <span
              key={t}
              className="bg-zinc-700 text-zinc-200 text-xs px-2 py-1 rounded flex items-center gap-1"
            >
              {t}
              <button className="text-zinc-400 hover:text-white" onClick={() => removeSearchTitle(t)}>×</button>
            </span>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <input
            className="flex-1 rounded bg-zinc-800 px-3 py-1.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            placeholder="e.g. Senior Product Manager"
            value={newSearchTitle}
            onChange={(e) => setNewSearchTitle(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addSearchTitle()}
          />
          <button
            onClick={addSearchTitle}
            className="rounded bg-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-600 hover:text-white"
          >
            Add
          </button>
        </div>
      </div>

      {/* Seniority weights */}
      <div>
        <label className="block text-zinc-300 text-sm font-medium mb-1">Seniority weights</label>
        <p className="text-zinc-500 text-xs mb-3">
          How much to prioritize each seniority level. Higher = more relevant. Add levels from your CV or that you aspire to.
        </p>
        {Object.entries(seniorityWeights).map(([level, weight]) => (
          <div key={level} className="flex items-center gap-3 mb-2">
            <span className="text-zinc-400 text-sm w-20 truncate capitalize" title={level === 'unknown' ? 'Jobs with no seniority signal in the title' : undefined}>
              {level === 'unknown' ? 'Unspecified' : level}
            </span>
            <input
              type="range"
              min={-15}
              max={15}
              value={weight}
              className="flex-1"
              onChange={(e) => setSeniorityWeights({ ...seniorityWeights, [level]: Number(e.target.value) })}
            />
            <span className={`text-sm w-7 text-right ${weight < 0 ? 'text-red-400' : weight > 0 ? 'text-emerald-400' : 'text-zinc-500'}`}>{weight}</span>
            <button
              onClick={() => removeSeniority(level)}
              className="text-zinc-600 hover:text-red-400 transition-colors text-sm leading-none"
              title="Remove level"
            >×</button>
          </div>
        ))}
        {/* Quick-add buttons for common levels not yet in weights */}
        <div className="flex flex-wrap gap-1.5 mt-2 mb-3">
          {SENIORITY_OPTIONS.filter((l) => !(l in seniorityWeights)).map((l) => (
            <button
              key={l}
              onClick={() => addSeniority(l)}
              title={l === 'unknown' ? 'Jobs with no seniority signal in the title' : undefined}
              className="rounded border border-zinc-700 px-2 py-0.5 text-xs text-zinc-500 transition-colors hover:border-zinc-500 hover:text-zinc-300 capitalize"
            >
              + {l === 'unknown' ? 'Unspecified' : l}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            className="flex-1 rounded bg-zinc-800 px-3 py-1.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            placeholder="Add custom level…"
            value={newSeniority}
            onChange={(e) => setNewSeniority(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addSeniority()}
          />
          <button
            onClick={() => addSeniority()}
            className="rounded bg-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-600 hover:text-white"
          >
            Add
          </button>
        </div>
      </div>

      {/* Domain weights */}
      <div>
        <label className="block text-zinc-300 text-sm font-medium mb-1">Domain weights</label>
        <p className="text-zinc-500 text-xs mb-3">
          Boost or penalise jobs by industry domain. Positive = prioritise, negative = deprioritise. The scoring engine uses these to rank jobs for you.
        </p>
        {Object.entries(domains).map(([domain, weight]) => (
          <div key={domain} className="flex items-center gap-3 mb-2">
            <span className="text-zinc-400 text-sm w-28 truncate" title={domain}>{domainLabel(domain)}</span>
            <input
              type="range"
              min={-20}
              max={20}
              value={weight}
              className="flex-1"
              onChange={(e) => setDomains({ ...domains, [domain]: Number(e.target.value) })}
            />
            <span className={`text-sm w-7 text-right ${weight < 0 ? 'text-red-400' : weight > 0 ? 'text-emerald-400' : 'text-zinc-500'}`}>
              {weight}
            </span>
            <button
              onClick={() => removeDomain(domain)}
              className="text-zinc-600 hover:text-red-400 transition-colors text-sm leading-none"
              title="Remove domain"
            >×</button>
          </div>
        ))}
        {/* Quick-add chips for known domains not yet added */}
        <div className="flex flex-wrap gap-1.5 mt-2 mb-3">
          {DOMAIN_CHIP_ORDER.filter((key) => !(key in domains)).map((key) => (
            <button
              key={key}
              onClick={() => { setDomains({ ...domains, [key]: 10 }); }}
              className="rounded border border-zinc-700 px-2 py-0.5 text-xs text-zinc-500 transition-colors hover:border-zinc-500 hover:text-zinc-300"
            >
              + {domainLabel(key)}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            className="flex-1 rounded bg-zinc-800 px-3 py-1.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            placeholder="Add custom domain…"
            value={newDomain}
            onChange={(e) => setNewDomain(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addDomain()}
          />
          <button
            onClick={addDomain}
            className="rounded bg-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-600 hover:text-white"
          >
            Add
          </button>
        </div>
      </div>

      {/* Skills */}
      <div>
        <label className="block text-zinc-300 text-sm font-medium mb-2">Skills</label>
        <div className="flex flex-wrap gap-2">
          {skills.map((s) => (
            <span
              key={s}
              className="bg-zinc-700 text-zinc-200 text-xs px-2 py-1 rounded flex items-center gap-1"
            >
              {s}
              <button className="text-zinc-400 hover:text-white" onClick={() => removeSkill(s)}>×</button>
            </span>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <input
            className="flex-1 rounded bg-zinc-800 px-3 py-1.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            placeholder="Add skill…"
            value={newSkill}
            onChange={(e) => setNewSkill(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addSkill()}
          />
          <button
            onClick={addSkill}
            className="rounded bg-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-600 hover:text-white"
          >
            Add
          </button>
        </div>
      </div>

      {/* Home locations */}
      <div>
        <label className="block text-zinc-300 text-sm font-medium mb-2">Home locations</label>
        <div className="flex flex-wrap gap-2">
          {locations.map((l) => (
            <span
              key={l}
              className="bg-zinc-700 text-zinc-200 text-xs px-2 py-1 rounded flex items-center gap-1"
            >
              {l}
              <button className="text-zinc-400 hover:text-white" onClick={() => removeLocation(l)}>×</button>
            </span>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <input
            className="flex-1 rounded bg-zinc-800 px-3 py-1.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            placeholder="Add location…"
            value={newLocation}
            onChange={(e) => setNewLocation(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addLocation()}
          />
          <button
            onClick={addLocation}
            className="rounded bg-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-600 hover:text-white"
          >
            Add
          </button>
        </div>
      </div>

      {/* Minimum salary */}
      <div>
        <label className="block text-zinc-300 text-sm font-medium mb-1">
          Minimum salary: {salaryMin.toLocaleString()} EUR
        </label>
        <input
          type="range"
          min={30000}
          max={300000}
          step={5000}
          value={salaryMin}
          className="w-full"
          onChange={(e) => setSalaryMin(Number(e.target.value))}
        />
      </div>

      {/* Location preference */}
      <div>
        <label className="block text-zinc-300 text-sm font-medium mb-2">Location preference</label>
        <select
          className="bg-zinc-800 text-white rounded px-3 py-2 text-sm"
          value={locationPref}
          onChange={(e) => setLocationPref(e.target.value)}
        >
          <option value="a">Remote only</option>
          <option value="b">Remote + home city</option>
          <option value="c">Anywhere in country</option>
          <option value="d">Anywhere in Europe</option>
        </select>
      </div>

      {/* Country weights */}
      <div>
        <label className="block text-zinc-300 text-sm font-medium mb-1">Country preferences</label>
        <p className="text-zinc-500 text-xs mb-3">
          Score jobs higher or lower based on where they're located. Negative = avoid. Add "remote" for fully remote jobs.
        </p>
        {Object.entries(countryWeights).map(([country, weight]) => (
          <div key={country} className="flex items-center gap-3 mb-2">
            <span className="text-zinc-400 text-sm w-24 truncate capitalize">{country}</span>
            <input
              type="range"
              min={-10}
              max={10}
              value={weight}
              className="flex-1"
              onChange={(e) => setCountryWeights({ ...countryWeights, [country]: Number(e.target.value) })}
            />
            <span className={`text-sm w-7 text-right ${weight < 0 ? 'text-red-400' : weight > 0 ? 'text-emerald-400' : 'text-zinc-500'}`}>
              {weight}
            </span>
            <button
              onClick={() => removeCountry(country)}
              className="text-zinc-600 hover:text-red-400 transition-colors text-sm leading-none"
              title="Remove country"
            >×</button>
          </div>
        ))}
        {/* Quick-add common countries not yet in weights */}
        <div className="flex flex-wrap gap-1.5 mt-2 mb-3">
          {COMMON_COUNTRIES.filter((c) => !(c in countryWeights)).map((c) => (
            <button
              key={c}
              onClick={() => addCountry(c)}
              className="rounded border border-zinc-700 px-2 py-0.5 text-xs text-zinc-500 transition-colors hover:border-zinc-500 hover:text-zinc-300 capitalize"
            >
              + {c}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            className="flex-1 rounded bg-zinc-800 px-3 py-1.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            placeholder="Add country…"
            value={newCountry}
            onChange={(e) => setNewCountry(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addCountry()}
          />
          <button
            onClick={() => addCountry()}
            className="rounded bg-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-600 hover:text-white"
          >
            Add
          </button>
        </div>
      </div>

      {/* Company type weights */}
      <div>
        <label className="block text-zinc-300 text-sm font-medium mb-1">Company type preferences</label>
        <p className="text-zinc-500 text-xs mb-3">
          Optionally boost or penalise jobs by company type. Leave empty to treat all types equally.
        </p>
        {Object.entries(companyTypeWeights).map(([ct, weight]) => (
          <div key={ct} className="flex items-center gap-3 mb-2">
            <span className="text-zinc-400 text-sm w-24 truncate capitalize">{ct}</span>
            <input
              type="range"
              min={-15}
              max={15}
              value={weight}
              className="flex-1"
              onChange={(e) => setCompanyTypeWeights({ ...companyTypeWeights, [ct]: Number(e.target.value) })}
            />
            <span className={`text-sm w-7 text-right ${weight < 0 ? 'text-red-400' : weight > 0 ? 'text-emerald-400' : 'text-zinc-500'}`}>
              {weight}
            </span>
            <button
              onClick={() => removeCompanyType(ct)}
              className="text-zinc-600 hover:text-red-400 transition-colors text-sm leading-none"
              title="Remove company type"
            >×</button>
          </div>
        ))}
        {/* Quick-add buttons for common types */}
        <div className="flex flex-wrap gap-1.5 mt-2 mb-3">
          {COMPANY_TYPE_OPTIONS.filter((t) => !(t in companyTypeWeights)).map((t) => (
            <button
              key={t}
              onClick={() => addCompanyType(t)}
              className="rounded border border-zinc-700 px-2 py-0.5 text-xs text-zinc-500 transition-colors hover:border-zinc-500 hover:text-zinc-300 capitalize"
            >
              + {t}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            className="flex-1 rounded bg-zinc-800 px-3 py-1.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            placeholder="Add company type…"
            value={newCompanyType}
            onChange={(e) => setNewCompanyType(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addCompanyType()}
          />
          <button
            onClick={() => addCompanyType()}
            className="rounded bg-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-600 hover:text-white"
          >
            Add
          </button>
        </div>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <button
        className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium px-6 py-2 rounded-lg"
        onClick={handleSave}
        disabled={saving}
      >
        {saving ? 'Saving…' : isNew ? 'Activate' : 'Save changes'}
      </button>
    </div>
  );
}
