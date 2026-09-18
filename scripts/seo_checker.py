from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse
import re


ROOT = Path(__file__).resolve().parents[1]

BASE_URL = "https://absmg.github.io"


EXCLUDED = {
    "404.html",

    "login.html",
    "logout.html",
    "register.html",
    "dashboard.html",
    "forgot-password.html",
    "reset-password.html",

    "privacy.html",
    "disclaimer.html",
}


class SEOParser(HTMLParser):

    def __init__(self):
        super().__init__()

        self.title = ""
        self.h1_count = 0
        self.lang = ""

        self.meta_description = False
        self.meta_robots = False

        self.og_title = False
        self.og_description = False
        self.og_url = ""

        self.canonical = ""

        self.in_title = False

    def handle_starttag(self, tag, attrs):

        tag = tag.lower()

        attributes = dict(attrs)

        if tag == "html":

            self.lang = (
                attributes.get("lang", "")
                or ""
            ).strip()

        elif tag == "title":

            self.in_title = True

        elif tag == "h1":

            self.h1_count += 1

        elif tag == "meta":

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

            if (
                name == "description"
                and content
            ):
                self.meta_description = True

            if (
                name == "robots"
                and content
            ):
                self.meta_robots = True

            if (
                property_name == "og:title"
                and content
            ):
                self.og_title = True

            if (
                property_name == "og:description"
                and content
            ):
                self.og_description = True

            if (
                property_name == "og:url"
                and content
            ):
                self.og_url = content

        elif tag == "link":

            rel = (
                attributes.get("rel", "")
                or ""
            ).lower().strip()

            href = (
                attributes.get("href", "")
                or ""
            ).strip()

            if (
                rel == "canonical"
                and href
            ):
                self.canonical = href

    def handle_endtag(self, tag):

        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):

        if self.in_title:
            self.title += data


def valid_absolute_url(url):

    try:

        parsed = urlparse(url)

        return (
            parsed.scheme in {
                "http",
                "https",
            }
            and bool(parsed.netloc)
        )

    except Exception:

        return False


def expected_url_for(path):

    relative = path.relative_to(ROOT).as_posix()

    if relative == "index.html":
        return BASE_URL + "/"

    return BASE_URL + "/" + relative


