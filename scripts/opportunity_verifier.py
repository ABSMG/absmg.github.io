import json
import re
import socket
from pathlib import Path
from urllib.parse import urlparse, urljoin, urlunparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone


BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "discovered_opportunities.json"
OUTPUT_FILE = BASE_DIR / "data" / "verified_opportunities.json"

TIMEOUT = 15

MAX_PAGE_BYTES = 500000

MAX_ANALYSIS_CHARS = 120000

MAX_LINKS_TO_ANALYZE = 250

MIN_PAGE_WORDS = 80

MAX_NEWS_PENALTY = 18


# ============================================================
# OPPORTUNITY KEYWORDS
# ============================================================

OPPORTUNITY_KEYWORDS = [
    "scholarship",
    "scholarships",
    "fellowship",
    "fellowships",
    "grant",
    "grants",
    "funding",
    "funded",
    "fully funded",
    "internship",
    "internships",
    "job",
    "jobs",
    "vacancy",
    "vacancies",
    "career",
    "careers",
    "course",
    "courses",
    "training",
    "trainings",
    "bootcamp",
    "academy",
    "opportunity",
    "opportunities",
    "application",
    "applications",
    "apply",
    "eligibility",
    "eligible",
    "deadline",
    "admission",
    "admissions",
    "fellow",
    "research",
    "researcher",
    "competition",
    "competitions",
    "contest",
    "challenge",
    "volunteer",
    "volunteering",
    "recruitment",
    "enrollment",
    "enrolment",
]


# ============================================================
# STRONG OPPORTUNITY SIGNALS
# ============================================================
#
# These phrases are stronger evidence than generic words such
# as "jobs", "career", "students", or "opportunity".
#
# IMPORTANT:
# A general news article containing "jobs" should not easily
# become an approved opportunity.
# ============================================================

STRONG_OPPORTUNITY_SIGNALS = [
    "apply now",
    "apply here",
    "apply online",
    "applications are open",
    "applications open",
    "application is open",
    "application deadline",
    "application period",
    "how to apply",
    "submit application",
    "submit your application",
    "eligible applicants",
    "eligibility criteria",
    "eligibility requirements",
    "who can apply",
    "selection criteria",
    "selection process",
    "deadline",
    "closing date",
    "last date to apply",
    "last day to apply",
    "apply by",
    "applications close",
    "funded by",
    "fully funded",
    "partial funding",
    "tuition fee",
    "tuition fees",
    "tuition waiver",
    "stipend",
    "monthly stipend",
    "living allowance",
    "financial support",
    "scholarship award",
    "scholarship program",
    "scholarship programme",
    "fellowship program",
    "fellowship programme",
    "internship program",
    "internship programme",
    "job opening",
    "job openings",
    "job vacancy",
    "job vacancies",
    "vacancy announcement",
    "vacancies available",
    "position available",
    "positions available",
    "course enrollment",
    "course enrolment",
    "register for the course",
    "registration is open",
    "training program",
    "training programme",
    "training opportunity",
    "call for applications",
    "call for proposals",
    "call for entries",
    "call for participants",
    "applications invited",
    "inviting applications",
    "now accepting applications",
]


# ============================================================
# NEWS / GENERAL CONTENT SIGNALS
# ============================================================
#
# These phrases frequently appear in news/reporting rather
# than on actual opportunity pages.
#
# They are not automatic rejection signals by themselves.
# They are combined with opportunity evidence.
# ============================================================

NEWS_SIGNALS = [
    "according to",
    "reported that",
    "reports that",
    "said that",
    "has said",
    "told reporters",
    "in a statement",
    "speaking during",
    "the minister said",
    "the president said",
    "government said",
    "government has",
    "economic growth",
    "economic update",
    "economy",
    "gross domestic product",
    "gdp",
    "inflation",
    "trade",
    "investment",
    "market",
    "business news",
    "news",
    "latest news",
    "political",
    "politics",
    "dialogue",
    "conference",
    "summit",
    "meeting",
    "partnership",
    "pledges to invest",
    "plans to invest",
    "announced today",
    "announced yesterday",
    "yesterday",
    "last week",
    "this week",
    "according to the report",
    "officials said",
    "sources said",
    "minister",
    "president",
    "government",
    "parliament",
    "election",
    "elections",
    "policy",
    "policies",
    "economic outlook",
    "market outlook",
]


# ============================================================
# GENERIC NEWS TITLE SIGNALS
# ============================================================

NEWS_TITLE_SIGNALS = [
    "latest news",
    "news",
    "economic update",
    "economy",
    "economic growth",
    "gdp",
    "investment",
    "market",
    "minister",
    "president",
    "government",
    "summit",
    "meeting",
    "dialogue",
    "partnership",
    "pledges",
    "plans to invest",
    "announces",
    "announced",
    "report",
    "reports",
    "update",
]


# ============================================================
# TRUSTED DOMAINS
# ============================================================
#
# Generic .org is intentionally NOT automatically trusted.
# ============================================================

TRUSTED_EXACT_DOMAINS = {
    "un.org",
    "www.un.org",

    "worldbank.org",
    "www.worldbank.org",

    "afdb.org",
    "www.afdb.org",

    "mastercardfdn.org",
    "www.mastercardfdn.org",

    "erasmus-plus.ec.europa.eu",
    "ec.europa.eu",

    "commonwealthscholarships.com",
    "www.commonwealthscholarships.com",
}


TRUSTED_DOMAIN_SUFFIXES = [
    ".edu",
    ".edu.tz",
    ".ac.tz",
    ".ac.uk",
    ".edu.au",
    ".edu.ca",
    ".edu.ng",
    ".edu.gh",
    ".edu.ke",
    ".edu.za",
    ".ac.za",
    ".gov",
    ".gov.tz",
    ".gov.uk",
    ".gov.au",
    ".gov.ca",
]


TRUSTED_DOMAIN_CONTAINS = [
    "commonwealthscholarships",
    "erasmus-plus.ec.europa.eu",
]


# ============================================================
# POSSIBLE CATEGORY KEYWORDS
# ============================================================

CATEGORY_KEYWORDS = {
    "scholarships": [
        "scholarship",
        "scholarships",
        "fully funded scholarship",
        "funded scholarship",
        "tuition scholarship",
        "scholarship award",
    ],

    "fellowships": [
        "fellowship",
        "fellowships",
        "fellow",
    ],

    "grants": [
        "grant",
        "grants",
        "funding opportunity",
        "funding opportunities",
        "call for proposals",
        "research grant",
    ],

    "internships": [
        "internship",
        "internships",
        "intern",
        "traineeship",
        "traineeships",
    ],

    "remote-jobs": [
        "remote job",
        "remote jobs",
        "remote work",
        "work from home",
        "work-from-home",
        "remote position",
        "remote positions",
    ],

    "jobs": [
        "job",
        "jobs",
        "vacancy",
        "vacancies",
        "employment",
        "recruitment",
        "career",
        "careers",
        "job opening",
        "job openings",
    ],

    "courses": [
        "course",
        "courses",
        "online course",
        "online courses",
        "certificate course",
        "certification",
        "certification course",
    ],

    "training": [
        "training",
        "trainings",
        "bootcamp",
        "boot camp",
        "academy",
        "workshop",
        "training program",
        "training programme",
    ],

    "competitions": [
        "competition",
        "competitions",
        "contest",
        "challenge",
        "hackathon",
        "award",
        "awards",
        "call for entries",
    ],

    "research": [
        "research opportunity",
        "research opportunities",
        "research grant",
        "research fellowship",
        "research position",
        "researcher",
        "research funding",
    ],

    "study-abroad": [
        "study abroad",
        "international students",
        "study in",
        "international scholarship",
        "overseas study",
        "study overseas",
    ],

    "volunteer": [
        "volunteer",
        "volunteering",
        "voluntary",
        "volunteer opportunity",
    ],
}


# ============================================================
# FUNDING KEYWORDS
# ============================================================

FUNDING_KEYWORDS = [
    "fully funded",
    "fully-funded",
    "funded",
    "funding",
    "financial support",
    "financial assistance",
    "stipend",
    "monthly stipend",
    "living allowance",
    "travel allowance",
    "travel support",
    "tuition waiver",
    "tuition fees",
    "tuition fee",
    "fee waiver",
    "scholarship award",
    "grant amount",
    "funding amount",
]


