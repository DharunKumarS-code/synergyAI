import json
import re
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import (
    urljoin,
    urlparse,
    urlunparse,
    urldefrag,
)
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_URL = "https://www.synergymarinegroup.com/"
BASE_DOMAIN = "www.synergymarinegroup.com"

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "website_content.json"

HEADERS = {
    "User-Agent": (
        "SynergyAI-Prototype/0.5 "
        "(educational website content research)"
    )
}

REQUEST_TIMEOUT = 20
REQUEST_DELAY_SECONDS = 1.5

MAX_PAGES = 40
MAX_CRAWL_DEPTH = 3
MAX_REDIRECTS = 5
MAX_TEXT_LENGTH = 50000

RESPECT_ROBOTS_TXT = True

RELEVANT_KEYWORDS = [
    "about",
    "company",
    "service",
    "management",
    "crew",
    "vessel",
    "fleet",
    "technical",
    "marine",
    "offshore",
    "newbuilding",
    "project",
    "sustainability",
    "safety",
    "quality",
    "news",
    "insight",
    "contact",
    "career",
]

EXCLUDED_PATH_KEYWORDS = [
    "/wp-admin",
    "/wp-login",
    "/login",
    "/logout",
    "/cart",
    "/checkout",
    "/search",
    "/feed",
    "/tag/",
    "/author/",
]

EXCLUDED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".zip",
    ".rar",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".mp4",
    ".mp3",
    ".css",
    ".js",
    ".xml",
}


# ============================================================
# 2. URL VALIDATION AND NORMALIZATION
# ============================================================

def normalize_url(url: str) -> str | None:
    """
    Validate a URL and normalize its hostname and path.

    Trailing slashes are preserved because the website may
    distinguish between URLs with and without trailing slashes.
    """

    if not isinstance(url, str) or not url.strip():
        return None

    url, _fragment = urldefrag(url.strip())
    parsed = urlparse(url)

    if parsed.scheme.lower() != "https":
        return None

    if parsed.hostname != BASE_DOMAIN:
        return None

    if parsed.username or parsed.password:
        return None

    if parsed.port not in (None, 443):
        return None

    path = re.sub(r"/+", "/", parsed.path or "/")

    if Path(path.lower()).suffix in EXCLUDED_EXTENSIONS:
        return None

    normalized_url = urlunparse(
        (
            "https",
            BASE_DOMAIN,
            path,
            "",
            "",
            "",
        )
    )

    lower_url = normalized_url.lower()

    if any(
        keyword in lower_url
        for keyword in EXCLUDED_PATH_KEYWORDS
    ):
        return None

    return normalized_url


def is_relevant_url(url: str) -> bool:
    """Prioritize pages likely to contain useful company information."""

    normalized_url = normalize_url(url)

    if not normalized_url:
        return False

    if urlparse(normalized_url).path == "/":
        return True

    path = urlparse(normalized_url).path.lower()

    return any(
        keyword in path
        for keyword in RELEVANT_KEYWORDS
    )


# ============================================================
# 3. ROBOTS.TXT
# ============================================================

def load_robots_parser(
    session: requests.Session,
) -> RobotFileParser | None:
    """Load the website's published crawling rules."""

    robots_url = urljoin(BASE_URL, "/robots.txt")

    try:
        response = session.get(
            robots_url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
        )

        if response.is_redirect or response.is_permanent_redirect:
            print("robots.txt redirected; stopping crawl.")
            response.close()
            return None

        if response.status_code != 200:
            print(
                "Could not verify robots.txt: "
                f"HTTP {response.status_code}"
            )
            response.close()
            return None

        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())

        response.close()

        print("Loaded robots.txt rules.")

        return parser

    except requests.RequestException as error:
        print(f"Could not load robots.txt: {error}")
        return None


def robots_allows(
    parser: RobotFileParser | None,
    url: str,
) -> bool:
    """Check whether the configured crawler may access a URL."""

    if parser is None:
        return False

    return parser.can_fetch(HEADERS["User-Agent"], url)


