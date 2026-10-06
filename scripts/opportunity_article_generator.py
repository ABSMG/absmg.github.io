from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timezone
import hashlib
import html
import json
import re


ROOT = Path(__file__).resolve().parents[1]

INPUT = ROOT / "data" / "approved_opportunities.json"

BASE_URL = "https://absmg.github.io"

SITE_NAME = "OpportunityBridge"

AUTHOR_NAME = "OpportunityBridge"

MAX_DESCRIPTION_LENGTH = 320

MAX_SUMMARY_LENGTH = 700

MAX_EVIDENCE_ITEMS = 12


# ============================================================
# BASIC HELPERS
# ============================================================

def clean(value):
    """
    Safely convert a value to normalized text.
    """

    if value is None:
        return ""

    return str(value).strip()


def clean_whitespace(value):
    """
    Normalize repeated whitespace.
    """

    value = clean(value)

    return re.sub(
        r"\s+",
        " ",
        value
    ).strip()


def slugify(text):
    """
    Convert a title into a URL-safe article slug.
    """

    text = clean(text).lower()

    text = re.sub(
        r"[^a-z0-9\s-]",
        "",
        text
    )

    text = re.sub(
        r"[\s_-]+",
        "-",
        text
    )

    text = re.sub(
        r"-+",
        "-",
        text
    )

    text = text.strip("-")

    return text[:100].strip("-")


def source_hash(source_url):
    """
    Generate a stable hash for filename collision handling.
    """

    return hashlib.sha1(
        clean(source_url).encode("utf-8")
    ).hexdigest()[:8]


def valid_url(url):
    """
    Validate HTTP/HTTPS URLs.
    """

    try:

        parsed = urlparse(
            clean(url)
        )

        return (
            parsed.scheme in {
                "http",
                "https",
            }
            and bool(parsed.netloc)
        )

    except Exception:

        return False


def escape(value):
    """
    Escape text for safe HTML attribute/content insertion.
    """

    return html.escape(
        clean(value),
        quote=True
    )


def escape_text(value):
    """
    Escape text for HTML content.
    """

    return html.escape(
        clean(value),
        quote=False
    )


def safe_json_ld(data):
    """
    Serialize JSON-LD safely.

    Replacing '<' prevents a title or source value containing
    '</script>' from prematurely closing the JSON-LD script.
    """

    serialized = json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    )

    serialized = serialized.replace(
        "<",
        "\\u003c"
    )

    serialized = serialized.replace(
        ">",
        "\\u003e"
    )

    serialized = serialized.replace(
        "&",
        "\\u0026"
    )

    return serialized


# ============================================================
# ARTICLE FILE DISCOVERY
# ============================================================

def article_files():
    """
    Return all root-level HTML files.

    The site currently keeps generated article pages in the
    repository root, so this preserves the existing architecture.
    """

    return {
        path.name: path
        for path in ROOT.glob("*.html")
    }


def find_existing_article(source_url):
    """
    Find an existing generated article containing the same
    source URL.

    This prevents repeated automation runs from creating
    duplicate articles for the same opportunity.
    """

    source_url = clean(source_url)

    if not source_url:
        return None

    normalized_source = (
        source_url
        .rstrip("/")
        .lower()
    )

    for path in ROOT.glob("*.html"):

        try:

            content = path.read_text(
                encoding="utf-8",
                errors="ignore"
            )

            normalized_content = content.lower()

            # Exact source URL match.
            if normalized_source in normalized_content:
                return path

            # Also check escaped HTML representation.
            escaped_source = (
                html.escape(
                    source_url,
                    quote=True
                )
                .lower()
            )

            if escaped_source in normalized_content:
                return path

        except Exception:

            continue

    return None


def unique_article_path(title, source_url):
    """
    Generate a collision-safe article filename.
    """

    base_slug = slugify(
        title
    )

    if not base_slug:

        base_slug = "opportunity"

    candidate = ROOT / f"{base_slug}.html"

    if not candidate.exists():

        return candidate

    # Same title but different source.
    # Add a stable hash rather than a random filename.
    hashed_slug = (
        f"{base_slug}-"
        f"{source_hash(source_url)}"
    )

    candidate = ROOT / f"{hashed_slug}.html"

    if not candidate.exists():

        return candidate

    # Extremely rare case:
    # same title + same hash but a file already exists.
    # Keep adding a deterministic suffix.
    counter = 2

    while True:

        candidate = ROOT / (
            f"{hashed_slug}-{counter}.html"
        )

        if not candidate.exists():

            return candidate

        counter += 1


# ============================================================
# FIELD EXTRACTION
# ============================================================

def get_source_url(item):
    """
    Resolve the best source URL from the approved record.

    official_url is preferred because the verification engine
    may have followed redirects or discovered a canonical URL.
    """

    candidates = [
        item.get("official_url"),
        item.get("source_url"),
        item.get("url"),
        item.get("link"),
    ]

    for value in candidates:

        value = clean(value)

        if valid_url(value):

            return value

    return ""


def get_application_url(item):
    """
    Resolve a detected application URL.
    """

    candidates = [
        item.get("application_url"),
        item.get("apply_url"),
        item.get("application_link"),
    ]

    for value in candidates:

        value = clean(value)

        if valid_url(value):

            return value

    return ""


