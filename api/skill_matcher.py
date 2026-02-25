"""Semantic skill matcher: compares user skills against job requirements.

Uses embedding-based cosine similarity when available, falls back to exact
substring matching when embeddings are unavailable (no API key or API error).
"""

import logging
from dataclasses import dataclass

from api.embeddings import cosine_similarity, get_embeddings_batch

logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 0.80    # strong match
PARTIAL_THRESHOLD = 0.68  # partial match


@dataclass
class SkillMatch:
    job_skill: str           # original skill text from job
    status: str              # "matched" | "partial" | "none"
    user_skill: str | None   # which user skill matched (if any)
    similarity: float        # best cosine similarity score


def match_skills(
    user_skills: list[str],
    job_skills: list[str],
    db_path: str,
) -> list[SkillMatch]:
    """Match job skills against user skills using embeddings.

    Falls back to exact substring matching if embeddings unavailable.
    """
    if not job_skills:
        return []

    # Normalize all skills
    norm_user = [s.strip().lower().replace("-", " ") for s in user_skills]
    norm_job = [s.strip().lower().replace("-", " ") for s in job_skills]

    # Get embeddings for all unique skills
    all_skills = list(set(norm_user + norm_job))
    embeddings = get_embeddings_batch(all_skills, db_path)

    # Check if we have enough embeddings for semantic matching
    has_embeddings = (
        len(embeddings) > 0
        and all(s in embeddings for s in norm_job)
        and any(s in embeddings for s in norm_user)
    )

    if has_embeddings and norm_user:
        return _semantic_match(norm_user, norm_job, job_skills, embeddings)
    else:
        return _substring_match(norm_user, norm_job, job_skills)


def _semantic_match(
    norm_user: list[str],
    norm_job: list[str],
    original_job_skills: list[str],
    embeddings: dict[str, list[float]],
) -> list[SkillMatch]:
    """Match using cosine similarity of embeddings."""
    results = []
    for i, job_skill in enumerate(norm_job):
        job_emb = embeddings.get(job_skill)
        if job_emb is None:
            results.append(SkillMatch(
                job_skill=original_job_skills[i],
                status="none",
                user_skill=None,
                similarity=0.0,
            ))
            continue

        best_sim = 0.0
        best_user = None
        for user_skill in norm_user:
            user_emb = embeddings.get(user_skill)
            if user_emb is None:
                continue
            sim = cosine_similarity(job_emb, user_emb)
            if sim > best_sim:
                best_sim = sim
                best_user = user_skill

        if best_sim >= MATCH_THRESHOLD:
            status = "matched"
        elif best_sim >= PARTIAL_THRESHOLD:
            status = "partial"
        else:
            status = "none"

        results.append(SkillMatch(
            job_skill=original_job_skills[i],
            status=status,
            user_skill=best_user if status != "none" else None,
            similarity=best_sim,
        ))

    return results


def _substring_match(
    norm_user: list[str],
    norm_job: list[str],
    original_job_skills: list[str],
) -> list[SkillMatch]:
    """Fallback: exact substring matching (current behavior)."""
    results = []
    for i, job_skill in enumerate(norm_job):
        matched_user = None
        for user_skill in norm_user:
            if user_skill in job_skill or job_skill in user_skill:
                matched_user = user_skill
                break

        results.append(SkillMatch(
            job_skill=original_job_skills[i],
            status="matched" if matched_user else "none",
            user_skill=matched_user,
            similarity=1.0 if matched_user else 0.0,
        ))

    return results