# ============================================================
# 4. SAFE HTTP REQUESTS AND REDIRECT HANDLING
# ============================================================

def fetch_html(
    session: requests.Session,
    url: str,
    robots_parser: RobotFileParser | None = None,
) -> dict | None:
    """
    Retrieve an HTML page while manually validating redirects.

    Redirects to another domain, HTTP URLs, or unapproved
    destinations are rejected. Redirect loops are detected.
    """

    current_url = normalize_url(url)

    if not current_url:
        print(f"Skipping disallowed URL: {url}")
        return None

    visited_redirects = set()

    for _ in range(MAX_REDIRECTS + 1):

        if current_url in visited_redirects:
            print(f"Redirect loop detected: {current_url}")
            return None

        visited_redirects.add(current_url)

        if RESPECT_ROBOTS_TXT:
            if not robots_allows(robots_parser, current_url):
                print(f"Blocked by robots.txt: {current_url}")
                return None

        try:
            response = session.get(
                current_url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
            )

        except requests.RequestException as error:
            print(f"Request failed for {current_url}: {error}")
            return None

        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")

            if not location:
                print(
                    f"Redirect has no Location header: {current_url}"
                )
                response.close()
                return None

            destination_url = urljoin(current_url, location)
            normalized_destination = normalize_url(destination_url)

            if not normalized_destination:
                print(
                    "Blocked redirect to an unapproved destination: "
                    f"{destination_url}"
                )
                response.close()
                return None

            status_code = response.status_code
            response.close()

            if normalized_destination == current_url:
                print(
                    "Redirect points to the same normalized URL. "
                    f"HTTP {status_code}; Location: {location}"
                )
                return None

            print(
                f"Following approved redirect "
                f"(HTTP {status_code}): "
                f"{normalized_destination}"
            )

            current_url = normalized_destination
            continue

        try:
            response.raise_for_status()

        except requests.RequestException as error:
            print(f"HTTP error for {current_url}: {error}")
            response.close()
            return None

        content_type = response.headers.get(
            "Content-Type",
            "",
        ).lower()

        if "text/html" not in content_type:
            print(f"Skipping non-HTML page: {current_url}")
            response.close()
            return None

        result = {
            "url": current_url,
            "html": response.text,
        }

        response.close()

        return result

    print(f"Redirect limit reached: {url}")

    return None


# ============================================================
# 5. PAGE CONTENT EXTRACTION
# ============================================================

def extract_page_content(html: str) -> dict:
    """Extract the page title, description, and readable text."""

    soup = BeautifulSoup(html, "html.parser")

    title = (
        soup.title.get_text(" ", strip=True)
        if soup.title
        else ""
    )

    description_tag = soup.find(
        "meta",
        attrs={"name": re.compile("^description$", re.I)},
    )

    description = (
        description_tag.get("content", "").strip()
        if description_tag
        else ""
    )

    # Remove scripts and layout elements that are not useful
    # for the textual knowledge base.
    for element in soup.select(
        "script, style, nav, footer, header, "
        "noscript, iframe, svg, form, button, template"
    ):
        element.decompose()

    main_content = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.body
    )

    if main_content is None:
        return {
            "title": title,
            "description": description,
            "text": "",
        }

    cleaned_lines = []
    previous_line = None

    for line in main_content.get_text(
        separator="\n",
        strip=True,
    ).splitlines():

        line = " ".join(line.split())

        if line and line != previous_line:
            cleaned_lines.append(line)

        previous_line = line

    cleaned_text = "\n".join(cleaned_lines)

    return {
        "title": title,
        "description": description,
        "text": cleaned_text[:MAX_TEXT_LENGTH],
    }


# ============================================================
# 6. SCRAPE A SINGLE PAGE
# ============================================================