def get_publisher(item):
    """
    Support publisher/source field names used by previous
    discovery and verification versions.
    """

    candidates = [
        item.get("publisher"),
        item.get("publisher_name"),
        item.get("source"),
        item.get("source_name"),
        item.get("source_domain"),
    ]

    for value in candidates:

        value = clean(value)

        if value:

            return value

    source_url = get_source_url(
        item
    )

    if valid_url(source_url):

        domain = urlparse(
            source_url
        ).netloc

        return domain

    return ""


def get_category(item):
    """
    Resolve the detected/approved category.
    """

    candidates = [
        item.get("approval_category"),
        item.get("detected_category"),
        item.get("category"),
        item.get("opportunity_type"),
        item.get("type"),
    ]

    for value in candidates:

        value = clean(value)

        if value:

            return value

    return "opportunities"


def get_location(item):
    """
    Resolve geographic information when available.
    """

    candidates = [
        item.get("approval_location"),
        item.get("detected_location"),
        item.get("location"),
        item.get("country"),
        item.get("region"),
    ]

    for value in candidates:

        value = clean(value)

        if value:

            return value

    return ""


def get_deadline(item):
    """
    Resolve the detected/approved deadline.

    The generator does not invent deadlines.
    """

    candidates = [
        item.get("approval_deadline"),
        item.get("detected_deadline"),
        item.get("deadline"),
        item.get("application_deadline"),
        item.get("closing_date"),
    ]

    for value in candidates:

        value = clean(value)

        if value:

            return value

    return ""


def get_funding_type(item):
    """
    Resolve funding information when the verifier/discovery
    pipeline has detected it.
    """

    candidates = [
        item.get("funding_type"),
        item.get("funding"),
        item.get("funding_status"),
        item.get("award_type"),
    ]

    for value in candidates:

        value = clean(value)

        if value:

            return value

    return ""


def get_eligibility(item):
    """
    Resolve eligibility information when available.
    """

    candidates = [
        item.get("eligibility"),
        item.get("eligibility_criteria"),
        item.get("requirements"),
        item.get("qualification"),
    ]

    for value in candidates:

        value = clean(value)

        if value:

            return value

    return ""


def get_evidence(item):
    """
    Get verification evidence from the approved item.
    """

    evidence = item.get(
        "approval_evidence"
    )

    if not isinstance(
        evidence,
        list
    ):

        evidence = item.get(
            "verification_evidence",
            []
        )

    if not isinstance(
        evidence,
        list
    ):

        return []

    cleaned = []

    for value in evidence:

        value = clean_whitespace(
            value
        )

        if value:

            cleaned.append(
                value
            )

    return cleaned[
        :MAX_EVIDENCE_ITEMS
    ]


# ============================================================
# CONTENT BUILDING
# ============================================================

def build_description(item):
    """
    Build an SEO-friendly description without inventing facts.
    """

    description = clean_whitespace(
        item.get("description")
        or item.get("summary")
        or item.get("content")
    )

    if description:

        return description[
            :MAX_DESCRIPTION_LENGTH
        ]

    title = clean_whitespace(
        item.get("title")
    )

    category = get_category(
        item
    )

    location = get_location(
        item
    )

    location_text = ""

    if location:

        location_text = (
            f" for {location}"
        )

    return (
        f"{title}. Explore this "
        f"{category}{location_text}, "
        f"including available application information, "
        f"eligibility details, deadlines and the official source."
    )[
        :MAX_DESCRIPTION_LENGTH
    ]


def build_summary(item):
    """
    Build the main article summary.
    """

    description = clean_whitespace(
        item.get("description")
        or item.get("summary")
        or item.get("content")
    )

    if description:

        return description[
            :MAX_SUMMARY_LENGTH
        ]

    title = clean_whitespace(
        item.get("title")
    )

    category = get_category(
        item
    )

    location = get_location(
        item
    )

    if location:

        return (
            f"{title} is listed as a "
            f"{category} opportunity associated with "
            f"{location}. Review the available details "
            f"and confirm all requirements through the "
            f"official source before applying."
        )

    return (
        f"{title} is listed as a "
        f"{category} opportunity. Review the available "
        f"details and confirm all requirements through "
        f"the official source before applying."
    )


def build_keywords(item):
    """
    Build keywords from verification/discovery metadata.
    """

    keywords = []

    raw_keywords = item.get(
        "matched_keywords",
        []
    )

    if isinstance(
        raw_keywords,
        list
    ):

        keywords.extend(
            clean_whitespace(
                keyword
            )
            for keyword in raw_keywords
            if clean_whitespace(
                keyword
            )
        )

    category = get_category(
        item
    )

    location = get_location(
        item
    )

    if category:
        keywords.append(
            category
        )

    if location:
        keywords.append(
            location
        )

    # Useful general terms remain as fallback.
    if not keywords:

        keywords = [
            "opportunities",
            "scholarships",
            "jobs",
            "internships",
            "courses",
        ]

    return ", ".join(
        dict.fromkeys(
            keywords
        )
    )


# ============================================================
# JSON-LD
# ============================================================

