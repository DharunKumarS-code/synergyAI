
from pathlib import Path

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

QDRANT_PATH = BASE_DIR / "data" / "qdrant_storage"

COLLECTION_NAME = "synergy_website"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

TOP_K = 3

# Diagnostic threshold only.
# This is not a validated relevance threshold.
# Tune it later using representative test questions.
DIAGNOSTIC_SCORE_THRESHOLD = 0.40


# ============================================================
# 2. LOAD EMBEDDING MODEL
# ============================================================

print("Loading embedding model...")

model = SentenceTransformer(MODEL_NAME)

print("Embedding model loaded successfully.")


# ============================================================
# 3. SEARCH THE KNOWLEDGE BASE
# ============================================================

def search_knowledge_base(
    question: str,
    limit: int = TOP_K,
):
    """
    Search Qdrant for content related to the question.

    Returns:
        A list of dictionaries containing the retrieved
        content, similarity score, title, and source URL.
    """

    question = question.strip()

    if not question:
        print("Please enter a question.")
        return []

    if limit < 1:
        print("Search limit must be at least 1.")
        return []

    if not QDRANT_PATH.exists():
        print(f"Qdrant database not found: {QDRANT_PATH}")
        return []

    client = None

    try:
        client = QdrantClient(path=str(QDRANT_PATH))

        # Check whether the expected collection exists.
        collections = client.get_collections().collections

        if not any(
            collection.name == COLLECTION_NAME
            for collection in collections
        ):
            print(
                f"Collection '{COLLECTION_NAME}' "
                "was not found."
            )
            return []

        # Convert the question into an embedding.
        query_vector = model.encode(
            question,
            normalize_embeddings=True,
        ).tolist()

        # Retrieve the most similar content chunks.
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            with_payload=True,
        ).points

        retrieved = []

        for result in results:
            payload = result.payload or {}

            retrieved.append(
                {
                    "score": float(result.score),
                    "title": payload.get("title", "Unknown"),
                    "url": payload.get("url", ""),
                    "text": payload.get("text", ""),
                    "chunk_type": payload.get(
                        "chunk_type",
                        "regular",
                    ),
                }
            )

        # Display the search results.
        print("\n" + "=" * 65)
        print("SYNERGYAI - SEMANTIC SEARCH EVALUATION")
        print("=" * 65)

        print(f"Question: {question}")
        print(f"Results retrieved: {len(retrieved)}")

        if not retrieved:
            print("\nNo results were returned by Qdrant.")
            return []

        for rank, item in enumerate(retrieved, start=1):
            print(f"\nResult {rank}")
            print("-" * 65)

            print(f"Similarity score: {item['score']:.4f}")
            print(f"Title: {item['title']}")
            print(f"Source: {item['url']}")
            print(f"Chunk type: {item['chunk_type']}")

            if item["score"] < DIAGNOSTIC_SCORE_THRESHOLD:
                print(
                    "Diagnostic: Low similarity score. "
                    "Review this result manually."
                )
            else:
                print(
                    "Diagnostic: Score is above the provisional "
                    "review threshold; relevance is not guaranteed."
                )

            print("\nContent:")
            print(item["text"])

        print("\n" + "=" * 65)

        return retrieved

    except Exception as error:
        print(f"Search error: {error}")
        return []

    finally:
        if client is not None:
            client.close()


# ============================================================
# 4. DIAGNOSTIC EVALUATION
# ============================================================

def evaluate_question(
    question: str,
    expected_terms: list[str],
):
    """
    Check whether expected terms appear in the retrieved text.

    This is a simple diagnostic, not a full relevance metric.
    """

    results = search_knowledge_base(question)

    combined_text = " ".join(
        item["text"] for item in results
    ).lower()

    print("\nEXPECTED INFORMATION CHECK")
    print("-" * 65)

    if not expected_terms:
        print(
            "No expected terms supplied. "
            "Manual review is required."
        )
        return

    for term in expected_terms:
        found = term.lower() in combined_text

        status = "FOUND" if found else "NOT FOUND"

        print(f"{status}: {term}")


# ============================================================
# 5. BUILT-IN TEST SUITE
# ============================================================

def run_test_suite():
    """
    Run known-answer questions and an unsupported question.
    """

    test_cases = [
        {
            "question": (
                "How many tankers are listed under "
                "vessels under management?"
            ),
            "expected_terms": [
                "319",
                "tankers",
                "June 2026",
            ],
        },
        {
            "question": (
                "How many bulk carriers are listed under "
                "vessels under management?"
            ),
            "expected_terms": [
                "287",
                "bulk carriers",
                "June 2026",
            ],
        },
        {
            "question": (
                "What vessel count does the website advertise?"
            ),
            "expected_terms": [
                "750+",
                "vessels",
            ],
        },
        {
            "question": (
                "What is Synergy Marine Group's exact annual revenue?"
            ),
            "expected_terms": [],
        },
    ]

    for index, test in enumerate(test_cases, start=1):
        print(f"\n\nTEST CASE {index}")

        evaluate_question(
            test["question"],
            test["expected_terms"],
        )

        if not test["expected_terms"]:
            print(
                "\nUnsupported-question test: inspect the retrieved "
                "content manually to confirm it does not establish "
                "the company's annual revenue."
            )


# ============================================================
# 6. INTERACTIVE MODE
# ============================================================

if __name__ == "__main__":

    print("\nSynergyAI Semantic Search is ready!")

    print("\nChoose a mode:")
    print("1. Interactive search")
    print("2. Run retrieval diagnostic tests")

    mode = input("\nEnter 1 or 2: ").strip()

    if mode == "2":
        run_test_suite()

    else:
        while True:
            question = input(
                "\nAsk a question (or type 'exit' to quit): "
            ).strip()

            if question.lower() in {"exit", "quit"}:
                print("Closing SynergyAI search.")
                break

            if not question:
                print("Please enter a question.")
                continue

            search_knowledge_base(question)
