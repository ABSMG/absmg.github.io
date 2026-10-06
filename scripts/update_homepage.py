from pathlib import Path
from datetime import datetime, timezone
from html import escape
from urllib.parse import urlparse
import json
import re


# ============================================================
# OPPORTUNITYBRIDGE HOMEPAGE AUTO-UPDATER
# ============================================================
#
# Version:
#   3.0
#
# Purpose:
#   Read approved opportunities and automatically publish
#   the latest approved opportunities into index.html.
#
# Required files:
#   data/approved_opportunities.json
#   index.html
#
# The script only manages content between:
#
#   <!-- OPPORTUNITYBRIDGE_AUTO_OPPORTUNITIES_START -->
#   <!-- OPPORTUNITYBRIDGE_AUTO_OPPORTUNITIES_END -->
#
# Everything outside those markers is preserved.
#
# The script also ensures that the CSS required by the
# automatically generated opportunity cards exists.
#
# Important:
#   This script DOES NOT generate article pages.
#
#   Article generation is handled by:
#
#       scripts/opportunity_article_generator.py
#
#   This script only publishes links to already-generated
#   article pages on the homepage.
#
# Expected automation order:
#
#   discovery
#       ↓
#   verifier
#       ↓
#   approval
#       ↓
#   article generator
#       ↓
#   homepage updater
#       ↓
#   internal links
#       ↓
#   sitemap
#       ↓
#   SEO checker
#
# ============================================================


ROOT = Path(__file__).resolve().parents[1]

INDEX_FILE = ROOT / "index.html"

APPROVED_FILE = (
    ROOT
    / "data"
    / "approved_opportunities.json"
)


# ============================================================
# CONFIGURATION
# ============================================================

MAX_HOMEPAGE_OPPORTUNITIES = 12

BASE_URL = "https://absmg.github.io"

START_MARKER = (
    "<!-- OPPORTUNITYBRIDGE_AUTO_OPPORTUNITIES_START -->"
)

END_MARKER = (
    "<!-- OPPORTUNITYBRIDGE_AUTO_OPPORTUNITIES_END -->"
)

AUTO_ARTICLE_MARKER = (
    "OPPORTUNITYBRIDGE_AUTO_ARTICLE"
)


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):
    """
    Convert a value to safe plain text.

    Dictionaries and lists are ignored because they should
    not accidentally become visible homepage text.
    """

    if value is None:
        return ""

    if isinstance(value, (dict, list, tuple, set)):
        return ""

    return str(value).strip()


def clean_lower(value):
    """
    Return normalized lowercase text.
    """

    return clean_text(value).lower()


def first_value(item, *keys):
    """
    Return the first non-empty value from a list of possible
    dictionary keys.
    """

    if not isinstance(item, dict):
        return ""

    for key in keys:

        value = item.get(key)

        if value is None:
            continue

        value = clean_text(value)

        if value:
            return value

    return ""


def safe_html(value):
    """
    Escape content before placing it into HTML.
    """

    return escape(
        clean_text(value),
        quote=True
    )


def normalize_whitespace(value):
    """
    Normalize repeated whitespace.
    """

    value = clean_text(value)

    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        value
    ).strip()


# ============================================================
# URL HELPERS
# ============================================================

def is_http_url(url):
    """
    Allow only normal HTTP/HTTPS URLs.
    """

    url = clean_text(url)

    if not url:
        return False

    try:

        parsed = urlparse(url)

        return (
            parsed.scheme.lower() in {
                "http",
                "https",
            }
            and bool(parsed.netloc)
        )

    except Exception:
        return False


def normalize_url(url):
    """
    Normalize a URL for comparison.

    This is used for deduplication and source matching.
    """

    url = clean_text(url)

    if not url:
        return ""

    # Remove HTML entity noise where possible.
    url = (
        url
        .replace("&amp;", "&")
        .replace("&#x2F;", "/")
        .replace("&#47;", "/")
    )

    # Remove surrounding whitespace.
    url = url.strip()

    # Remove trailing slash.
    url = url.rstrip("/")

    return url.lower()


def make_site_relative_url(url):
    """
    Convert an OpportunityBridge absolute URL into a
    root-relative URL.

    Example:

        https://absmg.github.io/example.html

    becomes:

        example.html
    """

    url = clean_text(url)

    if not url:
        return ""

    normalized = url.rstrip("/")

    base_variants = [
        BASE_URL.rstrip("/") + "/",
        BASE_URL.rstrip("/"),
    ]

    for base in base_variants:

        if normalized.startswith(base):

            relative = normalized[
                len(base):
            ].lstrip("/")

            return relative

    return ""


def safe_article_relative_url(value):
    """
    Validate and normalize an article path.

    External article URLs are rejected because the homepage
    should link to the internally generated OpportunityBridge
    article page.
    """

    value = clean_text(value)

    if not value:
        return ""

    # Absolute OpportunityBridge URL.
    site_relative = make_site_relative_url(
        value
    )

    if site_relative:
        value = site_relative

    # External URL should not be used as the article URL.
    if is_http_url(value):

        return ""

    value = value.lstrip("/")

    # Do not allow obvious path traversal.
    if ".." in Path(value).parts:
        return ""

    # Article pages generated by this system are root HTML files.
    if not value.lower().endswith(".html"):
        return ""

    article_path = ROOT / value

    try:

        article_path.resolve().relative_to(
            ROOT.resolve()
        )

    except Exception:

        return ""

    return value


# ============================================================
# DATE HELPERS
# ============================================================