def scrape_page(
    session: requests.Session,
    url: str,
    robots_parser: RobotFileParser | None = None,
) -> dict | None:
    """Retrieve and extract one approved page."""

    result = fetch_html(
        session,
        url,
        robots_parser,
    )

    if result is None:
        return None

    final_url = result["url"]

    page_content = extract_page_content(result["html"])

    if not page_content["text"].strip():
        print(f"No readable text extracted: {final_url}")
        return None

    return {
        "url": final_url,
        "title": page_content["title"],
        "description": page_content["description"],
        "text": page_content["text"],
        "retrieved_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }


# ============================================================
# 7. INTERNAL LINK DISCOVERY
# ============================================================

def discover_internal_links(
    html: str,
    current_url: str,
) -> list[str]:
    """Discover internal links and prioritize relevant pages."""

    soup = BeautifulSoup(html, "html.parser")

    relevant_links = []
    other_links = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()

        if not href:
            continue

        if href.startswith(
            ("mailto:", "tel:", "javascript:", "data:")
        ):
            continue

        absolute_url = urljoin(current_url, href)
        normalized_url = normalize_url(absolute_url)

        if not normalized_url:
            continue

        if normalized_url in seen:
            continue

        seen.add(normalized_url)

        if is_relevant_url(normalized_url):
            relevant_links.append(normalized_url)
        else:
            other_links.append(normalized_url)

    return relevant_links + other_links


# ============================================================
# 8. WEBSITE CRAWLER
# ============================================================

def scrape_website() -> list[dict]:
    """
    Crawl a limited number of relevant official website pages.

    Only successfully extracted pages are written to the output.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    collected_pages = []
    visited_urls = set()
    queued_urls = {BASE_URL}

    queue = deque([
        (BASE_URL, 0)
    ])

    with requests.Session() as session:

        robots_parser = None

        if RESPECT_ROBOTS_TXT:
            robots_parser = load_robots_parser(session)

            if robots_parser is None:
                print(
                    "Crawl stopped because robots.txt "
                    "could not be verified."
                )
                return []

        while queue and len(visited_urls) < MAX_PAGES:

            requested_url, depth = queue.popleft()

            normalized_url = normalize_url(requested_url)

            if not normalized_url:
                continue

            if normalized_url in visited_urls:
                continue

            if not is_relevant_url(normalized_url):
                continue

            print(
                f"\nProcessing page "
                f"{len(visited_urls) + 1}/{MAX_PAGES}: "
                f"{normalized_url}"
            )

            result = fetch_html(
                session,
                normalized_url,
                robots_parser,
            )

            visited_urls.add(normalized_url)

            if result is None:
                if queue:
                    time.sleep(REQUEST_DELAY_SECONDS)
                continue

            final_url = result["url"]

            visited_urls.add(final_url)

            page_content = extract_page_content(
                result["html"]
            )

            if page_content["text"].strip():

                collected_pages.append({
                    "url": final_url,
                    "title": page_content["title"],
                    "description": page_content["description"],
                    "text": page_content["text"],
                    "retrieved_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                })

                print(
                    f"Extracted: "
                    f"{page_content['title'] or final_url}"
                )

            else:
                print(f"No readable content: {final_url}")

            # Discover links from the HTML already downloaded.
            if depth < MAX_CRAWL_DEPTH:

                discovered_links = discover_internal_links(
                    result["html"],
                    final_url,
                )

                for link in discovered_links:

                    if (
                        link not in visited_urls
                        and link not in queued_urls
                        and is_relevant_url(link)
                    ):
                        queue.append(
                            (link, depth + 1)
                        )

                        queued_urls.add(link)

            if queue and len(visited_urls) < MAX_PAGES:
                time.sleep(REQUEST_DELAY_SECONDS)

    # Remove duplicate canonical URLs.
    unique_pages = []
    saved_urls = set()

    for page in collected_pages:

        canonical_url = page["url"]

        if canonical_url in saved_urls:
            continue

        saved_urls.add(canonical_url)
        unique_pages.append(page)

    OUTPUT_FILE.write_text(
        json.dumps(
            unique_pages,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print(
        f"Crawl completed. "
        f"Pages extracted: {len(unique_pages)}"
    )
    print(f"Saved content to: {OUTPUT_FILE}")
    print("=" * 60)

    return unique_pages


# ============================================================
# 9. ENTRY POINT
# ============================================================

if __name__ == "__main__":
    scrape_website()
