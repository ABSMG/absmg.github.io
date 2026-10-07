from pathlib import Path
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from html.parser import HTMLParser
import subprocess


ROOT = Path(__file__).resolve().parents[1]

BASE_URL = "https://absmg.github.io"

OUTPUT = ROOT / "sitemap.xml"


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

    # News / pages marked noindex
    "121-east-african-students-win-sh3-billion-global-scholarships-putting-education-at-heart-of-africas.html",

    "tanzania-economic-update-2026-making-jobs-work-world-bank-group.html",

    "tanzanian-billionaire-mo-dewji-pledges-to-invest-250-million-to-mozambique-and-create-20000-jobs-bil.html",

    "tanzanias-billionaire-led-metl-plans-250-million-mozambique-expansion-targeting-20000-jobs-business.html",

    "tanzanias-billionaire-led-metl-plans-250-million-mozambique-expansion-targeting-20000-jobs-cedirates.html",

    "tanzania-and-world-bank-finalize-kazi-mpa-central-corridor-jobs-programme-to-boost-youth-employment.html",

    "tanzania-to-host-2nd-doha-dialogue-to-boost-safe-overseas-job-opportunities-for-citizens-ippmediacot.html",

    "tanzania-urged-to-turn-economic-growth-into-better-jobs-channel-africa.html",

    "tanzania-must-risk-becoming-broke-to-create-20-million-jobs-uchumi360com.html",

    "tanzania-netherlands-deepen-partnership-around-investment-jobs-skills-ippmediacotz.html",

    "somalia-tanzania-discuss-youth-jobs-and-digital-government-cooperation-shabelle-media-network.html",

    "tanzanias-economy-gains-momentum-but-better-jobs-hold-the-key-to-broader-national-prosperity-devdisc.html",

    "tanzanias-kagera-coffee-nights-expose-a-deeper-jobs-and-skills-gap-pan-african-visions.html",

    "teagtl-inspires-future-professionals-through-career-day-engagements-at-udsm-thecitizencotz.html",

    "tra-doubles-jobs-for-disabled-workers-dailynewscotz.html",

    # Duplicate pages
    # Keep the preferred canonical versions instead.
    "cfas-canon-collins-rmtf-scholarships-for-postgraduate-study-fundsforngos.html",

    "free-it-certifications-and-courses-to-elevate-your-career-coursera.html",

    "scholarship-opportunities-for-students-graduates-researchers-fundsforngos.html",

    "tom-queba-and-pegasys-scholarships-for-social-change-south-africa-fundsforngos.html",
}


class SitemapMetadataParser(HTMLParser):
    """
    Lightweight HTML parser used only to inspect SEO metadata.

    The sitemap generator uses this parser to determine:
    - robots / noindex
    - canonical URL
    """

    def __init__(self):
        super().__init__()

        self.robots = ""
        self.canonical = ""

    def handle_starttag(self, tag, attrs):

        tag = tag.lower()

        attributes = dict(attrs)

        # =====================================================
        # META ROBOTS
        # =====================================================

        if tag == "meta":

            name = (
                attributes.get("name", "")
                or ""
            ).lower().strip()

            content = (
                attributes.get("content", "")
                or ""
            ).strip()

            if name == "robots":

                self.robots = content

        # =====================================================
        # CANONICAL
        # =====================================================

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


def page_url(path: Path) -> str:
    """
    Convert an HTML file path into its public URL.
    """

    relative = path.relative_to(ROOT).as_posix()

    if relative == "index.html":

        return BASE_URL + "/"

    return BASE_URL + "/" + relative


def read_metadata(path: Path):
    """
    Read robots and canonical metadata from an HTML page.

    Returns:
        parser object or None if the file cannot be parsed.
    """

    try:

        content = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    except Exception:

        return None

    parser = SitemapMetadataParser()

    try:

        parser.feed(content)

    except Exception:

        return None

    return parser


def has_noindex(parser: SitemapMetadataParser) -> bool:
    """
    Check whether the page explicitly contains noindex.
    """

    if parser is None:
        return False

    robots = (
        parser.robots
        or ""
    ).lower()

    # Normalize whitespace so values such as:
    # "noindex, follow"
    # "noindex , follow"
    # "NOINDEX"
    # are all detected.
    robots = " ".join(
        robots.split()
    )

    return "noindex" in robots


def has_valid_self_canonical(
    path: Path,
    parser: SitemapMetadataParser,
) -> bool:
    """
    Only include pages whose canonical points to the page itself.

    This is important because sitemap URLs should agree with
    the canonical URLs used by the website.
    """

    if parser is None:

        return False

    expected = page_url(path)

    canonical = (
        parser.canonical
        or ""
    ).strip()

    # A sitemap page must have a canonical.
    if not canonical:

        return False

    # Remove accidental trailing slash from non-root URLs
    # only for comparison.
    if expected != BASE_URL + "/":

        expected_compare = expected.rstrip("/")

        canonical_compare = canonical.rstrip("/")

    else:

        expected_compare = expected

        canonical_compare = canonical

    # Never allow the old project-path URL.
    if "/OpportunityBridge/" in canonical:

        return False

    if "/OpportunityBridge" in canonical:

        return False

    # Never allow the old HTTP version.
    if canonical.startswith(
        "http://absmg.github.io"
    ):

        return False

    # Canonical must exactly match the expected public URL.
    if canonical_compare != expected_compare:

        return False

    return True