def parse_date(value):
    """
    Try to parse a date/time string.

    Returns a timezone-aware datetime when possible.
    """

    value = clean_text(value)

    if not value:
        return None

    # ISO 8601.
    try:

        normalized = value.replace(
            "Z",
            "+00:00"
        )

        dt = datetime.fromisoformat(
            normalized
        )

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt

    except Exception:
        pass

    # Common date formats.
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]

    for fmt in formats:

        try:

            dt = datetime.strptime(
                value,
                fmt
            )

            return dt.replace(
                tzinfo=timezone.utc
            )

        except Exception:
            continue

    return None


def format_date_for_homepage(value):
    """
    Keep a real deadline/publication value readable.

    No date is invented.

    If the value is parseable, return a cleaner human-readable
    date. Otherwise preserve the original value.
    """

    value = clean_text(value)

    if not value:
        return ""

    dt = parse_date(value)

    if not dt:
        return value

    return dt.strftime(
        "%d %b %Y"
    )


def get_sort_date(item):
    """
    Find the most useful date for sorting opportunities.

    Preference is given to publication/approval timestamps.
    """

    date_keys = [
        "published_at",
        "published",
        "publication_date",
        "date_published",
        "approved_at",
        "verified_at",
        "updated_at",
        "date",
        "created_at",
    ]

    for key in date_keys:

        value = item.get(key)

        dt = parse_date(value)

        if dt:
            return dt

    return datetime.min.replace(
        tzinfo=timezone.utc
    )


# ============================================================
# CATEGORY DETECTION
# ============================================================

CATEGORY_RULES = {

    "scholarships": [
        "scholarship",
        "scholarships",
        "fully funded",
        "funded study",
        "study funding",
        "tuition funding",
    ],

    "jobs": [
        "job",
        "jobs",
        "employment",
        "vacancy",
        "vacancies",
        "career",
        "careers",
        "recruitment",
    ],

    "remote-jobs": [
        "remote job",
        "remote jobs",
        "work from home",
        "work-from-home",
        "remote work",
    ],

    "internships": [
        "internship",
        "internships",
        "intern",
        "graduate trainee",
        "traineeship",
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
        "financial support",
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
        "workshop",
        "academy",
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
        "researcher",
        "researchers",
    ],

    "study-abroad": [
        "study abroad",
        "international students",
        "study in",
        "university scholarship",
        "international scholarship",
        "overseas study",
    ],

    "volunteer": [
        "volunteer",
        "volunteering",
        "voluntary",
    ],

    "digital-skills": [
        "digital skills",
        "technology skills",
        "tech skills",
        "coding",
        "programming",
        "artificial intelligence",
        "ai skills",
        "data science",
        "cybersecurity",
    ],
}


def normalize_category(value):
    """
    Normalize category values coming from the approval engine.
    """

    value = clean_lower(value)

    if not value:
        return ""

    aliases = {

        "scholarship":
            "scholarships",

        "scholarships":
            "scholarships",

        "job":
            "jobs",

        "jobs":
            "jobs",

        "remote job":
            "remote-jobs",

        "remote jobs":
            "remote-jobs",

        "remote-job":
            "remote-jobs",

        "internship":
            "internships",

        "internships":
            "internships",

        "fellowship":
            "fellowships",

        "fellowships":
            "fellowships",

        "grant":
            "grants",

        "grants":
            "grants",

        "course":
            "courses",

        "courses":
            "courses",

        "training":
            "training",

        "trainings":
            "training",

        "competition":
            "competitions",

        "competitions":
            "competitions",

        "research":
            "research",

        "study abroad":
            "study-abroad",

        "study-abroad":
            "study-abroad",

        "volunteer":
            "volunteer",

        "volunteering":
            "volunteer",

        "digital skills":
            "digital-skills",

        "digital-skills":
            "digital-skills",

        "opportunity":
            "opportunities",

        "opportunities":
            "opportunities",
    }

    return aliases.get(
        value,
        value
    )


def detect_category(item):
    """
    Determine a useful homepage category.

    Explicit approval/verifier category values get priority
    over keyword detection.
    """

    explicit = first_value(
        item,
        "approval_category",
        "detected_category",
        "opportunity_type",
        "category",
        "type",
        "category_name",
    )

    explicit_normalized = normalize_category(
        explicit
    )

    if explicit_normalized in CATEGORY_LABELS:

        return explicit_normalized

    combined = " ".join(
        [
            first_value(
                item,
                "title",
                "name",
            ),
            first_value(
                item,
                "description",
                "summary",
            ),
            first_value(
                item,
                "matched_keywords",
            ),
            explicit,
        ]
    ).lower()

    # Keyword detection.
    for category, keywords in CATEGORY_RULES.items():

        for keyword in keywords:

            if keyword in combined:

                return category

    return "opportunities"


# ============================================================
# CATEGORY LABELS
# ============================================================

CATEGORY_LABELS = {

    "scholarships":
        "Scholarship",

    "jobs":
        "Job",

    "remote-jobs":
        "Remote Job",

    "internships":
        "Internship",

    "fellowships":
        "Fellowship",

    "grants":
        "Grant",

    "courses":
        "Course",

    "training":
        "Training",

    "competitions":
        "Competition",

    "research":
        "Research",

    "study-abroad":
        "Study Abroad",

    "volunteer":
        "Volunteer",

    "digital-skills":
        "Digital Skills",

    "opportunities":
        "Opportunity",
}


# ============================================================
# CATEGORY LINKS
# ============================================================

CATEGORY_LINKS = {

    "scholarships":
        "scholarships.html",

    "jobs":
        "jobs.html",

    "remote-jobs":
        "jobs.html",

    "internships":
        "internships.html",

    "courses":
        "courses.html",

    "training":
        "courses.html",

    "digital-skills":
        "ai-skills.html",

    "fellowships":
        "opportunities.html",

    "grants":
        "opportunities.html",

    "competitions":
        "opportunities.html",

    "research":
        "opportunities.html",

    "study-abroad":
        "opportunities.html",

    "volunteer":
        "opportunities.html",

    "opportunities":
        "opportunities.html",
}


