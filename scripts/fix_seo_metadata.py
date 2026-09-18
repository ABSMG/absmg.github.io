from pathlib import Path
from html import escape
from html.parser import HTMLParser
import re


ROOT = Path(__file__).resolve().parents[1]

BASE_URL = "https://absmg.github.io"


# Pages ambazo hazipaswi kuwa public SEO pages
EXCLUDED = {
    "404.html",
    "login.html",
    "logout.html",
    "register.html",
    "dashboard.html",
    "forgot-password.html",
    "reset-password.html",
}


class MetadataParser(HTMLParser):

    def __init__(self):
        super().__init__()

        self.title = ""
        self.description = ""
        self.robots = ""

        self.og_title = ""
        self.og_description = ""
        self.og_url = ""

        self.canonical = ""

        self.in_title = False

    def handle_starttag(self, tag, attrs):

        tag = tag.lower()

        attributes = dict(attrs)

        # TITLE
        if tag == "title":
            self.in_title = True
            return

        # META
        if tag == "meta":

            name = (
                attributes.get("name", "")
                or ""
            ).lower().strip()

            property_name = (
                attributes.get("property", "")
                or ""
            ).lower().strip()

            content = (
                attributes.get("content", "")
                or ""
            ).strip()

            if name == "description":
                self.description = content

            elif name == "robots":
                self.robots = content

            elif property_name == "og:title":
                self.og_title = content

            elif property_name == "og:description":
                self.og_description = content

            elif property_name == "og:url":
                self.og_url = content

        # CANONICAL
        elif tag == "link":

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

    def handle_endtag(self, tag):

        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):

        if self.in_title:
            self.title += data


def expected_url(path):

    relative = path.relative_to(ROOT).as_posix()

    if relative == "index.html":
        return BASE_URL + "/"

    return BASE_URL + "/" + relative


def insert_into_head(content, markup):

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


def clean_text(text):

    return re.sub(
        r"\s+",
        " ",
        text or ""
    ).strip()


def make_description(parser):

    title = clean_text(parser.title)

    if title:
        description = (
            f"{title}. "
            "Discover scholarships, jobs, internships, "
            "courses and digital opportunities on OpportunityBridge."
        )
    else:
        description = (
            "Discover scholarships, jobs, internships, "
            "online courses and digital opportunities on OpportunityBridge."
        )

    description = clean_text(description)

    # Keep description reasonably short
    if len(description) > 155:

        description = (
            description[:152]
            .rsplit(" ", 1)[0]
            + "..."
        )

    return description


def replace_meta(
    content,
    attribute,
    value,
    attribute_type="name"
):

    pattern = (
        rf'(<meta\s+[^>]*'
        rf'{attribute_type}=["\']'
        rf'{re.escape(attribute)}'
        rf'["\'][^>]*'
        rf'content=["\'])'
        rf'[^"\']*'
        rf'(["\'][^>]*>)'
    )

    replacement = (
        rf'\1{escape(value, quote=True)}\2'
    )

    updated, count = re.subn(
        pattern,
        replacement,
        content,
        count=1,
        flags=re.IGNORECASE
    )

    return updated, count


def replace_canonical(content, expected):

    pattern = (
        r'(<link\s+[^>]*'
        r'rel=["\']canonical["\']'
        r'[^>]*href=["\'])'
        r'[^"\']*'
        r'(["\'][^>]*>)'
    )

    replacement = (
        rf'\1{expected}\2'
    )

    updated, count = re.subn(
        pattern,
        replacement,
        content,
        count=1,
        flags=re.IGNORECASE
    )

    return updated, count


