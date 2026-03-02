"""ChromaDB vectorstore for Master CV — per-user collections for work/highlight/skill search."""

import os

import chromadb

CHROMA_DIR = os.environ.get("MASTER_CV_CHROMA_DIR", "data/master_cv_chroma")

_clients: dict[str, chromadb.ClientAPI] = {}


def _get_client() -> chromadb.ClientAPI:
    if CHROMA_DIR not in _clients:
        os.makedirs(CHROMA_DIR, exist_ok=True)
        _clients[CHROMA_DIR] = chromadb.PersistentClient(path=CHROMA_DIR)
    return _clients[CHROMA_DIR]


def get_collection(user_id: int) -> chromadb.Collection:
    """Return or create the per-user Master CV collection."""
    client = _get_client()
    return client.get_or_create_collection(name=f"master_cv_{user_id}")


def index_master_cv(user_id: int, master_cv: dict) -> None:
    """Clear collection and re-index all work, highlight, and skill entries."""
    col = get_collection(user_id)

    existing = col.get()
    if existing["ids"]:
        col.delete(ids=existing["ids"])

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    _collect_work(master_cv.get("work", []), ids, documents, metadatas)
    _collect_skills(master_cv.get("skills", []), ids, documents, metadatas)

    if ids:
        col.add(ids=ids, documents=documents, metadatas=metadatas)


def _collect_work(
    work: list[dict],
    ids: list[str],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    for entry in work:
        work_id = entry["id"]
        highlights = entry.get("highlights", [])
        summary = entry.get("summary") or ""
        skills = " ".join(entry.get("skills_used", []))

        work_doc = f"{entry['company']} {entry['position']} {summary} {skills}".strip()
        ids.append(work_id)
        documents.append(work_doc)
        metadatas.append({"type": "work", "source": entry.get("source", "")})

        for i, highlight in enumerate(highlights):
            ids.append(f"{work_id}_hl_{i}")
            documents.append(highlight)
            metadatas.append({"type": "highlight", "work_id": work_id})


def _collect_skills(
    skills: list[dict],
    ids: list[str],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    for i, skill in enumerate(skills):
        keywords = " ".join(skill.get("keywords", []))
        skill_doc = f"{skill['name']} {keywords}".strip()
        ids.append(f"skill_{i:03d}")
        documents.append(skill_doc)
        metadatas.append({"type": "skill"})


def query_similar_work(user_id: int, query_text: str, n_results: int = 4) -> list[dict]:
    """Query for work entries most similar to query_text."""
    col = get_collection(user_id)
    count = col.count()
    if count == 0:
        return []
    n = min(n_results, count)
    result = col.query(
        query_texts=[query_text],
        n_results=n,
        where={"type": {"$eq": "work"}},
    )
    return _flatten_query_result(result)


def query_similar_highlights(user_id: int, query_text: str, n_results: int = 10) -> list[dict]:
    """Query for highlights most similar to query_text."""
    col = get_collection(user_id)
    count = col.count()
    if count == 0:
        return []
    n = min(n_results, count)
    result = col.query(
        query_texts=[query_text],
        n_results=n,
        where={"type": {"$eq": "highlight"}},
    )
    return _flatten_query_result(result)


def _flatten_query_result(result: dict) -> list[dict]:
    out = []
    for i, doc_id in enumerate(result["ids"][0]):
        out.append(
            {
                "id": doc_id,
                "document": result["documents"][0][i],
                "metadata": result["metadatas"][0][i],
                "distance": result["distances"][0][i],
            }
        )
    return out