def build_json_ld(
    title,
    description,
    article_url,
    source_url,
    application_url,
    publisher,
    category,
    location,
    deadline,
    published_date,
    modified_date,
):
    """
    Build Article structured data.

    Only fields that actually exist are included.
    """

    data = {
        "@context": "https://schema.org",

        "@type": "Article",

        "headline": title,

        "description": description,

        "url": article_url,

        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": article_url,
        },

        "datePublished": published_date,

        "dateModified": modified_date,

        "author": {
            "@type": "Organization",
            "name": AUTHOR_NAME,
            "url": BASE_URL,
        },

        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": BASE_URL,
        },

        "isPartOf": {
            "@type": "WebSite",
            "name": SITE_NAME,
            "url": BASE_URL,
        },
    }

    if publisher:

        data["about"] = {
            "@type": "Thing",
            "name": publisher,
        }

    if category:

        data["articleSection"] = category

    if location:

        data["spatialCoverage"] = {
            "@type": "Place",
            "name": location,
        }

    if source_url:

        data["citation"] = source_url

    if application_url:

        data["potentialAction"] = {
            "@type": "ApplyAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": application_url,
            },
        }

    return safe_json_ld(
        data
    )


# ============================================================
# HTML COMPONENT HELPERS
# ============================================================

def build_meta_item(
    label,
    value,
):
    """
    Build a metadata item only when a value exists.
    """

    value = clean_whitespace(
        value
    )

    if not value:

        return ""

    return f"""
        <div class="meta-item">
            <span class="meta-label">{escape_text(label)}</span>
            <strong>{escape_text(value)}</strong>
        </div>
    """


def build_opportunity_details(
    item,
):
    """
    Build the opportunity information panel.

    No value is invented when the verifier does not provide it.
    """

    category = get_category(
        item
    )

    location = get_location(
        item
    )

    deadline = get_deadline(
        item
    )

    funding_type = get_funding_type(
        item
    )

    eligibility = get_eligibility(
        item
    )

    score = clean(
        item.get("approval_score")
        or item.get("opportunity_score")
    )

    verification_level = clean(
        item.get("verification_level")
    )

    classification = clean(
        item.get("opportunity_classification")
    )

    details = []

    details.append(
        build_meta_item(
            "Category",
            category,
        )
    )

    details.append(
        build_meta_item(
            "Location",
            location,
        )
    )

    details.append(
        build_meta_item(
            "Deadline",
            deadline,
        )
    )

    details.append(
        build_meta_item(
            "Funding",
            funding_type,
        )
    )

    if eligibility:

        details.append(
            build_meta_item(
                "Eligibility",
                eligibility,
            )
        )

    if score:

        details.append(
            build_meta_item(
                "Verification score",
                score,
            )
        )

    if verification_level:

        details.append(
            build_meta_item(
                "Verification level",
                verification_level,
            )
        )

    if classification:

        details.append(
            build_meta_item(
                "Classification",
                classification,
            )
        )

    details = [
        detail
        for detail in details
        if detail
    ]

    if not details:

        return ""

    return f"""
        <section
            class="opportunity-details"
            aria-labelledby="opportunity-details-heading"
        >

            <h2 id="opportunity-details-heading">
                Opportunity Details
            </h2>

            <div class="details-grid">

                {"".join(details)}

            </div>

        </section>
    """


def build_application_section(
    application_url,
):
    """
    Build an application CTA only when a valid application URL
    was detected by the verification pipeline.
    """

    if not valid_url(
        application_url
    ):

        return ""

    safe_url = escape(
        application_url
    )

    return f"""
        <section
            class="application-section"
            aria-labelledby="application-heading"
        >

            <h2 id="application-heading">
                Application
            </h2>

            <p>
                A possible application or registration link was
                detected during source verification. Confirm that
                the page is the official application destination
                before submitting personal information or documents.
            </p>

            <p>
                <a
                    class="apply-button"
                    href="{safe_url}"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    Visit Application Page
                </a>
            </p>

        </section>
    """


def build_source_section(
    source_url,
    publisher,
):
    """
    Build the official/source section.
    """

    if not valid_url(
        source_url
    ):

        return """
        <section
            class="source-section"
            aria-labelledby="source-heading"
        >

            <h2 id="source-heading">
                Official Source
            </h2>

            <p>
                No valid source URL was available in the approved record.
                Please verify the opportunity through the original source
                before taking action.
            </p>

        </section>
        """

    safe_url = escape(
        source_url
    )

    publisher_text = (
        escape_text(
            publisher
        )
        if publisher
        else "official/source page"
    )

    return f"""
        <section
            class="source-section"
            aria-labelledby="source-heading"
        >

            <h2 id="source-heading">
                Official Source
            </h2>

            <p>
                Source:
                <strong>{publisher_text}</strong>
            </p>

            <p>
                <a
                    class="source-button"
                    href="{safe_url}"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    View Official / Source Page
                </a>
            </p>

        </section>
    """