# ============================================================
# ELIGIBILITY KEYWORDS
# ============================================================

ELIGIBILITY_KEYWORDS = [
    "eligibility",
    "eligible",
    "eligibility criteria",
    "eligibility requirements",
    "requirements",
    "who can apply",
    "applicants must",
    "candidates must",
    "qualification",
    "qualifications",
    "minimum qualification",
    "academic requirements",
    "academic qualification",
    "age requirement",
    "nationality requirement",
    "citizenship requirement",
]


# ============================================================
# APPLICATION KEYWORDS
# ============================================================

APPLICATION_KEYWORDS = [
    "apply now",
    "apply here",
    "apply online",
    "how to apply",
    "application form",
    "application portal",
    "submit application",
    "submit your application",
    "applications are open",
    "applications open",
    "call for applications",
    "now accepting applications",
    "register now",
    "registration is open",
    "enroll now",
    "enrol now",
]


# ============================================================
# LOCATION KEYWORDS
# ============================================================

COUNTRIES = [
    "tanzania",
    "kenya",
    "uganda",
    "rwanda",
    "burundi",
    "ethiopia",
    "ghana",
    "nigeria",
    "south africa",
    "zambia",
    "zimbabwe",
    "malawi",
    "mozambique",
    "botswana",
    "namibia",
    "lesotho",
    "eswatini",
    "senegal",
    "gambia",
    "sierra leone",
    "liberia",
    "cameroon",
    "ivory coast",
    "côte d'ivoire",
    "democratic republic of the congo",
    "dr congo",
    "drc",
    "congo",
    "canada",
    "united states",
    "usa",
    "u.s.",
    "united kingdom",
    "uk",
    "england",
    "scotland",
    "wales",
    "northern ireland",
    "germany",
    "france",
    "italy",
    "spain",
    "netherlands",
    "belgium",
    "portugal",
    "australia",
    "new zealand",
    "japan",
    "china",
    "india",
    "south korea",
    "korea",
    "singapore",
    "malaysia",
    "sweden",
    "norway",
    "denmark",
    "finland",
    "ireland",
    "switzerland",
    "austria",
    "poland",
    "czech republic",
    "czechia",
    "hungary",
    "romania",
    "greece",
    "turkey",
    "israel",
    "united arab emirates",
    "uae",
    "saudi arabia",
]


REGIONS = [
    "africa",
    "east africa",
    "east african",
    "west africa",
    "west african",
    "southern africa",
    "southern african",
    "north africa",
    "north african",
    "europe",
    "european union",
    "asia",
    "asian",
    "north america",
    "south america",
    "latin america",
    "oceania",
    "global",
    "worldwide",
    "international",
]


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    """
    Normalize whitespace and safely convert values to text.
    """

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()


def clean_lower(value):
    """
    Normalize text and convert it to lowercase.
    """

    return clean_text(
        value
    ).lower()


def get_domain(url):
    """
    Extract hostname without port.
    """

    try:

        parsed = urlparse(
            clean_text(url)
        )

        return (
            parsed.netloc
            .lower()
            .split(":")[0]
            .strip(".")
        )

    except Exception:

        return ""


def is_valid_url(url):
    """
    Validate HTTP/HTTPS URLs.
    """

    try:

        parsed = urlparse(
            clean_text(url)
        )

        return (
            parsed.scheme in (
                "http",
                "https",
            )
            and bool(parsed.netloc)
        )

    except Exception:

        return False


def normalize_url(url):
    """
    Normalize URL for comparison.
    """

    url = clean_text(
        url
    )

    if not url:

        return ""

    try:

        parsed = urlparse(
            url
        )

        scheme = (
            parsed.scheme
            or "https"
        ).lower()

        netloc = (
            parsed.netloc
            .lower()
            .split(":")[0]
        )

        path = parsed.path.rstrip("/")

        return urlunparse(
            (
                scheme,
                netloc,
                path,
                "",
                parsed.query,
                "",
            )
        )

    except Exception:

        return url.rstrip("/")


def is_homepage_url(url):
    """
    Determine whether a URL looks like a publisher homepage
    rather than a specific article/opportunity page.
    """

    if not is_valid_url(url):

        return False

    try:

        parsed = urlparse(
            url
        )

        path = (
            parsed.path
            or "/"
        ).strip("/")

        if not path:

            return True

        generic_paths = {
            "home",
            "index.html",
            "index.php",
            "index",
        }

        if path.lower() in generic_paths:

            return True

        return False

    except Exception:

        return False


def is_trusted_domain(url):
    """
    Determine whether a domain belongs to a trusted class.

    Generic .org domains are NOT automatically trusted.
    """

    domain = get_domain(
        url
    )

    if not domain:

        return False

    # Exact trusted domains
    if domain in TRUSTED_EXACT_DOMAINS:

        return True

    # Trusted suffixes
    for suffix in TRUSTED_DOMAIN_SUFFIXES:

        if domain.endswith(
            suffix
        ):

            return True

    # Known trusted patterns
    for pattern in TRUSTED_DOMAIN_CONTAINS:

        if pattern in domain:

            return True

    return False


def same_domain(url1, url2):
    """
    Compare two URLs by hostname.
    """

    domain1 = get_domain(
        url1
    )

    domain2 = get_domain(
        url2
    )

    return (
        bool(domain1)
        and bool(domain2)
        and domain1 == domain2
    )


def strip_html(html):
    """
    Convert HTML into readable text.

    Script/style/noscript/template sections are removed first.
    """

    if not html:

        return ""

    text = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    text = re.sub(
        r"<noscript\b[^>]*>.*?</noscript>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    text = re.sub(
        r"<template\b[^>]*>.*?</template>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    text = re.sub(
        r"<svg\b[^>]*>.*?</svg>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
        flags=re.DOTALL,
    )

    # Decode common HTML entities.
    text = (
        text
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&#x27;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )

    return clean_text(
        text
    )


def extract_title(html):
    """
    Extract HTML <title>.
    """

    if not html:

        return ""

    title_match = re.search(
        r"<title[^>]*>(.*?)</title>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not title_match:

        return ""

    return clean_text(
        strip_html(
            title_match.group(1)
        )
    )


def extract_meta_description(html):
    """
    Extract meta description.
    """

    if not html:

        return ""

    patterns = [
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        if match:

            return clean_text(
                match.group(1)
            )

    return ""


def extract_canonical(
    html,
    base_url,
):
    """
    Extract canonical URL when available.
    """

    if not html:

        return ""

    patterns = [
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](.*?)["\']',
        r'<link[^>]+href=["\'](.*?)["\'][^>]+rel=["\']canonical["\']',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        if match:

            value = clean_text(
                match.group(1)
            )

            if value:

                return urljoin(
                    base_url,
                    value,
                )

    return ""


def extract_meta_property(
    html,
    property_name,
):
    """
    Extract an Open Graph / meta property.
    """

    if not html:

        return ""

    escaped = re.escape(
        property_name
    )

    patterns = [
        rf'<meta[^>]+property=["\']{escaped}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']{escaped}["\']',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        if match:

            return clean_text(
                match.group(1)
            )

    return ""


def extract_h1(html):
    """
    Extract the first H1 heading.
    """

    if not html:

        return ""

    match = re.search(
        r"<h1[^>]*>(.*?)</h1>",
        html,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if not match:

        return ""

    return clean_text(
        strip_html(
            match.group(1)
        )
    )


def extract_links(
    html,
    base_url,
):
    """
    Extract links from the source page.

    Returns a list of dictionaries containing:
        url
        anchor
    """

    if not html:

        return []

    links = []

    pattern = re.compile(
        r'<a\b[^>]*href=["\'](.*?)["\'][^>]*>(.*?)</a>',
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    for match in pattern.finditer(
        html
    ):

        href = clean_text(
            match.group(1)
        )

        anchor = clean_text(
            strip_html(
                match.group(2)
            )
        )

        if not href:

            continue

        if href.startswith(
            (
                "#",
                "mailto:",
                "tel:",
                "javascript:",
                "data:",
            )
        ):

            continue

        absolute = urljoin(
            base_url,
            href,
        )

        if not is_valid_url(
            absolute
        ):

            continue

        links.append(
            {
                "url": absolute,
                "anchor": anchor,
            }
        )

        if len(links) >= MAX_LINKS_TO_ANALYZE:

            break

    # Deduplicate by normalized URL.
    unique = []

    seen = set()

    for link in links:

        normalized = normalize_url(
            link["url"]
        ).lower()

        if normalized in seen:

            continue

        seen.add(
            normalized
        )

        unique.append(
            link
        )

    return unique


def extract_date_candidates(text):
    """
    Extract common date formats.

    This is only a candidate extractor.
    It does not claim every date found is a deadline.
    """

    if not text:

        return []

    patterns = [

        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",

        r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",

        r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
        r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+\d{1,2},?\s+\d{4}\b",
    ]

    results = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        for match in matches:

            value = clean_text(
                match
            )

            if (
                value
                and value not in results
            ):

                results.append(
                    value
                )

    return results[:15]


def extract_deadline(text):
    """
    Extract a deadline only when a date appears close to a
    deadline/application closing phrase.

    This reduces false deadline values.
    """

    if not text:

        return ""

    deadline_patterns = [

        r"(?:application\s+)?deadline"
        r"\s*(?:is|:|-|–|until|on)?\s*"
        r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",

        r"closing\s+date"
        r"\s*(?:is|:|-|–|until|on)?\s*"
        r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",

        r"last\s+(?:date|day)\s+to\s+apply"
        r"\s*(?:is|:|-|–|until|on)?\s*"
        r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",

        r"(?:application\s+)?deadline"
        r"\s*(?:is|:|-|–|until|on)?\s*"
        r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})",

        r"(?:application\s+)?deadline"
        r"\s*(?:is|:|-|–|until|on)?\s*"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    ]

    for pattern in deadline_patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:

            return clean_text(
                match.group(1)
            )

    secondary_patterns = [

        r"apply\s+by\s+"
        r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",

        r"applications?\s+close\s+"
        r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",

        r"applications?\s+close\s+"
        r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})",

        r"apply\s+by\s+"
        r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})",

        r"closing\s+on\s+"
        r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",

        r"closing\s+on\s+"
        r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})",
    ]

    for pattern in secondary_patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:

            return clean_text(
                match.group(1)
            )

    return ""


