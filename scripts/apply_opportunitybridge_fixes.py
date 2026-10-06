from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]

DISCOVERY = ROOT / "scripts" / "opportunity_discovery.py"
VERIFIER = ROOT / "scripts" / "opportunity_verifier.py"
APPROVAL = ROOT / "scripts" / "opportunity_approval.py"


def read_file(path):
    return path.read_text(
        encoding="utf-8"
    )


def write_file(path, content):
    path.write_text(
        content,
        encoding="utf-8"
    )


def replace_once(
    content,
    old,
    new,
    label,
):
    if old not in content:
        raise RuntimeError(
            f"Could not find expected section: {label}"
        )

    return content.replace(
        old,
        new,
        1,
    )


def update_discovery():
    print()
    print("=" * 70)
    print("Updating opportunity_discovery.py")
    print("=" * 70)

    content = read_file(
        DISCOVERY
    )

    # --------------------------------------------------------
    # 1. Use the REAL Google News article URL.
    #
    # Previously:
    #     publisher_url or news_url
    #
    # This could send the verifier to a publisher homepage
    # instead of the actual opportunity/news article.
    # --------------------------------------------------------

    old = '''                "source_url":
                    publisher_url or news_url,'''

    new = '''                "source_url":
                    news_url,'''

    content = replace_once(
        content,
        old,
        new,
        "Google News source_url",
    )

    # --------------------------------------------------------
    # 2. Replace title-only deduplication with URL-first
    #    deduplication.
    #
    # URL is a much stronger identifier than title.
    # Title remains a fallback.
    # --------------------------------------------------------

    old = '''def remove_duplicates(items):
    unique = {}

    for item in items:

        key = (
            item.get(
                "title",
                ""
            )
            .strip()
            .lower()
        )

        if key and key not in unique:
            unique[key] = item

    return list(
        unique.values()
    )'''

    new = '''def normalize_url(url):
    """
    Normalize a URL for stable deduplication.
    """

    url = (url or "").strip().lower()

    if not url:
        return ""

    return url.rstrip("/")


def remove_duplicates(items):
    """
    Deduplicate by the real discovered URL first.

    Google News can contain the same opportunity with slightly
    different titles. The URL is a stronger identifier than the
    title, so it is preferred. Title remains a fallback.
    """

    unique = {}

    for item in items:

        source_url = normalize_url(
            item.get("source_url")
            or item.get("news_url")
            or item.get("url")
            or item.get("link")
        )

        title = (
            item.get(
                "title",
                ""
            )
            .strip()
            .lower()
        )

        key = (
            f"url:{source_url}"
            if source_url
            else f"title:{title}"
        )

        if key and key not in unique:
            unique[key] = item

    return list(
        unique.values()
    )'''

    content = replace_once(
        content,
        old,
        new,
        "remove_duplicates",
    )

    # --------------------------------------------------------
    # 3. Increase discovery pool.
    #
    # This DOES NOT mean all 300 will be published.
    # Verification + approval still decide what can become
    # an article.
    # --------------------------------------------------------

    old = '''    payload = {
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "total":
            len(all_items),

        "items":
            all_items[:100],
    }'''

    new = '''    discovery_limit = 300

    payload = {
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "total":
            len(all_items),

        "items":
            all_items[:discovery_limit],
    }'''

    content = replace_once(
        content,
        old,
        new,
        "discovery payload limit",
    )

    old = '''        f"Saved {len(all_items[:100])} discoveries."'''

    new = '''        f"Saved {len(all_items[:discovery_limit])} discoveries."'''

    content = replace_once(
        content,
        old,
        new,
        "discovery saved count",
    )

    write_file(
        DISCOVERY,
        content,
    )

    print(
        "OK: opportunity_discovery.py updated"
    )