def build_evidence_section(
    item,
):
    """
    Display verification evidence when available.

    This gives readers more transparency without pretending that
    OpportunityBridge is the original provider of the opportunity.
    """

    evidence = get_evidence(
        item
    )

    if not evidence:

        return ""

    list_items = []

    for evidence_item in evidence:

        list_items.append(
            f"""
            <li>
                {escape_text(evidence_item)}
            </li>
            """
        )

    return f"""
        <section
            class="verification-section"
            aria-labelledby="verification-heading"
        >

            <h2 id="verification-heading">
                Verification Information
            </h2>

            <p>
                The opportunity passed the OpportunityBridge
                verification pipeline before being approved for
                automated article generation.
            </p>

            <ul class="evidence-list">
                {"".join(list_items)}
            </ul>

        </section>
    """


def build_before_apply_section():
    """
    Build the standard safety/verification checklist.
    """

    return """
        <section
            class="before-apply-section"
            aria-labelledby="before-apply-heading"
        >

            <h2 id="before-apply-heading">
                Before You Apply
            </h2>

            <ul>

                <li>
                    Check the official eligibility requirements.
                </li>

                <li>
                    Confirm the application deadline.
                </li>

                <li>
                    Review all required documents.
                </li>

                <li>
                    Confirm whether the opportunity is fully funded,
                    partially funded, paid or unpaid when that information
                    is provided by the official source.
                </li>

                <li>
                    Check the official source for the latest updates
                    before submitting an application.
                </li>

                <li>
                    Apply through the official source whenever possible.
                </li>

            </ul>

        </section>
    """


# ============================================================
# ARTICLE BUILDER
# ============================================================

