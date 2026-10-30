from pathlib import Path

from qdrant_client import QdrantClient


BASE_DIR = Path(__file__).resolve().parent
QDRANT_PATH = BASE_DIR / "data" / "qdrant_storage"

client = QdrantClient(
    path=str(QDRANT_PATH)
)

try:
    results, _ = client.scroll(
        collection_name="synergy_website",
        scroll_filter=None,
        limit=20,
        with_payload=True,
        with_vectors=False,
    )

    found = False

    for point in results:
        payload = point.payload or {}

        if payload.get("chunk_type") == "structured_facts":
            found = True

            print("\nStructured vessel facts found:\n")
            print(payload.get("text", ""))

    if not found:
        print("No structured fact chunk was found.")

finally:
    client.close()