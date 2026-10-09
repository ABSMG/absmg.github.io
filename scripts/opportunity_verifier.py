import json
import re
import socket
import ipaddress
from pathlib import Path
from urllib.parse import urlparse, urljoin, urlunparse, urlsplit
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener
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
    "scholarships": [        "scholarships",
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
    Validate a well-formed HTTP/HTTPS URL without credentials.
    """
    value = clean_text(url)

    if not value or re.search(r"\s", value):
        return False

    try:
        parsed = urlsplit(value)

        if parsed.scheme.lower() not in ("http", "https"):
            return False

        if not parsed.netloc or not parsed.hostname:
            return False

        if parsed.username is not None or parsed.password is not None:
            return False

        # Accessing .port raises ValueError for malformed ports.
        port = parsed.port

        if port is not None and not (1 <= port <= 65535):
            return False

        hostname = parsed.hostname.rstrip(".").lower()

        if not hostname:
            return False

        if any(character.isspace() for character in hostname):
            return False

        if hostname in {
            "localhost",
            "localhost.localdomain",
        }:
            return False

        return True

    except (TypeError, ValueError, UnicodeError):
        return False


def is_public_http_url(url):
    """
    Reject destinations that do not resolve exclusively to
    globally routable public IP addresses.
    """
    if not is_valid_url(url):
        return False

    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname

        if not hostname:
            return False

        port = parsed.port or (
            443 if parsed.scheme.lower() == "https" else 80
        )

        # Validate IP addresses supplied directly in the URL.
        try:
            address = ipaddress.ip_address(hostname)
            return address.is_global
        except ValueError:
            pass

        # Reject local and single-label hostnames.
        if "." not in hostname or hostname.endswith(".local"):
            return False

        records = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )

        addresses = {
            record[4][0]
            for record in records
            if record and len(record) > 4 and record[4]
        }

        if not addresses:
            return False

        for raw_address in addresses:
            try:
                address = ipaddress.ip_address(raw_address)
            except ValueError:
                return False

            if not address.is_global:
                return False

        return True

    except (TypeError, ValueError, OSError):
        return False


class SafeRedirectHandler(HTTPRedirectHandler):
    """
    Validate redirect destinations before following them.
    """

    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        target_url = urljoin(
            req.full_url,
            newurl,
        )

        if not is_public_http_url(target_url):
            raise URLError(
                "Redirect target is not a valid public HTTP/HTTPS URL."
            )

        return super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            target_url,
        )


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

    if domain in TRUSTED_EXACT_DOMAINS:

        return True

    for suffix in TRUSTED_DOMAIN_SUFFIXES:

        if domain.endswith(
            suffix
        ):

            return True

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

    if not title_match:        return ""

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


# ============================================================
# DATE / DEADLINE DETECTION
# ============================================================

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


# ============================================================
# DEADLINE EXPIRY CHECK
# ============================================================

def parse_deadline_date(value):
    """
    Parse a detected deadline into a timezone-aware UTC datetime.

    Returns None when the value cannot be parsed safely.
    """

    value = clean_text(
        value
    )

    if not value:

        return None

    candidates = [
        value,
        value.replace(
            "Z",
            "+00:00"
        ),
    ]

    for candidate in candidates:

        try:

            parsed = datetime.fromisoformat(
                candidate
            )

            if parsed.tzinfo is None:

                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed.astimezone(
                timezone.utc
            )

        except Exception:

            pass

    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]

    for date_format in date_formats:

        try:

            parsed = datetime.strptime(
                value,
                date_format
            )

            return parsed.replace(
                tzinfo=timezone.utc
            )

        except Exception:

            pass

    return None


def deadline_is_expired(value):
    """
    Return True when a parseable deadline is already in the past.
    """

    parsed = parse_deadline_date(
        value
    )

    if parsed is None:

        return False

    return parsed < datetime.now(
        timezone.utc
    )


# ============================================================
# CATEGORY / LOCATION / FUNDING / ELIGIBILITY
# ============================================================

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
    Fetch and analyze an HTTP/HTTPS page.

    Validate the initial URL and redirect destinations.
    Limit the response size and retain the existing result schema.
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
        if not is_public_http_url(url):
            result["error"] = (
                "Rejected invalid URL or destination that does not "
                "resolve exclusively to public IP addresses."
            )
            return result

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
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        opener = build_opener(
            SafeRedirectHandler
        )

        with opener.open(
            request,
            timeout=TIMEOUT,
        ) as response:

            status_code = response.getcode()
            final_url = response.geturl()

            content_type = response.headers.get(
                "Content-Type",
                "",
            )

            if not is_public_http_url(final_url):
                result["status_code"] = status_code
                result["final_url"] = final_url
                result["content_type"] = content_type
                result["error"] = (
                    "Rejected final URL because it is not a valid "
                    "public HTTP/HTTPS destination."
                )
                return result

            media_type = (
                content_type
                .split(";", 1)[0]
                .strip()
                .lower()
            )

            if media_type and media_type not in {
                "text/html",
                "application/xhtml+xml",
            } and not media_type.endswith("+html"):

                result["status_code"] = status_code
                result["final_url"] = final_url
                result["content_type"] = content_type
                result["error"] = (
                    "Unsupported content type; expected an HTML page."
                )
                return result

            raw = response.read(
                MAX_PAGE_BYTES
            )

            content = raw.decode(
                "utf-8",
                errors="replace",
            )

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

            result.update({
                "reachable": (
                    200 <= status_code < 400
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
            })

    except HTTPError as error:
        result["status_code"] = error.code
        result["error"] = f"HTTP {error.code}"

    except (
        URLError,
        socket.timeout,
        TimeoutError,
        OSError,
    ) as error:
        result["error"] = str(error)

    except Exception as error:
        result["error"] = str(error)

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


def has_direct_application_evidence(
    text
):
    """
    Detect direct application evidence from page text.

    This supplements HTML application-link detection because
    many modern websites use JavaScript buttons, forms, or
    external application systems that may not appear as a
    simple <a> element.
    """

    normalized = clean_lower(
        text
    )

    direct_application_phrases = [
        "apply now",
        "apply here",
        "apply online",
        "applications are open",
        "applications open",
        "application is open",
        "application form",
        "application portal",
        "submit application",
        "submit your application",
        "how to apply",
        "call for applications",
        "now accepting applications",
        "applications invited",
        "inviting applications",
        "register now",
        "registration is open",
        "enroll now",
        "enrol now",
    ]

    return any(
        phrase in normalized
        for phrase in direct_application_phrases
    )


def has_direct_deadline_evidence(
    text,
    deadline="",
):
    """
    Detect meaningful deadline evidence.

    A parsed deadline is strongest, but explicit deadline
    wording also counts as direct evidence.
    """

    if deadline:

        return True

    normalized = clean_lower(
        text
    )

    deadline_phrases = [
        "application deadline",
        "deadline",
        "closing date",
        "last date to apply",
        "last day to apply",
        "apply by",
        "applications close",
        "applications closing",
    ]

    return any(
        phrase in normalized
        for phrase in deadline_phrases
    )


def has_direct_funding_evidence(
    text
):
    """
    Detect meaningful funding evidence.

    This keeps funding as a distinct evidence category.
    """

    normalized = clean_lower(
        text
    )

    direct_funding_phrases = [
        "fully funded",
        "fully-funded",
        "funded by",
        "tuition waiver",
        "tuition fee",        "tuition fees",
        "fee waiver",
        "stipend",
        "monthly stipend",
        "living allowance",
        "financial support",
        "financial assistance",
        "travel allowance",
        "travel support",
        "scholarship award",
        "grant amount",
        "funding amount",
    ]

    return any(
        phrase in normalized
        for phrase in direct_funding_phrases
    )


def has_direct_eligibility_evidence(
    text
):
    """
    Detect meaningful eligibility evidence.

    This keeps eligibility as a distinct evidence category.
    """

    normalized = clean_lower(
        text
    )

    direct_eligibility_phrases = [
        "eligibility criteria",
        "eligibility requirements",
        "eligible applicants",
        "who can apply",
        "applicants must",
        "candidates must",
        "academic requirements",
        "academic qualification",
        "minimum qualification",
        "nationality requirement",
        "citizenship requirement",
        "age requirement",
    ]

    return any(
        phrase in normalized
        for phrase in direct_eligibility_phrases
    )


def count_direct_evidence_categories(
    strong_signals,
    application_url,
    page_text,
    deadline="",
):
    """
    Count independent categories of direct opportunity evidence.

    Categories:
        1. opportunity-specific strong signals
        2. application mechanism
        3. eligibility
        4. funding
        5. deadline

    Multiple phrases inside the same category do not inflate
    this count. This prevents repeated generic wording from
    being treated as independent evidence.
    """

    categories = []

    if strong_signals:

        categories.append(
            "opportunity_signal"
        )

    if (
        application_url
        or has_direct_application_evidence(
            page_text
        )
    ):

        categories.append(
            "application"
        )

    if has_direct_eligibility_evidence(
        page_text
    ):

        categories.append(
            "eligibility"
        )

    if has_direct_funding_evidence(
        page_text
    ):

        categories.append(
            "funding"
        )

    if has_direct_deadline_evidence(
        page_text,
        deadline,
    ):

        categories.append(
            "deadline"
        )

    return categories


def count_direct_evidence_strength(
    strong_signals,
    application_url,
    page_text,
    deadline="",
):
    """
    Calculate a conservative direct-evidence strength score.

    This is separate from the general opportunity score.

    The purpose is to distinguish a genuinely detailed
    opportunity page from a news article that happens to contain
    words such as scholarship, application, or opportunity.
    """

    categories = count_direct_evidence_categories(
        strong_signals=strong_signals,
        application_url=application_url,
        page_text=page_text,
        deadline=deadline,
    )

    strength = len(
        categories
    )

    normalized = clean_lower(
        page_text
    )

    # Additional quality bonuses are deliberately small.
    if (
        "call for applications" in normalized
        or "call for proposals" in normalized
        or "now accepting applications" in normalized
        or "applications are open" in normalized
    ):

        strength += 1

    if (
        "eligibility criteria" in normalized
        and (
            "deadline" in normalized
            or deadline
        )
    ):

        strength += 1

    if (
        has_direct_funding_evidence(
            page_text
        )
        and has_direct_eligibility_evidence(
            page_text
        )
    ):

        strength += 1

    return strength


def has_substantial_direct_opportunity_evidence(
    strong_signals,
    application_url,
    page_text,
    deadline="",
):
    """
    Determine whether the page has enough independent direct
    evidence to be considered a strong opportunity candidate.

    This is intentionally stricter than merely checking for
    opportunity keywords.
    """

    categories = count_direct_evidence_categories(
        strong_signals=strong_signals,
        application_url=application_url,
        page_text=page_text,
        deadline=deadline,
    )

    strength = count_direct_evidence_strength(
        strong_signals=strong_signals,
        application_url=application_url,
        page_text=page_text,
        deadline=deadline,
    )

    # Three independent categories is strong evidence.
    if len(categories) >= 3:

        return True

    # Two categories can be enough when the actual signals are
    # concrete and the page contains enough detail.
    if (
        len(categories) >= 2
        and strength >= 3
        and count_words(page_text) >= MIN_PAGE_WORDS
    ):

        return True

    return False


def news_is_dominated_by_direct_evidence(
    title,
    text,
    news_signals,
    strong_signals,
    application_url,
    deadline="",
):
    """
    Determine whether direct opportunity evidence is strong
    enough that normal news wording should not dominate it.

    A legitimate opportunity page can contain words such as
    announced, government, partnership, conference, report, etc.
    Those words should not automatically make the page a news
    page when the same page contains application, eligibility,
    funding, and deadline evidence.
    """

    direct_categories = count_direct_evidence_categories(
        strong_signals=strong_signals,
        application_url=application_url,
        page_text=text,
        deadline=deadline,
    )

    direct_strength = count_direct_evidence_strength(
        strong_signals=strong_signals,
        application_url=application_url,
        page_text=text,
        deadline=deadline,
    )

    title_news = find_title_news_signals(
        title
    )

    news_count = len(
        news_signals
    )

    if (
        len(direct_categories) >= 3
        and direct_strength >= 4
    ):

        return True

    if (
        application_url
        and (
            deadline
            or has_direct_eligibility_evidence(
                text
            )
            or has_direct_funding_evidence(
                text
            )
        )
        and direct_strength >= 3
    ):

        return True

    if (
        not title_news
        and news_count <= 6        and len(direct_categories) >= 2
        and direct_strength >= 3
    ):

        return True

    return False


def is_news_heavy(
    title,
    text,
    news_signals,
):
    """
    Determine whether a page looks more like news/general
    reporting than an opportunity listing.

    Important:
    This function remains conservative and does not decide
    final relevance by itself. Direct opportunity evidence can
    override news-heavy classification later.
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

    application_evidence = has_direct_application_evidence(
        normalized_text
    )

    eligibility_evidence = has_direct_eligibility_evidence(
        normalized_text
    )

    funding_evidence = has_direct_funding_evidence(
        normalized_text
    )

    deadline_evidence = has_direct_deadline_evidence(
        normalized_text
    )

    direct_category_count = sum(
        [
            bool(opportunity_count),
            application_evidence,
            eligibility_evidence,
            funding_evidence,
            deadline_evidence,
        ]
    )

    # Strong direct evidence protects legitimate opportunity
    # pages from being classified as news simply because they
    # mention reporting/announcement/context.
    if (
        direct_category_count >= 3
        and word_count >= MIN_PAGE_WORDS
    ):

        return False

    # Strong application language plus eligibility/funding is
    # especially strong evidence of an actual opportunity.
    if (
        application_evidence
        and (
            eligibility_evidence
            or funding_evidence
            or deadline_evidence
        )
    ):

        return False

    # Strong news title with little opportunity evidence.
    if (
        title_news
        and opportunity_count == 0
        and not application_evidence
        and not deadline_evidence
    ):

        return True

    # Very news-heavy text.
    if (
        news_count >= 6
        and opportunity_count <= 1
        and direct_category_count <= 1
    ):

        return True

    # Extremely short article with news signals and no
    # meaningful application evidence.
    if (
        word_count < MIN_PAGE_WORDS
        and news_count >= 3
        and opportunity_count == 0
        and not application_evidence
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
        or has_direct_application_evidence(
            text
        )
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
    # Direct application language
    # --------------------------------------------------------

    if (
        has_direct_application_evidence(
            page_text
        )
        and not application_url
    ):

        score += 4

        reasons.append(
            "direct application language detected"
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

    direct_evidence_protection = (
        has_substantial_direct_opportunity_evidence(
            strong_signals=strong_signals,
            application_url=application_url,
            page_text=page_text,
            deadline=deadline,
        )
    )

    if news_signals:

        penalty = min(
            len(news_signals) * 2,
            MAX_NEWS_PENALTY,
        )

        # Do not allow normal contextual news wording to
        # overwhelm a page that has substantial direct
        # opportunity evidence.
        if direct_evidence_protection:

            penalty = min(
                penalty,
                6,
            )

            reasons.append(
                "news/general signals present but "
                "reduced because direct opportunity "
                "evidence is strong"
            )

        else:

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

        title_penalty = min(
            len(title_news_signals) * 2,
            6,
        )

        if direct_evidence_protection:

            title_penalty = min(
                title_penalty,
                2,
            )

            reasons.append(
                "news-style title detected but "
                "reduced because direct opportunity "
                "evidence is strong"
            )

        else:

            score -= title_penalty

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
        and not direct_evidence_protection
    ):

        score -= 5

        reasons.append(
            "news evidence outweighs opportunity evidence"
        )

    # --------------------------------------------------------
    # Direct evidence quality bonus
    # --------------------------------------------------------

    direct_categories = count_direct_evidence_categories(
        strong_signals=strong_signals,
        application_url=application_url,
        page_text=page_text,
        deadline=deadline,
    )

    direct_strength = count_direct_evidence_strength(
        strong_signals=strong_signals,
        application_url=application_url,
        page_text=page_text,
        deadline=deadline,
    )

    if len(
        direct_categories
    ) >= 3:

        score += 3

        reasons.append(
            "multiple independent opportunity evidence "
            "categories detected"
        )

    elif (
        len(direct_categories) >= 2
        and direct_strength >= 3
    ):

        score += 2

        reasons.append(
            "multiple direct opportunity evidence "
            "categories detected"
        )

    if direct_strength >= 5:

        score += 2

        reasons.append(
            "strong direct evidence quality"
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
            needs_human_review,            classification
        )

    IMPORTANT:
    - confirmed_opportunity = eligible for automatic approval
    - trusted_opportunity = eligible for automatic approval
    - possible_opportunity = HUMAN REVIEW ONLY
    - news/general = rejected
    - insufficient evidence = rejected

    This function deliberately improves automatic approval for
    genuinely detailed opportunity pages without allowing weak
    news/general pages to bypass verification.
    """

    # --------------------------------------------------------
    # 1. Detect news/general characteristics.
    # --------------------------------------------------------

    news_heavy = is_news_heavy(
        title,
        page_text,
        news_signals,
    )

    # --------------------------------------------------------
    # 2. Detect direct evidence.
    #
    # These are independent categories. Repeating the same
    # keyword many times does not create multiple categories.
    # --------------------------------------------------------

    meaningful_application_evidence = (
        bool(application_url)
        or has_application_language(
            page_text
        )
        or has_direct_application_evidence(
            page_text
        )
    )

    meaningful_eligibility = (
        has_eligibility_language(
            page_text
        )
        or has_direct_eligibility_evidence(
            page_text
        )
    )

    meaningful_funding = (
        has_funding_language(
            page_text
        )
        or has_direct_funding_evidence(
            page_text
        )
    )

    meaningful_deadline = (
        bool(deadline)
        or has_direct_deadline_evidence(
            page_text,
            deadline,
        )
    )

    # --------------------------------------------------------
    # 3. Calculate direct evidence categories and strength.
    # --------------------------------------------------------

    direct_categories = count_direct_evidence_categories(
        strong_signals=strong_signals,
        application_url=application_url,
        page_text=page_text,
        deadline=deadline,
    )

    direct_strength = count_direct_evidence_strength(
        strong_signals=strong_signals,
        application_url=application_url,
        page_text=page_text,
        deadline=deadline,
    )

    strong_direct_evidence = (
        has_substantial_direct_opportunity_evidence(
            strong_signals=strong_signals,
            application_url=application_url,
            page_text=page_text,
            deadline=deadline,
        )
    )

    # --------------------------------------------------------
    # 4. Determine whether news wording is outweighed by
    # genuine opportunity evidence.
    # --------------------------------------------------------

    news_override_protection = (
        news_is_dominated_by_direct_evidence(
            title=title,
            text=page_text,
            news_signals=news_signals,
            strong_signals=strong_signals,
            application_url=application_url,
            deadline=deadline,
        )
    )

    # --------------------------------------------------------
    # 5. Additional direct-evidence checks.
    #
    # These are intentionally explicit because some legitimate
    # opportunity pages do not contain a traditional HTML
    # application link.
    # --------------------------------------------------------

    has_application_category = (
        meaningful_application_evidence
    )

    has_eligibility_category = (
        meaningful_eligibility
    )

    has_funding_category = (
        meaningful_funding
    )

    has_deadline_category = (
        meaningful_deadline
    )

    has_opportunity_signal_category = bool(
        strong_signals
    )

    # --------------------------------------------------------
    # 6. Count independent categories again using the
    # meaningful-evidence interpretation.
    #
    # This protects against cases where direct evidence exists
    # through text rather than an application URL.
    # --------------------------------------------------------

    meaningful_category_count = sum(
        [
            has_opportunity_signal_category,
            has_application_category,
            has_eligibility_category,
            has_funding_category,
            has_deadline_category,
        ]
    )

    # --------------------------------------------------------
    # 7. Identify a strong "call for applications" page.
    #
    # These pages are often announced through news/RSS feeds,
    # but the actual page itself contains application evidence.
    # --------------------------------------------------------

    normalized_page_text = clean_lower(
        page_text
    )

    call_for_applications = (
        "call for applications"
        in normalized_page_text
    )

    applications_open = (
        "applications are open"
        in normalized_page_text
        or "applications open"
        in normalized_page_text
        or "application is open"
        in normalized_page_text
    )

    now_accepting = (
        "now accepting applications"
        in normalized_page_text
    )

    applications_invited = (
        "applications invited"
        in normalized_page_text
        or "inviting applications"
        in normalized_page_text
    )

    strong_application_notice = (
        call_for_applications
        or applications_open
        or now_accepting
        or applications_invited
    )

    # --------------------------------------------------------
    # 8. Detect detailed opportunity-page structure.
    #
    # A page with application + eligibility + funding/deadline
    # is much more likely to be the actual opportunity than a
    # news article mentioning an opportunity.
    # --------------------------------------------------------

    detailed_opportunity_structure = (
        has_application_category
        and (
            has_eligibility_category
            or has_funding_category
            or has_deadline_category
        )
        and page_word_count >= MIN_PAGE_WORDS
    )

    # --------------------------------------------------------
    # 9. Determine whether news evidence should be ignored for
    # classification purposes.
    #
    # News wording is acceptable when the page has enough
    # direct opportunity evidence.
    # --------------------------------------------------------

    direct_opportunity_overrides_news = (
        strong_direct_evidence
        or news_override_protection
        or detailed_opportunity_structure
        or (
            meaningful_category_count >= 3
            and page_word_count >= MIN_PAGE_WORDS
        )
    )

    # --------------------------------------------------------
    # 10. HARD NEWS PROTECTION.
    #
    # Do NOT allow an obvious news/general page to become an
    # automatically approved opportunity merely because it
    # contains words such as scholarship, funding, application,
    # government, announcement, etc.
    #
    # Exception:
    # A page with sufficient direct opportunity evidence is
    # allowed through to the normal classification logic.
    # --------------------------------------------------------

    if (
        news_heavy
        and not direct_opportunity_overrides_news
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
    # 11. CONFIRMED OPPORTUNITY.
    #
    # This is the primary path to automatic approval.
    #
    # Requirements:
    # - high evidence score
    # - adequate page content
    # - at least 2 meaningful independent evidence categories
    # - enough evidence strength
    #
    # OR:
    # - 3+ independent categories
    #
    # News language is allowed only when direct opportunity
    # evidence clearly outweighs it.
    # --------------------------------------------------------

    confirmed_evidence = (
        meaningful_category_count >= 3
        or (
            meaningful_category_count >= 2
            and direct_strength >= 3
        )
        or (
            strong_application_notice
            and (
                has_eligibility_category
                or has_funding_category
                or has_deadline_category
            )
            and page_word_count >= MIN_PAGE_WORDS
        )
    )

    if (        score >= 16
        and confirmed_evidence
        and page_word_count >= MIN_PAGE_WORDS
        and (
            not news_heavy
            or direct_opportunity_overrides_news
        )
    ):

        return (
            True,
            False,
            "confirmed_opportunity",
        )

    # --------------------------------------------------------
    # 12. TRUSTED OPPORTUNITY.
    #
    # Trusted domains still require actual opportunity evidence.
    #
    # Trust alone is NEVER enough.
    #
    # This allows legitimate university/government/UN/etc.
    # opportunity pages to become verified when their page
    # contains concrete application evidence.
    # --------------------------------------------------------

    trusted_evidence = (
        meaningful_category_count >= 2
        or (
            strong_application_notice
            and (
                has_eligibility_category
                or has_funding_category
                or has_deadline_category
            )
        )
        or (
            bool(application_url)
            and (
                has_eligibility_category
                or has_funding_category
                or has_deadline_category
            )
        )
    )

    if (
        trusted_domain
        and score >= 10
        and trusted_evidence
        and page_word_count >= MIN_PAGE_WORDS
        and (
            not news_heavy
            or direct_opportunity_overrides_news
        )
    ):

        return (
            True,
            False,
            "trusted_opportunity",
        )

    # --------------------------------------------------------
    # 13. STRONG APPLICATION PAGE FALLBACK.
    #
    # Some pages score slightly below the normal threshold
    # because the source text contains many news/context words.
    #
    # We still require multiple direct evidence categories and
    # adequate content. This does NOT approve weak pages.
    # --------------------------------------------------------

    strong_application_page = (
        (
            bool(application_url)
            or strong_application_notice
        )
        and (
            has_eligibility_category
            or has_funding_category
            or has_deadline_category
        )
        and page_word_count >= MIN_PAGE_WORDS
        and direct_strength >= 3
    )

    if (
        strong_application_page
        and score >= 14
        and (
            not news_heavy
            or direct_opportunity_overrides_news
        )
    ):

        return (
            True,
            False,
            "confirmed_opportunity",
        )

    # --------------------------------------------------------
    # 14. POSSIBLE OPPORTUNITY.
    #
    # IMPORTANT:
    # This remains HUMAN REVIEW ONLY.
    #
    # It must NEVER be treated as verified/auto-approved by
    # this verifier.
    # --------------------------------------------------------

    if (
        score >= 7
        and (
            bool(strong_signals)
            or bool(application_url)
            or bool(deadline)
            or meaningful_eligibility
            or meaningful_funding
            or meaningful_application_evidence
        )
    ):

        return (
            True,
            True,
            "possible_opportunity",
        )

    # --------------------------------------------------------
    # 15. NEWS / GENERAL CONTENT.
    # --------------------------------------------------------

    if news_heavy:

        return (
            False,
            True,
            "likely_news_or_general_content",
        )

    # --------------------------------------------------------
    # 16. INSUFFICIENT EVIDENCE.
    # --------------------------------------------------------

    return (
        False,
        True,
        "insufficient_opportunity_evidence",
    )
# ============================================================
# VERIFICATION
# ============================================================

def determine_verification(item):
    """
    Verify one discovered opportunity using page-level evidence.

    Features:
    - Preserves original discovery metadata.
    - Checks URL fields independently.
    - Fetches and analyzes the discovered source page.
    - Searches publisher homepages for a more specific opportunity page.
    - Fetches and evaluates the specific candidate before using it.
    - Extracts application, deadline, funding, eligibility,
      category, location, and source evidence.
    - Separates confirmed opportunities from candidates needing review.
    - Never marks a possible opportunity as source-verified.
    - Records diagnostics for downstream workflows.
    """

    # ---------------------------------------------------------
    # 1. Read discovery metadata
    # ---------------------------------------------------------

    if not isinstance(item, dict):
        item = {}

    original_discovered_url = ""

    for field in (
        "source_url",
        "url",
        "link",
        "news_url",
    ):
        value = clean_text(item.get(field, ""))

        if value and is_valid_url(value):
            original_discovered_url = value
            break

    selected_url = choose_candidate_source_url(item)

    title = clean_text(item.get("title", ""))
    description = clean_text(item.get("description", ""))
    publisher_name = clean_text(item.get("publisher_name", ""))

    result = dict(item)

    # ---------------------------------------------------------
    # 2. Initialize all verification fields
    # ---------------------------------------------------------

    result.update({
        "verification_level": "failed",
        "source_verified": False,
        "page_reachable": False,
        "source_domain_trusted": False,
        "opportunity_relevant": False,
        "needs_human_review": True,
        "verification_reason": "",
        "checked_url": selected_url,
        "original_discovered_url": original_discovered_url,
        "final_url": "",
        "official_url": "",
        "application_url": "",
        "application_domain": "",
        "application_domain_trusted": False,
        "canonical_url": "",
        "http_status": None,
        "content_type": "",
        "source_domain": "",
        "opportunity_score": 0,
        "opportunity_classification": "unverified",
        "matched_keywords": [],
        "strong_opportunity_signals": [],
        "news_signals": [],
        "news_title_signals": [],
        "verification_evidence": [],
        "detected_category": "",
        "detected_location": "",
        "detected_deadline": "",
        "deadline_expired": False,
        "date_candidates": [],
        "eligibility_signals": [],
        "funding_detected": False,
        "funding_type": "",
        "funding_signals": [],
        "page_title": "",
        "page_description": "",
        "page_h1": "",
        "page_word_count": 0,
        "page_type": "",
        "source_url_resolved": False,
        "source_url_resolution_method": "",
        "application_candidates": [],
        "publisher_name": publisher_name,
        "direct_evidence_categories": [],
        "direct_evidence_strength": 0,
        "strong_direct_opportunity_evidence": False,
        "specific_opportunity_candidate_url": "",
        "specific_opportunity_candidate_checked": False,
        "specific_opportunity_candidate_reachable": False,
        "verification_error": "",
    })

    # ---------------------------------------------------------
    # 3. Stop safely when no valid source URL exists
    # ---------------------------------------------------------

    if not selected_url or not is_valid_url(selected_url):
        result["verification_reason"] = (
            "No valid HTTP/HTTPS source URL was found."
        )
        result["verification_error"] = (
            "Missing or invalid source URL."
        )
        return result

    result["checked_url"] = selected_url

    # ---------------------------------------------------------
    # 4. Fetch the discovered source page
    # ---------------------------------------------------------

    try:
        page = fetch_page(selected_url)

    except Exception as error:
        result["verification_reason"] = (
            "The source page could not be fetched."
        )
        result["verification_error"] = str(error)
        return result

    if not isinstance(page, dict):
        result["verification_reason"] = (
            "The page fetcher returned an invalid result."
        )
        result["verification_error"] = (
            "Invalid fetch_page result."
        )
        return result

    # ---------------------------------------------------------
    # 5. Search for a specific opportunity page when the
    # discovered URL is a homepage or generic landing page    # ---------------------------------------------------------

    current_page_url = clean_text(
        page.get("final_url", "")
    ) or selected_url

    current_is_homepage = is_homepage_url(
        current_page_url
    )
    # A homepage is not sufficient evidence of an actual opportunity.
    homepage_without_specific_page = bool(
        page.get("reachable")
        and current_is_homepage
    )
    if page.get("reachable") and current_is_homepage:
        try:
            candidate_url = find_more_specific_link(
                page=page,
                base_url=current_page_url,
                title=title,
                description=description,
            )
        except Exception:
            candidate_url = ""

        candidate_url = clean_text(candidate_url)

        if (
            candidate_url
            and is_valid_url(candidate_url)
            and not is_homepage_url(candidate_url)
        ):
            result["specific_opportunity_candidate_url"] = (
                candidate_url
            )

            result["specific_opportunity_candidate_checked"] = True

            # Fetch the candidate. Finding a link alone is not
            # proof that the link contains a real opportunity.
            try:
                candidate_page = fetch_page(candidate_url)
            except Exception:
                candidate_page = {}

            if not isinstance(candidate_page, dict):
                candidate_page = {}

            result["specific_opportunity_candidate_reachable"] = (
                bool(candidate_page.get("reachable"))
            )

            candidate_text = clean_text(
                candidate_page.get("text", "")
            )

            current_text = clean_text(
                page.get("text", "")
            )

            # Use the candidate only if it is reachable and
            # provides usable content. Otherwise preserve the
            # original source page for analysis.
            if (
                candidate_page.get("reachable")
                and candidate_text
            ):
                page = candidate_page
                selected_url = candidate_url

                result["checked_url"] = candidate_url

                result["source_url_resolution_method"] = (
                    "specific_opportunity_link"
                )
                homepage_without_specific_page = False
            elif not current_text:
                result["verification_error"] = (
                    "The specific opportunity candidate was not "
                    "reachable and the original page has no usable text."
                )

    # ---------------------------------------------------------
    # 6. Collect fetch and page metadata
    # ---------------------------------------------------------

    final_url = clean_text(
        page.get("final_url", "")
    ) or selected_url

    result["final_url"] = final_url

    result["http_status"] = page.get("status_code")

    result["content_type"] = clean_text(
        page.get("content_type", "")
    )

    result["page_reachable"] = bool(
        page.get("reachable")
    )

    result["page_title"] = clean_text(
        page.get("title", "")
    )

    result["page_description"] = clean_text(
        page.get("description", "")
    )

    result["page_h1"] = clean_text(
        page.get("h1", "")
    )

    page_text = clean_text(
        page.get("text", "")
    )[:MAX_ANALYSIS_CHARS]

    page_word_count = count_words(page_text)

    result["page_word_count"] = page_word_count

    result["canonical_url"] = clean_text(
        page.get("canonical", "")
    )

    result["source_domain"] = get_domain(final_url)

    # ---------------------------------------------------------
    # 7. Resolve the most appropriate official/source URL
    # ---------------------------------------------------------

    official_url = resolve_official_url(
        selected_url,
        page,
    )

    result["official_url"] = official_url

    result["source_url_resolved"] = bool(
        official_url
    )

    if not result["source_url_resolution_method"]:
        if (
            official_url
            and normalize_url(official_url)
            == normalize_url(selected_url)
        ):
            result["source_url_resolution_method"] = (
                "selected_source_url"
            )
        elif (
            official_url
            and normalize_url(official_url)
            == normalize_url(final_url)
        ):
            result["source_url_resolution_method"] = (
                "final_redirect_url"
            )
        elif official_url:
            result["source_url_resolution_method"] = (
                "resolved_source_url"
            )
        else:
            result["source_url_resolution_method"] = (
                "unresolved"
            )

    # Trust the domain of the page being analyzed, not a random
    # application link discovered on that page.
    trusted_domain = bool(
        official_url
        and is_trusted_domain(official_url)
    )

    result["source_domain_trusted"] = trusted_domain

    # ---------------------------------------------------------
    # 8. Stop if the source page is unreachable
    # ---------------------------------------------------------

    if not page.get("reachable"):
        result["verification_level"] = "failed"

        result["source_verified"] = False

        result["opportunity_relevant"] = False

        result["needs_human_review"] = True

        fetch_error = clean_text(
            page.get("error", "")
        )

        result["verification_error"] = (
            fetch_error
            or result["verification_error"]
            or "Source page is not reachable."
        )

        result["verification_reason"] = (
            "The source page could not be successfully fetched "
            "and analyzed. No automatic approval was granted."
        )

        return result

    if not page_text:
        result["verification_level"] = "failed"

        result["source_verified"] = False

        result["opportunity_relevant"] = False

        result["needs_human_review"] = True

        result["verification_error"] = (
            "The source page contains no usable text."
        )

        result["verification_reason"] = (
            "The page responded, but there is insufficient "
            "readable content to verify the opportunity."
        )

        return result

    # ---------------------------------------------------------
    # 9. Analyze the actual page content
    #
    # Discovery metadata is preserved, but the primary
    # evidence checks below use the fetched page text.
    # ---------------------------------------------------------

    analysis_title = (
        result["page_title"]
        or result["page_h1"]
        or title
    )

    analysis_description = (
        result["page_description"]
        or description
    )

    page_evidence_text = clean_text(
        " ".join([
            analysis_title,
            analysis_description,
            result["page_h1"],
            page_text,
        ])
    )[:MAX_ANALYSIS_CHARS]

    # Keep keyword and strong-signal evidence tied to the page.
    matched_keywords = find_matching_keywords(
        page_evidence_text
    )

    strong_signals = find_strong_signals(
        page_evidence_text
    )

    news_signals = find_news_signals(
        page_text
    )

    news_title_signals = find_title_news_signals(
        analysis_title
    )

    result["matched_keywords"] = matched_keywords

    result["strong_opportunity_signals"] = strong_signals

    result["news_signals"] = news_signals

    result["news_title_signals"] = news_title_signals

    # ---------------------------------------------------------
    # 10. Detect application links and candidates
    # ---------------------------------------------------------

    html_content = page.get("content", "")

    if not isinstance(html_content, str):
        html_content = ""

    try:
        application_candidates = find_application_candidates(
            html_content,
            final_url,
        )
    except Exception:
        application_candidates = []

    result["application_candidates"] = (
        application_candidates
    )

    try:
        application_url = find_application_url(
            html_content,            final_url,
        )
    except Exception:
        application_url = ""

    # If the main detector did not find a URL, use the highest
    # ranked candidate already extracted from the same page.
    if (
        not application_url
        and application_candidates
        and isinstance(application_candidates[0], dict)
    ):
        application_url = clean_text(
            application_candidates[0].get("url", "")
        )

    if (
        application_url
        and not is_valid_url(application_url)
    ):
        application_url = ""

    result["application_url"] = application_url

    result["application_domain"] = (
        get_domain(application_url)
        if application_url
        else ""
    )

    result["application_domain_trusted"] = (
        is_trusted_domain(application_url)
        if application_url
        else False
    )

    # ---------------------------------------------------------
    # 11. Detect deadline and expiry
    # ---------------------------------------------------------

    detected_deadline = extract_deadline(
        page_evidence_text
    )

    result["detected_deadline"] = detected_deadline

    result["date_candidates"] = extract_date_candidates(
        page_evidence_text
    )

    deadline_expired = deadline_is_expired(
        detected_deadline
    )

    result["deadline_expired"] = deadline_expired

    # ---------------------------------------------------------
    # 12. Detect funding, eligibility, category, and location
    # ---------------------------------------------------------

    funding_data = detect_funding(
        page_evidence_text
    )

    result["funding_detected"] = bool(
        funding_data.get("funding_detected")
    )

    result["funding_type"] = clean_text(
        funding_data.get("funding_type", "")
    )

    result["funding_signals"] = (
        funding_data.get("funding_signals", [])
    )

    result["eligibility_signals"] = detect_eligibility(
        page_evidence_text
    )

    result["detected_category"] = detect_category(
        page_evidence_text
    )

    result["detected_location"] = detect_location(
        page_evidence_text
    )

    # ---------------------------------------------------------
    # 13. Detect the page type
    # ---------------------------------------------------------

    page_type = detect_page_type(
        title=analysis_title,
        text=page_text,
        application_url=application_url,
        deadline=detected_deadline,
        news_signals=news_signals,
        strong_signals=strong_signals,
    )

    result["page_type"] = page_type

    # ---------------------------------------------------------
    # 14. Calculate the opportunity score
    # ---------------------------------------------------------

    score, score_reasons = calculate_opportunity_score(
        title=title,
        description=description,
        page_title=analysis_title,
        page_description=analysis_description,
        page_text=page_text,
        trusted_domain=trusted_domain,
        application_url=application_url,
        deadline=detected_deadline,
        page_word_count=page_word_count,
    )

    result["opportunity_score"] = score

    # ---------------------------------------------------------
    # 15. Calculate direct-evidence strength
    # ---------------------------------------------------------

    direct_categories = count_direct_evidence_categories(
        strong_signals=strong_signals,
        application_url=application_url,
        page_text=page_text,
        deadline=detected_deadline,
    )

    direct_strength = count_direct_evidence_strength(
        strong_signals=strong_signals,
        application_url=application_url,
        page_text=page_text,
        deadline=detected_deadline,
    )

    strong_direct_evidence = (
        has_substantial_direct_opportunity_evidence(
            strong_signals=strong_signals,
            application_url=application_url,
            page_text=page_text,
            deadline=detected_deadline,
        )
    )

    result["direct_evidence_categories"] = (
        direct_categories
    )

    result["direct_evidence_strength"] = direct_strength

    result["strong_direct_opportunity_evidence"] = (
        strong_direct_evidence
    )

    # ---------------------------------------------------------
    # 16. Assemble verification evidence
    # ---------------------------------------------------------

    evidence = []

    if result["page_reachable"]:
        evidence.append("source_page_reachable")

    if official_url:
        evidence.append("source_url_resolved")

    if trusted_domain:
        evidence.append("trusted_source_domain")

    if strong_signals:
        evidence.append("opportunity_signals_detected")

    if application_url:
        evidence.append("application_link_detected")

    if has_direct_application_evidence(page_text):
        evidence.append("direct_application_language")

    if result["eligibility_signals"]:
        evidence.append("eligibility_information_detected")

    if result["funding_detected"]:
        evidence.append("funding_information_detected")

    if detected_deadline:
        evidence.append("deadline_detected")

    if deadline_expired:
        evidence.append("deadline_expired")

    if page_word_count >= MIN_PAGE_WORDS:
        evidence.append("sufficient_page_content")

    if news_signals:
        evidence.append("news_or_general_signals_detected")

    if strong_direct_evidence:
        evidence.append("strong_direct_opportunity_evidence")

    result["verification_evidence"] = evidence

    # ---------------------------------------------------------
    # 17. Classify the opportunity
    # ---------------------------------------------------------

    relevant, needs_review, classification = classify_relevance(
        score=score,
        trusted_domain=trusted_domain,
        strong_signals=strong_signals,
        application_url=application_url,
        deadline=detected_deadline,
        news_signals=news_signals,
        title=analysis_title,
        page_text=page_text,
        page_word_count=page_word_count,
    )

    result["opportunity_relevant"] = bool(relevant)

    result["needs_human_review"] = bool(needs_review)

    result["opportunity_classification"] = classification

    # ---------------------------------------------------------
    # 18. Prevent expired opportunities from automatic approval
    # ---------------------------------------------------------

    if deadline_expired:
        result["verification_level"] = "review"

        result["source_verified"] = False

      # ---------------------------------------------------------
    # BLOCK AUTOMATIC APPROVAL OF HOMEPAGES
    #
    # A publisher homepage is not itself proof of a specific
    # scholarship, job, internship, course, or other opportunity.
    # Automatic approval requires a reachable, specific page.
    # ---------------------------------------------------------

    if homepage_without_specific_page:

        result["verification_level"] = "review"

        result["source_verified"] = False

        result["opportunity_relevant"] = False

        result["needs_human_review"] = True

        result["opportunity_classification"] = (
            "homepage_without_specific_page"
        )

        result["verification_reason"] = (
            "The source is a publisher homepage or generic "
            "landing page, and no reachable specific opportunity "
            "page was verified. Automatic approval was blocked."
        )

        result["verification_evidence"].append(
            "automatic_approval_blocked_homepage"
        )

        result["verification_evidence"] = list(
            dict.fromkeys(
                result["verification_evidence"]
            )
        )

        return result  

    # ---------------------------------------------------------
    # 19. Decide the final verification level
    #
    # Only confirmed/trusted opportunities with sufficient
    # evidence can be marked source_verified=True.
    # ---------------------------------------------------------

    if (
        relevant
        and not needs_review
        and classification in {
            "confirmed_opportunity",
            "trusted_opportunity",
        }
    ):
        result["verification_level"] = "verified"

        result["source_verified"] = True

        result["needs_human_review"] = False

        result["verification_reason"] = (
            "The fetched source page contains sufficient "
            "opportunity evidence for automatic verification."
        )

    elif (
        relevant
        or classification in {
            "possible_opportunity",
            "likely_news_or_general_content",
        }
    ):
       result["verification_level"] = "review"

        # A possible opportunity is not a verified source.
        result["source_verified"] = False
        result["needs_human_review"] = True

        if classification == "possible_opportunity":
            result["verification_reason"] = (
                "The page may describe an opportunity, but "
                "the available evidence is insufficient for "
                "automatic verification."
            ) 

        elif classification == "likely_news_or_general_content":
            result["verification_reason"] = (
                "The page contains news or general-content "
                "signals and requires human review."
            )

        else:
            result["verification_reason"] = (
                "The page contains some opportunity evidence, "
                "but it did not meet every automatic-verification "
                "requirement."
            )

    else:
        result["verification_level"] = "failed"

        result["source_verified"] = False

        result["opportunity_relevant"] = False

        result["needs_human_review"] = True

        result["verification_reason"] = (
            "The page did not provide sufficient evidence "
            "to verify a relevant opportunity."
        )

    # ---------------------------------------------------------
    # 20. Add score/classification diagnostics
    # ---------------------------------------------------------

    result["verification_evidence"].extend(
        score_reasons
    )

    result["verification_evidence"] = list(
        dict.fromkeys(
            clean_text(value)
            for value in result["verification_evidence"]
            if clean_text(value)
        )
    )

    # ---------------------------------------------------------
    # 21. Preserve any fetch warning
    # ---------------------------------------------------------

    fetch_warning = clean_text(
        page.get("error", "")
    )

    if fetch_warning and not result["verification_error"]:
        result["verification_error"] = fetch_warning

    return result


# ============================================================
# ITEM VERIFICATION WRAPPER
# ============================================================

def verify_item(
    item
):
    """
    Verify one item and remove large temporary page fields
    before returning the final JSON record.
    """

    result = determine_verification(
        item
    )

    # Never store raw HTML/page content in the final dataset.
    result.pop(
        "content",
        None
    )

    result.pop(
        "html",
        None
    )

    result.pop(
        "links",
        None
    )

    return result


# ============================================================
# JSON HELPERS
# ============================================================

def load_json_file(
    path
):
    """
    Load a JSON file safely.
    """

    if not path.exists():

        return []

    try:

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(
                file
            )

        if isinstance(
            data,
            list,
        ):

            return data

        if isinstance(
            data,
            dict,
        ):

            if isinstance(
                data.get(
                    "items"
                ),
                list,
            ):

                return data[
                    "items"
                ]

            if isinstance(
                data.get(
                    "opportunities"
                ),
                list,
            ):

                return data[
                    "opportunities"
                ]

    except Exception as error:

        print(
            f"ERROR loading {path}: {error}"
        )

    return []


# ============================================================
# MAIN
# ============================================================

def main():
    """
    Verify all discovered opportunities and save the results.
    """

    items = load_json_file(
        INPUT_FILE
    )

    print(
        f"Loaded {len(items)} discovered opportunities."
    )

    verified_items = []

    counters = {
        "total": 0,
        "verified": 0,
        "review": 0,
        "failed": 0,
        "relevant": 0,
        "expired": 0,
        "news_or_general": 0,
    }

    for index, item in enumerate(
        items,
        start=1,
    ):

        counters[
            "total"
        ] += 1

        try:

            result = verify_item(
                item
            )

            verified_items.append(
                result
            )

            verification_level = result.get(
                "verification_level",
                "failed",
            )

            if verification_level == "verified":

                counters[
                    "verified"
                ] += 1

            elif verification_level == "review":

                counters[
                    "review"
                ] += 1

            else:

                counters[
                    "failed"
                ] += 1

            if result.get(
                "opportunity_relevant",
                False,
            ):

                counters[
                    "relevant"
                ] += 1

            if result.get(
                "deadline_expired",
                False,
            ):

                counters[
                    "expired"
                ] += 1

            classification = result.get(
                "opportunity_classification",
                "",
            )

            if classification in {
                "likely_news_or_general_content",
                "general_page",
            }:

                counters[
                    "news_or_general"
                ] += 1

        except Exception as error:

            print(
                f"ERROR verifying item "
                f"{index}: {error}"
            )

            fallback = dict(
                item
            )

            fallback.update(
                {
                    "verification_level": "failed",

                    "source_verified": False,

                    "page_reachable": False,

                    "opportunity_relevant": False,

                    "needs_human_review": True,

                    "verification_reason": (
                        f"Verifier exception: {error}"
                    ),                    "opportunity_classification": (
                        "verification_error"
                    ),

                    "opportunity_score": 0,

                    "deadline_expired": False,

                    "direct_evidence_categories": [],

                    "direct_evidence_strength": 0,

                    "strong_direct_opportunity_evidence": False,

                    "news_override_protection": False,
                }
            )

            verified_items.append(
                fallback
            )

            counters[
                "failed"
            ] += 1

    # --------------------------------------------------------
    # Build final output.
    # --------------------------------------------------------

    output = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "source_file": str(
            INPUT_FILE
        ),

        "total_discovered": len(
            items
        ),

        "summary": {
            "total": counters[
                "total"
            ],

            "verified": counters[
                "verified"
            ],

            "review": counters[
                "review"
            ],

            "failed": counters[
                "failed"
            ],

            "relevant": counters[
                "relevant"
            ],

            "expired": counters[
                "expired"
            ],

            "news_or_general": counters[
                "news_or_general"
            ],
        },

        "items": verified_items,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(
        "Verification complete."
    )

    print(
        f"Total: {counters['total']}"
    )

    print(
        f"Verified: {counters['verified']}"
    )

    print(
        f"Review: {counters['review']}"
    )

    print(
        f"Failed: {counters['failed']}"
    )

    print(
        f"Relevant: {counters['relevant']}"
    )

    print(
        f"Expired: {counters['expired']}"
    )

    print(
        f"News/general: {counters['news_or_general']}"
    )

    print(
        f"Saved to: {OUTPUT_FILE}"
    )


if __name__ == "__main__":

    main()
