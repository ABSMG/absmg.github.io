import json
import re
import socket
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "discovered_opportunities.json"
OUTPUT_FILE = BASE_DIR / "data" / "verified_opportunities.json"

TIMEOUT = 15

OPPORTUNITY_KEYWORDS = [
    "scholarship",
    "scholarships",
    "fellowship",
    "grant",
    "funding",
    "internship",
    "internships",
    "job",
    "jobs",
    "career",
    "course",
    "courses",
    "training",
    "opportunity",
    "opportunities",
    "application",
    "apply",
]

TRUSTED_DOMAIN_PATTERNS = [
    ".edu",
    ".ac.",
    ".gov",
    ".org",
    "un.org",
    "worldbank.org",
    "afdb.org",
    "mastercardfdn.org",
    "commonwealthscholarships",
    "erasmus-plus.ec.europa.eu",
]


def clean_text(value):
    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value)).strip()


def get_domain(url):
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower().split(":")[0]
    except Exception:
        return ""


def is_valid_url(url):
    try:
        parsed = urlparse(url)

        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.netloc)
        )
    except Exception:
        return False


def is_trusted_domain(url):
    domain = get_domain(url)

    if not domain:
        return False

    return any(
        pattern in domain
        for pattern in TRUSTED_DOMAIN_PATTERNS
    )


def fetch_page(url):
    """
    Checks whether the source page is reachable.

    Returns:
        {
            "reachable": bool,
            "status_code": int or None,
            "final_url": str,
            "content_type": str,
            "title": str,
            "content": str,
            "error": str or None
        }
    """

    result = {
        "reachable": False,
        "status_code": None,
        "final_url": url,
        "content_type": "",
        "title": "",
        "content": "",
        "error": None,
    }

    try:
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; OpportunityBridgeBot/1.0; "
                    "+https://absmg.github.io/)"
                )
            },
        )

        with urlopen(request, timeout=TIMEOUT) as response:
            status_code = response.getcode()
            final_url = response.geturl()
            content_type = response.headers.get("Content-Type", "")

            raw = response.read(500000)

            try:
                content = raw.decode("utf-8", errors="ignore")
            except Exception:
                content = ""

            title_match = re.search(
                r"<title[^>]*>(.*?)</title>",
                content,
                flags=re.IGNORECASE | re.DOTALL,
            )

            title = ""

            if title_match:
                title = clean_text(
                    re.sub("<.*?>", " ", title_match.group(1))
                )

            result.update(
                {
                    "reachable": 200 <= status_code < 400,
                    "status_code": status_code,
                    "final_url": final_url,
                    "content_type": content_type,
                    "title": title,
                    "content": content,
                }
            )

    except HTTPError as error:
        result["status_code"] = error.code
        result["error"] = f"HTTP {error.code}"

    except (URLError, socket.timeout) as error:
        result["error"] = str(error)

    except Exception as error:
        result["error"] = str(error)

    return result


def contains_opportunity_keyword(text):
    text = clean_text(text).lower()

    return any(
        keyword in text
        for keyword in OPPORTUNITY_KEYWORDS
    )


def determine_verification(item):
    url = clean_text(
        item.get("url")
        or item.get("link")
        or item.get("source_url")
    )

    title = clean_text(
        item.get("title")
    )

    description = clean_text(
        item.get("description")
        or item.get("summary")
    )

    result = {
        "verification_level": "failed",
        "source_verified": False,
        "page_reachable": False,
        "source_domain_trusted": False,
        "opportunity_relevant": False,
        "needs_human_review": True,
        "verification_reason": "",
        "checked_url": url,
        "final_url": url,
        "http_status": None,
    }

    # -----------------------------------------
    # 1. URL validation
    # -----------------------------------------

    if not is_valid_url(url):
        result["verification_reason"] = "Invalid or missing URL."
        return result

    # -----------------------------------------
    # 2. Domain trust check
    # -----------------------------------------

    trusted_domain = is_trusted_domain(url)

    result["source_domain_trusted"] = trusted_domain

    # -----------------------------------------
    # 3. Reachability check
    # -----------------------------------------

    page = fetch_page(url)

    result["page_reachable"] = page["reachable"]
    result["http_status"] = page["status_code"]
    result["final_url"] = page["final_url"]

    if not page["reachable"]:
        result["verification_reason"] = (
            "Source page could not be reached."
        )
        return result

    # -----------------------------------------
    # 4. Opportunity relevance check
    # -----------------------------------------

    page_text = page["title"] + " " + page["content"]

    relevant = contains_opportunity_keyword(
        f"{title} {description} {page_text}"
    )

    result["opportunity_relevant"] = relevant

    if not relevant:
        result["verification_reason"] = (
            "Source page was reachable but no "
            "opportunity-related information was detected."
        )
        return result

    # -----------------------------------------
    # 5. Verification level
    # -----------------------------------------

    if trusted_domain:
        result["verification_level"] = "source_checked"
        result["source_verified"] = True
        result["verification_reason"] = (
            "Source domain is trusted, the page is reachable, "
            "and opportunity-related information was detected."
        )

    else:
        result["verification_level"] = "page_checked"
        result["source_verified"] = True
        result["verification_reason"] = (
            "Source page is reachable and contains "
            "opportunity-related information, but the domain "
            "is not in the trusted-domain list."
        )

    return result


def verify_item(item):
    verification = determine_verification(item)

    verified_item = dict(item)

    verified_item.update(verification)

    # Do not keep the full downloaded HTML in the JSON database.
    verified_item.pop("content", None)

    return verified_item


def main():
    if not INPUT_FILE.exists():
        print(f"Input file not found: {INPUT_FILE}")
        return

    try:
        data = json.loads(
            INPUT_FILE.read_text(encoding="utf-8")
        )
    except Exception as error:
        print(f"Could not read input JSON: {error}")
        return

    items = data.get("items", [])

    verified_items = []

    source_checked = 0
    page_checked = 0
    failed = 0

    print("=" * 60)
    print("OPPORTUNITYBRIDGE VERIFICATION ENGINE")
    print("=" * 60)

    for index, item in enumerate(items, start=1):
        title = clean_text(item.get("title"))

        print()
        print(f"[{index}/{len(items)}] {title}")

        verified = verify_item(item)

        level = verified.get(
            "verification_level",
            "failed"
        )

        print(f"Verification level: {level}")
        print(
            f"Source trusted: "
            f"{verified.get('source_domain_trusted')}"
        )
        print(
            f"Page reachable: "
            f"{verified.get('page_reachable')}"
        )
        print(
            f"Relevant: "
            f"{verified.get('opportunity_relevant')}"
        )

        if level == "source_checked":
            source_checked += 1

        elif level == "page_checked":
            page_checked += 1

        else:
            failed += 1

        verified_items.append(verified)

    output = {
        "verification_engine_version": "2.0",
        "total_checked": len(verified_items),
        "source_checked": source_checked,
        "page_checked": page_checked,
        "failed": failed,
        "items": verified_items,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)
    print(f"Total checked: {len(verified_items)}")
    print(f"Source checked: {source_checked}")
    print(f"Page checked: {page_checked}")
    print(f"Failed: {failed}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
