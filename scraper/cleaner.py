import json
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "website_content.json"
OUTPUT_FILE = BASE_DIR / "data" / "cleaned_content.json"


# Common website navigation and interface text.
NOISE_PHRASES = {
    "explore our services",
    "read more",
    "reach us",
    "experience",
    "maritime excellence",
    "need help with something? we're here",
    "talk to one of our team members",
    "speak with our experts",
    "get the latest news updates",
    "in your mailbox",
}


def normalize_line(line: str) -> str:
    """Normalize whitespace and punctuation for comparison."""
    line = re.sub(r"\s+", " ", line).strip()
    return line.casefold()


def clean_text(text: str) -> str:
    """Remove duplicate lines and common interface clutter."""

    lines = text.splitlines()

    cleaned_lines = []
    seen_lines = set()

    for line in lines:
        line = re.sub(r"\s+", " ", line).strip()

        if not line:
            continue

        normalized = normalize_line(line)

        # Remove common interface text.
        if normalized in NOISE_PHRASES:
            continue

        # Remove duplicate lines across the entire page.
        if normalized in seen_lines:
            continue

        seen_lines.add(normalized)
        cleaned_lines.append(line)

    cleaned_text = "\n".join(cleaned_lines)

    # Normalize malformed animated counter fragments.
    cleaned_text = re.sub(
        r"(?m)^750\s*\n0\s*\n\+\s*$",
        "750+",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"(?m)^34,000\s*\n0\s*$",
        "34,000",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"(?m)^31\s*\n0\s*$",
        "31",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"(?m)^15\s*\n0\s*$",
        "15",
        cleaned_text,
    )

    return cleaned_text.strip()


def process_pages():
    """Read scraped pages, clean content, and save the output."""

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        pages = json.load(file)

    cleaned_pages = []

    for page in pages:
        original_text = page.get("text", "")
        cleaned = clean_text(original_text)

        if not cleaned:
            continue

        cleaned_pages.append({
            "url": page.get("url", ""),
            "title": page.get("title", ""),
            "text": cleaned,
            "retrieved_at": page.get("retrieved_at"),
        })

        print(f"Processed: {page.get('title', 'Untitled page')}")
        print(f"Original characters: {len(original_text)}")
        print(f"Cleaned characters:  {len(cleaned)}")
        print("-" * 40)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            cleaned_pages,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nTotal pages processed: {len(pages)}")
    print(f"Total pages saved: {len(cleaned_pages)}")
    print(f"Output file: {OUTPUT_FILE}")


if __name__ == "__main__":
    process_pages()