def get_category_link(category):
    """
    Return a safe internal category page.
    """

    category = normalize_category(
        category
    )

    return CATEGORY_LINKS.get(
        category,
        "opportunities.html"
    )


# ============================================================
# ARTICLE URL RESOLUTION
# ============================================================

def article_file_contains_source(
    html_file,
    source_urls
):
    """
    Check whether a generated article contains one of the
    approved source URLs.

    This is used as a compatibility fallback for older
    generated article pages that may not yet contain the
    newer article metadata fields.
    """

    try:

        content = html_file.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    except Exception:

        return False

    if not content:
        return False

    # Prefer generated article marker.
    has_generated_marker = (
        AUTO_ARTICLE_MARKER
        in content
    )

    normalized_content = normalize_url(
        content
    )

    for source_url in source_urls:

        source_url = normalize_url(
            source_url
        )

        if not source_url:
            continue

        if source_url in normalized_content:

            # If it is a generated article, this is a
            # strong match.
            if has_generated_marker:
                return True

            # Backwards compatibility:
            # Older generator pages may not have the marker.
            #
            # Require OpportunityBridge branding so that a
            # completely unrelated HTML page is less likely
            # to be selected.
            if (
                "OpportunityBridge"
                in content
            ):
                return True

    return False


def get_article_url(item):
    """
    Find the generated article URL.

    Preferred:
        article_url
        article
        article_path
        article_filename

    If those are not available, use source/official/
    application URLs to locate an existing generated
    OpportunityBridge HTML article.

    The article URL must point to a local root HTML file.
    """

    direct_url = first_value(
        item,
        "article_url",
        "article",
        "article_path",
        "article_filename",
    )

    if direct_url:

        direct_relative = safe_article_relative_url(
            direct_url
        )

        if direct_relative:

            article_path = (
                ROOT / direct_relative
            )

            if article_path.exists():

                return direct_relative

    # Gather all possible source URLs.
    source_candidates = [

        first_value(
            item,
            "official_url",
        ),

        first_value(
            item,
            "source_url",
        ),

        first_value(
            item,
            "application_url",
        ),

        first_value(
            item,
            "url",
        ),

        first_value(
            item,
            "link",
        ),
    ]

    source_candidates = [
        url
        for url in source_candidates
        if is_http_url(url)
    ]

    if not source_candidates:

        return ""

    # Prefer generated article pages.
    for html_file in ROOT.glob(
        "*.html"
    ):

        if article_file_contains_source(
            html_file,
            source_candidates
        ):

            return html_file.name

    return ""


# ============================================================
# DESCRIPTION
# ============================================================

def build_description(item):
    """
    Build a concise homepage description.

    The description is based only on information already
    present in the approved record.

    No opportunity facts are invented.
    """

    description = first_value(
        item,
        "short_description",
        "description",
        "summary",
        "excerpt",
    )

    description = normalize_whitespace(
        description
    )

    if not description:

        title = first_value(
            item,
            "title",
            "name",
        )

        category = CATEGORY_LABELS.get(
            detect_category(item),
            "Opportunity"
        )

        if title:

            description = (
                f"Explore this {category.lower()} "
                f"and check the official source for "
                f"eligibility, deadline and application details."
            )

        else:

            description = (
                "Explore this opportunity and check "
                "the official source for eligibility, "
                "deadline and application details."
            )

    # Keep homepage cards compact.
    if len(description) > 220:

        description = (
            description[:217].rstrip()
            + "..."
        )

    return description


# ============================================================
# REGION / COUNTRY
# ============================================================

def get_location(item):
    """
    Get country/region information if available.

    Never invent a location.
    """

    # Approval/verifier values get priority.
    location = first_value(
        item,
        "approval_location",
        "detected_location",
        "location",
    )

    country = first_value(
        item,
        "country",
        "country_name",
        "location_country",
    )

    region = first_value(
        item,
        "region",
        "region_name",
        "continent",
        "location_region",
    )

    if location:

        location = normalize_whitespace(
            location
        )

        if location:
            return location

    if country and region:

        if country.lower() not in region.lower():

            return (
                f"{country} • {region}"
            )

        return country

    if country:
        return country

    if region:
        return region

    # Do not invent a country.
    return ""


# ============================================================
# DEADLINE
# ============================================================

def get_deadline(item):
    """
    Get deadline if the data source provides one.

    Never invent a deadline.
    """

    deadline = first_value(
        item,
        "approval_deadline",
        "detected_deadline",
        "deadline",
        "application_deadline",
        "closing_date",
        "close_date",
        "deadline_date",
    )

    if not deadline:
        return ""

    return format_date_for_homepage(
        deadline
    )


# ============================================================
# SOURCE / PUBLISHER
# ============================================================

def get_source_name(item):
    """
    Get the source/publisher name.

    Discovery currently uses publisher_name, while older
    records may use publisher/source/source_name.
    """

    return first_value(
        item,
        "publisher_name",
        "publisher",
        "source_name",
        "organization",
        "provider",
        "source",
    )


# ============================================================
# OFFICIAL URL
# ============================================================

def get_official_url(item):
    """
    Get the authoritative source URL.

    Priority:
        official_url
        source_url
        url
        link

    application_url is intentionally NOT used as the
    official source fallback because it represents the
    application destination rather than necessarily the
    main opportunity information page.
    """

    candidates = [
        first_value(
            item,
            "official_url",
        ),

        first_value(
            item,
            "source_url",
        ),

        first_value(
            item,
            "url",
        ),

        first_value(
            item,
            "link",
        ),
    ]

    for candidate in candidates:

        if is_http_url(candidate):

            return candidate

    return ""