def check_page(path):

    parser = SEOParser()

    try:

        parser.feed(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:

        return [
            f"READ ERROR: {error}"
        ], [], parser

    errors = []
    warnings = []

    title = parser.title.strip()

    expected_url = expected_url_for(path)

    # =========================================================
    # REQUIRED SEO ELEMENTS
    # =========================================================

    if not title:

        errors.append(
            "Missing <title>"
        )

    if not parser.meta_description:

        errors.append(
            "Missing meta description"
        )

    if parser.h1_count == 0:

        errors.append(
            "Missing <h1>"
        )

    elif parser.h1_count > 1:

        errors.append(
            f"Multiple <h1> tags ({parser.h1_count})"
        )

    if not parser.lang:

        errors.append(
            'Missing <html lang="">'
        )

    # =========================================================
    # CANONICAL
    # =========================================================

    if not parser.canonical:

        errors.append(
            "Missing canonical URL"
        )

    else:

        canonical = parser.canonical.strip()

        if not valid_absolute_url(canonical):

            errors.append(
                "Canonical is not an absolute URL"
            )

        elif canonical != expected_url:

            errors.append(
                "Canonical does not match expected page URL "
                f"(expected: {expected_url}, found: {canonical})"
            )

        if "/OpportunityBridge/" in canonical:

            errors.append(
                "Canonical still contains /OpportunityBridge/"
            )

    # =========================================================
    # OPEN GRAPH URL
    # =========================================================

    if not parser.og_url:

        warnings.append(
            "Missing og:url"
        )

    else:

        og_url = parser.og_url.strip()

        if not valid_absolute_url(og_url):

            errors.append(
                "og:url is not an absolute URL"
            )

        elif og_url != expected_url:

            errors.append(
                "og:url does not match expected page URL "
                f"(expected: {expected_url}, found: {og_url})"
            )

        if "/OpportunityBridge/" in og_url:

            errors.append(
                "og:url still contains /OpportunityBridge/"
            )

    # =========================================================
    # TITLE LENGTH
    # =========================================================

    if title:

        if len(title) > 65:

            warnings.append(
                f"Title is long ({len(title)} characters)"
            )

        elif len(title) < 20:

            warnings.append(
                f"Title is short ({len(title)} characters)"
            )

    # =========================================================
    # OPTIONAL SEO ELEMENTS
    # =========================================================

    if not parser.meta_robots:

        warnings.append(
            "Missing robots meta tag"
        )

    if not parser.og_title:

        warnings.append(
            "Missing og:title"
        )

    if not parser.og_description:

        warnings.append(
            "Missing og:description"
        )

    return errors, warnings, parser


def is_google_verification(path):

    return (
        path.name.lower().startswith("google")
        and path.name.lower().endswith(".html")
    )


def is_html_file(path):

    return (
        path.is_file()
        and path.suffix.lower() == ".html"
    )


def main():

    print("=" * 70)

    print(
        "OPPORTUNITYBRIDGE SEO CHECKER v2.0"
    )

    print("=" * 70)

    pages = []

    for path in sorted(
        ROOT.glob("*.html")
    ):

        if not is_html_file(path):
            continue

        if path.name in EXCLUDED:
            continue

        if path.name.startswith("_"):
            continue

        if is_google_verification(path):
            continue

        pages.append(path)

    total_errors = 0
    total_warnings = 0
    pages_with_errors = 0

    titles = {}
    canonicals = {}

    # =========================================================
    # CHECK EVERY PAGE
    # =========================================================

    for page in pages:

        errors, warnings, parser = check_page(page)

        title = (
            parser.title
            .strip()
            .lower()
        )

        canonical = (
            parser.canonical
            .strip()
            .lower()
        )

        if title:

            titles.setdefault(
                title,
                []
            ).append(
                page.name
            )

        if canonical:

            canonicals.setdefault(
                canonical,
                []
            ).append(
                page.name
            )

        if errors:

            pages_with_errors += 1

            total_errors += len(errors)

            print(
                f"\n❌ {page.name}"
            )

            for error in errors:

                print(
                    f"   ERROR: {error}"
                )

        else:

            print(
                f"✅ {page.name}"
            )

        for warning in warnings:

            total_warnings += 1

            print(
                f"   ⚠️ WARNING: {warning}"
            )

    # =========================================================
    # DUPLICATE TITLES
    # =========================================================

    for title, page_list in titles.items():

        if len(page_list) > 1:

            total_errors += 1

            print(
                "\n❌ DUPLICATE TITLE"
            )

            print(
                f"   Title: {title}"
            )

            print(
                f"   Pages: {page_list}"
            )

    # =========================================================
    # DUPLICATE CANONICALS
    # =========================================================

    for canonical, page_list in canonicals.items():

        if len(page_list) > 1:

            total_errors += 1

            print(
                "\n❌ DUPLICATE CANONICAL"
            )

            print(
                f"   Canonical: {canonical}"
            )

            print(
                f"   Pages: {page_list}"
            )

    # =========================================================
    # LEGACY URL SCAN
    # =========================================================

    legacy_files = []

    for page in pages:

        try:

            content = page.read_text(
                encoding="utf-8"
            )

        except Exception:

            continue

        if (
            "https://absmg.github.io/OpportunityBridge"
            in content
        ):

            legacy_files.append(
                page.name
            )

    if legacy_files:

        total_errors += len(
            legacy_files
        )

        print(
            "\n❌ LEGACY /OpportunityBridge/ URLS FOUND"
        )

        for filename in legacy_files:

            print(
                f"   {filename}"
            )

    # =========================================================
    # FINAL REPORT
    # =========================================================

    print(
        "\n" + "=" * 70
    )

    print(
        f"Pages checked: {len(pages)}"
    )

    print(
        f"Pages with errors: {pages_with_errors}"
    )

    print(
        f"Total errors: {total_errors}"
    )

    print(
        f"SEO warnings: {total_warnings}"
    )

    print(
        "=" * 70
    )

    if total_errors:

        print(
            "SEO CHECK FAILED."
        )

        raise SystemExit(1)

    print(
        "SEO CHECK PASSED."
    )

    if total_warnings:

        print(
            "Warnings detected, but they do not block deployment."
        )


if __name__ == "__main__":

    main()