def detect_category(text):
    """
    Determine the strongest opportunity category.
    """

    normalized = clean_lower(
        text
    )

    scores = {}

    for category, keywords in CATEGORY_KEYWORDS.items():

        score = 0

        for keyword in keywords:

            if keyword in normalized:

                score += 1

        scores[category] = score

    best_category = "opportunities"

    best_score = 0

    for category, score in scores.items():

        if score > best_score:

            best_category = category

            best_score = score

    return best_category


def detect_location(text):
    """
    Try to detect broad geographic information.

    This is deliberately conservative.
    """

    normalized = clean_lower(
        text
    )

    found_countries = []

    for country in COUNTRIES:

        if country in normalized:

            display = country.title()

            if country == "usa":

                display = "USA"

            elif country == "u.s.":

                display = "USA"

            elif country == "uk":

                display = "UK"

            elif country == "uae":

                display = "UAE"

            elif country == "drc":

                display = "DRC"

            elif country == "côte d'ivoire":

                display = "Côte d'Ivoire"

            elif country == "south africa":

                display = "South Africa"

            elif country == "united states":

                display = "United States"

            elif country == "united kingdom":

                display = "United Kingdom"

            elif country == "new zealand":

                display = "New Zealand"

            elif country == "south korea":

                display = "South Korea"

            elif country == "united arab emirates":

                display = "United Arab Emirates"

            found_countries.append(
                display
            )

    found_regions = []

    for region in REGIONS:

        if region in normalized:

            found_regions.append(
                region.title()
            )

    # Prefer a country over a broad region.
    if found_countries:

        return found_countries[0]

    if found_regions:

        return found_regions[0]

    return ""


def detect_funding(text):
    """
    Detect funding information.
    """

    normalized = clean_lower(
        text
    )

    matches = []

    for keyword in FUNDING_KEYWORDS:

        if keyword in normalized:

            matches.append(
                keyword
            )

    unique = []

    for match in matches:

        if match not in unique:

            unique.append(
                match
            )

    if not unique:

        return {
            "funding_detected": False,
            "funding_type": "",
            "funding_signals": [],
        }

    if (
        "fully funded" in normalized
        or "fully-funded" in normalized
    ):

        funding_type = "fully funded"

    elif (
        "scholarship" in normalized
        or "tuition" in normalized
        or "fee waiver" in normalized
    ):

        funding_type = "scholarship/tuition support"

    elif (
        "stipend" in normalized
        or "living allowance" in normalized
        or "financial support" in normalized
    ):

        funding_type = "stipend/financial support"

    elif (
        "grant" in normalized
        or "funding" in normalized
    ):

        funding_type = "grant/funding"

    else:

        funding_type = "funding available"

    return {
        "funding_detected": True,
        "funding_type": funding_type,
        "funding_signals": unique[:10],
    }


def detect_eligibility(text):
    """
    Detect eligibility/requirements information.
    """

    normalized = clean_lower(
        text
    )

    matches = []

    for keyword in ELIGIBILITY_KEYWORDS:

        if keyword in normalized:

            matches.append(
                keyword
            )

    unique = []

    for match in matches:

        if match not in unique:

            unique.append(
                match
            )

    return unique[:12]


def count_words(text):
    """
    Count approximate words.
    """

    if not text:

        return 0

    return len(
        re.findall(
            r"\b[\w'-]+\b",
            text,
            flags=re.UNICODE,
        )
    )


def count_occurrences(
    text,
    phrase,
):
    """
    Count non-overlapping phrase occurrences.
    """

    if not text or not phrase:

        return 0

    return text.lower().count(
        phrase.lower()
    )


# ============================================================
# PAGE FETCHING
# ============================================================

def fetch_page(url):
    """
    Check whether the source page is reachable.

    Returns:
        {
            "reachable": bool,
            "status_code": int or None,
            "final_url": str,
            "content_type": str,
            "title": str,
            "description": str,
            "canonical": str,
            "h1": str,
            "content": str,
            "text": str,
            "links": list,
            "word_count": int,
            "error": str or None
        }
    """

    result = {
        "reachable": False,
        "status_code": None,
        "final_url": url,
        "content_type": "",
        "title": "",
        "description": "",
        "canonical": "",
        "h1": "",
        "content": "",
        "text": "",
        "links": [],
        "word_count": 0,
        "error": None,
    }

    try:

        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; OpportunityBridgeBot/3.0; "
                    "+https://absmg.github.io/)"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": (
                    "en-US,en;q=0.9"
                ),
            },
        )

        with urlopen(
            request,
            timeout=TIMEOUT,
        ) as response:

            status_code = response.getcode()

            final_url = response.geturl()

            content_type = (
                response.headers.get(
                    "Content-Type",
                    "",
                )
            )

            raw = response.read(
                MAX_PAGE_BYTES
            )

            try:

                content = raw.decode(
                    "utf-8",
                    errors="ignore",
                )

            except Exception:

                content = ""

            title = extract_title(
                content
            )

            description = extract_meta_description(
                content
            )

            canonical = extract_canonical(
                content,
                final_url,
            )

            h1 = extract_h1(
                content
            )

            text = strip_html(
                content
            )

            links = extract_links(
                content,
                final_url,
            )

            result.update(
                {
                    "reachable": (
                        200
                        <= status_code
                        < 400
                    ),
                    "status_code": status_code,
                    "final_url": final_url,
                    "content_type": content_type,
                    "title": title,
                    "description": description,
                    "canonical": canonical,
                    "h1": h1,
                    "content": content,
                    "text": text,
                    "links": links,
                    "word_count": count_words(
                        text
                    ),
                }
            )

    except HTTPError as error:

        result[
            "status_code"
        ] = error.code

        result[
            "error"
        ] = f"HTTP {error.code}"

    except (
        URLError,
        socket.timeout,
    ) as error:

        result[
            "error"
        ] = str(error)

    except Exception as error:

        result[
            "error"
        ] = str(error)

    return result