def build_article(
    item,
    article_path,
    published_date,
    modified_date,
):
    """
    Generate the complete OpportunityBridge article.

    Existing features are preserved while adding:
        - verification metadata
        - category
        - location
        - deadline
        - funding information
        - eligibility information
        - application link
        - verification evidence
        - dateModified metadata
        - stronger SEO metadata
        - responsive design
        - breadcrumbs
        - Article JSON-LD
    """

    title = clean_whitespace(
        item.get("title")
    )

    source_url = get_source_url(
        item
    )

    application_url = get_application_url(
        item
    )

    publisher = get_publisher(
        item
    )

    category = get_category(
        item
    )

    location = get_location(
        item
    )

    deadline = get_deadline(
        item
    )

    description = build_description(
        item
    )

    summary = build_summary(
        item
    )

    keywords = build_keywords(
        item
    )

    slug = article_path.stem

    article_url = (
        f"{BASE_URL}/{article_path.name}"
    )

    json_ld = build_json_ld(
        title=title,
        description=description,
        article_url=article_url,
        source_url=source_url,
        application_url=application_url,
        publisher=publisher,
        category=category,
        location=location,
        deadline=deadline,
        published_date=published_date,
        modified_date=modified_date,
    )

    safe_title = escape(
        title
    )

    safe_description = escape(
        description
    )

    safe_keywords = escape(
        keywords
    )

    safe_publisher = escape(
        publisher
        or SITE_NAME
    )

    safe_category = escape_text(
        category
    )

    safe_location = escape_text(
        location
    )

    safe_deadline = escape_text(
        deadline
    )

    safe_published_date = escape_text(
        published_date
    )

    safe_modified_date = escape_text(
        modified_date
    )

    details_section = (
        build_opportunity_details(
            item
        )
    )

    application_section = (
        build_application_section(
            application_url
        )
    )

    source_section = (
        build_source_section(
            source_url,
            publisher,
        )
    )

    evidence_section = (
        build_evidence_section(
            item
        )
    )

    before_apply_section = (
        build_before_apply_section()
    )

    location_meta = ""

    if location:

        location_meta = f"""
    <meta
        name="geo.placename"
        content="{escape(location)}"
    >
        """

    deadline_meta = ""

    if deadline:

        deadline_meta = f"""
    <meta
        name="opportunity:deadline"
        content="{escape(deadline)}"
    >
        """

    application_meta = ""

    if application_url:

        application_meta = f"""
    <meta
        name="opportunity:application_url"
        content="{escape(application_url)}"
    >
        """

    source_meta = ""

    if source_url:

        source_meta = f"""
    <meta
        name="opportunity:source_url"
        content="{escape(source_url)}"
    >
        """

    return f"""<!DOCTYPE html>
<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>
        {safe_title} | OpportunityBridge
    </title>

    <meta
        name="description"
        content="{safe_description}"
    >

    <meta
        name="keywords"
        content="{safe_keywords}"
    >

    <meta
        name="author"
        content="{escape(AUTHOR_NAME)}"
    >

    <meta
        name="robots"
        content="index, follow"
    >

    <meta
        name="datePublished"
        content="{escape(published_date)}"
    >

    <meta
        name="dateModified"
        content="{escape(modified_date)}"
    >

    <meta
        name="opportunity:category"
        content="{escape(category)}"
    >

    {location_meta}

    {deadline_meta}

    {application_meta}

    {source_meta}

    <link
        rel="canonical"
        href="{escape(article_url)}"
    >

    <meta
        property="og:type"
        content="article"
    >

    <meta
        property="og:title"
        content="{safe_title} | OpportunityBridge"
    >

    <meta
        property="og:description"
        content="{safe_description}"
    >

    <meta
        property="og:url"
        content="{escape(article_url)}"
    >

    <meta
        property="og:site_name"
        content="{escape(SITE_NAME)}"
    >

    <meta
        property="article:published_time"
        content="{escape(published_date)}"
    >

    <meta
        property="article:modified_time"
        content="{escape(modified_date)}"
    >

    <meta
        property="article:section"
        content="{escape(category)}"
    >

    <meta
        name="twitter:card"
        content="summary"
    >

    <meta
        name="twitter:title"
        content="{safe_title} | OpportunityBridge"
    >

    <meta
        name="twitter:description"
        content="{safe_description}"
    >

    <script type="application/ld+json">
{json_ld}
    </script>

    <style>

        :root {{
            --navy: #0b3d91;
            --blue: #1769d1;
            --gold: #f4c542;
            --dark: #172033;
            --muted: #64748b;
            --light: #f6f8fc;
            --white: #ffffff;
            --border: #e2e8f0;
            --footer: #071f49;
            --success: #166534;
            --success-bg: #f0fdf4;
            --info-bg: #eff6ff;
        }}

        * {{
            box-sizing: border-box;
        }}

        html {{
            scroll-behavior: smooth;
        }}

        body {{
            font-family:
                Arial,
                Helvetica,
                sans-serif;

            line-height: 1.7;

            margin: 0;

            background: var(--light);

            color: var(--dark);
        }}

        a {{
            color: var(--blue);

            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        .site-header {{
            background: var(--navy);

            color: var(--white);

            padding: 16px 20px;
        }}

        .header-inner {{
            max-width: 1100px;

            margin: 0 auto;

            display: flex;

            align-items: center;

            justify-content: space-between;

            gap: 20px;
        }}

        .brand {{
            color: var(--white);

            font-size: 20px;

            font-weight: 700;
        }}

        .brand:hover {{
            text-decoration: none;
        }}

        .breadcrumb {{
            max-width: 900px;

            margin: 24px auto 0;

            padding: 0 20px;

            color: var(--muted);

            font-size: 14px;
        }}

        .breadcrumb a {{
            color: var(--blue);
        }}

        main {{
            max-width: 900px;

            margin: 28px auto 60px;

            padding: 36px;

            background: var(--white);

            border: 1px solid var(--border);

            border-radius: 14px;

            box-shadow:
                0 8px 30px
                rgba(15, 23, 42, 0.05);
        }}

        article {{
            width: 100%;
        }}

        h1 {{
            line-height: 1.25;

            font-size: clamp(
                30px,
                5vw,
                44px
            );

            margin-top: 0;

            margin-bottom: 18px;

            color: var(--dark);
        }}

        h2 {{
            margin-top: 36px;

            color: var(--navy);

            line-height: 1.3;
        }}

        p {{
            margin: 0 0 18px;
        }}

        .meta {{
            color: var(--muted);

            font-size: 14px;

            margin-bottom: 26px;
        }}

        .category-badge {{
            display: inline-block;

            background: #e8f0ff;

            color: var(--navy);

            border-radius: 999px;

            padding: 6px 12px;

            font-size: 13px;

            font-weight: 700;

            margin-bottom: 18px;
        }}

        .summary {{
            font-size: 18px;

            line-height: 1.8;

            color: #334155;
        }}

        .notice {{
            padding: 18px 20px;

            margin: 28px 0;

            border-left: 4px solid var(--blue);

            background: var(--info-bg);

            border-radius: 8px;
        }}

        .opportunity-details {{
            margin: 30px 0;

            padding: 24px;

            background: #f8fafc;

            border: 1px solid var(--border);

            border-radius: 12px;
        }}

        .opportunity-details h2 {{
            margin-top: 0;
        }}

        .details-grid {{
            display: grid;

            grid-template-columns:
                repeat(
                    auto-fit,
                    minmax(
                        210px,
                        1fr
                    )
                );

            gap: 14px;
        }}

        .meta-item {{
            padding: 15px;

            background: var(--white);

            border: 1px solid var(--border);

            border-radius: 9px;

            min-height: 76px;
        }}

        .meta-label {{
            display: block;

            color: var(--muted);

            font-size: 12px;

            text-transform: uppercase;

            letter-spacing: 0.04em;

            margin-bottom: 4px;
        }}

        .application-section {{
            margin: 30px 0;

            padding: 24px;

            background: var(--success-bg);

            border: 1px solid #bbf7d0;

            border-radius: 12px;
        }}

        .application-section h2 {{
            color: var(--success);

            margin-top: 0;
        }}

        .apply-button,
        .source-button {{
            display: inline-block;

            padding: 11px 18px;

            border-radius: 8px;

            font-weight: 700;

            text-decoration: none;
        }}

        .apply-button {{
            background: var(--navy);

            color: var(--white);
        }}

        .apply-button:hover {{
            background: var(--blue);

            text-decoration: none;
        }}

        .source-button {{
            background: #e8f0ff;

            color: var(--navy);

            border: 1px solid #cbdaf8;
        }}

        .source-button:hover {{
            background: #dbe8ff;

            text-decoration: none;
        }}

        .source-section {{
            margin-top: 34px;

            padding-top: 20px;

            border-top: 1px solid var(--border);
        }}

        .verification-section {{
            margin-top: 34px;

            padding: 22px;

            background: #f8fafc;

            border: 1px solid var(--border);

            border-radius: 12px;
        }}

        .verification-section h2 {{
            margin-top: 0;
        }}

        .evidence-list {{
            padding-left: 22px;

            margin-bottom: 0;
        }}

        .before-apply-section {{
            margin-top: 34px;

            padding-top: 20px;

            border-top: 1px solid var(--border);
        }}

        .before-apply-section li {{
            margin-bottom: 10px;
        }}

        .footer {{
            background: var(--footer);

            color: var(--white);

            text-align: center;

            padding: 30px 20px;
        }}

        .footer a {{
            color: var(--white);
        }}

        @media (max-width: 700px) {{

            .site-header {{
                padding: 14px 16px;
            }}

            .header-inner {{
                display: block;
            }}

            main {{
                margin: 18px 12px 40px;

                padding: 22px 18px;

                border-radius: 10px;
            }}

            .breadcrumb {{
                padding: 0 14px;

                margin-top: 16px;
            }}

            h1 {{
                font-size: 30px;
            }}

            .summary {{
                font-size: 17px;
            }}

            .details-grid {{
                grid-template-columns: 1fr;
            }}

            .application-section,
            .opportunity-details,
            .verification-section {{
                padding: 18px;
            }}

            .apply-button,
            .source-button {{
                display: block;

                width: 100%;

                text-align: center;
            }}
        }}

    </style>

</head>

<body>

<header class="site-header">

    <div class="header-inner">

        <a
            class="brand"
            href="{BASE_URL}/"
        >
            OpportunityBridge
        </a>

    </div>

</header>


<nav
    class="breadcrumb"
    aria-label="Breadcrumb"
>

    <a href="{BASE_URL}/">
        Home
    </a>

    <span aria-hidden="true">
        &nbsp;›&nbsp;
    </span>

    <a href="{BASE_URL}/opportunities.html">
        Opportunities
    </a>

    <span aria-hidden="true">
        &nbsp;›&nbsp;
    </span>

    <span>
        {safe_title}
    </span>

</nav>


<main>

    <article>

        <span class="category-badge">
            {safe_category}
        </span>

        <h1>
            {safe_title}
        </h1>

        <p class="meta">

            Published:
            <strong>
                {safe_published_date}
            </strong>

            <br>

            Updated:
            <strong>
                {safe_modified_date}
            </strong>

            <br>

            Source:
            <strong>
                {safe_publisher}
            </strong>

            {"<br>Location: <strong>" + safe_location + "</strong>" if location else ""}

            {"<br>Deadline: <strong>" + safe_deadline + "</strong>" if deadline else ""}

        </p>


        <p class="summary">
            {escape_text(summary)}
        </p>


        <div class="notice">

            <strong>
                Important:
            </strong>

            OpportunityBridge provides information about
            opportunities and does not replace the official
            provider's application instructions.

            Always confirm eligibility, deadline, funding details,
            application requirements and any changes on the
            official source before applying.

        </div>


        {details_section}


        {application_section}


        <section
            aria-labelledby="about-opportunity-heading"
        >

            <h2 id="about-opportunity-heading">
                About This Opportunity
            </h2>

            <p>
                This opportunity was discovered and processed
                through the OpportunityBridge opportunity discovery,
                verification and approval system.
            </p>

            <p>
                The information shown on this page is based on the
                approved opportunity record available to the
                OpportunityBridge automation pipeline. Availability,
                deadlines, eligibility requirements and application
                procedures can change, so readers should always
                confirm the latest information directly with the
                official source.
            </p>

        </section>


        {evidence_section}


        {source_section}


        {before_apply_section}


        <section
            aria-labelledby="related-guidance-heading"
        >

            <h2 id="related-guidance-heading">
                OpportunityBridge Guidance
            </h2>

            <p>
                Explore more opportunities and practical resources
                through OpportunityBridge.
            </p>

            <ul>

                <li>
                    <a href="{BASE_URL}/scholarships.html">
                        Scholarships
                    </a>
                </li>

                <li>
                    <a href="{BASE_URL}/jobs.html">
                        Jobs
                    </a>
                </li>

                <li>
                    <a href="{BASE_URL}/internships.html">
                        Internships
                    </a>
                </li>

                <li>
                    <a href="{BASE_URL}/courses.html">
                        Online Courses
                    </a>
                </li>

                <li>
                    <a href="{BASE_URL}/opportunities.html">
                        All Opportunities
                    </a>
                </li>

            </ul>

        </section>


    </article>

</main>


<footer class="footer">

    <p>
        © {datetime.now(timezone.utc).year}
        OpportunityBridge.
        All rights reserved.
    </p>

    <p>

        <a href="{BASE_URL}/about.html">
            About
        </a>

        &nbsp;|&nbsp;

        <a href="{BASE_URL}/contact.html">
            Contact
        </a>

        &nbsp;|&nbsp;

        <a href="{BASE_URL}/privacy.html">
            Privacy
        </a>

        &nbsp;|&nbsp;

        <a href="{BASE_URL}/disclaimer.html">
            Disclaimer
        </a>

    </p>

</footer>


</body>

</html>
"""


