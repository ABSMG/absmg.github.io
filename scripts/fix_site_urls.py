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


def replace_canonical(content, expected):

    parser = SEOURLParser()

    try:
        parser.feed(content)
    except Exception:
        return content

    old = parser.canonical

    if not old:
        return content

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

    if not old:
        return content

    return content.replace(
        old,
        expected,
        1
    )


def replace_legacy_urls(content):

    replacements = {
        "https://absmg.github.io/OpportunityBridge/":
            "https://absmg.github.io/",

        "https://absmg.github.io/OpportunityBridge":
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

    if path.name in EXCLUDED:
        return False

    try:

        content = path.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError:

        return False

    original = content

    expected = expected_url(path)

    # ---------------------------------------------------------
    # 1. Remove legacy /OpportunityBridge/ URLs
    # ---------------------------------------------------------

    content = replace_legacy_urls(
        content
    )

    # ---------------------------------------------------------
    # 2. Repair canonical URL
    # ---------------------------------------------------------

    content = replace_canonical(
        content,
        expected
    )

    # ---------------------------------------------------------
    # 3. Repair Open Graph URL
    # ---------------------------------------------------------

    content = replace_og_url(
        content,
        expected
    )

    # ---------------------------------------------------------
    # 4. Write only if something changed
    # ---------------------------------------------------------

    if content == original:

        return False

    path.write_text(
        content,
        encoding="utf-8"
    )

    return True


def main():

    print("=" * 70)
    print(
        "OPPORTUNITYBRIDGE SITE URL REPAIR v2.0"
    )
    print("=" * 70)

    changed = []

    for path in sorted(
        ROOT.glob("*.html")
    ):

        if process_file(path):

            changed.append(
                path.name
            )

    print()

    if changed:

        print("Updated files:")

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

    print("=" * 70)


if __name__ == "__main__":

    main()