# ============================================================
# APPLICATION URL
# ============================================================

def get_application_url(item):
    """
    Get the application URL if the verification/approval
    system detected one.

    Never invent an application URL.
    """

    application_url = first_value(
        item,
        "application_url",
        "apply_url",
        "application_link",
    )

    if not is_http_url(
        application_url
    ):

        return ""

    return application_url


# ============================================================
# DEDUPLICATION
# ============================================================

def opportunity_identity(item):
    """
    Generate a stable identity for deduplication.

    Priority:
        official URL
        source URL
        application URL
        article URL
        title
    """

    url_candidates = [

        first_value(
            item,
            "official_url",
        ),

        first_value(
            item,
            "source_url",
        ),

        first_value(
            item,
            "application_url",
        ),

        first_value(
            item,
            "article_url",
        ),
    ]

    for url in url_candidates:

        normalized = normalize_url(
            url
        )

        if normalized:

            return (
                "url:"
                + normalized
            )

    title = first_value(
        item,
        "title",
        "name",
    ).lower()

    title = re.sub(
        r"\s+",
        " ",
        title
    ).strip()

    if title:

        return (
            "title:"
            + title
        )

    return ""


def deduplicate_opportunities(items):
    """
    Remove duplicate opportunities while preserving
    the first/best occurrence.

    The approval engine should already have filtered the
    records, but this second gate prevents duplicate cards.
    """

    seen = set()
    result = []

    for item in items:

        if not isinstance(
            item,
            dict
        ):

            continue

        identity = opportunity_identity(
            item
        )

        if not identity:
            continue

        if identity in seen:
            continue

        seen.add(identity)

        result.append(
            item
        )

    return result


# ============================================================
# QUALITY / APPROVAL CHECK
# ============================================================

def is_usable_opportunity(item):
    """
    Basic safety/quality gate for homepage publishing.

    Only approved items should normally reach this script,
    but this second gate prevents obviously invalid records.
    """

    if not isinstance(
        item,
        dict
    ):

        return False

    title = first_value(
        item,
        "title",
        "name",
    )

    if not title:
        return False

    # --------------------------------------------------------
    # Respect explicit approval status.
    # --------------------------------------------------------

    approval_status = first_value(
        item,
        "approval_status",
        "status",
    ).lower()

    if approval_status:

        allowed = {
            "approved",
            "publish",
            "published",
        }

        if approval_status not in allowed:

            return False

    # --------------------------------------------------------
    # If the record explicitly says it is NOT approved for
    # homepage publication, reject it.
    # --------------------------------------------------------

    approved_for_homepage = item.get(
        "approved_for_homepage"
    )

    if (
        approved_for_homepage is not None
        and approved_for_homepage is not True
    ):

        return False

    # --------------------------------------------------------
    # If the record has an explicit approval classification,
    # reject known non-opportunity classifications.
    # --------------------------------------------------------

    classification = clean_lower(
        first_value(
            item,
            "opportunity_classification",
        )
    )

    rejected_classifications = {
        "failed",
        "likely_news_or_general_content",
        "insufficient_opportunity_evidence",
        "possible_opportunity",
    }

    if classification in rejected_classifications:

        return False

    # --------------------------------------------------------
    # Do not publish records that explicitly require human
    # review when they are not also approved.
    # --------------------------------------------------------

    needs_human_review = item.get(
        "needs_human_review"
    )

    if (
        needs_human_review is True
        and approval_status != "approved"
    ):

        return False

    # Article must be resolvable later.
    return True


# ============================================================
# LOAD APPROVED OPPORTUNITIES
# ============================================================

