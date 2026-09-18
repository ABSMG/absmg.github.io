from pathlib import Path
from datetime import datetime, timezone
from xml.sax.saxutils import escape
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
}


def should_include(path: Path) -> bool:
    if not path.is_file():
        return False

    if path.suffix.lower() != ".html":
        return False

    if path.name in EXCLUDED:
        return False

    # Google Search Console verification files
    if path.name.lower().startswith("google"):
        return False

    if path.name.startswith("_"):
        return False

    return True


def page_url(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()

    if relative == "index.html":
        return BASE_URL + "/"

    return BASE_URL + "/" + relative


def last_modified(path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(path.relative_to(ROOT))],
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

    return datetime.now(timezone.utc).isoformat()


def priority_for(path: Path) -> str:
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
    print("OPPORTUNITYBRIDGE SITEMAP GENERATOR v2.1")
    print("=" * 70)

    pages = []

    for path in sorted(ROOT.glob("*.html")):
        if should_include(path):
            pages.append(path)

    # Remove duplicate URLs
    unique_pages = []
    seen_urls = set()

    for path in pages:
        url = page_url(path)

        if url in seen_urls:
            continue

        seen_urls.add(url)
        unique_pages.append(path)

    pages = unique_pages

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

    lines.append("</urlset>")

    OUTPUT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print()
    print(f"Pages included: {len(pages)}")
    print(f"Sitemap saved: {OUTPUT}")
    print()
    print("Excluded:")
    print("- 404.html")
    print("- authentication pages")
    print("- privacy/disclaimer")
    print("- Google verification HTML files")
    print()
    print(f"Sitemap URL: {BASE_URL}/sitemap.xml")
    print("=" * 70)


if __name__ == "__main__":
    main()
