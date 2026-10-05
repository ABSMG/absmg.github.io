from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent

# Pages that are news/reporting rather than actionable opportunities.
NOINDEX_PAGES = [
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
]

# Duplicate -> preferred canonical page.
DUPLICATES = {
    "cfas-canon-collins-rmtf-scholarships-for-postgraduate-study-fundsforngos.html":
        "cfas-canon-collins-rmtf-scholarships-for-postgraduate-study-fundsforngosorg.html",

    "free-it-certifications-and-courses-to-elevate-your-career-coursera.html":
        "free-it-certifications-and-courses-to-elevate-your-career-courseraorg.html",

    "scholarship-opportunities-for-students-graduates-researchers-fundsforngos.html":
        "scholarship-opportunities-for-students-graduates-researchers-fundsforngosorg.html",

    "tom-queba-and-pegasys-scholarships-for-social-change-south-africa-fundsforngos.html":
        "tom-queba-and-pegasys-scholarships-for-social-change-south-africa-fundsforngosor.html",
}


def add_noindex(html):
    robots_pattern = re.compile(
        r'<meta\s+name=["\']robots["\'][^>]*>',
        re.I
    )

    replacement = '<meta name="robots" content="noindex, follow">'

    if robots_pattern.search(html):
        return robots_pattern.sub(replacement, html, count=1)

    viewport_pattern = re.compile(
        r'(<meta\s+name=["\']viewport["\'][^>]*>)',
        re.I
    )

    if viewport_pattern.search(html):
        return viewport_pattern.sub(
            r'\1\n    ' + replacement,
            html,
            count=1
        )

    return html.replace(
        "<head>",
        "<head>\n    " + replacement,
        1
    )


def set_canonical(html, canonical_url):
    canonical_pattern = re.compile(
        r'<link\s+rel=["\']canonical["\']\s+href=["\'][^"\']+["\']\s*/?>',
        re.I
    )

    canonical_tag = f'<link rel="canonical" href="{canonical_url}">'

    if canonical_pattern.search(html):
        return canonical_pattern.sub(
            canonical_tag,
            html,
            count=1
        )

    return html.replace(
        "</head>",
        f'    {canonical_tag}\n</head>',
        1
    )


changed = []

# 1. Noindex news-only pages
for filename in NOINDEX_PAGES:
    path = ROOT / filename

    if not path.exists():
        print(f"SKIP: {filename}")
        continue

    html = path.read_text(encoding="utf-8")
    updated = add_noindex(html)

    if updated != html:
        path.write_text(updated, encoding="utf-8")
        changed.append(filename)
        print(f"NOINDEX: {filename}")
    else:
        print(f"UNCHANGED: {filename}")


# 2. Consolidate duplicates
for duplicate, preferred in DUPLICATES.items():
    path = ROOT / duplicate

    if not path.exists():
        print(f"SKIP DUPLICATE: {duplicate}")
        continue

    html = path.read_text(encoding="utf-8")

    canonical_url = (
        "https://absmg.github.io/" + preferred
    )

    updated = set_canonical(html, canonical_url)
    updated = add_noindex(updated)

    if updated != html:
        path.write_text(updated, encoding="utf-8")
        changed.append(duplicate)

        print(
            f"MERGE: {duplicate} -> {preferred}"
        )
    else:
        print(f"UNCHANGED DUPLICATE: {duplicate}")


print()
print("=" * 60)
print("OPPORTUNITYBRIDGE SEO CLEANUP COMPLETE")
print("=" * 60)
print(f"Pages changed: {len(changed)}")

for item in changed:
    print(" -", item)