# ============================================================
# KEYWORD / RELEVANCE CHECKS
# ============================================================

def contains_opportunity_keyword(text):
    """
    Check whether opportunity-related terminology appears.
    """

    text = clean_lower(
        text
    )

    return any(
        keyword in text
        for keyword in OPPORTUNITY_KEYWORDS
    )


def find_matching_keywords(text):
    """
    Return opportunity keywords found in the text.
    """

    text = clean_lower(
        text
    )

    matches = []

    for keyword in OPPORTUNITY_KEYWORDS:

        if keyword in text:

            matches.append(
                keyword
            )

    return matches


def find_strong_signals(text):
    """
    Return strong opportunity signals.
    """

    text = clean_lower(
        text
    )

    matches = []

    for signal in STRONG_OPPORTUNITY_SIGNALS:

        if signal in text:

            matches.append(
                signal
            )

    return matches


def find_news_signals(text):
    """
    Return common news/general-reporting signals.
    """

    text = clean_lower(
        text
    )

    matches = []

    for signal in NEWS_SIGNALS:

        if signal in text:

            matches.append(
                signal
            )

    return matches


def find_title_news_signals(text):
    """
    Detect news-style wording specifically in a title.
    """

    text = clean_lower(
        text
    )

    matches = []

    for signal in NEWS_TITLE_SIGNALS:

        if signal in text:

            matches.append(
                signal
            )

    return matches


# ============================================================
# APPLICATION LINK DETECTION
# ============================================================

def is_application_link(
    url,
    anchor_text="",
):
    """
    Determine whether a link looks like an application link.
    """

    combined = (
        clean_text(url)
        + " "
        + clean_text(anchor_text)
    ).lower()

    application_terms = [
        "apply",
        "application",
        "apply-now",
        "applynow",
        "register",
        "registration",
        "admissions",
        "admission",
        "enroll",
        "enrol",
        "portal",
        "application-form",
        "applicationform",
        "job-application",
        "jobs/apply",
        "careers/apply",
        "scholarship/apply",
        "fellowship/apply",
    ]

    return any(
        term in combined
        for term in application_terms
    )


def application_link_score(
    url,
    anchor_text="",
):
    """
    Score an application URL candidate.
    """

    combined = (
        clean_text(url)
        + " "
        + clean_text(anchor_text)
    ).lower()

    score = 0

    strong_terms = [
        "apply now",
        "apply here",
        "application form",
        "application portal",
        "submit application",
        "apply online",
    ]

    medium_terms = [
        "apply",
        "application",
        "register",
        "registration",
        "admission",
        "admissions",
        "enroll",
        "enrol",
        "portal",
    ]

    for term in strong_terms:

        if term in combined:

            score += 5

    for term in medium_terms:

        if term in combined:

            score += 2

    return score


