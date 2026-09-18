from pathlib import Path
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, ElementTree
import subprocess


BASE_URL = "https://absmg.github.io"

ROOT = Path(__file__).resolve().parents[1]

OUTPUT = ROOT / "sitemap.xml"


# Pages that should NOT appear in Google sitemap.
EXCLUDED = {
    "404.html",

    # Authentication / private pages
    "login.html",
    "logout.html",
    "register.html",
    "dashboard.html",
    "forgot-password.html",
    "reset-password.html",

    # Legal / low-search-value pages
    "privacy.html",
    "disclaimer.html",
}


# Important public pages.
PRIORITIES = {
    "index.html": "1.0",

    "scholarships.html": "0.9",
    "jobs.html": "0.9",
    "internships.html": "0.9",
    "courses.html": "0.9",
    "opportunities.html": "0.9",

    "skills.html": "0.8",
    "digital-skills.html": "0.8",
    "career-skills.html": "0.8",
    "computer-skills.html": "0.8",
    "data-skills.html": "0.8",
    "digital-marketing.html": "0.8",
    "web-development.html": "0.8",
    "ai-skills.html": "0.8",

    "about.html": "0.6",
    "contact.html": "0.5",
}


# Change frequency hints.
CHANGEFREQ = {
    "index.html": "daily",

    "scholarships.html": "daily",
    "jobs.html": "daily",
    "internships.html": "daily",
    "courses.html": "daily",
    "opportunities.html": "daily",

    "skills.html": "weekly",
    "digital-skills.html": "weekly",
    "career-skills.html": "weekly",
    "computer-skills.html": "weekly",
    "data-skills.html": "weekly",
    "digital-marketing.html": "weekly",
    "web-development.html": "weekly",
    "ai-skills.html": "weekly",

    "about.html": "monthly",
    "contact.html": "monthly",
}


def get_last_modified(path: Path) -> str:
    """
    Get the last Git commit date for the file.
    Falls back to filesystem modification date.
    """

    try:
        relative_path = path.relative_to(ROOT)

        result = subprocess.run(
            [
                "git",
                "log",
                "-1",
                "--format=%cs",
                "--",
                str(relative_path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        value = result.stdout.strip()

        if value:
            return value

    except Exception:
        pass

    return datetime.fromtimestamp(
        path.stat().st_mtime,
        tz=timezone.utc,
    ).date().isoformat()


def url_for(path: Path) -> str:
    """
    Convert a local HTML file into its public OpportunityBridge URL.
    """

    relative = path.relative_to(ROOT).as_posix()

    # Homepage must use root URL.
    if relative == "index.html":
        return BASE_URL + "/"

    return BASE_URL + "/" + relative


def should_include(path: Path) -> bool:
    """
    Decide whether a file belongs in the public sitemap.
    """

    # Must be a real file.
    if not path.is_file():
        return False

    # Only HTML pages.
    if path.suffix.lower() != ".html":
        return False

    # Excluded pages.
    if path.name in EXCLUDED:
        return False

    # Ignore hidden/internal files.
    if path.name.startswith("_"):
        return False

    return True


def collect_public_pages():
    """
    Collect public HTML files from the repository root.
    """

    pages = []

    for path in ROOT.glob("*.html"):
        if should_include(path):
            pages.append(path)

    # Remove duplicate paths defensively.
    unique = {}

    for page in pages:
        unique[page.resolve()] = page

    pages = list(unique.values())

    # Homepage first, then alphabetical.
    pages.sort(
        key=lambda p: (
            p.name.lower() != "index.html",
            p.name.lower(),
        )
    )

    return pages


def generate_sitemap(pages):
    """
    Generate sitemap.xml.
    """

    urlset = Element(
        "urlset",
        {
            "xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"
        },
    )

    seen_urls = set()

    for page in pages:

        url = url_for(page)

        # Prevent duplicate URLs.
        if url in seen_urls:
            continue

        seen_urls.add(url)

        url_node = SubElement(
            urlset,
            "url",
        )

        # Public URL
        SubElement(
            url_node,
            "loc",
        ).text = url

        # Last modification
        SubElement(
            url_node,
            "lastmod",
        ).text = get_last_modified(page)

        # Change frequency
        SubElement(
            url_node,
            "changefreq",
        ).text = CHANGEFREQ.get(
            page.name,
            "weekly",
        )

        # Priority
        SubElement(
            url_node,
            "priority",
        ).text = PRIORITIES.get(
            page.name,
            "0.6",
        )

    ElementTree(urlset).write(
        OUTPUT,
        encoding="utf-8",
        xml_declaration=True,
    )

    return len(seen_urls)


def main():

    print("=" * 70)
    print("OPPORTUNITYBRIDGE SITEMAP GENERATOR v2.0")
    print("=" * 70)

    pages = collect_public_pages()

    count = generate_sitemap(pages)

    print()
    print(f"Public HTML pages found: {len(pages)}")
    print(f"Unique sitemap URLs: {count}")
    print(f"Output: {OUTPUT}")
    print()
    print("Homepage:")
    print(f"{BASE_URL}/")
    print()
    print("Sitemap:")
    print(f"{BASE_URL}/sitemap.xml")
    print()
    print("Sitemap generation completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()
