"""
Vector store setup for Phase 2 RAG scoring.
Chunks knowledge base files and embeds them into ChromaDB.
"""

import os
import re
import chromadb
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

CHROMA_DIR = "./chroma_db"
EMBED_MODEL = "text-embedding-3-small"

# Default knowledge files (used when no profile provided, e.g. standalone testing)
_DEFAULT_KNOWLEDGE_DIR = "knowledge/juan"
_DEFAULT_COLLECTION_NAME = "juan_profile"
_DEFAULT_KNOWLEDGE_FILES = {
    "master-cv-profile.md": "profile",
    "master-cv-experience.md": "experience",
}


def _resolve_knowledge_config(profile: dict | None):
    """Extract knowledge dir, collection name, and files dict from a profile.

    profile["knowledge"]["profile_files"] is a list of filenames.
    We infer doc_type from filename: if 'experience' in name → 'experience', else → 'profile'.
    Returns (knowledge_dir, collection_name, files_dict).
    """
    if not profile:
        return _DEFAULT_KNOWLEDGE_DIR, _DEFAULT_COLLECTION_NAME, _DEFAULT_KNOWLEDGE_FILES

    knowledge = profile.get("knowledge") or {}
    knowledge_dir = knowledge.get("dir", _DEFAULT_KNOWLEDGE_DIR)
    collection_name = knowledge.get("collection_name", _DEFAULT_COLLECTION_NAME)
    profile_files = knowledge.get("profile_files") or []

    files_dict = {}
    for fname in profile_files:
        if "experience" in fname.lower():
            doc_type = "experience"
        else:
            doc_type = "profile"
        files_dict[fname] = doc_type

    if not files_dict:
        files_dict = _DEFAULT_KNOWLEDGE_FILES

    return knowledge_dir, collection_name, files_dict


def _chunk_markdown(text, source_file, doc_type, max_chars=800, overlap=100):
    """
    Split markdown into chunks. Splits on ## headings first,
    then further splits large sections by paragraph.
    Returns list of {text, source, doc_type, section} dicts.
    """
    chunks = []

    # Split on ## headings (keep heading with its content)
    sections = re.split(r"\n(?=## )", text)

    for section in sections:
        if not section.strip():
            continue

        # Extract section title
        first_line = section.split("\n", 1)[0].strip()
        section_title = first_line.lstrip("#").strip()

        if len(section) <= max_chars:
            chunks.append(
                {
                    "text": section.strip(),
                    "source": source_file,
                    "doc_type": doc_type,
                    "section": section_title,
                }
            )
        else:
            # Split large sections by paragraph with overlap
            paragraphs = re.split(r"\n\n+", section)
            current = ""
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                if len(current) + len(para) + 2 <= max_chars:
                    current = (current + "\n\n" + para).strip()
                else:
                    if current:
                        chunks.append(
                            {
                                "text": current,
                                "source": source_file,
                                "doc_type": doc_type,
                                "section": section_title,
                            }
                        )
                    # Start new chunk with overlap from end of previous
                    overlap_text = current[-overlap:] if len(current) > overlap else current
                    current = (overlap_text + "\n\n" + para).strip() if overlap_text else para
            if current:
                chunks.append(
                    {
                        "text": current,
                        "source": source_file,
                        "doc_type": doc_type,
                        "section": section_title,
                    }
                )

    return chunks


def _embed_texts(texts, client):
    """Embed a list of texts using OpenAI. Returns list of vectors."""
    # Batch in groups of 100 (API limit)
    all_embeddings = []
    for i in range(0, len(texts), 100):
        batch = texts[i : i + 100]
        response = client.embeddings.create(model=EMBED_MODEL, input=batch)
        all_embeddings.extend([r.embedding for r in response.data])
    return all_embeddings


def build_vectorstore(profile=None, chroma_dir=CHROMA_DIR, force_rebuild=False):
    """
    Build or load the ChromaDB vector store from knowledge base files.
    Reads knowledge dir, collection name, and files from the user profile.
    Returns the ChromaDB collection.
    """
    knowledge_dir, collection_name, knowledge_files = _resolve_knowledge_config(profile)

    chroma_client = chromadb.PersistentClient(path=chroma_dir)

    # Check if collection already exists
    existing = [c.name for c in chroma_client.list_collections()]
    if collection_name in existing:
        if force_rebuild:
            chroma_client.delete_collection(collection_name)
        else:
            collection = chroma_client.get_collection(collection_name)
            if collection.count() > 0:
                print(f"Vectorstore loaded: {collection.count()} chunks in '{collection_name}'")
                return collection
            # Empty collection - rebuild
            chroma_client.delete_collection(collection_name)

    print(f"Building vectorstore for '{collection_name}' from {knowledge_dir}...")
    openai_client = OpenAI()
    collection = chroma_client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    all_chunks = []
    for filename, doc_type in knowledge_files.items():
        filepath = os.path.join(knowledge_dir, filename)
        if not os.path.exists(filepath):
            print(f"  Skipping {filename} (not found at {filepath})")
            continue
        with open(filepath, "r") as f:
            text = f.read()
        chunks = _chunk_markdown(text, filename, doc_type)
        all_chunks.extend(chunks)
        print(f"  {filename}: {len(chunks)} chunks")

    print(f"  Total: {len(all_chunks)} chunks. Embedding with {EMBED_MODEL}...")
    texts = [c["text"] for c in all_chunks]
    embeddings = _embed_texts(texts, openai_client)

    # Add to ChromaDB
    collection.add(
        ids=[f"chunk_{i}" for i in range(len(all_chunks))],
        embeddings=embeddings,
        documents=texts,
        metadatas=[
            {
                "source": c["source"],
                "doc_type": c["doc_type"],
                "section": c["section"],
            }
            for c in all_chunks
        ],
    )

    print(f"Vectorstore built: {collection.count()} chunks stored in '{collection_name}'")
    return collection


def retrieve_relevant_chunks(query, collection, n_results=8):
    """
    Retrieve the top-n most relevant chunks for a query.
    Returns list of (text, metadata) tuples.
    """
    openai_client = OpenAI()
    response = openai_client.embeddings.create(model=EMBED_MODEL, input=[query])
    query_embedding = response.data[0].embedding

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append(
            {
                "text": doc,
                "source": meta.get("source", ""),
                "doc_type": meta.get("doc_type", ""),
                "section": meta.get("section", ""),
                "relevance": round(1 - dist, 3),  # cosine similarity
            }
        )

    return chunks


if __name__ == "__main__":
    import sys
    from user_config import load_profile, list_profiles

    profile_id = sys.argv[1] if len(sys.argv) > 1 else list_profiles()[0]
    profile = load_profile(profile_id)
    print(f"Building vectorstore for profile: {profile_id}")

    collection = build_vectorstore(profile=profile, force_rebuild=True)
    print("\nTest retrieval: 'data platform Snowplow Kafka'")
    chunks = retrieve_relevant_chunks("data platform Snowplow Kafka real-time pipeline", collection)
    for c in chunks:
        print(f"  [{c['relevance']:.2f}] {c['source']} / {c['section']}: {c['text'][:80]}...")
