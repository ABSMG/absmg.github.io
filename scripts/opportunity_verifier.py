import json
import re
import socket
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "discovered_opportunities.json"
OUTPUT_FILE = BASE_DIR / "data" / "verified_opportunities.json"

TIMEOUT = 15

MAX_PAGE_BYTES = 500000


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
    "deadline",
    "deadline",
    "admission",
    "fellow",
    "research",
    "researcher",
    "competition",
    "competitions",
    "contest",
    "challenge",
    "volunteer",
    "volunteering",
]


# ============================================================
# STRONG OPPORTUNITY SIGNALS
# ============================================================
#
# These are more important than generic words such as
# "career", "students", or "opportunity".
#
# A news article saying "jobs increased" should NOT easily
# pass just because it contains the word "jobs".
# ============================================================

STRONG_OPPORTUNITY_SIGNALS = [
    "apply now",
    "apply here",
    "applications are open",
    "applications open",
    "application is open",
    "application deadline",
    "application period",
    "how to apply",
    "apply online",
    "submit application",
    "submit your application",
    "eligible applicants",
    "eligibility criteria",
    "eligibility requirements",
    "requirements",
    "selection criteria",
    "selection process",
    "deadline",
    "closing date",
    "last date to apply",
    "funded by",
    "fully funded",
    "partial funding",
    "tuition fee",
    "tuition fees",
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
    "job vacancy",
    "job vacancies",
    "vacancy announcement",
    "recruitment",
    "position",
    "positions available",
    "course enrollment",
    "course enrolment",
    "register for the course",
    "registration is open",
    "training program",
    "training programme",
    "call for applications",
    "call for proposals",
    "call for entries",
]


# ============================================================
# NEWS / GENERAL CONTENT SIGNALS
# ============================================================
#
# These phrases commonly appear in news/reporting rather than
# actual opportunity pages.
#
# They are not automatic rejection signals by themselves.
# They are used together with the opportunity evidence score.
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
    "yesterday",
    "last week",
    "this week",
]


# ============================================================
# TRUSTED DOMAINS
# ============================================================
#
# Exact / structured domain matching is safer than simply
# checking whether ".org" occurs somewhere in a hostname.
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
    ],

    "fellowships": [
        "fellowship",
        "fellowships",
    ],

    "grants": [
        "grant",
        "grants",
        "funding opportunity",
        "funding opportunities",
        "call for proposals",
    ],

    "internships": [
        "internship",
        "internships",
        "intern",
        "traineeship",
    ],

    "remote-jobs": [
        "remote job",
        "remote jobs",
        "remote work",
        "work from home",
        "work-from-home",
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
    ],

    "courses": [
        "course",
        "courses",
        "online course",
        "online courses",
        "certificate course",
        "certification",
    ],

    "training": [
        "training",
        "trainings",
        "bootcamp",
        "boot camp",
        "academy",
        "workshop",
    ],

    "competitions": [
        "competition",
        "competitions",
        "contest",
        "challenge",
        "hackathon",
        "award",
        "awards",
    ],

    "research": [
        "research opportunity",
        "research opportunities",
        "research grant",
        "research fellowship",
        "research position",
        "researcher",
    ],

    "study-abroad": [
        "study abroad",
        "international students",
        "study in",
        "international scholarship",
        "overseas study",
    ],

    "volunteer": [
        "volunteer",
        "volunteering",
        "voluntary",
    ],
}


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


def get_domain(url):
    """
    Extract hostname without port.
    """

    try:
        parsed = urlparse(url)

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
        parsed = urlparse(url)

        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.netloc)
        )

    except Exception:
        return False


def is_trusted_domain(url):
    """
    Determine whether a domain belongs to a trusted class.

    This is intentionally stricter than the previous version.
    Generic .org domains are NOT automatically trusted.
    """

    domain = get_domain(url)

    if not domain:
        return False

    # Exact trusted domains
    if domain in TRUSTED_EXACT_DOMAINS:
        return True

    # Trusted suffixes
    for suffix in TRUSTED_DOMAIN_SUFFIXES:

        if domain.endswith(suffix):
            return True

    # Known trusted domain patterns
    for pattern in TRUSTED_DOMAIN_CONTAINS:

        if pattern in domain:
            return True

    return False