# ============================================================
# EXISTING ARTICLE UPDATE
# ============================================================

def update_existing_article(
    existing,
    item,
    modified_date,
):
    """
    Update an existing article without creating a duplicate.

    The previous generator attempted to update dateModified,
    but generated pages did not contain the meta tag. This
    version explicitly supports both the meta tag and JSON-LD.
    """

    try:

        content = existing.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        safe_modified = escape(
            modified_date
        )

        # ----------------------------------------------------
        # Update meta dateModified.
        # ----------------------------------------------------

        date_modified_pattern = (
            r'(<meta\s+'
            r'name=["\']dateModified["\']\s+'
            r'content=["\'])'
            r'[^"\']*'
            r'(["\'])'
        )

        if re.search(
            date_modified_pattern,
            content,
            flags=re.IGNORECASE,
        ):

            content = re.sub(
                date_modified_pattern,
                rf'\g<1>{safe_modified}\g<2>',
                content,
                flags=re.IGNORECASE,
            )

        else:

            content = content.replace(
                '<meta name="robots" content="index, follow">',
                (
                    '<meta name="robots" content="index, follow">\n\n'
                    f'    <meta name="dateModified" '
                    f'content="{safe_modified}">'
                ),
                1,
            )

        # ----------------------------------------------------
        # Update property article:modified_time.
        # ----------------------------------------------------

        modified_time_pattern = (
            r'(<meta\s+'
            r'property=["\']article:modified_time["\']\s+'
            r'content=["\'])'
            r'[^"\']*'
            r'(["\'])'
        )

        if re.search(
            modified_time_pattern,
            content,
            flags=re.IGNORECASE,
        ):

            content = re.sub(
                modified_time_pattern,
                rf'\g<1>{safe_modified}\g<2>',
                content,
                flags=re.IGNORECASE,
            )

        else:

            marker = (
                '<meta\n'
                '        property="article:published_time"'
            )

            if marker in content:

                content = content.replace(
                    marker,
                    (
                        '<meta\n'
                        '        property="article:modified_time"\n'
                        f'        content="{safe_modified}"\n'
                        '    >\n\n'
                        '    '
                        + marker
                    ),
                    1,
                )

        # ----------------------------------------------------
        # Update JSON-LD dateModified.
        # ----------------------------------------------------

        json_ld_pattern = (
            r'("dateModified"\s*:\s*)'
            r'"[^"]*"'
        )

        content = re.sub(
            json_ld_pattern,
            (
                r'\g<1>'
                f'"{json.dumps(modified_date)[1:-1]}"'
            ),
            content,
            count=1,
        )

        existing.write_text(
            content,
            encoding="utf-8"
        )

        return True

    except Exception as error:

        print(
            "Warning: Could not update existing article "
            f"{existing.name}: {error}"
        )

        return False


