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

    # News / pages marked noindex
    "121-east-african-students-win-sh3-billion-global-scholarships-putting-education-at-heart-of-africas.html",
    "tanzania-economic-update-2026-making-jobs-work-world-bank-group.html",
    "tanzanian-billionaire-mo-dewji-pledges-to-invest-250-million-in-mozambique-and-create-20000-jobs-bil.html",
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


def should_include(path: Path) -> bool:
    """
    Decide whether an HTML page should appear in sitemap.xml.
    """

    if not path.is_file():
        return False

    if path.suffix.lower() != ".html":
        return False

    # Explicit exclusions
    if path.name in EXCLUDED:
        return False

    # Google Search Console verification files
    if path.name.lower().startswith("google"):
        return False

    # Internal / temporary files
    if path.name.startswith("_"):
        return False

    # Safety check:
    # Never include a page that explicitly contains noindex.
    try:
        content = path.read_text(
            encoding="utf-8",
            errors="ignore",
        ).lower()

        if 'name="robots"' in content and "noindex" in content:
            return False

        if "name='robots'" in content and "noindex" in content:
            return False

    except Exception:
        pass

    return True


def page_url(path: Path) -> str:
    """
    Convert an HTML file path into its public URL.
    """

    relative = path.relative_to(ROOT).as_posix()

    if relative == "index.html":
        return BASE_URL + "/"

    return BASE_URL + "/" + relative


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

    return datetime.now(timezone.utc).isoformat()


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
    print("OPPORTUNITYBRIDGE SITEMAP GENERATOR v3.0")
    print("=" * 70)

    pages = []

    # Scan only root-level HTML pages.
    for path in sorted(ROOT.glob("*.html")):
        if should_include(path):
            pages.append(path)

    # Remove duplicate URLs.
    unique_pages = []
    seen_urls = set()

    for path in pages:
        url = page_url(path)

        if url in seen_urls:
            continue

        seen_urls.add(url)
        unique_pages.append(path)

    pages = unique_pages

    # Build sitemap XML.
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
    print("- privacy.html")
    print("- disclaimer.html")
    print("- Google verification HTML files")
    print("- explicitly excluded news pages")
    print("- duplicate article pages")
    print("- any HTML page containing a robots noindex directive")
    print()
    print("Sitemap URL:")
    print(f"{BASE_URL}/sitemap.xml")
    print("=" * 70)


if __name__ == "__main__":
    main()