def normalize_url(url):
    """
    Normalize URL for comparison.
    """

    url = clean_text(url)

    if not url:
        return ""

    return url.rstrip("/")


def strip_html(html):
    """
    Convert HTML into readable text.

    Script/style/noscript sections are removed first.
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
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )

    return clean_text(text)


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
            flags=re.IGNORECASE | re.DOTALL,
        )

        if match:

            return clean_text(
                match.group(1)
            )

    return ""


def extract_canonical(html, base_url):
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
            flags=re.IGNORECASE | re.DOTALL,
        )

        if match:

            value = clean_text(
                match.group(1)
            )

            if value:

                return urljoin(
                    base_url,
                    value
                )

    return ""


def extract_links(html, base_url):
    """
    Extract links from the source page.

    Returns a list of absolute URLs.
    """

    if not html:
        return []

    links = []

    pattern = re.compile(
        r'<a[^>]+href=["\'](.*?)["\']',
        flags=re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html):

        href = clean_text(
            match.group(1)
        )

        if not href:
            continue

        if href.startswith(
            ("#", "mailto:", "tel:", "javascript:")
        ):
            continue

        absolute = urljoin(
            base_url,
            href
        )

        if is_valid_url(absolute):

            links.append(
                absolute
            )

    # Deduplicate
    unique = []

    seen = set()

    for link in links:

        normalized = normalize_url(
            link
        ).lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        unique.append(link)

    return unique


def extract_date_candidates(text):
    """
    Extract common date formats.

    This is only a candidate extractor.
    It does not claim that every date found is a deadline.
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

            value = clean_text(match)

            if value and value not in results:
                results.append(value)

    return results[:10]


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

        r"last\s+date\s+to\s+apply"
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

    # If no explicit "deadline" date was found, look for
    # "apply by" / "applications close" language.
    secondary_patterns = [

        r"apply\s+by\s+"
        r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",

        r"applications?\s+close\s+"
        r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",

        r"applications?\s+close\s+"
        r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})",

        r"apply\s+by\s+"
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

    normalized = clean_text(
        text
    ).lower()

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

    normalized = clean_text(
        text
    ).lower()

    countries = [
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
        "canada",
        "united states",
        "usa",
        "united kingdom",
        "uk",
        "germany",
        "france",
        "italy",
        "spain",
        "netherlands",
        "australia",
        "new zealand",
        "japan",
        "china",
        "india",
        "sweden",
        "norway",
        "denmark",
        "finland",
        "ireland",
        "switzerland",
    ]

    regions = [
        "africa",
        "east africa",
        "west africa",
        "southern africa",
        "north africa",
        "europe",
        "asia",
        "north america",
        "south america",
        "oceania",
    ]

    found_countries = []

    for country in countries:

        if country in normalized:
            found_countries.append(
                country.title()
            )

    found_regions = []

    for region in regions:

        if region in normalized:
            found_regions.append(
                region.title()
            )

    # Prefer country.
    if found_countries:

        return found_countries[0]

    if found_regions:

        return found_regions[0]

    return ""


# ============================================================
# PAGE FETCHING
# ============================================================

