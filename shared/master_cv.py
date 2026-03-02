"""Master CV JSON schema validation and ID generators."""

MASTER_CV_SCHEMA_VERSION = "1.0"

_REQUIRED_WORK_FIELDS = ("id", "company", "position", "highlights")
_REQUIRED_EDU_FIELDS = ("id", "institution", "area")
_REQUIRED_SKILL_FIELDS = ("name",)


def validate_master_cv(data: dict) -> list[str]:
    """Return list of error strings. Empty list means valid."""
    if not isinstance(data, dict):
        return ["Root must be a dict"]

    errors: list[str] = []

    if "version" not in data:
        errors.append("Missing required field: version")

    _validate_work(data.get("work", []), errors)
    _validate_education(data.get("education", []), errors)
    _validate_skills(data.get("skills", []), errors)

    return errors


def _validate_work(work: object, errors: list[str]) -> None:
    if not isinstance(work, list):
        errors.append("work must be a list")
        return
    for i, entry in enumerate(work):
        prefix = f"work[{i}]"
        for field in _REQUIRED_WORK_FIELDS:
            if field not in entry:
                errors.append(f"{prefix} missing required field: {field}")
        if "highlights" in entry and not isinstance(entry["highlights"], list):
            errors.append(f"{prefix}.highlights must be a list")


def _validate_education(education: object, errors: list[str]) -> None:
    if not isinstance(education, list):
        errors.append("education must be a list")
        return
    for i, entry in enumerate(education):
        prefix = f"education[{i}]"
        for field in _REQUIRED_EDU_FIELDS:
            if field not in entry:
                errors.append(f"{prefix} missing required field: {field}")


def _validate_skills(skills: object, errors: list[str]) -> None:
    if not isinstance(skills, list):
        errors.append("skills must be a list")
        return
    for i, entry in enumerate(skills):
        for field in _REQUIRED_SKILL_FIELDS:
            if field not in entry:
                errors.append(f"skills[{i}] missing required field: {field}")


def generate_work_id(index: int) -> str:
    return f"work_{index:03d}"


def generate_edu_id(index: int) -> str:
    return f"edu_{index:03d}"


def generate_cert_id(index: int) -> str:
    return f"cert_{index:03d}"


def generate_proj_id(index: int) -> str:
    return f"proj_{index:03d}"
