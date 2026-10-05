from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
SITEMAP = ROOT / "sitemap.xml"

EXCLUDE = {
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

    # duplicate pages
    "cfas-canon-collins-rmtf-scholarships-for-postgraduate-study-fundsforngos.html",
    "free-it-certifications-and-courses-to-elevate-your-career-coursera.html",
    "scholarship-opportunities-for-students-graduates-researchers-fundsforngos.html",
    "tom-queba-and-pegasys-scholarships-for-social-change-south-africa-fundsforngos.html",
}

xml = SITEMAP.read_text(encoding="utf-8")

removed = 0

def remove_if_excluded(match):
    global removed

    block = match.group(0)

    for filename in EXCLUDE:
        if f"/{filename}</loc>" in block:
            removed += 1
            return ""

    return block

cleaned = re.sub(
    r"<url>.*?</url>",
    remove_if_excluded,
    xml,
    flags=re.DOTALL,
)

SITEMAP.write_text(cleaned, encoding="utf-8")

print(f"Removed {removed} URLs from sitemap.xml")
print("SITEMAP CLEANUP COMPLETE")