def load_approved_opportunities():
    """
    Load approved opportunities from JSON.

    Supported structures:

        1. list

        2. {
             "approved_items": [...]
           }

        3. {
             "opportunities": [...]
           }

        4. {
             "approved_opportunities": [...]
           }

        5. {
             "items": [...]
           }

        6. {
             "data": [...]
           }
    """

    if not APPROVED_FILE.exists():

        print(
            "WARNING: approved_opportunities.json "
            "was not found."
        )

        return []

    try:

        data = json.loads(
            APPROVED_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:

        print(
            "ERROR: Could not read "
            f"{APPROVED_FILE}: {exc}"
        )

        return []

    # --------------------------------------------------------
    # Direct list.
    # --------------------------------------------------------

    if isinstance(
        data,
        list
    ):

        return data

    # --------------------------------------------------------
    # Dictionary structures.
    # --------------------------------------------------------

    if isinstance(
        data,
        dict
    ):

        for key in [

            "approved_items",

            "opportunities",

            "approved_opportunities",

            "items",

            "data",
        ]:

            value = data.get(
                key
            )

            if isinstance(
                value,
                list
            ):

                return value

    print(
        "WARNING: No opportunity list was found "
        "inside approved_opportunities.json."
    )

    return []


# ============================================================
# PREPARE HOMEPAGE ITEMS
# ============================================================

def prepare_homepage_items(items):
    """
    Prepare approved opportunities for homepage publishing.

    Only opportunities with a real generated article page
    are included.

    This prevents broken homepage links.
    """

    prepared = []

    for item in items:

        if not is_usable_opportunity(
            item
        ):

            continue

        title = first_value(
            item,
            "title",
            "name",
        )

        # ----------------------------------------------------
        # Article URL
        # ----------------------------------------------------

        article_url = get_article_url(
            item
        )

        if not article_url:

            print(
                "SKIP: No generated article found for:"
                f" {title}"
            )

            continue

        article_path = (
            ROOT / article_url
        )

        if not article_path.exists():

            print(
                "SKIP: Article file does not exist:"
                f" {article_url}"
            )

            continue

        # ----------------------------------------------------
        # Category
        # ----------------------------------------------------

        category = detect_category(
            item
        )

        category_label = CATEGORY_LABELS.get(
            category,
            "Opportunity"
        )

        category_link = get_category_link(
            category
        )

        # ----------------------------------------------------
        # Description
        # ----------------------------------------------------

        description = build_description(
            item
        )

        # ----------------------------------------------------
        # Location
        # ----------------------------------------------------

        location = get_location(
            item
        )

        # ----------------------------------------------------
        # Deadline
        # ----------------------------------------------------

        deadline = get_deadline(
            item
        )

        # ----------------------------------------------------
        # Source
        # ----------------------------------------------------

        source_name = get_source_name(
            item
        )

        # ----------------------------------------------------
        # URLs
        # ----------------------------------------------------

        official_url = get_official_url(
            item
        )

        application_url = get_application_url(
            item
        )

        # ----------------------------------------------------
        # Prepare record.
        # ----------------------------------------------------

        prepared.append(
            {
                "title":
                    title,

                "article_url":
                    article_url,

                "category":
                    category,

                "category_label":
                    category_label,

                "category_link":
                    category_link,

                "description":
                    description,

                "location":
                    location,

                "deadline":
                    deadline,

                "source_name":
                    source_name,

                "official_url":
                    official_url,

                "application_url":
                    application_url,

                "sort_date":
                    get_sort_date(
                        item
                    ),
            }
        )

    # ========================================================
    # Newest first.
    # ========================================================

    prepared.sort(
        key=lambda x: x["sort_date"],
        reverse=True
    )

    # ========================================================
    # Deduplicate after preparation.
    # ========================================================

    unique = []

    seen = set()

    for item in prepared:

        identity = (
            normalize_url(
                item["official_url"]
            )
            or normalize_url(
                item["article_url"]
            )
            or item["title"].lower()
        )

        if identity in seen:
            continue

        seen.add(
            identity
        )

        unique.append(
            item
        )

    # ========================================================
    # Homepage limit.
    # ========================================================

    return unique[
        :MAX_HOMEPAGE_OPPORTUNITIES
    ]


# ============================================================
# HTML CARD
# ============================================================

def build_card(item):
    """
    Generate one homepage opportunity card.

    The card contains only verified/approved information
    already available in the approved opportunity record.
    """

    title = safe_html(
        item["title"]
    )

    category_label = safe_html(
        item["category_label"]
    )

    description = safe_html(
        item["description"]
    )

    article_url = safe_html(
        item["article_url"]
    )

    location = safe_html(
        item["location"]
    )

    deadline = safe_html(
        item["deadline"]
    )

    source_name = safe_html(
        item["source_name"]
    )

    category_link = safe_html(
        item["category_link"]
    )

    metadata_parts = []

    # --------------------------------------------------------
    # Category badge.
    # --------------------------------------------------------

    if category_label:

        metadata_parts.append(
            f'<span class="opportunity-badge">'
            f'{category_label}'
            f'</span>'
        )

    # --------------------------------------------------------
    # Location.
    # --------------------------------------------------------

    if location:

        metadata_parts.append(
            f'<span class="opportunity-location">'
            f'{location}'
            f'</span>'
        )

    metadata_html = ""

    if metadata_parts:

        metadata_html = (
            '<div class="opportunity-meta">'
            + "".join(
                metadata_parts
            )
            + '</div>'
        )

    # --------------------------------------------------------
    # Deadline.
    # --------------------------------------------------------

    deadline_html = ""

    if deadline:

        deadline_html = (
            '<p class="opportunity-deadline">'
            '<strong>Deadline:</strong> '
            f'{deadline}'
            '</p>'
        )

    # --------------------------------------------------------
    # Source.
    # --------------------------------------------------------

    source_html = ""

    if source_name:

        source_html = (
            '<p class="opportunity-source">'
            '<strong>Source:</strong> '
            f'{source_name}'
            '</p>'
        )

    # --------------------------------------------------------
    # Application link.
    #
    # Use application URL as the primary CTA when a valid
    # application destination was detected.
    # --------------------------------------------------------

    application_url = (
        item["application_url"]
    )

    application_html = ""

    if is_http_url(
        application_url
    ):

        safe_application_url = safe_html(
            application_url
        )

        application_html = (
            '<a '
            f'href="{safe_application_url}" '
            'class="opportunity-apply-link" '
            'target="_blank" '
            'rel="noopener noreferrer">'
            'Apply / Official Application →'
            '</a>'
        )

    # --------------------------------------------------------
    # Category link.
    # --------------------------------------------------------

    category_html = ""

    if category_link:

        category_html = (
            '<a '
            f'href="{category_link}" '
            'class="opportunity-category-link">'
            f'Browse {category_label} '
            '→'
            '</a>'
        )

    # --------------------------------------------------------
    # Card.
    # --------------------------------------------------------

    return f"""
        <article
          class="card latest-opportunity-card"
          data-category="{safe_html(item["category"])}"
          data-opportunity="latest">

          <div
            class="card-icon"
            aria-hidden="true">
          </div>

          {metadata_html}

          <h3>
            {title}
          </h3>

          <p>
            {description}
          </p>

          {deadline_html}

          {source_html}

          <div class="opportunity-card-actions">

            <a
              href="{article_url}"
              class="card-link"
              aria-label="Read {title}">

              Read Opportunity →

            </a>

            {application_html}

          </div>

          {category_html}

        </article>
    """.strip()


# ============================================================
# EMPTY STATE
# ============================================================

def build_empty_state():
    """
    Safe homepage state when no approved opportunities
    with valid article pages are available.
    """

    return """
        <div
          class="latest-empty-state"
          role="status">

          <h3>
            New opportunities are being checked
          </h3>

          <p>
            Please explore our opportunity categories
            while the latest verified opportunities are
            being prepared.
          </p>

          <a
            href="opportunities.html"
            class="card-link">

            Explore All Opportunities →

          </a>

        </div>
    """.strip()


# ============================================================
# HOMEPAGE SECTION
# ============================================================

def build_homepage_section(items):
    """
    Build the complete automatically managed section.

    This function does not add the outer automation markers.
    Those are handled by update_index_html().
    """

    generated_at = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    if not items:

        cards_html = build_empty_state()

    else:

        cards = []

        for item in items:

            cards.append(
                build_card(
                    item
                )
            )

        cards_html = "\n\n".join(
            cards
        )

    return f"""
    <!-- =================================================
         AUTOMATICALLY UPDATED OPPORTUNITIES
         Generated: {generated_at}
         DO NOT EDIT BETWEEN AUTOMATION MARKERS
    ================================================== -->

    <section
      class="container latest-opportunities"
      id="latest-opportunities"
      aria-labelledby="latest-opportunities-heading">

      <div class="section-title">

        <h2 id="latest-opportunities-heading">
          Latest Opportunities
        </h2>

        <p>
          Explore the latest approved opportunities
          published on OpportunityBridge.
        </p>

      </div>

      <div
        class="cards latest-opportunity-grid"
        id="latestOpportunityCards">

        {cards_html}

      </div>

    </section>
    """.strip()


# ============================================================
# INSERT / REPLACE AUTOMATION BLOCK
# ============================================================

def update_index_html(
    html,
    section_html
):
    """
    Replace the automated homepage block.

    If markers do not exist, insert the section before
    the first recognizable opportunity-card section.

    Everything outside the managed block remains unchanged.
    """

    if not INDEX_FILE.exists():

        raise FileNotFoundError(
            f"Homepage not found: {INDEX_FILE}"
        )

    # ========================================================
    # Existing markers.
    # ========================================================

    start_position = html.find(
        START_MARKER
    )

    end_position = html.find(
        END_MARKER
    )

    if (
        start_position != -1
        and end_position != -1
        and end_position > start_position
    ):

        replacement_start = (
            start_position
            + len(START_MARKER)
        )

        new_html = (
            html[:replacement_start]
            + "\n\n"
            + section_html
            + "\n\n"
            + html[end_position:]
        )

        return (
            new_html,
            "replaced"
        )

    # ========================================================
    # Broken marker state.
    #
    # If only one marker exists, do NOT blindly duplicate
    # another block. Remove the incomplete automation block
    # only if it is clearly recoverable.
    # ========================================================

    if (
        start_position != -1
        and end_position == -1
    ):

        print(
            "WARNING: Start marker exists but end marker "
            "was not found."
        )

        # Append an end marker after the existing content
        # only if we can safely identify the homepage main.
        main_end = html.lower().rfind(
            "</main>"
        )

        if main_end != -1:

            recovered_html = (
                html[:main_end]
                + "\n\n"
                + END_MARKER
                + "\n"
                + html[main_end:]
            )

            end_position = recovered_html.find(
                END_MARKER
            )

            start_position = recovered_html.find(
                START_MARKER
            )

            replacement_start = (
                start_position
                + len(START_MARKER)
            )

            new_html = (
                recovered_html[
                    :replacement_start
                ]
                + "\n\n"
                + section_html
                + "\n\n"
                + recovered_html[
                    end_position:
                ]
            )

            return (
                new_html,
                "repaired-and-replaced"
            )

    # ========================================================
    # Missing markers.
    #
    # Insert immediately before the first recognizable
    # opportunity cards section.
    # ========================================================

    marker_pattern = re.compile(
        r'(\s*<!-- =================================================\s*'
        r'OPPORTUNITY CARDS\s*'
        r'================================================== -->)',
        re.IGNORECASE
    )

    match = marker_pattern.search(
        html
    )

    if match:

        insertion = (
            "\n\n"
            + START_MARKER
            + "\n\n"
            + section_html
            + "\n\n"
            + END_MARKER
            + "\n\n"
        )

        new_html = (
            html[:match.start()]
            + insertion
            + html[match.start():]
        )

        return (
            new_html,
            "inserted"
        )

    # ========================================================
    # Fallback:
    #
    # Insert before </main>.
    #
    # This keeps the dynamic section inside the homepage's
    # main content instead of accidentally placing it after
    # </main>.
    # ========================================================

    main_end = html.lower().rfind(
        "</main>"
    )

    if main_end != -1:

        insertion = (
            "\n\n"
            + START_MARKER
            + "\n\n"
            + section_html
            + "\n\n"
            + END_MARKER
            + "\n\n"
        )

        new_html = (
            html[:main_end]
            + insertion
            + html[main_end:]
        )

        return (
            new_html,
            "inserted-before-main-close"
        )

    # ========================================================
    # No safe insertion point.
    # ========================================================

    raise RuntimeError(
        "Could not find a safe location to insert "
        "the automated homepage section."
    )


# ============================================================
# ADD REQUIRED CSS
# ============================================================

AUTO_CSS_MARKER_START = (
    "/* OPPORTUNITYBRIDGE AUTO OPPORTUNITIES CSS START */"
)

AUTO_CSS_MARKER_END = (
    "/* OPPORTUNITYBRIDGE AUTO OPPORTUNITIES CSS END */"
)


AUTO_CSS = f"""
    {AUTO_CSS_MARKER_START}

    .latest-opportunities {{
      padding-top: 34px;
    }}

    .latest-opportunity-grid {{
      margin-top: 4px;
    }}

    .latest-opportunity-card {{
      min-height: 310px;
    }}

    .latest-opportunity-card .opportunity-meta {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-bottom: 13px;
    }}

    .latest-opportunity-card .opportunity-badge {{
      display: inline-block;
      padding: 5px 9px;
      border-radius: 999px;
      background: #eef4ff;
      color: var(--navy);
      font-size: 12px;
      font-weight: 700;
    }}

    .latest-opportunity-card .opportunity-location {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }}

    .latest-opportunity-card .opportunity-deadline,
    .latest-opportunity-card .opportunity-source {{
      margin-bottom: 9px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }}

    .latest-opportunity-card .opportunity-deadline strong,
    .latest-opportunity-card .opportunity-source strong {{
      color: var(--dark);
    }}

    .latest-opportunity-card
    .opportunity-card-actions {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      margin-top: 14px;
    }}

    .latest-opportunity-card
    .opportunity-apply-link {{
      display: inline-block;
      color: var(--navy);
      font-size: 13px;
      font-weight: 700;
      text-decoration: none;
    }}

    .latest-opportunity-card
    .opportunity-apply-link:hover {{
      text-decoration: underline;
    }}

    .latest-opportunity-card
    .opportunity-category-link {{
      display: inline-block;
      margin-top: 12px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
      text-decoration: none;
    }}

    .latest-opportunity-card
    .opportunity-category-link:hover {{
      color: var(--navy);
      text-decoration: underline;
    }}

    .latest-empty-state {{
      grid-column: 1 / -1;
      padding: 34px 26px;
      background: var(--white);
      border: 1px solid var(--border);
      border-radius: 12px;
      text-align: center;
      box-shadow: var(--shadow);
    }}

    .latest-empty-state h3 {{
      color: var(--navy);
      margin-bottom: 8px;
      font-size: 21px;
    }}

    .latest-empty-state p {{
      max-width: 650px;
      margin: 0 auto 15px;
      color: var(--muted);
    }}

    {AUTO_CSS_MARKER_END}
""".strip()


def ensure_css(html):
    """
    Add CSS required by automatically generated opportunity
    cards.

    The CSS is inserted before the LAST </style> element.

    The operation is idempotent:
    running the script repeatedly will not duplicate the CSS.
    """

    if (
        AUTO_CSS_MARKER_START in html
        and AUTO_CSS_MARKER_END in html
    ):

        return (
            html,
            False
        )

    style_end = html.lower().rfind(
        "</style>"
    )

    if style_end == -1:

        print(
            "WARNING: No </style> tag found. "
            "Automatic opportunity CSS was not added."
        )

        return (
            html,
            False
        )

    new_html = (
        html[:style_end]
        + "\n\n"
        + AUTO_CSS
        + "\n\n"
        + html[style_end:]
    )

    return (
        new_html,
        True
    )


# ============================================================
# HTML STRUCTURE SAFETY CHECKS
# ============================================================

def validate_generated_block(
    html
):
    """
    Validate the managed homepage block before writing.

    This provides a final safety check against accidentally
    producing an incomplete automation section.
    """

    start_count = html.count(
        START_MARKER
    )

    end_count = html.count(
        END_MARKER
    )

    if start_count != 1:

        raise RuntimeError(
            "Homepage safety check failed: expected exactly "
            f"1 start marker, found {start_count}."
        )

    if end_count != 1:

        raise RuntimeError(
            "Homepage safety check failed: expected exactly "
            f"1 end marker, found {end_count}."
        )

    start_position = html.find(
        START_MARKER
    )

    end_position = html.find(
        END_MARKER
    )

    if end_position <= start_position:

        raise RuntimeError(
            "Homepage safety check failed: end marker "
            "appears before start marker."
        )

    # The managed section should be inside <main>.
    main_start = html.lower().find(
        "<main"
    )

    main_end = html.lower().rfind(
        "</main>"
    )

    if (
        main_start != -1
        and main_end != -1
    ):

        if not (
            main_start
            < start_position
            < end_position
            < main_end
        ):

            raise RuntimeError(
                "Homepage safety check failed: automatic "
                "opportunity section is not inside <main>."
            )

    return True


# ============================================================
# BACKUP / CHANGE PROTECTION
# ============================================================

def count_existing_automation_blocks(
    html
):
    """
    Return the number of automation start/end markers.

    Used before and after updates to make sure the updater
    does not duplicate its own block.
    """

    return {
        "start":
            html.count(
                START_MARKER
            ),

        "end":
            html.count(
                END_MARKER
            ),
    }


def has_major_html_structure(
    html
):
    """
    Basic protection against writing to an unexpectedly
    corrupted homepage.
    """

    required_tokens = [
        "<html",
        "<head",
        "<body",
    ]

    lowered = html.lower()

    for token in required_tokens:

        if token not in lowered:

            return False

    return True


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================================"
    )

    print(
        "OpportunityBridge Homepage Updater v3.0"
    )

    print(
        "============================================================"
    )

    print(
        f"Root: {ROOT}"
    )

    print(
        f"Homepage: {INDEX_FILE}"
    )

    print(
        f"Approved data: {APPROVED_FILE}"
    )

    print()

    # ========================================================
    # Validate homepage.
    # ========================================================

    if not INDEX_FILE.exists():

        raise SystemExit(
            "ERROR: index.html was not found."
        )

    try:

        original_html = INDEX_FILE.read_text(
            encoding="utf-8"
        )

    except Exception as exc:

        raise SystemExit(
            f"ERROR: Could not read index.html: {exc}"
        )

    if not has_major_html_structure(
        original_html
    ):

        raise SystemExit(
            "ERROR: index.html does not look like a valid "
            "HTML document. No changes were made."
        )

    original_marker_counts = (
        count_existing_automation_blocks(
            original_html
        )
    )

    print(
        "Existing automation markers:"
    )

    print(
        f"  Start markers: "
        f"{original_marker_counts['start']}"
    )

    print(
        f"  End markers:   "
        f"{original_marker_counts['end']}"
    )

    print()

    # ========================================================
    # Load approved opportunities.
    # ========================================================

    approved = (
        load_approved_opportunities()
    )

    print(
        "Approved records loaded: "
        f"{len(approved)}"
    )

    # ========================================================
    # Deduplicate approved records.
    # ========================================================

    approved = (
        deduplicate_opportunities(
            approved
        )
    )

    print(
        "After deduplication: "
        f"{len(approved)}"
    )

    print()

    # ========================================================
    # Prepare homepage items.
    # ========================================================

    items = (
        prepare_homepage_items(
            approved
        )
    )

    print(
        "Valid homepage opportunities: "
        f"{len(items)}"
    )

    print()

    # ========================================================
    # Display selected opportunities.
    # ========================================================

    if items:

        print(
            "Homepage opportunities:"
        )

        for index, item in enumerate(
            items,
            start=1
        ):

            deadline_text = (
                item["deadline"]
                if item["deadline"]
                else "No deadline available"
            )

            location_text = (
                item["location"]
                if item["location"]
                else "Location not specified"
            )

            print(
                f"{index}. "
                f"{item['title']}"
            )

            print(
                f"   Category: "
                f"{item['category_label']}"
            )

            print(
                f"   Location: "
                f"{location_text}"
            )

            print(
                f"   Deadline: "
                f"{deadline_text}"
            )

            print(
                f"   Article: "
                f"{item['article_url']}"
            )

            if item["application_url"]:

                print(
                    f"   Application: "
                    f"{item['application_url']}"
                )

    else:

        print(
            "No approved opportunities with valid generated "
            "article pages are currently available."
        )

    print()

    # ========================================================
    # Build automated section.
    # ========================================================

    section_html = (
        build_homepage_section(
            items
        )
    )

    # ========================================================
    # Add CSS first.
    #
    # IMPORTANT:
    # The section update must operate on the CSS-updated
    # document, not on the original document.
    #
    # This fixes the original implementation's double-pass
    # issue where the first update was created from the old
    # HTML and CSS was then re-applied afterward.
    # ========================================================

    html_with_css, css_added = (
        ensure_css(
            original_html
        )
    )

    if css_added:

        print(
            "Automatic opportunity card CSS added."
        )

    else:

        print(
            "Automatic opportunity card CSS already exists."
        )

    # ========================================================
    # Update homepage section.
    # ========================================================

    updated_html, action = (
        update_index_html(
            html_with_css,
            section_html
        )
    )

    # ========================================================
    # Final safety validation.
    # ========================================================

    try:

        validate_generated_block(
            updated_html
        )

    except Exception as exc:

        raise SystemExit(
            "ERROR: Homepage safety validation failed. "
            "No changes were written.\n"
            f"Reason: {exc}"
        )

    # ========================================================
    # Check marker counts again.
    # ========================================================

    updated_marker_counts = (
        count_existing_automation_blocks(
            updated_html
        )
    )

    if (
        updated_marker_counts["start"]
        != 1
        or
        updated_marker_counts["end"]
        != 1
    ):

        raise SystemExit(
            "ERROR: Homepage marker safety check failed. "
            "No changes were written."
        )

    # ========================================================
    # Avoid unnecessary write.
    # ========================================================

    if updated_html == original_html:

        print(
            "Homepage already up to date."
        )

        print(
            "No file changes required."
        )

        print(
            f"Published cards: {len(items)}"
        )

        print(
            "OPPORTUNITYBRIDGE HOMEPAGE UPDATE COMPLETE"
        )

        return

    # ========================================================
    # Write homepage.
    # ========================================================

    try:

        INDEX_FILE.write_text(
            updated_html,
            encoding="utf-8"
        )

    except Exception as exc:

        raise SystemExit(
            f"ERROR: Could not write index.html: {exc}"
        )

    # ========================================================
    # Confirm written file.
    # ========================================================

    try:

        written_html = INDEX_FILE.read_text(
            encoding="utf-8"
        )

    except Exception as exc:

        raise SystemExit(
            "ERROR: Could not re-read index.html "
            f"after writing: {exc}"
        )

    try:

        validate_generated_block(
            written_html
        )

    except Exception as exc:

        raise SystemExit(
            "ERROR: Post-write homepage validation failed. "
            f"Reason: {exc}"
        )

    # ========================================================
    # Final report.
    # ========================================================

    print()

    print(
        "------------------------------------------------------------"
    )

    print(
        f"Homepage update action: {action}"
    )

    print(
        f"Approved records loaded: {len(approved)}"
    )

    print(
        f"Published cards:          {len(items)}"
    )

    print(
        f"CSS added:                "
        f"{'YES' if css_added else 'NO'}"
    )

    print(
        f"Start markers:            "
        f"{updated_marker_counts['start']}"
    )

    print(
        f"End markers:              "
        f"{updated_marker_counts['end']}"
    )

    print(
        "------------------------------------------------------------"
    )

    print()

    print(
        "index.html updated successfully."
    )

    print(
        "Only the managed OpportunityBridge automation block "
        "was changed."
    )

    print(
        "OPPORTUNITYBRIDGE HOMEPAGE UPDATE COMPLETE"
    )


# ============================================================
# SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