def update_verifier():
    print()
    print("=" * 70)
    print("Updating opportunity_verifier.py")
    print("=" * 70)

    content = read_file(
        VERIFIER
    )

    # --------------------------------------------------------
    # 1. Add deadline parsing helpers.
    #
    # datetime/timezone are already imported by the current
    # verifier, so no import removal or replacement is needed.
    # --------------------------------------------------------

    marker = '''def get_domain(url):
    """
    Extract hostname without port.
    '''    

    helpers = '''def parse_deadline_date(value):
    """
    Parse a detected deadline into a timezone-aware UTC datetime.

    Returns None when the value cannot be parsed safely.
    """

    value = clean_text(
        value
    )

    if not value:
        return None

    candidates = [
        value,
        value.replace(
            "Z",
            "+00:00"
        ),
    ]

    for candidate in candidates:

        try:

            parsed = datetime.fromisoformat(
                candidate
            )

            if parsed.tzinfo is None:

                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed.astimezone(
                timezone.utc
            )

        except Exception:
            pass

    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]

    for date_format in date_formats:

        try:

            parsed = datetime.strptime(
                value,
                date_format
            )

            return parsed.replace(
                tzinfo=timezone.utc
            )

        except Exception:
            pass

    return None


def deadline_is_expired(value):
    """
    Return True when a parseable deadline is already in the past.
    """

    parsed = parse_deadline_date(
        value
    )

    if parsed is None:
        return False

    return parsed < datetime.now(
        timezone.utc
    )


'''

    if "def parse_deadline_date(value):" not in content:
        content = replace_once(
            content,
            marker,
            helpers + marker,
            "deadline helper insertion point",
        )

    # --------------------------------------------------------
    # 2. Fix URL fallback bug.
    #
    # IMPORTANT:
    # The previous expression:
    #
    #     item.get(
    #         "source_url"
    #         or "url"
    #         ...
    #     )
    #
    # evaluates "source_url" before item.get().
    # Therefore the other fallbacks were never reached.
    # --------------------------------------------------------

    old = '''    original_discovered_url = clean_text(
        item.get(
            "source_url"
            or "url"
            or "link"
            or "news_url"
        )
    )'''

    new = '''    original_discovered_url = clean_text(
        item.get("source_url")
        or item.get("url")
        or item.get("link")
        or item.get("news_url")
    )'''

    content = replace_once(
        content,
        old,
        new,
        "original discovered URL fallback",
    )

    # --------------------------------------------------------
    # 3. Add deadline_expired to the result structure.
    # --------------------------------------------------------

    if '"deadline_expired": False' not in content:

        old = '''        "deadline": "",
'''

        new = '''        "deadline": "",

        "deadline_expired": False,
'''

        content = replace_once(
            content,
            old,
            new,
            "deadline result field",
        )

    # --------------------------------------------------------
    # 4. Detect expired opportunities immediately after
    #    deadline extraction.
    #
    # Expired opportunities will NOT proceed to article
    # generation.
    # --------------------------------------------------------

    if 'result["deadline_expired"] = deadline_is_expired' not in content:

        pattern = re.compile(
            r'''(?P<indent>\s*)detected_deadline = extract_deadline\(
(?P<body>.*?)
(?P<indent2>\s*)result\["deadline"\] = detected_deadline
''',
            re.DOTALL,
        )

        match = pattern.search(
            content
        )

        if not match:
            raise RuntimeError(
                "Could not find deadline extraction section."
            )

        indent = match.group(
            "indent"
        )

        replacement = (
            match.group(
                "indent"
            )
            + 'detected_deadline = extract_deadline(\n'
            + match.group(
                "body"
            )
            + match.group(
                "indent2"
            )
            + 'result["deadline"] = detected_deadline\n\n'
            + indent
            + 'result["deadline_expired"] = deadline_is_expired(\n'
            + indent
            + '    detected_deadline\n'
            + indent
            + ')\n\n'
            + indent
            + 'if result.get("deadline_expired", False):\n\n'
            + indent
            + '    result["opportunity_relevant"] = False\n\n'
            + indent
            + '    result["needs_human_review"] = False\n\n'
            + indent
            + '    result["opportunity_classification"] = (\n'
            + indent
            + '        "expired_opportunity"\n'
            + indent
            + '    )\n\n'
            + indent
            + '    result["verification_level"] = "failed"\n\n'
            + indent
            + '    result["source_verified"] = False\n\n'
            + indent
            + '    result["verification_reason"] = (\n'
            + indent
            + '        "The detected application deadline has already passed."\n'
            + indent
            + '    )\n\n'
            + indent
            + '    return result\n'
        )

        content = (
            content[:match.start()]
            + replacement
            + content[match.end():]
        )

    write_file(
        VERIFIER,
        content,
    )

    print(
        "OK: opportunity_verifier.py updated"
    )


def update_approval():
    print()
    print("=" * 70)
    print("Updating opportunity_approval.py")
    print("=" * 70)

    content = read_file(
        APPROVAL
    )

    # --------------------------------------------------------
    # 1. Reject expired opportunities at approval stage.
    # --------------------------------------------------------

    if 'item.get("deadline_expired", False)' not in content:

        old = '''    if not item.get("opportunity_relevant", False):
        return False
'''

        new = '''    if not item.get("opportunity_relevant", False):
        return False

    if item.get("deadline_expired", False):
        return False
'''

        if old in content:
            content = replace_once(
                content,
                old,
                new,
                "approval relevance check",
            )

        else:
            raise RuntimeError(
                "Could not find approval relevance check."
            )

    # --------------------------------------------------------
    # 2. Explicitly reject expired classification.
    # --------------------------------------------------------

    if '== "expired_opportunity"' not in content:

        possible_markers = [
            '''    if item.get("opportunity_classification") == "insufficient_opportunity_evidence":
        return False
''',
            '''    if item.get("opportunity_classification") == "likely_news_or_general_content":
        return False
''',
        ]

        inserted = False

        for old in possible_markers:

            if old in content:

                new = (
                    old
                    + '''
    if item.get("opportunity_classification") == "expired_opportunity":
        return False
'''
                )

                content = replace_once(
                    content,
                    old,
                    new,
                    "expired classification approval check",
                )

                inserted = True
                break

        if not inserted:
            print(
                "WARNING: explicit expired classification "
                "check was not inserted because the expected "
                "classification block was not found."
            )

    write_file(
        APPROVAL,
        content,
    )

    print(
        "OK: opportunity_approval.py updated"
    )


def main():

    print()
    print("=" * 70)
    print("OPPORTUNITYBRIDGE SAFE AUTOMATION PATCH")
    print("=" * 70)

    print()
    print(
        "This patch preserves the existing automation architecture."
    )

    print(
        "It does NOT replace or minimize the article generator."
    )

    print(
        "It does NOT remove publishing or index.html updating."
    )

    print()

    update_discovery()

    update_verifier()

    update_approval()

    print()
    print("=" * 70)
    print("PATCH COMPLETE")
    print("=" * 70)

    print()
    print(
        "Files changed:"
    )

    print(
        "1. scripts/opportunity_discovery.py"
    )

    print(
        "2. scripts/opportunity_verifier.py"
    )

    print(
        "3. scripts/opportunity_approval.py"
    )

    print()
    print(
        "NOT changed:"
    )

    print(
        "scripts/opportunity_article_generator.py"
    )

    print()
    print(
        "The existing article generation and publishing system "
        "remains intact."
    )

    print(
        "The existing index.html update/publish step also remains intact."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
