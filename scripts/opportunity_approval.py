from pathlib import Path
from urllib.parse import urlparse
import json


ROOT = Path(__file__).resolve().parents[1]

INPUT = ROOT / "data" / "verified_opportunities.json"
OUTPUT = ROOT / "data" / "approved_opportunities.json"


REQUIRED_KEYWORDS = {
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
}


def clean(value):
    return str(value or "").strip()


def valid_url(url):
    try:
        parsed = urlparse(clean(url))

        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.netloc)
        )

    except Exception:
        return False


def has_opportunity_keyword(item):
    title = clean(
        item.get("title")
    ).lower()

    description = clean(
        item.get("description")
        or item.get("summary")
    ).lower()

    matched_keywords = [
        clean(keyword).lower()
        for keyword in item.get(
            "matched_keywords",
            []
        )
    ]

    combined = (
        f"{title} "
        f"{description} "
        f"{' '.join(matched_keywords)}"
    )

    return any(
        keyword in combined
        for keyword in REQUIRED_KEYWORDS
    )


def approve(item):
    title = clean(
        item.get("title")
    )

    source_url = clean(
        item.get("source_url")
        or item.get("url")
        or item.get("link")
    )

    verification_level = clean(
        item.get("verification_level")
    )

    source_verified = bool(
        item.get("source_verified", False)
    )

    page_reachable = bool(
        item.get("page_reachable", False)
    )

    opportunity_relevant = bool(
        item.get("opportunity_relevant", False)
    )

    # -----------------------------------------
    # 1. Title
    # -----------------------------------------

    if not title:
        return False, "Missing title"

    # -----------------------------------------
    # 2. Source URL
    # -----------------------------------------

    if not valid_url(source_url):
        return False, "Invalid source URL"

    # -----------------------------------------
    # 3. Verification level
    # -----------------------------------------

    if verification_level not in {
        "source_checked",
        "page_checked",
    }:
        return False, (
            "Opportunity did not pass "
            "verification engine"
        )

    # -----------------------------------------
    # 4. Source verification
    # -----------------------------------------

    if not source_verified:
        return False, (
            "Source has not passed "
            "source verification"
        )

    # -----------------------------------------
    # 5. Page reachability
    # -----------------------------------------

    if not page_reachable:
        return False, (
            "Source page is not reachable"
        )

    # -----------------------------------------
    # 6. Opportunity relevance
    # -----------------------------------------

    if not opportunity_relevant:
        return False, (
            "Source page is not recognized "
            "as an opportunity"
        )

    # -----------------------------------------
    # 7. Opportunity keyword
    # -----------------------------------------

    if not has_opportunity_keyword(item):
        return False, (
            "Opportunity type not recognized"
        )

    # -----------------------------------------
    # Passed
    # -----------------------------------------

    if verification_level == "source_checked":
        return True, (
            "Passed source verification, "
            "page reachability and opportunity checks"
        )

    return True, (
        "Passed page verification, "
        "page reachability and opportunity checks"
    )


def main():

    print("=" * 60)
    print("OPPORTUNITYBRIDGE APPROVAL ENGINE v2.0")
    print("=" * 60)

    if not INPUT.exists():
        raise SystemExit(
            "ERROR: verified_opportunities.json was not found."
        )

    try:
        data = json.loads(
            INPUT.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:
        raise SystemExit(
            f"ERROR: Could not read verification data: {error}"
        )

    items = data.get(
        "items",
        []
    )

    approved = []
    rejected = []

    for item in items:

        is_approved, reason = approve(
            item
        )

        updated = dict(item)

        updated["approval_status"] = (
            "approved"
            if is_approved
            else "rejected"
        )

        updated["approval_reason"] = reason

        if is_approved:
            approved.append(updated)
        else:
            rejected.append(updated)

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result = {
        "approval_engine_version": "2.0",
        "approved_at": data.get(
            "verified_at",
            ""
        ),
        "total_checked": len(items),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "approved_items": approved,
    }

    OUTPUT.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print()
    print(f"Checked: {len(items)}")
    print(f"Approved: {len(approved)}")
    print(f"Rejected: {len(rejected)}")
    print()
    print(f"Saved: {OUTPUT}")
    print("=" * 60)


if __name__ == "__main__":
    main()