def fetch_page(url):
    """
    Checks whether the source page is reachable.

    Returns:
        {
            "reachable": bool,
            "status_code": int or None,
            "final_url": str,
            "content_type": str,
            "title": str,
            "description": str,
            "canonical": str,
            "content": str,
            "text": str,
            "links": list,
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
        "content": "",
        "text": "",
        "links": [],
        "error": None,
    }

    try:

        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; OpportunityBridgeBot/2.0; "
                    "+https://absmg.github.io/)"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,*/*;q=0.8"
                ),
            },
        )

        with urlopen(
            request,
            timeout=TIMEOUT
        ) as response:

            status_code = response.getcode()

            final_url = response.geturl()

            content_type = (
                response.headers.get(
                    "Content-Type",
                    ""
                )
            )

            raw = response.read(
                MAX_PAGE_BYTES
            )

            try:

                content = raw.decode(
                    "utf-8",
                    errors="ignore"
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
                final_url
            )

            text = strip_html(
                content
            )

            links = extract_links(
                content,
                final_url
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
                    "content": content,
                    "text": text,
                    "links": links,
                }
            )

    except HTTPError as error:

        result["status_code"] = error.code

        result["error"] = (
            f"HTTP {error.code}"
        )

    except (
        URLError,
        socket.timeout
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

    text = clean_text(
        text
    ).lower()

    return any(
        keyword in text
        for keyword in OPPORTUNITY_KEYWORDS
    )


def find_matching_keywords(text):
    """
    Return opportunity keywords found in the text.
    """

    text = clean_text(
        text
    ).lower()

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

    text = clean_text(
        text
    ).lower()

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

    text = clean_text(
        text
    ).lower()

    matches = []

    for signal in NEWS_SIGNALS:

        if signal in text:

            matches.append(
                signal
            )

    return matches


# ============================================================
# APPLICATION LINK DETECTION
# ============================================================

def is_application_link(url, anchor_text=""):
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
    ]

    return any(
        term in combined
        for term in application_terms
    )


def find_application_url(
    html,
    base_url
):
    """
    Find a likely application URL from page links.

    This does NOT automatically claim that the URL is safe
    or official; it is stored as a candidate.
    """

    if not html:
        return ""

    pattern = re.compile(
        r'<a[^>]+href=["\'](.*?)["\'][^>]*>'
        r"(.*?)"
        r"</a>",
        flags=re.IGNORECASE | re.DOTALL,
    )

    candidates = []

    for match in pattern.finditer(html):

        href = clean_text(
            match.group(1)
        )

        anchor = strip_html(
            match.group(2)
        )

        if not href:
            continue

        absolute = urljoin(
            base_url,
            href
        )

        if not is_valid_url(
            absolute
        ):
            continue

        if is_application_link(
            absolute,
            anchor
        ):

            candidates.append(
                absolute
            )

    if candidates:

        return candidates[0]

    return ""


# ============================================================
# OFFICIAL URL RESOLUTION
# ============================================================

def resolve_official_url(
    original_url,
    page
):
    """
    Determine the best source URL to use.

    The actual fetched final URL is preferred when redirects
    occur.

    We do not replace it with a random publisher homepage.
    """

    final_url = clean_text(
        page.get("final_url")
    )

    canonical = clean_text(
        page.get("canonical")
    )

    if canonical and is_valid_url(
        canonical
    ):

        return canonical

    if final_url and is_valid_url(
        final_url
    ):

        return final_url

    return original_url


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
):
    """
    Calculate an evidence score.

    The score is intentionally conservative.

    Higher score = stronger evidence that the page is an
    actual opportunity page rather than a general news article.
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

        # Cap this contribution so repeated words do not
        # artificially create a huge score.
        contribution = min(
            len(strong_signals) * 3,
            18
        )

        score += contribution

        reasons.append(
            f"strong opportunity signals: "
            f"{', '.join(strong_signals[:6])}"
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
            8
        )

        score += contribution

        reasons.append(
            f"opportunity keywords: "
            f"{', '.join(keyword_matches[:8])}"
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

    eligibility_signals = [
        "eligibility",
        "eligible",
        "requirements",
        "who can apply",
        "applicants must",
        "qualification",
        "qualifications",
    ]

    eligibility_count = sum(
        1
        for signal in eligibility_signals
        if signal in combined
    )

    if eligibility_count:

        score += min(
            eligibility_count * 2,
            6
        )

        reasons.append(
            "eligibility information detected"
        )

    # --------------------------------------------------------
    # Deadline language
    # --------------------------------------------------------

    deadline = extract_deadline(
        combined
    )

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
    # News signals
    # --------------------------------------------------------

    news_signals = find_news_signals(
        combined
    )

    if news_signals:

        # News signals are a warning rather than an automatic
        # rejection.
        penalty = min(
            len(news_signals) * 2,
            12
        )

        score -= penalty

        reasons.append(
            f"news/general signals: "
            f"{', '.join(news_signals[:6])}"
        )

    return score, reasons


def classify_relevance(
    score,
    trusted_domain,
    strong_signals,
    application_url,
    deadline,
    news_signals,
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

    # Strong evidence:
    if (
        score >= 16
        and (
            strong_signals
            or application_url
            or deadline
        )
    ):

        return (
            True,
            False,
            "confirmed_opportunity"
        )

    # Trusted source + meaningful evidence.
    if (
        trusted_domain
        and score >= 10
        and (
            strong_signals
            or deadline
            or application_url
        )
    ):

        return (
            True,
            False,
            "trusted_opportunity"
        )

    # Medium evidence should not be auto-approved.
    if score >= 7:

        return (
            True,
            True,
            "possible_opportunity"
        )

    # News-heavy pages with weak evidence.
    if (
        news_signals
        and score < 7
    ):

        return (
            False,
            True,
            "likely_news_or_general_content"
        )

    return (
        False,
        True,
        "insufficient_opportunity_evidence"
    )


# ============================================================
# VERIFICATION ENGINE
# ============================================================

def determine_verification(item):

    url = clean_text(
        item.get("url")
        or item.get("link")
        or item.get("source_url")
    )

    title = clean_text(
        item.get("title")
    )

    description = clean_text(
        item.get("description")
        or item.get("summary")
    )

    result = {
        "verification_level": "failed",

        "source_verified": False,

        "page_reachable": False,

        "source_domain_trusted": False,

        "opportunity_relevant": False,

        "needs_human_review": True,

        "verification_reason": "",

        "checked_url": url,

        "final_url": url,

        "official_url": url,

        "application_url": "",

        "canonical_url": "",

        "http_status": None,

        "source_domain": get_domain(url),

        "opportunity_score": 0,

        "opportunity_classification": "failed",

        "matched_keywords": [],

        "strong_opportunity_signals": [],

        "news_signals": [],

        "detected_category": "opportunities",

        "detected_location": "",

        "detected_deadline": "",
    }

    # ========================================================
    # 1. URL validation
    # ========================================================

    if not is_valid_url(url):

        result["verification_reason"] = (
            "Invalid or missing URL."
        )

        return result

    # ========================================================
    # 2. Domain trust check
    # ========================================================

    trusted_domain = is_trusted_domain(
        url
    )

    result[
        "source_domain_trusted"
    ] = trusted_domain

    # ========================================================
    # 3. Reachability check
    # ========================================================

    page = fetch_page(
        url
    )

    result[
        "page_reachable"
    ] = page["reachable"]

    result[
        "http_status"
    ] = page["status_code"]

    result[
        "final_url"
    ] = page["final_url"]

    result[
        "canonical_url"
    ] = page.get(
        "canonical",
        ""
    )

    if not page["reachable"]:

        result["verification_reason"] = (
            "Source page could not be reached."
        )

        return result

    # ========================================================
    # 4. Resolve official/source URL
    # ========================================================

    official_url = resolve_official_url(
        url,
        page
    )

    result[
        "official_url"
    ] = official_url

    result[
        "source_domain"
    ] = get_domain(
        official_url
    )

    # Re-check trust after redirects.
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
            ""
        )
    )

    page_description = clean_text(
        page.get(
            "description",
            ""
        )
    )

    page_text = clean_text(
        page.get(
            "text",
            ""
        )
    )

    # Limit analysis size to keep the workflow efficient.
    analysis_text = clean_text(
        " ".join(
            [
                title,
                description,
                page_title,
                page_description,
                page_text[:120000],
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

    result[
        "matched_keywords"
    ] = matched_keywords

    result[
        "strong_opportunity_signals"
    ] = strong_signals

    result[
        "news_signals"
    ] = news_signals

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

    # ========================================================
    # 10. Detect application URL
    # ========================================================

    application_url = find_application_url(
        page.get(
            "content",
            ""
        ),
        page.get(
            "final_url",
            url
        )
    )

    result[
        "application_url"
    ] = application_url

    # ========================================================
    # 11. Basic opportunity presence
    # ========================================================

    relevant_keyword_found = (
        contains_opportunity_keyword(
            analysis_text
        )
    )

    if not relevant_keyword_found:

        result["verification_reason"] = (
            "Source page was reachable but no "
            "opportunity-related terminology was detected."
        )

        return result

    # ========================================================
    # 12. Evidence score
    # ========================================================

    score, score_reasons = (
        calculate_opportunity_score(
            title=title,
            description=description,
            page_title=page_title,
            page_description=page_description,
            page_text=page_text[:120000],
            trusted_domain=result[
                "source_domain_trusted"
            ],
            application_url=application_url,
        )
    )

    result[
        "opportunity_score"
    ] = score

    # ========================================================
    # 13. Classification
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
    # 14. Verification level
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
                "The source page is reachable and contains "
                "strong opportunity evidence. The source "
                "domain is trusted and/or the page contains "
                "application, eligibility or deadline signals. "
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
                "The source page is reachable and contains "
                "strong evidence of a real opportunity. "
                "The domain is not on the trusted-domain list, "
                "so the page should receive additional review "
                f"before publication. Evidence score: {score}."
            )

            # Even strong non-trusted domains should be
            # reviewed before automatic publication.
            result[
                "needs_human_review"
            ] = True

    elif classification == "possible_opportunity":

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
            "evidence, but the evidence is not strong enough "
            "for automatic approval. Human review is required. "
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
            "The page is reachable but there is insufficient "
            "evidence that it represents a real opportunity "
            "rather than news, commentary, or general content. "
            f"Evidence score: {score}."
        )

    # ========================================================
    # 15. Add score explanation
    # ========================================================

    result[
        "verification_evidence"
    ] = score_reasons[:12]

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

    # Do not keep downloaded page HTML in the JSON database.
    verified_item.pop(
        "content",
        None
    )

    return verified_item


# ============================================================
# MAIN
# ============================================================

def main():

    if not INPUT_FILE.exists():

        print(
            f"Input file not found: {INPUT_FILE}"
        )

        return

    try:

        data = json.loads(
            INPUT_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:

        print(
            f"Could not read input JSON: {error}"
        )

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

    possible_opportunities = 0

    rejected_or_non_opportunities = 0

    print(
        "=" * 60
    )

    print(
        "OPPORTUNITYBRIDGE VERIFICATION ENGINE"
    )

    print(
        "Version: 3.0"
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
            "Official URL: "
            f"{verified.get('official_url')}"
        )

        # ----------------------------------------------------
        # Counters
        # ----------------------------------------------------

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

        if classification in {
            "confirmed_opportunity",
            "trusted_opportunity",
        }:

            confirmed_opportunities += 1

        elif classification == (
            "possible_opportunity"
        ):

            possible_opportunities += 1

        else:

            rejected_or_non_opportunities += 1

        verified_items.append(
            verified
        )

    # ========================================================
    # OUTPUT
    # ========================================================

    output = {

        "verification_engine_version": "3.0",

        "generated_at": (
            __import__(
                "datetime"
            )
            .datetime
            .now(
                __import__(
                    "datetime"
                ).timezone.utc
            )
            .isoformat()
        ),

        "total_checked": len(
            verified_items
        ),

        "source_checked": source_checked,

        "page_checked": page_checked,

        "failed": failed,

        "human_review_required": human_review,

        "confirmed_opportunities": (
            confirmed_opportunities
        ),

        "possible_opportunities": (
            possible_opportunities
        ),

        "rejected_or_non_opportunities": (
            rejected_or_non_opportunities
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
        f"Failed: "
        f"{failed}"
    )

    print(
        f"Confirmed opportunities: "
        f"{confirmed_opportunities}"
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
        f"Rejected/non-opportunities: "
        f"{rejected_or_non_opportunities}"
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
