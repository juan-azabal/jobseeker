def merge_profiles(existing: dict, extracted: dict) -> dict:
    """Merge LLM-extracted profile data into existing user profile.

    Returns a new dict with merged values. Never mutates inputs.

    Merge strategy:
    - skills: union, case-insensitive dedup, existing order preserved, new appended
    - domains: existing weights immutable, new domains added with extracted weights
    - seniority_weights, country_weights, company_type_weights: existing preserved if non-empty
    - name, email, languages, home_locations: new CV wins
    - role_type, role_function: new wins if non-null/non-empty, else keep existing
    - track: new wins if non-null, else keep existing
    - exclude_companies: union, dedup, order preserved
    - current_level, target_level: new wins
    """
    result = {}

    # --- Skills: union, case-insensitive dedup, existing order + new appended ---
    existing_skills = list(existing.get("skills") or [])
    extracted_skills = list(extracted.get("skills") or [])
    lower_set = {s.lower() for s in existing_skills}
    merged_skills = list(existing_skills)
    for skill in extracted_skills:
        if skill.lower() not in lower_set:
            merged_skills.append(skill)
            lower_set.add(skill.lower())
    result["skills"] = merged_skills

    # --- Domains: existing weights win for shared keys, new domains added ---
    existing_domains = dict(existing.get("domains") or {})
    extracted_domains = dict(extracted.get("domains") or {})
    merged_domains = {**extracted_domains, **existing_domains}  # existing overrides extracted
    result["domains"] = merged_domains

    # --- Weights: existing preserved if non-empty ---
    for weight_key in ("seniority_weights", "country_weights", "company_type_weights"):
        existing_val = existing.get(weight_key)
        extracted_val = extracted.get(weight_key)
        if existing_val:
            result[weight_key] = dict(existing_val)
        elif extracted_val:
            result[weight_key] = dict(extracted_val)
        # omit if both absent

    # --- Factual fields: new CV wins ---
    for factual_key in ("name", "email", "languages", "home_locations"):
        extracted_val = extracted.get(factual_key)
        existing_val = existing.get(factual_key)
        if extracted_val is not None and extracted_val != [] and extracted_val != "":
            result[factual_key] = extracted_val
        elif existing_val is not None:
            result[factual_key] = existing_val

    # --- role_type, role_function: new wins if non-null/non-empty ---
    for field in ("role_type", "role_function"):
        extracted_val = extracted.get(field)
        existing_val = existing.get(field)
        if extracted_val is not None and extracted_val != "":
            result[field] = extracted_val
        elif existing_val is not None:
            result[field] = existing_val

    # --- track: new wins if non-null ---
    extracted_track = extracted.get("track")
    existing_track = existing.get("track")
    if extracted_track is not None:
        result["track"] = extracted_track
    elif existing_track is not None:
        result["track"] = existing_track

    # --- current_level, target_level: new wins ---
    for level_key in ("current_level", "target_level"):
        extracted_val = extracted.get(level_key)
        existing_val = existing.get(level_key)
        if extracted_val is not None:
            result[level_key] = extracted_val
        elif existing_val is not None:
            result[level_key] = existing_val

    # --- exclude_companies: union, dedup, order preserved ---
    existing_exclude = list(existing.get("exclude_companies") or [])
    extracted_exclude = list(extracted.get("exclude_companies") or [])
    merged_exclude = list(dict.fromkeys(existing_exclude + extracted_exclude))
    result["exclude_companies"] = merged_exclude

    return result