def should_include(path: Path) -> bool:
    """
    Decide whether an HTML page should appear in sitemap.xml.
    """

    # =========================================================
    # BASIC FILE VALIDATION
    # =========================================================

    if not path.is_file():

        return False

    if path.suffix.lower() != ".html":

        return False

    # =========================================================
    # EXPLICIT EXCLUSIONS
    # =========================================================

    if path.name in EXCLUDED:

        return False

    # =========================================================
    # GOOGLE SEARCH CONSOLE VERIFICATION FILES
    # =========================================================

    if path.name.lower().startswith("google"):

        return False

    # =========================================================
    # INTERNAL / TEMPORARY FILES
    # =========================================================

    if path.name.startswith("_"):

        return False

    # =========================================================
    # READ SEO METADATA
    # =========================================================

    parser = read_metadata(path)

    if parser is None:

        print(
            f"SKIP: {path.name} "
            "(could not read HTML metadata)"
        )

        return False

    # =========================================================
    # NOINDEX SAFETY CHECK
    # =========================================================

    if has_noindex(parser):

        print(
            f"SKIP: {path.name} "
            "(robots noindex)"
        )

        return False

    # =========================================================
    # SELF-CANONICAL SAFETY CHECK
    # =========================================================

    if not has_valid_self_canonical(
        path,
        parser
    ):

        expected = page_url(path)

        canonical = (
            parser.canonical
            or "[missing]"
        )

        print(
            f"SKIP: {path.name} "
            f"(canonical mismatch)"
        )

        print(
            f"      Expected: {expected}"
        )

        print(
            f"      Found:    {canonical}"
        )

        return False

    # =========================================================
    # ALL CHECKS PASSED
    # =========================================================

    return True


def last_modified(path: Path) -> str:
    """
    Get the latest Git commit date for the file.
    Falls back to the current UTC time if Git information is unavailable.
    """

    try:

        result = subprocess.run(
            [
                "git",
                "log",
                "-1",
                "--format=%cI",
                "--",
                str(path.relative_to(ROOT)),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        value = result.stdout.strip()

        if value:

            return value

    except Exception:

        pass

    return datetime.now(
        timezone.utc
    ).isoformat()


def priority_for(path: Path) -> str:
    """
    Assign sitemap priority.
    """

    if path.name == "index.html":

        return "1.0"

    important_pages = {
        "scholarships.html",
        "jobs.html",
        "internships.html",
        "courses.html",
        "opportunities.html",
    }

    if path.name in important_pages:

        return "0.9"

    return "0.7"


def changefreq_for(path: Path) -> str:
    """
    Assign sitemap change frequency.
    """

    if path.name == "index.html":

        return "daily"

    important_pages = {
        "scholarships.html",
        "jobs.html",
        "internships.html",
        "courses.html",
        "opportunities.html",
    }

    if path.name in important_pages:

        return "daily"

    return "weekly"


def main():

    print("=" * 70)

    print(
        "OPPORTUNITYBRIDGE SITEMAP GENERATOR v4.0"
    )

    print("=" * 70)

    pages = []

    # =========================================================
    # SCAN ROOT-LEVEL HTML PAGES
    # =========================================================

    for path in sorted(
        ROOT.glob("*.html")
    ):

        if should_include(path):

            pages.append(path)

    # =========================================================
    # REMOVE DUPLICATE URLS
    # =========================================================

    unique_pages = []

    seen_urls = set()

    for path in pages:

        url = page_url(path)

        if url in seen_urls:

            continue

        seen_urls.add(url)

        unique_pages.append(path)

    pages = unique_pages

    # =========================================================
    # BUILD SITEMAP XML
    # =========================================================

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',

        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for path in pages:

        url = page_url(path)

        modified = last_modified(path)

        priority = priority_for(path)

        changefreq = changefreq_for(path)

        lines.extend(
            [
                "  <url>",

                f"    <loc>{escape(url)}</loc>",

                f"    <lastmod>{escape(modified)}</lastmod>",

                f"    <changefreq>{changefreq}</changefreq>",

                f"    <priority>{priority}</priority>",

                "  </url>",
            ]
        )

    lines.append(
        "</urlset>"
    )

    # =========================================================
    # WRITE SITEMAP
    # =========================================================

    OUTPUT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    # =========================================================
    # REPORT
    # =========================================================

    print()

    print(
        f"Pages included: {len(pages)}"
    )

    print(
        f"Sitemap saved: {OUTPUT}"
    )

    print()

    print("Excluded:")

    print("- 404.html")

    print("- authentication pages")

    print("- privacy.html")

    print("- disclaimer.html")

    print("- Google verification HTML files")

    print("- explicitly excluded news pages")

    print("- duplicate article pages")

    print("- any HTML page containing a robots noindex directive")

    print("- any HTML page with a missing canonical")

    print("- any HTML page with a different canonical")

    print("- any HTML page using the old /OpportunityBridge/ URL")

    print("- any HTML page using the old HTTP URL")

    print()

    print(
        "Sitemap URL:"
    )

    print(
        f"{BASE_URL}/sitemap.xml"
    )

    print()

    print(
        "Self-canonical validation: ENABLED"
    )

    print(
        "Noindex validation: ENABLED"
    )

    print(
        "Legacy /OpportunityBridge/ validation: ENABLED"
    )

    print()

    print(
        "Sitemap generation completed."
    )

    print("=" * 70)


if __name__ == "__main__":

    main()