def find_application_url(
    html,
    base_url,
):
    """
    Find the strongest likely application URL.

    This does NOT automatically claim that the URL is safe
    or official. It is stored as a candidate.
    """

    if not html:

        return ""

    pattern = re.compile(
        r'<a\b[^>]*href=["\'](.*?)["\'][^>]*>(.*?)</a>',
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    candidates = []

    for match in pattern.finditer(
        html
    ):

        href = clean_text(
            match.group(1)
        )

        anchor = clean_text(
            strip_html(
                match.group(2)
            )
        )

        if not href:

            continue

        absolute = urljoin(
            base_url,
            href,
        )

        if not is_valid_url(
            absolute
        ):

            continue

        if is_application_link(
            absolute,
            anchor,
        ):

            score = application_link_score(
                absolute,
                anchor,
            )

            candidates.append(
                (
                    score,
                    absolute,
                    anchor,
                )
            )

    if not candidates:

        return ""

    candidates.sort(
        key=lambda item: (
            item[0],
            len(item[2]),
        ),
        reverse=True,
    )

    return candidates[0][1]


def find_application_candidates(
    html,
    base_url,
):
    """
    Return multiple application candidates for diagnostics.
    """

    if not html:

        return []

    pattern = re.compile(
        r'<a\b[^>]*href=["\'](.*?)["\'][^>]*>(.*?)</a>',
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    candidates = []

    seen = set()

    for match in pattern.finditer(
        html
    ):

        href = clean_text(
            match.group(1)
        )

        anchor = clean_text(
            strip_html(
                match.group(2)
            )
        )

        if not href:

            continue

        absolute = urljoin(
            base_url,
            href,
        )

        if not is_valid_url(
            absolute
        ):

            continue

        if not is_application_link(
            absolute,
            anchor,
        ):

            continue

        normalized = normalize_url(
            absolute
        ).lower()

        if normalized in seen:

            continue

        seen.add(
            normalized
        )

        candidates.append(
            {
                "url": absolute,
                "anchor": anchor,
                "score": application_link_score(
                    absolute,
                    anchor,
                ),
                "trusted_domain": is_trusted_domain(
                    absolute
                ),
            }
        )

        if len(candidates) >= 10:

            break

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return candidates


# ============================================================
# OFFICIAL URL RESOLUTION
# ============================================================

def resolve_official_url(
    original_url,
    page,
):
    """
    Determine the best source URL to use.

    Priority:
        1. canonical URL
        2. final redirected URL
        3. original URL

    We do NOT replace an actual article URL with a publisher
    homepage simply because the publisher domain is trusted.
    """

    canonical = clean_text(
        page.get(
            "canonical",
            "",
        )
    )

    final_url = clean_text(
        page.get(
            "final_url",
            "",
        )
    )

    if (
        canonical
        and is_valid_url(
            canonical
        )
        and not is_homepage_url(
            canonical
        )
    ):

        return canonical

    if (
        final_url
        and is_valid_url(
            final_url
        )
    ):

        return final_url

    return original_url


# ============================================================
# SOURCE URL RESOLUTION
# ============================================================

def choose_candidate_source_url(
    item,
):
    """
    Select the best URL from the discovered item.

    Discovery can contain multiple URL fields. We prefer the
    most specific-looking source URL rather than blindly using
    a publisher homepage.
    """

    candidates = []

    field_names = [
        "source_url",
        "url",
        "link",
        "news_url",
        "publisher_url",
    ]

    for field in field_names:

        value = clean_text(
            item.get(
                field,
                "",
            )
        )

        if not value:

            continue

        if not is_valid_url(
            value
        ):

            continue

        normalized = normalize_url(
            value
        ).lower()

        if any(
            candidate["normalized"]
            == normalized
            for candidate in candidates
        ):

            continue

        candidates.append(
            {
                "field": field,
                "url": value,
                "normalized": normalized,
                "homepage": is_homepage_url(
                    value
                ),
            }
        )

    if not candidates:

        return ""

    # Prefer non-homepage URLs.
    non_homepage = [
        candidate
        for candidate in candidates
        if not candidate["homepage"]
    ]

    if non_homepage:

        # source_url / url / link / news_url preferred.
        priority = {
            "source_url": 5,
            "url": 4,
            "link": 4,
            "news_url": 3,
            "publisher_url": 1,
        }

        non_homepage.sort(
            key=lambda candidate: priority.get(
                candidate["field"],
                0,
            ),
            reverse=True,
        )

        return non_homepage[0]["url"]

    # If everything is homepage-like, use the first URL.
    return candidates[0]["url"]


def find_more_specific_link(
    page,
    base_url,
    title,
    description,
):
    """
    When discovery supplied a publisher homepage, inspect its
    links for a more specific opportunity/article page.

    This is deliberately conservative and only returns a
    candidate when the linked page appears relevant from its
    anchor text/URL.
    """

    links = page.get(
        "links",
        []
    )

    if not links:

        return ""

    target_text = clean_lower(
        " ".join(
            [
                title,
                description,
            ]
        )
    )

    target_terms = []

    for keyword in OPPORTUNITY_KEYWORDS:

        if keyword in target_text:

            target_terms.append(
                keyword
            )

    candidates = []

    for link in links:

        link_url = clean_text(
            link.get(
                "url",
                "",
            )
        )

        anchor = clean_text(
            link.get(
                "anchor",
                "",
            )
        )

        if not link_url:

            continue

        if not is_valid_url(
            link_url
        ):

            continue

        if is_homepage_url(
            link_url
        ):

            continue

        combined = clean_lower(
            link_url
            + " "
            + anchor
        )

        score = 0

        # Opportunity terminology in URL/anchor.
        for keyword in target_terms:

            if keyword in combined:

                score += 3

        # Strong application terminology.
        for signal in STRONG_OPPORTUNITY_SIGNALS:

            if signal in combined:

                score += 5

        # Match title words.
        title_words = [
            word
            for word in re.findall(
                r"\b[a-zA-Z]{4,}\b",
                clean_lower(title),
            )
            if word not in {
                "with",
                "from",
                "this",
                "that",
                "your",
                "about",
                "2025",
                "2026",
                "2027",
                "2028",
            }
        ]

        for word in title_words[:20]:

            if word in combined:

                score += 1

        if score >= 5:

            candidates.append(
                (
                    score,
                    link_url,
                    anchor,
                )
            )

    if not candidates:

        return ""

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return candidates[0][1]


# ============================================================
# QUALITY / EVIDENCE HELPERS
# ============================================================

def has_application_language(text):
    """
    Determine whether text contains meaningful application
    language.
    """

    normalized = clean_lower(
        text
    )

    return any(
        phrase in normalized
        for phrase in APPLICATION_KEYWORDS
    )


def has_eligibility_language(text):
    """
    Determine whether meaningful eligibility language exists.
    """

    normalized = clean_lower(
        text
    )

    return any(
        phrase in normalized
        for phrase in ELIGIBILITY_KEYWORDS
    )


def has_funding_language(text):
    """
    Determine whether funding information exists.
    """

    normalized = clean_lower(
        text
    )

    return any(
        phrase in normalized
        for phrase in FUNDING_KEYWORDS
    )


def is_news_heavy(
    title,
    text,
    news_signals,
):
    """
    Determine whether a page looks more like news/general
    reporting than an opportunity listing.
    """

    normalized_title = clean_lower(
        title
    )

    normalized_text = clean_lower(
        text
    )

    title_news = find_title_news_signals(
        normalized_title
    )

    word_count = count_words(
        normalized_text
    )

    news_count = len(
        news_signals
    )

    opportunity_count = len(
        find_strong_signals(
            normalized_text
        )
    )

    # Strong news title with little opportunity evidence.
    if (
        title_news
        and opportunity_count == 0
    ):

        return True

    # Very news-heavy text.
    if (
        news_count >= 6
        and opportunity_count <= 1
    ):

        return True

    # Extremely short article with news signals and no
    # application evidence.
    if (
        word_count < MIN_PAGE_WORDS
        and news_count >= 3
        and opportunity_count == 0
    ):

        return True

    return False


def detect_page_type(
    title,
    text,
    application_url,
    deadline,
    news_signals,
    strong_signals,
):
    """
    Classify the general page type.
    """

    if (
        application_url
        or deadline
        or (
            len(strong_signals) >= 2
            and has_application_language(text)
        )
    ):

        return "opportunity_page"

    if is_news_heavy(
        title,
        text,
        news_signals,
    ):

        return "news_or_general_page"

    if (
        has_opportunity_language_only(
            text
        )
    ):

        return "possible_opportunity_page"

    return "general_page"


def has_opportunity_language_only(
    text
):
    """
    Detect broad opportunity language.
    """

    normalized = clean_lower(
        text
    )

    return any(
        keyword in normalized
        for keyword in OPPORTUNITY_KEYWORDS
    )


# ============================================================
# QUALITY SCORING
# ============================================================

def calculate_opportunity_score(
    title,
    description,
    page_title,
    page_description,
    page_text,
    trusted_domain,
    application_url,
    deadline="",
    page_word_count=0,
):
    """
    Calculate an evidence score.

    Higher score = stronger evidence that the page is an
    actual opportunity page rather than a general news article.

    The score is intentionally capped/penalized so that simply
    repeating generic words cannot create a high score.
    """

    combined = clean_text(
        " ".join(
            [
                title,
                description,
                page_title,
                page_description,
                page_text,
            ]
        )
    ).lower()

    score = 0

    reasons = []

    # --------------------------------------------------------
    # Strong opportunity signals
    # --------------------------------------------------------

    strong_signals = find_strong_signals(
        combined
    )

    if strong_signals:

        contribution = min(
            len(strong_signals) * 3,
            21,
        )

        score += contribution

        reasons.append(
            "strong opportunity signals: "
            + ", ".join(
                strong_signals[:8]
            )
        )

    # --------------------------------------------------------
    # Opportunity keywords
    # --------------------------------------------------------

    keyword_matches = find_matching_keywords(
        combined
    )

    if keyword_matches:

        contribution = min(
            len(keyword_matches),
            8,
        )

        score += contribution

        reasons.append(
            "opportunity keywords: "
            + ", ".join(
                keyword_matches[:8]
            )
        )

    # --------------------------------------------------------
    # Trusted domain
    # --------------------------------------------------------

    if trusted_domain:

        score += 5

        reasons.append(
            "trusted source domain"
        )

    # --------------------------------------------------------
    # Application URL
    # --------------------------------------------------------

    if application_url:

        score += 8

        reasons.append(
            "application link detected"
        )

    # --------------------------------------------------------
    # Eligibility language
    # --------------------------------------------------------

    eligibility_signals = detect_eligibility(
        combined
    )

    if eligibility_signals:

        score += min(
            len(eligibility_signals) * 2,
            8,
        )

        reasons.append(
            "eligibility information detected"
        )

    # --------------------------------------------------------
    # Funding language
    # --------------------------------------------------------

    funding_data = detect_funding(
        combined
    )

    if funding_data[
        "funding_detected"
    ]:

        score += min(
            len(
                funding_data[
                    "funding_signals"
                ]
            ) * 2,
            8,
        )

        reasons.append(
            "funding information detected"
        )

    # --------------------------------------------------------
    # Deadline
    # --------------------------------------------------------

    if deadline:

        score += 6

        reasons.append(
            f"deadline detected: {deadline}"
        )

    elif "deadline" in combined:

        score += 2

        reasons.append(
            "deadline language detected"
        )

    # --------------------------------------------------------
    # Page quality
    # --------------------------------------------------------

    if page_word_count >= 500:

        score += 3

        reasons.append(
            "substantial page content"
        )

    elif page_word_count >= 200:

        score += 2

        reasons.append(
            "adequate page content"
        )

    elif page_word_count >= MIN_PAGE_WORDS:

        score += 1

    else:

        score -= 3

        reasons.append(
            "very short page content"
        )

    # --------------------------------------------------------
    # News signals
    # --------------------------------------------------------

    news_signals = find_news_signals(
        combined
    )

    if news_signals:

        penalty = min(
            len(news_signals) * 2,
            MAX_NEWS_PENALTY,
        )

        score -= penalty

        reasons.append(
            "news/general signals: "
            + ", ".join(
                news_signals[:8]
            )
        )

    # --------------------------------------------------------
    # News-heavy title
    # --------------------------------------------------------

    title_news_signals = find_title_news_signals(
        title
        + " "
        + page_title
    )

    if title_news_signals:

        score -= min(
            len(title_news_signals) * 2,
            6,
        )

        reasons.append(
            "news-style title signals: "
            + ", ".join(
                title_news_signals[:6]
            )
        )

    # --------------------------------------------------------
    # Opportunity vs news balance
    # --------------------------------------------------------

    if (
        len(news_signals) >= 5
        and len(strong_signals) <= 1
        and not application_url
        and not deadline
    ):

        score -= 5

        reasons.append(
            "news evidence outweighs opportunity evidence"
        )

    return score, reasons


def classify_relevance(
    score,
    trusted_domain,
    strong_signals,
    application_url,
    deadline,
    news_signals,
    title,
    page_text,
    page_word_count,
):
    """
    Convert evidence into a conservative classification.

    Returns:
        (
            relevant,
            needs_human_review,
            classification
        )
    """

    news_heavy = is_news_heavy(
        title,
        page_text,
        news_signals,
    )

    meaningful_application_evidence = (
        bool(application_url)
        or has_application_language(
            page_text
        )
    )

    meaningful_eligibility = (
        has_eligibility_language(
            page_text
        )
    )

    meaningful_funding = (
        has_funding_language(
            page_text
        )
    )

    meaningful_deadline = bool(
        deadline
    )

    # --------------------------------------------------------
    # Hard protection against obvious news/general pages.
    # --------------------------------------------------------

    if (
        news_heavy
        and not application_url
        and not deadline
        and not meaningful_application_evidence
    ):

        return (
            False,
            True,
            "likely_news_or_general_content",
        )

    # --------------------------------------------------------
    # Confirmed opportunity.
    #
    # Requires strong evidence, not just generic keywords.
    # --------------------------------------------------------

    strong_evidence_count = sum(
        [
            bool(strong_signals),
            bool(application_url),
            meaningful_application_evidence,
            meaningful_eligibility,
            meaningful_funding,
            meaningful_deadline,
        ]
    )

    if (
        score >= 16
        and strong_evidence_count >= 2
        and page_word_count >= MIN_PAGE_WORDS
        and not (
            news_heavy
            and not application_url
            and not deadline
        )
    ):

        return (
            True,
            False,
            "confirmed_opportunity",
        )

    # --------------------------------------------------------
    # Trusted opportunity.
    # --------------------------------------------------------

    if (
        trusted_domain
        and score >= 10
        and (
            strong_signals
            or application_url
            or deadline
        )
        and page_word_count >= MIN_PAGE_WORDS
    ):

        return (
            True,
            False,
            "trusted_opportunity",
        )

    # --------------------------------------------------------
    # Possible opportunity.
    #
    # Useful for diagnostics but NOT for auto publication.
    # --------------------------------------------------------

    if (
        score >= 7
        and (
            strong_signals
            or application_url
            or deadline
            or meaningful_eligibility
            or meaningful_funding
        )
    ):

        return (
            True,
            True,
            "possible_opportunity",
        )

    # --------------------------------------------------------
    # News-heavy weak pages.
    # --------------------------------------------------------

    if (
        news_signals
        and score < 7
    ):

        return (
            False,
            True,
            "likely_news_or_general_content",
        )

    return (
        False,
        True,
        "insufficient_opportunity_evidence",
    )


# ============================================================
# VERIFICATION ENGINE
# ============================================================

def determine_verification(item):

    original_discovered_url = clean_text(
        item.get(
            "source_url"
            or "url"
            or "link"
            or "news_url"
        )
    )

    selected_url = choose_candidate_source_url(
        item
    )

    title = clean_text(
        item.get(
            "title"
        )
    )

    description = clean_text(
        item.get(
            "description"
        )
        or item.get(
            "summary"
        )
    )

    publisher_name = clean_text(
        item.get(
            "publisher_name"
        )
        or item.get(
            "publisher"
        )
    )

    result = {
        "verification_level": "failed",

        "source_verified": False,

        "page_reachable": False,

        "source_domain_trusted": False,

        "opportunity_relevant": False,

        "needs_human_review": True,

        "verification_reason": "",

        "checked_url": selected_url,

        "original_discovered_url": (
            original_discovered_url
        ),

        "final_url": selected_url,

        "official_url": selected_url,

        "application_url": "",

        "application_domain": "",

        "application_domain_trusted": False,

        "canonical_url": "",

        "http_status": None,

        "content_type": "",

        "source_domain": get_domain(
            selected_url
        ),

        "opportunity_score": 0,

        "opportunity_classification": "failed",

        "matched_keywords": [],

        "strong_opportunity_signals": [],

        "news_signals": [],

        "news_title_signals": [],

        "verification_evidence": [],

        "detected_category": "opportunities",

        "detected_location": "",

        "detected_deadline": "",

        "date_candidates": [],

        "eligibility_signals": [],

        "funding_detected": False,

        "funding_type": "",

        "funding_signals": [],

        "page_title": "",

        "page_description": "",

        "page_h1": "",

        "page_word_count": 0,

        "page_type": "unknown",

        "source_url_resolved": False,

        "source_url_resolution_method": "",

        "application_candidates": [],

        "publisher_name": publisher_name,
    }

    # ========================================================
    # 1. URL validation
    # ========================================================

    if not is_valid_url(
        selected_url
    ):

        result[
            "verification_reason"
        ] = (
            "Invalid or missing source URL."
        )

        return result

    # ========================================================
    # 2. Domain trust check
    # ========================================================

    trusted_domain = is_trusted_domain(
        selected_url
    )

    result[
        "source_domain_trusted"
    ] = trusted_domain

    # ========================================================
    # 3. Reachability check
    # ========================================================

    page = fetch_page(
        selected_url
    )

    result[
        "page_reachable"
    ] = page[
        "reachable"
    ]

    result[
        "http_status"
    ] = page[
        "status_code"
    ]

    result[
        "final_url"
    ] = page[
        "final_url"
    ]

    result[
        "content_type"
    ] = page.get(
        "content_type",
        "",
    )

    if not page[
        "reachable"
    ]:

        result[
            "verification_reason"
        ] = (
            "Source page could not be reached."
        )

        if page.get(
            "error"
        ):

            result[
                "verification_error"
            ] = page[
                "error"
            ]

        return result

    # ========================================================
    # 4. Resolve official/source URL
    # ========================================================

    official_url = resolve_official_url(
        selected_url,
        page,
    )

    result[
        "official_url"
    ] = official_url

    result[
        "source_domain"
    ] = get_domain(
        official_url
    )

    redirected = (
        normalize_url(
            selected_url
        )
        != normalize_url(
            page.get(
                "final_url",
                selected_url,
            )
        )
    )

    canonical_exists = bool(
        page.get(
            "canonical",
            "",
        )
    )

    if canonical_exists:

        result[
            "source_url_resolved"
        ] = True

        result[
            "source_url_resolution_method"
        ] = "canonical"

    elif redirected:

        result[
            "source_url_resolved"
        ] = True

        result[
            "source_url_resolution_method"
        ] = "redirect"

    else:

        result[
            "source_url_resolved"
        ] = False

        result[
            "source_url_resolution_method"
        ] = "original"

    # Re-check trust after redirects/canonical.
    result[
        "source_domain_trusted"
    ] = (
        trusted_domain
        or is_trusted_domain(
            official_url
        )
    )

    # ========================================================
    # 5. Extract page information
    # ========================================================

    page_title = clean_text(
        page.get(
            "title",
            "",
        )
    )

    page_description = clean_text(
        page.get(
            "description",
            "",
        )
    )

    page_h1 = clean_text(
        page.get(
            "h1",
            "",
        )
    )

    page_text = clean_text(
        page.get(
            "text",
            "",
        )
    )

    page_word_count = int(
        page.get(
            "word_count",
            0,
        )
        or 0
    )

    result[
        "page_title"
    ] = page_title

    result[
        "page_description"
    ] = page_description

    result[
        "page_h1"
    ] = page_h1

    result[
        "page_word_count"
    ] = page_word_count

    result[
        "canonical_url"
    ] = clean_text(
        page.get(
            "canonical",
            "",
        )
    )

    # Limit analysis size to keep workflow efficient.
    analysis_text = clean_text(
        " ".join(
            [
                title,
                description,
                page_title,
                page_description,
                page_h1,
                page_text[:MAX_ANALYSIS_CHARS],
            ]
        )
    )

    # ========================================================
    # 6. Keyword detection
    # ========================================================

    matched_keywords = find_matching_keywords(
        analysis_text
    )

    strong_signals = find_strong_signals(
        analysis_text
    )

    news_signals = find_news_signals(
        analysis_text
    )

    news_title_signals = find_title_news_signals(
        " ".join(
            [
                title,
                page_title,
                page_h1,
            ]
        )
    )

    result[
        "matched_keywords"
    ] = matched_keywords

    result[
        "strong_opportunity_signals"
    ] = strong_signals

    result[
        "news_signals"
    ] = news_signals

    result[
        "news_title_signals"
    ] = news_title_signals

    # ========================================================
    # 7. Detect category
    # ========================================================

    result[
        "detected_category"
    ] = detect_category(
        analysis_text
    )

    # ========================================================
    # 8. Detect location
    # ========================================================

    result[
        "detected_location"
    ] = detect_location(
        analysis_text
    )

    # ========================================================
    # 9. Detect deadline
    # ========================================================

    detected_deadline = extract_deadline(
        analysis_text
    )

    result[
        "detected_deadline"
    ] = detected_deadline

    result[
        "date_candidates"
    ] = extract_date_candidates(
        analysis_text
    )

    # ========================================================
    # 10. Detect eligibility
    # ========================================================

    eligibility_signals = detect_eligibility(
        analysis_text
    )

    result[
        "eligibility_signals"
    ] = eligibility_signals

    # ========================================================
    # 11. Detect funding
    # ========================================================

    funding_data = detect_funding(
        analysis_text
    )

    result[
        "funding_detected"
    ] = funding_data[
        "funding_detected"
    ]

    result[
        "funding_type"
    ] = funding_data[
        "funding_type"
    ]

    result[
        "funding_signals"
    ] = funding_data[
        "funding_signals"
    ]

    # ========================================================
    # 12. Detect application URL
    # ========================================================

    application_candidates = (
        find_application_candidates(
            page.get(
                "content",
                "",
            ),
            page.get(
                "final_url",
                selected_url,
            ),
        )
    )

    result[
        "application_candidates"
    ] = [
        {
            "url": candidate[
                "url"
            ],
            "anchor": candidate[
                "anchor"
            ],
            "score": candidate[
                "score"
            ],
            "trusted_domain": candidate[
                "trusted_domain"
            ],
        }
        for candidate in application_candidates[:10]
    ]

    application_url = ""

    if application_candidates:

        application_url = (
            application_candidates[0][
                "url"
            ]
        )

    result[
        "application_url"
    ] = application_url

    if application_url:

        result[
            "application_domain"
        ] = get_domain(
            application_url
        )

        result[
            "application_domain_trusted"
        ] = is_trusted_domain(
            application_url
        )

    # ========================================================
    # 13. Basic opportunity presence
    # ========================================================

    relevant_keyword_found = (
        contains_opportunity_keyword(
            analysis_text
        )
    )

    if not relevant_keyword_found:

        result[
            "verification_reason"
        ] = (
            "Source page was reachable but no "
            "opportunity-related terminology was detected."
        )

        result[
            "page_type"
        ] = "general_page"

        return result

    # ========================================================
    # 14. Publisher homepage protection
    # ========================================================
    #
    # If the discovered URL is a homepage and the homepage
    # contains links to more specific opportunity pages,
    # record the candidate. We do not blindly switch pages
    # because the candidate still needs verification.
    # ========================================================

    if is_homepage_url(
        selected_url
    ):

        specific_candidate = find_more_specific_link(
            page=page,
            base_url=page.get(
                "final_url",
                selected_url,
            ),
            title=title,
            description=description,
        )

        if specific_candidate:

            result[
                "specific_opportunity_candidate_url"
            ] = specific_candidate

            result[
                "verification_evidence"
            ].append(
                "Publisher homepage detected; "
                "a more specific opportunity/article "
                "candidate link was found."
            )

    # ========================================================
    # 15. Evidence score
    # ========================================================

    score, score_reasons = (
        calculate_opportunity_score(
            title=title,
            description=description,
            page_title=page_title,
            page_description=page_description,
            page_text=page_text[:MAX_ANALYSIS_CHARS],
            trusted_domain=result[
                "source_domain_trusted"
            ],
            application_url=application_url,
            deadline=detected_deadline,
            page_word_count=page_word_count,
        )
    )

    result[
        "opportunity_score"
    ] = score

    # ========================================================
    # 16. Page type
    # ========================================================

    page_type = detect_page_type(
        title=(
            title
            + " "
            + page_title
        ),
        text=page_text,
        application_url=application_url,
        deadline=detected_deadline,
        news_signals=news_signals,
        strong_signals=strong_signals,
    )

    result[
        "page_type"
    ] = page_type

    # ========================================================
    # 17. Classification
    # ========================================================

    (
        relevant,
        needs_review,
        classification,
    ) = classify_relevance(
        score=score,
        trusted_domain=result[
            "source_domain_trusted"
        ],
        strong_signals=strong_signals,
        application_url=application_url,
        deadline=detected_deadline,
        news_signals=news_signals,
        title=(
            title
            + " "
            + page_title
        ),
        page_text=page_text,
        page_word_count=page_word_count,
    )

    result[
        "opportunity_relevant"
    ] = relevant

    result[
        "needs_human_review"
    ] = needs_review

    result[
        "opportunity_classification"
    ] = classification

    # ========================================================
    # 18. Verification level
    # ========================================================

    if classification in {
        "confirmed_opportunity",
        "trusted_opportunity",
    }:

        if result[
            "source_domain_trusted"
        ]:

            result[
                "verification_level"
            ] = "source_checked"

            result[
                "source_verified"
            ] = True

            result[
                "verification_reason"
            ] = (
                "The source page is reachable and "
                "contains meaningful evidence of a real "
                "opportunity. The source domain is trusted "
                "and/or the page contains application, "
                "eligibility, funding or deadline signals. "
                f"Evidence score: {score}."
            )

        else:

            result[
                "verification_level"
            ] = "page_checked"

            result[
                "source_verified"
            ] = True

            result[
                "verification_reason"
            ] = (
                "The source page is reachable and "
                "contains strong evidence of a real "
                "opportunity. The domain is not on the "
                "trusted-domain list, so additional "
                "review is required before automatic "
                f"publication. Evidence score: {score}."
            )

            # Non-trusted domains remain human-review items.
            result[
                "needs_human_review"
            ] = True

    elif classification == (
        "possible_opportunity"
    ):

        result[
            "verification_level"
        ] = "page_checked"

        result[
            "source_verified"
        ] = False

        result[
            "verification_reason"
        ] = (
            "The page contains some opportunity-related "
            "evidence, but the evidence is not strong "
            "enough for automatic approval. Human review "
            f"is required. Evidence score: {score}."
        )

    elif classification == (
        "likely_news_or_general_content"
    ):

        result[
            "verification_level"
        ] = "failed"

        result[
            "source_verified"
        ] = False

        result[
            "verification_reason"
        ] = (
            "The page is reachable but appears to be "
            "news/reporting or general content rather "
            "than a specific opportunity listing. "
            f"Evidence score: {score}."
        )

    else:

        result[
            "verification_level"
        ] = "failed"

        result[
            "source_verified"
        ] = False

        result[
            "verification_reason"
        ] = (
            "The page is reachable but there is "
            "insufficient evidence that it represents "
            "a real opportunity rather than general "
            f"content. Evidence score: {score}."
        )

    # ========================================================
    # 19. Strong evidence summary
    # ========================================================

    evidence_summary = list(
        score_reasons
    )

    if application_url:

        evidence_summary.append(
            "application URL: "
            + application_url
        )

    if detected_deadline:

        evidence_summary.append(
            "detected deadline: "
            + detected_deadline
        )

    if eligibility_signals:

        evidence_summary.append(
            "eligibility signals present"
        )

    if funding_data[
        "funding_detected"
    ]:

        evidence_summary.append(
            "funding signals present: "
            + ", ".join(
                funding_data[
                    "funding_signals"
                ][:6]
            )
        )

    result[
        "verification_evidence"
    ] = evidence_summary[:20]

    # ========================================================
    # 20. Preserve original item metadata
    # ========================================================

    if publisher_name:

        result[
            "publisher_name"
        ] = publisher_name

    return result


# ============================================================
# VERIFY ONE ITEM
# ============================================================

def verify_item(item):

    verification = determine_verification(
        item
    )

    verified_item = dict(
        item
    )

    verified_item.update(
        verification
    )

    # --------------------------------------------------------
    # Never store downloaded page HTML in JSON.
    # --------------------------------------------------------

    verified_item.pop(
        "content",
        None
    )

    verified_item.pop(
        "html",
        None
    )

    # --------------------------------------------------------
    # Never store internal full page links unnecessarily.
    # --------------------------------------------------------

    verified_item.pop(
        "links",
        None
    )

    return verified_item


# ============================================================
# SAFE JSON LOADING
# ============================================================

def load_json_file(
    path,
):
    """
    Load JSON safely.
    """

    try:

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:

        print(
            f"Could not read JSON file {path}: {error}"
        )

        return None


# ============================================================
# MAIN
# ============================================================

def main():

    if not INPUT_FILE.exists():

        print(
            f"Input file not found: {INPUT_FILE}"
        )

        return

    data = load_json_file(
        INPUT_FILE
    )

    if data is None:

        return

    # --------------------------------------------------------
    # Support the existing discovered JSON structure.
    # --------------------------------------------------------

    items = data.get(
        "items",
        []
    )

    if not isinstance(
        items,
        list
    ):

        print(
            "Input JSON does not contain a valid "
            "'items' list."
        )

        return

    verified_items = []

    source_checked = 0

    page_checked = 0

    failed = 0

    human_review = 0

    confirmed_opportunities = 0

    trusted_opportunities = 0

    possible_opportunities = 0

    rejected_or_non_opportunities = 0

    likely_news = 0

    insufficient_evidence = 0

    application_links_detected = 0

    deadlines_detected = 0

    funding_detected = 0

    eligibility_detected = 0

    trusted_sources = 0

    non_trusted_sources = 0

    reachable_pages = 0

    unreachable_pages = 0

    total_score = 0

    print(
        "=" * 60
    )

    print(
        "OPPORTUNITYBRIDGE VERIFICATION ENGINE"
    )

    print(
        "Version: 4.0"
    )

    print(
        "=" * 60
    )

    print(
        f"Input items: {len(items)}"
    )

    for index, item in enumerate(
        items,
        start=1
    ):

        title = clean_text(
            item.get(
                "title"
            )
        )

        print()

        print(
            f"[{index}/{len(items)}] {title}"
        )

        verified = verify_item(
            item
        )

        level = verified.get(
            "verification_level",
            "failed"
        )

        classification = verified.get(
            "opportunity_classification",
            "failed"
        )

        score = verified.get(
            "opportunity_score",
            0
        )

        total_score += int(
            score
            or 0
        )

        print(
            f"Verification level: {level}"
        )

        print(
            f"Classification: {classification}"
        )

        print(
            f"Opportunity score: {score}"
        )

        print(
            "Source trusted: "
            f"{verified.get('source_domain_trusted')}"
        )

        print(
            "Page reachable: "
            f"{verified.get('page_reachable')}"
        )

        print(
            "Relevant: "
            f"{verified.get('opportunity_relevant')}"
        )

        print(
            "Human review: "
            f"{verified.get('needs_human_review')}"
        )

        print(
            "Category: "
            f"{verified.get('detected_category')}"
        )

        print(
            "Location: "
            f"{verified.get('detected_location')}"
        )

        print(
            "Deadline: "
            f"{verified.get('detected_deadline')}"
        )

        print(
            "Funding: "
            f"{verified.get('funding_type')}"
        )

        print(
            "Application URL: "
            f"{verified.get('application_url')}"
        )

        print(
            "Page type: "
            f"{verified.get('page_type')}"
        )

        print(
            "Page words: "
            f"{verified.get('page_word_count')}"
        )

        print(
            "Official URL: "
            f"{verified.get('official_url')}"
        )

        # ----------------------------------------------------
        # Counters
        # ----------------------------------------------------

        if verified.get(
            "page_reachable"
        ):

            reachable_pages += 1

        else:

            unreachable_pages += 1

        if level == "source_checked":

            source_checked += 1

        elif level == "page_checked":

            page_checked += 1

        else:

            failed += 1

        if verified.get(
            "needs_human_review"
        ):

            human_review += 1

        if verified.get(
            "source_domain_trusted"
        ):

            trusted_sources += 1

        else:

            non_trusted_sources += 1

        if verified.get(
            "application_url"
        ):

            application_links_detected += 1

        if verified.get(
            "detected_deadline"
        ):

            deadlines_detected += 1

        if verified.get(
            "funding_detected"
        ):

            funding_detected += 1

        if verified.get(
            "eligibility_signals"
        ):

            eligibility_detected += 1

        if classification == (
            "confirmed_opportunity"
        ):

            confirmed_opportunities += 1

        elif classification == (
            "trusted_opportunity"
        ):

            trusted_opportunities += 1

        elif classification == (
            "possible_opportunity"
        ):

            possible_opportunities += 1

        else:

            rejected_or_non_opportunities += 1

        if classification == (
            "likely_news_or_general_content"
        ):

            likely_news += 1

        elif classification == (
            "insufficient_opportunity_evidence"
        ):

            insufficient_evidence += 1

        verified_items.append(
            verified
        )

    # ========================================================
    # AVERAGE SCORE
    # ========================================================

    if verified_items:

        average_score = round(
            total_score
            / len(
                verified_items
            ),
            2,
        )

    else:

        average_score = 0

    # ========================================================
    # OUTPUT
    # ========================================================

    output = {

        "verification_engine_version": "4.0",

        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "total_checked": len(
            verified_items
        ),

        "source_checked": source_checked,

        "page_checked": page_checked,

        "failed": failed,

        "reachable_pages": reachable_pages,

        "unreachable_pages": unreachable_pages,

        "human_review_required": human_review,

        "confirmed_opportunities": (
            confirmed_opportunities
        ),

        "trusted_opportunities": (
            trusted_opportunities
        ),

        "possible_opportunities": (
            possible_opportunities
        ),

        "rejected_or_non_opportunities": (
            rejected_or_non_opportunities
        ),

        "likely_news_or_general_content": (
            likely_news
        ),

        "insufficient_opportunity_evidence": (
            insufficient_evidence
        ),

        "trusted_sources": (
            trusted_sources
        ),

        "non_trusted_sources": (
            non_trusted_sources
        ),

        "application_links_detected": (
            application_links_detected
        ),

        "deadlines_detected": (
            deadlines_detected
        ),

        "funding_detected": (
            funding_detected
        ),

        "eligibility_detected": (
            eligibility_detected
        ),

        "average_opportunity_score": (
            average_score
        ),

        "items": verified_items,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # ========================================================
    # FINAL REPORT
    # ========================================================

    print()

    print(
        "=" * 60
    )

    print(
        "VERIFICATION COMPLETE"
    )

    print(
        "=" * 60
    )

    print(
        f"Total checked: "
        f"{len(verified_items)}"
    )

    print(
        f"Source checked: "
        f"{source_checked}"
    )

    print(
        f"Page checked: "
        f"{page_checked}"
    )

    print(
        f"Reachable pages: "
        f"{reachable_pages}"
    )

    print(
        f"Unreachable pages: "
        f"{unreachable_pages}"
    )

    print(
        f"Failed: "
        f"{failed}"
    )

    print(
        f"Confirmed opportunities: "
        f"{confirmed_opportunities}"
    )

    print(
        f"Trusted opportunities: "
        f"{trusted_opportunities}"
    )

    print(
        f"Possible opportunities: "
        f"{possible_opportunities}"
    )

    print(
        f"Human review required: "
        f"{human_review}"
    )

    print(
        f"Likely news/general content: "
        f"{likely_news}"
    )

    print(
        f"Insufficient opportunity evidence: "
        f"{insufficient_evidence}"
    )

    print(
        f"Trusted sources: "
        f"{trusted_sources}"
    )

    print(
        f"Non-trusted sources: "
        f"{non_trusted_sources}"
    )

    print(
        f"Application links detected: "
        f"{application_links_detected}"
    )

    print(
        f"Deadlines detected: "
        f"{deadlines_detected}"
    )

    print(
        f"Funding detected: "
        f"{funding_detected}"
    )

    print(
        f"Eligibility detected: "
        f"{eligibility_detected}"
    )

    print(
        f"Average opportunity score: "
        f"{average_score}"
    )

    print(
        f"Output: "
        f"{OUTPUT_FILE}"
    )

    print()

    print(
        "OPPORTUNITYBRIDGE VERIFICATION "
        "ENGINE COMPLETE"
    )


if __name__ == "__main__":

    main()