# ============================================================
# PROCESS ONE APPROVED OPPORTUNITY
# ============================================================

def process_item(item):
    """
    Process one approved opportunity.

    Returns:
        (Path or None, message)
    """

    if not isinstance(
        item,
        dict
    ):

        return (
            None,
            "Skipped: opportunity item is not an object"
        )

    title = clean_whitespace(
        item.get("title")
    )

    source_url = get_source_url(
        item
    )

    if not title:

        return (
            None,
            "Skipped: missing title"
        )

    if not valid_url(
        source_url
    ):

        return (
            None,
            f"Skipped: invalid source URL for '{title}'"
        )

    # --------------------------------------------------------
    # IMPORTANT:
    # Only approved records should reach this generator.
    # Add a defensive check so a wrongly structured record
    # does not accidentally become an article.
    # --------------------------------------------------------

    approval_status = clean(
        item.get("approval_status")
    ).lower()

    approved_for_article = item.get(
        "approved_for_article_generation"
    )

    if (
        approval_status
        and approval_status != "approved"
    ):

        return (
            None,
            f"Skipped: not approved for article generation: '{title}'"
        )

    if (
        approved_for_article is False
    ):

        return (
            None,
            f"Skipped: article generation disabled: '{title}'"
        )

    # --------------------------------------------------------
    # Check source URL before creating a new article.
    # --------------------------------------------------------

    existing = find_existing_article(
        source_url
    )

    now = datetime.now(
        timezone.utc
    ).isoformat()

    if existing:

        updated = update_existing_article(
            existing=existing,
            item=item,
            modified_date=now,
        )

        if updated:

            return (
                existing,
                f"Updated existing article: {existing.name}"
            )

        return (
            existing,
            f"Existing article found: {existing.name}"
        )

    # --------------------------------------------------------
    # Create new article path.
    # --------------------------------------------------------

    article_path = unique_article_path(
        title,
        source_url,
    )

    # --------------------------------------------------------
    # Published date.
    # --------------------------------------------------------

    published_date = clean(
        item.get("published_at")
        or item.get("published")
        or item.get("date")
        or item.get("discovered_at")
    )

    if not published_date:

        published_date = now

    modified_date = now

    # --------------------------------------------------------
    # Generate complete HTML.
    # --------------------------------------------------------

    article_html = build_article(
        item=item,
        article_path=article_path,
        published_date=published_date,
        modified_date=modified_date,
    )

    article_path.write_text(
        article_html,
        encoding="utf-8"
    )

    return (
        article_path,
        f"Created article: {article_path.name}"
    )


