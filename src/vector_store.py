import json
import os
from pathlib import Path

import faiss
import numpy as np
from dotenv import load_dotenv
from google import genai

from src.document_loader import load_documents, create_chunks


load_dotenv()

# Gemini client
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

EMBEDDING_MODEL = "gemini-embedding-001"

VECTOR_DIR = Path("data/vector_store")
INDEX_PATH = VECTOR_DIR / "airport_policy.index"
CHUNKS_PATH = VECTOR_DIR / "chunks.json"


def generate_embeddings(texts: list[str]) -> np.ndarray:
    """
    Generate Gemini embeddings for a list of texts.
    """

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts
    )

    embeddings = [
        embedding.values
        for embedding in response.embeddings
    ]

    vectors = np.array(
        embeddings,
        dtype="float32"
    )

    # Normalize for cosine similarity
    faiss.normalize_L2(vectors)

    return vectors


def build_vector_store():
    """
    Load policies, create chunks, generate embeddings,
    and store them in FAISS.
    """

    print("Loading policy documents...")

    documents = load_documents()

    print(f"Documents loaded: {len(documents)}")

    chunks = create_chunks(documents)

    print(f"Chunks created: {len(chunks)}")

    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    print("Generating embeddings...")

    vectors = generate_embeddings(texts)

    print(
        f"Embedding shape: {vectors.shape}"
    )

    # Dimension of embedding
    dimension = vectors.shape[1]

    # Inner product on normalized vectors = cosine similarity
    index = faiss.IndexFlatIP(dimension)

    index.add(vectors)

    VECTOR_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # Save FAISS index
    faiss.write_index(
        index,
        str(INDEX_PATH)
    )

    # Save chunk metadata
    with open(
        CHUNKS_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            chunks,
            file,
            indent=2,
            ensure_ascii=False
        )

    print("\nVector store created successfully.")

    print(f"FAISS index: {INDEX_PATH}")
    print(f"Chunk metadata: {CHUNKS_PATH}")
    print(f"Vector dimension: {dimension}")


def load_vector_store():
    """
    Load existing FAISS index and chunk metadata.
    """

    if not INDEX_PATH.exists():
        raise FileNotFoundError(
            "FAISS index not found. "
            "Run build_vector_store() first."
        )

    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(
            "Chunk metadata not found."
        )

    index = faiss.read_index(
        str(INDEX_PATH)
    )

    with open(
        CHUNKS_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        chunks = json.load(file)

    return index, chunks


def search(query: str, top_k: int = 3):
    """
    Perform semantic search against FAISS.
    """

    index, chunks = load_vector_store()

    query_vector = generate_embeddings(
        [query]
    )

    scores, indices = index.search(
        query_vector,
        top_k
    )

    results = []

    for score, index_id in zip(
        scores[0],
        indices[0]
    ):

        if index_id == -1:
            continue

        result = chunks[index_id].copy()

        result["score"] = float(score)

        results.append(result)

    return results


if __name__ == "__main__":

    build_vector_store()

    print("\nTesting semantic search...")

    query = "What is the maximum surge multiplier allowed at SFO?"

    results = search(query, top_k=3)

    print("\nQuery:")
    print(query)

    print("\nTop results:")

    for result in results:

        print("\n" + "=" * 70)

        print(
            f"Score: {result['score']:.4f}"
        )

        print(
            f"Document: {result['document_name']}"
        )

        print(
            f"Airport: {result['airport']}"
        )

        print(
            f"Section: {result['section_number']}"
        )

        print("\nText:")
        print(result["text"])