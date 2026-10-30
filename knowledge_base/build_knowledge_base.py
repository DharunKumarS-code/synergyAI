
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models


# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "website_content.json"
QDRANT_PATH = BASE_DIR / "data" / "qdrant_storage"
BACKUP_DIR = BASE_DIR / "data" / "qdrant_backups"

COLLECTION_NAME = "synergy_website"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

CHUNK_SIZE = 180
CHUNK_OVERLAP = 40

BATCH_SIZE = 64


# ==========================================
# LOAD SOURCE DATA
# ==========================================

def load_documents():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Source file not found: {INPUT_FILE}"
        )

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        documents = json.load(file)

    if not isinstance(documents, list) or not documents:
        raise ValueError(
            "website_content.json must contain a non-empty list."
        )

    valid_documents = []

    for document in documents:
        if not isinstance(document, dict):
            continue

        text = document.get("text", "")

        if not isinstance(text, str) or not text.strip():
            continue

        valid_documents.append(document)

    if not valid_documents:
        raise ValueError(
            "No valid documents containing text were found."
        )

    return valid_documents


# ==========================================
# CLEAN WEBSITE TEXT
# ==========================================

def clean_text(text):
    """
    Remove repeated adjacent lines and normalize whitespace.

    This preserves the original wording while reducing repeated
    navigation labels and duplicated page elements.
    """

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    cleaned_lines = []
    previous_line = None

    for line in text.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()

        if not line:
            continue

        normalized = line.casefold()

        if previous_line == normalized:
            continue

        cleaned_lines.append(line)
        previous_line = normalized

    return "\n".join(cleaned_lines).strip()


# ==========================================
# SPLIT TEXT INTO CHUNKS
# ==========================================

def split_text(text):
    words = text.split()

    if not words:
        return []

    chunks = []
    start = 0

    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))

        chunk = " ".join(words[start:end]).strip()

        if chunk:
            chunks.append(chunk)

        if end == len(words):
            break

        start = end - CHUNK_OVERLAP

    return chunks


# ==========================================
# EXTRACT STRUCTURED VESSEL FACTS
# ==========================================

def extract_vessel_facts(text):
    """
    Extract the published vessel figures only when all expected
    category labels, numbers, and the reporting date are present.

    The headline figure is checked flexibly because webpage
    extraction may place 750, 0, and + on separate lines.
    """

    if not re.search(
        r"Vessels\s+Under\s+Management",
        text,
        flags=re.IGNORECASE,
    ):
        return None

    if not re.search(
        r"as of June 2026",
        text,
        flags=re.IGNORECASE,
    ):
        return None

    categories = [
        ("Tankers", 319),
        ("Bulk carriers", 287),
        ("Container vessels", 45),
        ("LPG carriers", 40),
        ("Offshore vessels", 34),
        ("LNG carriers", 6),
    ]

    extracted = []

    for label, expected_count in categories:
        pattern = (
            rf"(?<!\d){expected_count}(?!\d)"
            rf"\s+{re.escape(label)}\b"
        )

        if not re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):
            return None

        extracted.append(f"- {label}: {expected_count}")

    # Support both "750+ Vessels" and "750 0 + Vessels".
    headline_pattern = (
        r"750\s*(?:0\s*)?\+\s*Vessels"
    )

    if not re.search(
        headline_pattern,
        text,
        flags=re.IGNORECASE,
    ):
        return None

    return (
        "VESSEL MANAGEMENT FACTS\n"
        "Source: Synergy Marine Group official website.\n"
        "Website headline figure: 750+ vessels.\n"
        "The website states that the category figures represent "
        "vessels under full technical management as of June 2026.\n"
        "Published category figures:\n"
        + "\n".join(extracted)
        + "\n"
        "Important interpretation: The website presents the "
        "headline figure and category figures separately. "
        "Do not assume they have identical scope or add the "
        "category figures to the headline figure."
    )


# ==========================================
# PREPARE DOCUMENT CHUNKS
# ==========================================

def prepare_chunks(documents):
    chunks = []

    for document_index, document in enumerate(documents):
        original_text = document.get("text", "")
        text = clean_text(original_text)

        url = document.get("url", "")
        title = document.get("title", "Website content")

        if not text:
            continue

        retrieved_at = document.get(
            "retrieved_at",
            datetime.now(timezone.utc).isoformat(),
        )

        page_chunks = split_text(text)

        for chunk_index, chunk_text in enumerate(page_chunks):
            chunks.append({
                "title": title,
                "url": url,
                "text": chunk_text,
                "chunk_index": chunk_index,
                "chunk_type": "website_text",
                "document_index": document_index,
                "retrieved_at": retrieved_at,
            })

        vessel_facts = extract_vessel_facts(text)

        if vessel_facts:
            chunks.append({
                "title": "Vessel Management Figures",
                "url": url,
                "text": vessel_facts,
                "chunk_index": 0,
                "chunk_type": "structured_facts",
                "document_index": document_index,
                "retrieved_at": retrieved_at,
            })

    if not chunks:
        raise ValueError(
            "No text chunks were generated from the source data."
        )

    return chunks


# ==========================================
# BACK UP EXISTING QDRANT STORAGE
# ==========================================

def backup_qdrant_storage():
    """
    Create a filesystem backup before modifying the local Qdrant
    storage. Qdrant must not be open elsewhere during the copy.
    """

    if not QDRANT_PATH.exists():
        print("No existing Qdrant storage found; skipping backup.")
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"qdrant_storage_{timestamp}"

    print(f"Backing up local Qdrant storage to:\n{backup_path}")

    shutil.copytree(QDRANT_PATH, backup_path)

    print("Qdrant storage backup completed.")

    return backup_path


