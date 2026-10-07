from pathlib import Path
from html.parser import HTMLParser


ROOT = Path(__file__).resolve().parents[1]

BASE_URL = "https://absmg.github.io"

EXCLUDED = {
    "404.html",
}


class SEOURLParser(HTMLParser):

    def __init__(self):
        super().__init__()

        self.canonical = ""
        self.og_url = ""

    def handle_starttag(self, tag, attrs):

        tag = tag.lower()

        attributes = dict(attrs)

        # =====================================================
        # CANONICAL
        # =====================================================

        if tag == "link":

            rel = (
                attributes.get("rel", "")
                or ""
            ).lower().strip()

            href = (
                attributes.get("href", "")
                or ""
            ).strip()

            if rel == "canonical":

                self.canonical = href

        # =====================================================
        # OPEN GRAPH URL
        # =====================================================

        elif tag == "meta":

            property_name = (
                attributes.get("property", "")
                or ""
            ).lower().strip()

            content = (
                attributes.get("content", "")
                or ""
            ).strip()

            if property_name == "og:url":

                self.og_url = content


def expected_url(path):

    relative = path.relative_to(ROOT).as_posix()

    if relative == "index.html":

        return BASE_URL + "/"

    return BASE_URL + "/" + relative


def insert_into_head(content, markup):

    """
    Add SEO markup immediately before </head>.
    """

    import re

    match = re.search(
        r"</head\s*>",
        content,
        flags=re.IGNORECASE
    )

    if not match:

        return content

    return (
        content[:match.start()]
        + markup
        + "\n"
        + content[match.start():]
    )


def replace_canonical(content, expected):

    parser = SEOURLParser()

    try:

        parser.feed(content)

    except Exception:

        return content

    old = parser.canonical

    # =========================================================
    # Canonical does not exist
    # =========================================================

    if not old:

        return insert_into_head(
            content,
            (
                f'  <link rel="canonical" '
                f'href="{expected}">'
            )
        )

    # =========================================================
    # Canonical already exists
    # =========================================================

    return content.replace(
        old,
        expected,
        1
    )


def replace_og_url(content, expected):

    parser = SEOURLParser()

    try:

        parser.feed(content)

    except Exception:

        return content

    old = parser.og_url

    # =========================================================
    # OG URL does not exist
    # =========================================================

    if not old:

        return insert_into_head(
            content,
            (
                f'  <meta property="og:url" '
                f'content="{expected}">'
            )
        )

    # =========================================================
    # OG URL already exists
    # =========================================================

    return content.replace(
        old,
        expected,
        1
    )


def replace_legacy_urls(content):

    """
    Remove all known legacy OpportunityBridge URLs.

    The old project-path URL:
        https://absmg.github.io/OpportunityBridge/

    must never remain as a canonical, OG URL, internal URL,
    or other absolute URL in the HTML.
    """

    replacements = {

        # =====================================================
        # HTTPS legacy URL WITH trailing slash
        # =====================================================

        "https://absmg.github.io/OpportunityBridge/":
            "https://absmg.github.io/",

        # =====================================================
        # HTTPS legacy URL WITHOUT trailing slash
        # =====================================================

        "https://absmg.github.io/OpportunityBridge":
            "https://absmg.github.io",

        # =====================================================
        # HTTP legacy URL WITH trailing slash
        # =====================================================

        "http://absmg.github.io/OpportunityBridge/":
            "https://absmg.github.io/",

        # =====================================================
        # HTTP legacy URL WITHOUT trailing slash
        # =====================================================

        "http://absmg.github.io/OpportunityBridge":
            "https://absmg.github.io",
    }

    updated = content

    for old, new in replacements.items():

        updated = updated.replace(
            old,
            new
        )

    return updated


def process_file(path):

    # =========================================================
    # EXCLUDED FILES
    # =========================================================

    if path.name in EXCLUDED:

        return False

    # =========================================================
    # READ FILE
    # =========================================================

    try:

        content = path.read_text(
            encoding="utf-8"
        )

    except (
        UnicodeDecodeError,
        OSError
    ):

        return False

    original = content

    expected = expected_url(path)

    # =========================================================
    # 1. REMOVE LEGACY /OpportunityBridge/ URLs
    # =========================================================

    content = replace_legacy_urls(
        content
    )

    # =========================================================
    # 2. REPAIR CANONICAL URL
    # =========================================================

    content = replace_canonical(
        content,
        expected
    )

    # =========================================================
    # 3. REPAIR OPEN GRAPH URL
    # =========================================================

    content = replace_og_url(
        content,
        expected
    )

    # =========================================================
    # 4. WRITE ONLY IF SOMETHING CHANGED
    # =========================================================

    if content == original:

        return False

    try:

        path.write_text(
            content,
            encoding="utf-8"
        )

    except OSError:

        return False

    return True


def main():

    print("=" * 70)

    print(
        "OPPORTUNITYBRIDGE SITE URL REPAIR v3.0"
    )

    print("=" * 70)

    changed = []

    # =========================================================
    # PROCESS ROOT HTML FILES
    # =========================================================

    for path in sorted(
        ROOT.glob("*.html")
    ):

        if process_file(path):

            changed.append(
                path.name
            )

    print()

    # =========================================================
    # REPORT UPDATED FILES
    # =========================================================

    if changed:

        print(
            "Updated files:"
        )

        for filename in changed:

            print(
                f"- {filename}"
            )

    else:

        print(
            "No URL repairs were necessary."
        )

    print()

    print(
        f"Files updated: {len(changed)}"
    )

    print()

    # =========================================================
    # CANONICAL STRATEGY
    # =========================================================

    print(
        "Canonical strategy:"
    )

    print(
        f"- Homepage: {BASE_URL}/"
    )

    print(
        f"- Other pages: {BASE_URL}/filename.html"
    )

    print()

    # =========================================================
    # LEGACY URL STRATEGY
    # =========================================================

    print(
        "Legacy URL cleanup:"
    )

    print(
        "- HTTPS /OpportunityBridge/ removed"
    )

    print(
        "- HTTPS /OpportunityBridge removed"
    )

    print(
        "- HTTP /OpportunityBridge/ removed"
    )

    print(
        "- HTTP /OpportunityBridge removed"
    )

    print()

    # =========================================================
    # SEO ELEMENTS
    # =========================================================

    print(
        "SEO URL elements repaired:"
    )

    print(
        "- Canonical URL"
    )

    print(
        "- Open Graph og:url"
    )

    print(
        "- Missing canonical URLs"
    )

    print(
        "- Missing Open Graph URLs"
    )

    print()

    print("=" * 70)


if __name__ == "__main__":

    main()