# ============================================================
# DUPLICATE APPROVED ITEM DETECTION
# ============================================================

def deduplicate_approved_items(items):
    """
    Prevent the same approved opportunity from being processed
    multiple times in one workflow run.

    Deduplication uses source URL first and title second.
    """

    unique_items = []

    seen_sources = set()

    seen_titles = set()

    duplicates = 0

    for item in items:

        if not isinstance(
            item,
            dict
        ):

            duplicates += 1

            continue

        source_url = get_source_url(
            item
        )

        title = clean_whitespace(
            item.get("title")
        ).lower()

        source_key = (
            source_url
            .rstrip("/")
            .lower()
            if source_url
            else ""
        )

        # Prefer source URL as the strongest identifier.
        if source_key:

            if source_key in seen_sources:

                duplicates += 1

                continue

            seen_sources.add(
                source_key
            )

        elif title:

            if title in seen_titles:

                duplicates += 1

                continue

        if title:

            seen_titles.add(
                title
            )

        unique_items.append(
            item
        )

    return (
        unique_items,
        duplicates,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=" * 70
    )

    print(
        "OPPORTUNITYBRIDGE ARTICLE GENERATOR v3.0"
    )

    print(
        "=" * 70
    )

    print(
        "Purpose:"
    )

    print(
        "Generate complete SEO-friendly articles from approved "
        "opportunities without creating duplicate pages."
    )

    print(
        "=" * 70
    )

    # --------------------------------------------------------
    # Input validation.
    # --------------------------------------------------------

    if not INPUT.exists():

        raise SystemExit(
            "ERROR: approved_opportunities.json was not found."
        )

    try:

        data = json.loads(
            INPUT.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:

        raise SystemExit(
            "ERROR: Could not read approved opportunities: "
            f"{error}"
        )

    # --------------------------------------------------------
    # Existing approval engine structure.
    # --------------------------------------------------------

    items = data.get(
        "approved_items",
        []
    )

    if not isinstance(
        items,
        list
    ):

        raise SystemExit(
            "ERROR: approved_items is not a list."
        )

    print(
        f"Approved records found: {len(items)}"
    )

    # --------------------------------------------------------
    # Deduplicate current input.
    # --------------------------------------------------------

    unique_items, duplicate_count = (
        deduplicate_approved_items(
            items
        )
    )

    print(
        f"Duplicate records skipped in input: "
        f"{duplicate_count}"
    )

    print(
        f"Unique approved records to process: "
        f"{len(unique_items)}"
    )

    print()

    # --------------------------------------------------------
    # Counters.
    # --------------------------------------------------------

    created = 0

    updated = 0

    skipped = 0

    processed = 0

    # --------------------------------------------------------
    # Process each approved opportunity.
    # --------------------------------------------------------

    for index, item in enumerate(
        unique_items,
        start=1
    ):

        title = clean_whitespace(
            item.get("title")
        )

        print(
            "-" * 70
        )

        print(
            f"[{index}/{len(unique_items)}]"
        )

        print(
            f"Title: {title}"
        )

        print(
            f"Category: "
            f"{get_category(item)}"
        )

        print(
            f"Location: "
            f"{get_location(item) or 'Not provided'}"
        )

        print(
            f"Deadline: "
            f"{get_deadline(item) or 'Not provided'}"
        )

        print(
            f"Source: "
            f"{get_source_url(item)}"
        )

        print(
            f"Application: "
            f"{get_application_url(item) or 'Not detected'}"
        )

        path, message = process_item(
            item
        )

        print(
            message
        )

        # ----------------------------------------------------
        # Counters.
        # ----------------------------------------------------

        if path is None:

            skipped += 1

        elif (
            "Updated existing"
            in message
        ):

            updated += 1

            processed += 1

        elif (
            "Existing article found"
            in message
        ):

            updated += 1

            processed += 1

        elif (
            "Created article"
            in message
        ):

            created += 1

            processed += 1

        else:

            processed += 1

    # --------------------------------------------------------
    # Final report.
    # --------------------------------------------------------

    print()

    print(
        "=" * 70
    )

    print(
        "ARTICLE GENERATION COMPLETE"
    )

    print(
        "=" * 70
    )

    print(
        f"Approved records received: "
        f"{len(items)}"
    )

    print(
        f"Duplicate input records skipped: "
        f"{duplicate_count}"
    )

    print(
        f"Unique records processed: "
        f"{len(unique_items)}"
    )

    print(
        f"New articles: "
        f"{created}"
    )

    print(
        f"Updated articles: "
        f"{updated}"
    )

    print(
        f"Skipped: "
        f"{skipped}"
    )

    print(
        f"Successfully processed: "
        f"{processed}"
    )

    print(
        "-" * 70
    )

    print(
        "Generated articles are saved in the repository root."
    )

    print(
        "The next automation step should update index.html "
        "with approved article cards."
    )

    print(
        "=" * 70
    )

    print(
        "OPPORTUNITYBRIDGE ARTICLE GENERATOR "
        "v3.0 COMPLETE"
    )


if __name__ == "__main__":

    main()