# ==========================================
# CREATE AND POPULATE COLLECTION
# ==========================================

def build_knowledge_base():
    print("=" * 60)
    print("SYNERGYAI KNOWLEDGE BASE BUILDER")
    print("=" * 60)

    print("\nLoading scraped website documents...")

    documents = load_documents()

    print(f"Valid source pages: {len(documents)}")

    print("\nPreparing cleaned text chunks...")

    chunks = prepare_chunks(documents)

    structured_count = sum(
        1
        for chunk in chunks
        if chunk["chunk_type"] == "structured_facts"
    )

    print(f"Total chunks prepared: {len(chunks)}")
    print(f"Structured fact chunks: {structured_count}")

    if structured_count == 0:
        raise ValueError(
            "No structured vessel facts were extracted. "
            "The existing knowledge base has not been changed."
        )

    print("\nLoading embedding model...")

    embedding_model = SentenceTransformer(
        EMBEDDING_MODEL
    )

    print("\nGenerating embeddings in batches...")

    texts = [chunk["text"] for chunk in chunks]

    embeddings = embedding_model.encode(
        texts,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    vector_size = len(embeddings[0])

    print(f"Embedding dimensions: {vector_size}")

    # Validate all embeddings before modifying Qdrant.
    if len(embeddings) != len(chunks):
        raise RuntimeError(
            "Embedding count does not match chunk count."
        )

    print("\nCreating backup of existing Qdrant storage...")

    backup_path = backup_qdrant_storage()

    print("\nConnecting to local Qdrant...")

    QDRANT_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    client = QdrantClient(
        path=str(QDRANT_PATH)
    )

    temporary_collection = (
        f"{COLLECTION_NAME}_staging_{uuid.uuid4().hex[:8]}"
    )

    try:
        print(
            f"\nCreating temporary collection: "
            f"{temporary_collection}"
        )

        client.create_collection(
            collection_name=temporary_collection,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

        # Upload in batches to avoid oversized requests.
        for start in range(0, len(chunks), BATCH_SIZE):
            end = min(start + BATCH_SIZE, len(chunks))

            points = []

            for index in range(start, end):
                points.append(
                    models.PointStruct(
                        id=index,
                        vector=embeddings[index].tolist(),
                        payload=chunks[index],
                    )
                )

            client.upsert(
                collection_name=temporary_collection,
                points=points,
                wait=True,
            )

            print(
                f"Uploaded chunks {start + 1}-{end} "
                f"of {len(chunks)}"
            )

        # Confirm the temporary collection has the expected points.
        collection_info = client.get_collection(
            collection_name=temporary_collection
        )

        stored_count = collection_info.points_count

        if stored_count != len(chunks):
            raise RuntimeError(
                f"Validation failed: expected {len(chunks)} points, "
                f"but Qdrant reports {stored_count}."
            )

        print("\nTemporary collection validated successfully.")

        # The old collection is retained until the new collection
        # is fully prepared and validated.
        old_collection_exists = client.collection_exists(
            COLLECTION_NAME
        )

        if old_collection_exists:
            print(
                f"\nReplacing existing collection: "
                f"{COLLECTION_NAME}"
            )

            client.delete_collection(
                collection_name=COLLECTION_NAME
            )

        try:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )

            # Copy validated points from the staging collection.
            offset = None

            while True:
                records, offset = client.scroll(
                    collection_name=temporary_collection,
                    limit=BATCH_SIZE,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True,
                )

                if not records:
                    break

                client.upload_points(
                    collection_name=COLLECTION_NAME,
                    points=[
                        models.PointStruct(
                            id=record.id,
                            vector=record.vector,
                            payload=record.payload,
                        )
                        for record in records
                    ],
                    wait=True,
                )

                if offset is None:
                    break

            final_info = client.get_collection(
                collection_name=COLLECTION_NAME
            )

            if final_info.points_count != len(chunks):
                raise RuntimeError(
                    "Final collection validation failed."
                )

        except Exception:
            # Remove the incomplete replacement collection.
            if client.collection_exists(COLLECTION_NAME):
                client.delete_collection(COLLECTION_NAME)

            # Recreate the old collection from the validated staging
            # collection when possible.
            if old_collection_exists:
                client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE,
                    ),
                )

                offset = None

                while True:
                    records, offset = client.scroll(
                        collection_name=temporary_collection,
                        limit=BATCH_SIZE,
                        offset=offset,
                        with_payload=True,
                        with_vectors=True,
                    )

                    if not records:
                        break

                    client.upload_points(
                        collection_name=COLLECTION_NAME,
                        points=[
                            models.PointStruct(
                                id=record.id,
                                vector=record.vector,
                                payload=record.payload,
                            )
                            for record in records
                        ],
                        wait=True,
                    )

                    if offset is None:
                        break

            raise

        print("\nRemoving temporary collection...")

        client.delete_collection(
            collection_name=temporary_collection
        )

        print("\n" + "=" * 60)
        print("KNOWLEDGE BASE BUILT SUCCESSFULLY")
        print("=" * 60)
        print(f"Source pages: {len(documents)}")
        print(f"Stored chunks: {len(chunks)}")
        print(f"Structured facts: {structured_count}")
        print(f"Collection: {COLLECTION_NAME}")

        if backup_path:
            print(f"Backup location: {backup_path}")

    finally:
        client.close()


if __name__ == "__main__":
    build_knowledge_base()