def repair_file(path):

    if path.name in EXCLUDED:
        return False

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

    parser = MetadataParser()

    try:

        parser.feed(content)

    except Exception:

        return False

    title = clean_text(parser.title)

    if not title:

        print(
            f"SKIP: {path.name} "
            "(missing title)"
        )

        return False

    expected = expected_url(path)

    description = (
        parser.description
        or make_description(parser)
    )

    og_title = (
        parser.og_title
        or title
    )

    og_description = (
        parser.og_description
        or description
    )

    # =========================================================
    # 1. REMOVE OLD /OpportunityBridge/ URLs
    # =========================================================

    content = content.replace(
        BASE_URL + "/OpportunityBridge/",
        BASE_URL + "/"
    )

    content = content.replace(
        BASE_URL + "/OpportunityBridge",
        BASE_URL
    )

    # =========================================================
    # 2. CANONICAL
    # =========================================================

    parser2 = MetadataParser()

    try:
        parser2.feed(content)
    except Exception:
        return False

    if parser2.canonical:

        content, _ = replace_canonical(
            content,
            expected
        )

    else:

        content = insert_into_head(
            content,
            (
                f'  <link rel="canonical" '
                f'href="{expected}">'
            )
        )

    # =========================================================
    # 3. ROBOTS
    # =========================================================

    parser3 = MetadataParser()

    try:
        parser3.feed(content)
    except Exception:
        return False

    if parser3.robots:

        content, _ = replace_meta(
            content,
            "robots",
            "index, follow",
            "name"
        )

    else:

        content = insert_into_head(
            content,
            (
                '  <meta name="robots" '
                'content="index, follow">'
            )
        )

    # =========================================================
    # 4. META DESCRIPTION
    # =========================================================

    parser4 = MetadataParser()

    try:
        parser4.feed(content)
    except Exception:
        return False

    if parser4.description:

        content, _ = replace_meta(
            content,
            "description",
            description,
            "name"
        )

    else:

        content = insert_into_head(
            content,
            (
                f'  <meta name="description" '
                f'content="{escape(description, quote=True)}">'
            )
        )

    # =========================================================
    # 5. OG TITLE
    # =========================================================

    if re.search(
        r'<meta\s+[^>]*property=["\']og:title["\']',
        content,
        flags=re.IGNORECASE
    ):

        content, _ = replace_meta(
            content,
            "og:title",
            og_title,
            "property"
        )

    else:

        content = insert_into_head(
            content,
            (
                f'  <meta property="og:title" '
                f'content="{escape(og_title, quote=True)}">'
            )
        )

    # =========================================================
    # 6. OG DESCRIPTION
    # =========================================================

    if re.search(
        r'<meta\s+[^>]*property=["\']og:description["\']',
        content,
        flags=re.IGNORECASE
    ):

        content, _ = replace_meta(
            content,
            "og:description",
            og_description,
            "property"
        )

    else:

        content = insert_into_head(
            content,
            (
                f'  <meta property="og:description" '
                f'content="{escape(og_description, quote=True)}">'
            )
        )

    # =========================================================
    # 7. OG URL
    # =========================================================

    if re.search(
        r'<meta\s+[^>]*property=["\']og:url["\']',
        content,
        flags=re.IGNORECASE
    ):

        content, _ = replace_meta(
            content,
            "og:url",
            expected,
            "property"
        )

    else:

        content = insert_into_head(
            content,
            (
                f'  <meta property="og:url" '
                f'content="{expected}">'
            )
        )

    # =========================================================
    # 8. WRITE ONLY IF CHANGED
    # =========================================================

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
        "OPPORTUNITYBRIDGE SEO METADATA REPAIR"
    )

    print("=" * 70)

    changed = []

    for path in sorted(
        ROOT.glob("*.html")
    ):

        if repair_file(path):

            changed.append(
                path.name
            )

    print()

    if changed:

        print(
            "SEO metadata updated:"
        )

        for filename in changed:

            print(
                f"  ✅ {filename}"
            )

    else:

        print(
            "No SEO metadata changes were required."
        )

    print()

    print(
        f"Files updated: {len(changed)}"
    )

    print()

    print(
        "SEO metadata repair completed."
    )

    print("=" * 70)


if __name__ == "__main__":

    main()
