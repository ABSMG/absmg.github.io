from pathlib import Path
from datetime import datetime, timezone
from html import escape
import json
import re


# ============================================================
# OPPORTUNITYBRIDGE HOMEPAGE AUTO-UPDATER
# ============================================================
#
# Purpose:
#   Read approved opportunities and automatically publish
#   the latest approved opportunities into index.html.
#
# Required files:
#   data/approved_opportunities.json
#   index.html
#
# The script only replaces content between:
#
#   <!-- OPPORTUNITYBRIDGE_AUTO_OPPORTUNITIES_START -->
#   <!-- OPPORTUNITYBRIDGE_AUTO_OPPORTUNITIES_END -->
#
# Everything outside those markers is preserved.
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

START_MARKER = (
    "<!-- OPPORTUNITYBRIDGE_AUTO_OPPORTUNITIES_START -->"
)

END_MARKER = (
    "<!-- OPPORTUNITYBRIDGE_AUTO_OPPORTUNITIES_END -->"
)


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):
    """
    Convert any value to safe plain text.
    """
    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        return ""

    return str(value).strip()


def first_value(item, *keys):
    """
    Return the first non-empty value from a list of possible keys.
    """
    for key in keys:
        value = item.get(key)

        if value is None:
            continue

        value = clean_text(value)

        if value:
            return value

    return ""


def normalize_url(url):
    """
    Normalize a URL for comparison.
    """
    url = clean_text(url)

    if not url:
        return ""

    return url.rstrip("/").lower()


def is_http_url(url):
    """
    Allow only normal HTTP/HTTPS URLs.
    """
    url = clean_text(url).lower()

    return (
        url.startswith("https://")
        or url.startswith("http://")
    )


def safe_html(value):
    """
    Escape content before placing it into HTML.
    """
    return escape(
        clean_text(value),
        quote=True
    )


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

    # ISO 8601
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

    # Common date formats
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
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


def get_sort_date(item):
    """
    Find the most useful date for sorting opportunities.
    """

    date_keys = [
        "published_at",
        "published",
        "publication_date",
        "date_published",
        "verified_at",
        "approved_at",
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


def detect_category(item):
    """
    Determine a useful homepage category.
    """

    explicit = first_value(
        item,
        "opportunity_type",
        "category",
        "type",
        "category_name",
    )

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
            explicit,
        ]
    ).lower()

    # Explicit category gets priority.
    if explicit:

        normalized = explicit.lower().strip()

        aliases = {
            "scholarship": "scholarships",
            "job": "jobs",
            "internship": "internships",
            "course": "courses",
            "fellowship": "fellowships",
            "grant": "grants",
            "competition": "competitions",
            "research": "research",
            "training": "training",
            "volunteer": "volunteer",
            "remote job": "remote-jobs",
            "remote jobs": "remote-jobs",
            "study abroad": "study-abroad",
        }

        if normalized in aliases:
            return aliases[normalized]

        if normalized in CATEGORY_RULES:
            return normalized

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
# ARTICLE URL RESOLUTION
# ============================================================

def get_article_url(item):
    """
    Find the generated article URL.

    Preferred:
        article_url
        article
        article_path
        article_filename

    If those are not available, use source/title information
    to locate an existing HTML article where possible.
    """

    direct_url = first_value(
        item,
        "article_url",
        "article",
        "article_path",
        "article_filename",
    )

    if direct_url:

        direct_url = direct_url.strip()

        # Absolute site URL
        if direct_url.startswith(
            "https://absmg.github.io/"
        ):

            direct_url = direct_url.replace(
                "https://absmg.github.io/",
                "",
                1
            )

        # Remove leading slash
        direct_url = direct_url.lstrip("/")

        # Do not allow external article URL
        if (
            direct_url
            and not direct_url.startswith("http://")
            and not direct_url.startswith("https://")
        ):

            article_path = ROOT / direct_url

            if article_path.exists():
                return direct_url

    # Try source_url -> existing HTML
    source_url = first_value(
        item,
        "source_url",
        "official_url",
        "url",
        "link",
    )

    source_url_normalized = normalize_url(
        source_url
    )

    if source_url_normalized:

        for html_file in ROOT.glob("*.html"):

            try:

                content = html_file.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )

            except Exception:
                continue

            # Search for the source URL inside the article.
            if source_url_normalized in normalize_url(
                content
            ):

                return html_file.name

    return ""


# ============================================================
# DESCRIPTION
# ============================================================

def build_description(item):
    """
    Build a concise homepage description.
    """

    description = first_value(
        item,
        "short_description",
        "description",
        "summary",
        "excerpt",
    )

    if not description:

        title = first_value(
            item,
            "title",
            "name",
        )

        description = (
            f"Explore this {detect_category(item)} "
            f"and check the official source for "
            f"eligibility, deadline and application details."
        )

    # Normalize whitespace
    description = re.sub(
        r"\s+",
        " ",
        description
    ).strip()

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
    """

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

    if country and region:

        if country.lower() not in region.lower():

            return f"{country} • {region}"

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
        "deadline",
        "application_deadline",
        "closing_date",
        "close_date",
        "deadline_date",
    )

    if not deadline:
        return ""

    return deadline


# ============================================================
# SOURCE / PUBLISHER
# ============================================================

def get_source_name(item):
    """
    Get the source/publisher name.
    """

    return first_value(
        item,
        "publisher",
        "publisher_name",
        "source_name",
        "organization",
        "provider",
        "source",
    )


# ============================================================
# DEDUPLICATION
# ============================================================

def opportunity_identity(item):
    """
    Generate a stable identity for deduplication.
    """

    source_url = normalize_url(
        first_value(
            item,
            "official_url",
            "source_url",
            "url",
            "link",
        )
    )

    if source_url:
        return "url:" + source_url

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

    return "title:" + title


def deduplicate_opportunities(items):
    """
    Remove duplicate opportunities while preserving
    the first/best occurrence.
    """

    seen = set()
    result = []

    for item in items:

        if not isinstance(item, dict):
            continue

        identity = opportunity_identity(
            item
        )

        if not identity:
            continue

        if identity in seen:
            continue

        seen.add(identity)
        result.append(item)

    return result


# ============================================================
# QUALITY CHECK
# ============================================================

def is_usable_opportunity(item):
    """
    Basic safety/quality gate for homepage publishing.

    Only approved items should normally reach this script,
    but this second gate prevents obviously invalid records.
    """

    if not isinstance(item, dict):
        return False

    title = first_value(
        item,
        "title",
        "name",
    )

    if not title:
        return False

    # Respect explicit approval status.
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

    # Article must be resolvable later.
    return True


# ============================================================
# LOAD APPROVED OPPORTUNITIES
# ============================================================

def load_approved_opportunities():
    """
    Load approved opportunities from JSON.
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

    # Supported structures:
    #
    # 1. list
    # 2. {"opportunities": [...]}
    # 3. {"approved_opportunities": [...]}
    # 4. {"items": [...]}

    if isinstance(data, list):

        return data

    if isinstance(data, dict):

        for key in [
            "opportunities",
            "approved_opportunities",
            "items",
            "data",
        ]:

            value = data.get(key)

            if isinstance(value, list):
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
    """

    prepared = []

    for item in items:

        if not is_usable_opportunity(item):
            continue

        title = first_value(
            item,
            "title",
            "name",
        )

        article_url = get_article_url(
            item
        )

        # Do not create broken homepage links.
        if not article_url:
            print(
                "SKIP: No generated article found for:"
                f" {title}"
            )
            continue

        article_path = ROOT / article_url

        if not article_path.exists():

            print(
                "SKIP: Article file does not exist:"
                f" {article_url}"
            )

            continue

        category = detect_category(
            item
        )

        category_label = CATEGORY_LABELS.get(
            category,
            "Opportunity"
        )

        description = build_description(
            item
        )

        location = get_location(
            item
        )

        deadline = get_deadline(
            item
        )

        source_name = get_source_name(
            item
        )

        official_url = first_value(
            item,
            "official_url",
            "source_url",
            "url",
            "link",
        )

        prepared.append(
            {
                "title": title,
                "article_url": article_url,
                "category": category,
                "category_label": category_label,
                "description": description,
                "location": location,
                "deadline": deadline,
                "source_name": source_name,
                "official_url": official_url,
                "sort_date": get_sort_date(item),
            }
        )

    # Newest first
    prepared.sort(
        key=lambda x: x["sort_date"],
        reverse=True
    )

    # Deduplicate after preparation.
    unique = []

    seen = set()

    for item in prepared:

        identity = (
            normalize_url(
                item["article_url"]
            )
            or item["title"].lower()
        )

        if identity in seen:
            continue

        seen.add(identity)
        unique.append(item)

    return unique[
        :MAX_HOMEPAGE_OPPORTUNITIES
    ]


# ============================================================
# HTML CARD
# ============================================================

def build_card(item):
    """
    Generate one homepage opportunity card.
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

    metadata_parts = []

    if category_label:

        metadata_parts.append(
            f'<span class="opportunity-badge">'
            f'{category_label}'
            f'</span>'
        )

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
            + "".join(metadata_parts)
            + '</div>'
        )

    deadline_html = ""

    if deadline:

        deadline_html = (
            '<p class="opportunity-deadline">'
            '<strong>Deadline:</strong> '
            f'{deadline}'
            '</p>'
        )

    source_html = ""

    if source_name:

        source_html = (
            '<p class="opportunity-source">'
            '<strong>Source:</strong> '
            f'{source_name}'
            '</p>'
        )

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

          <a
            href="{article_url}"
            class="card-link"
            aria-label="Read {title}">

            Read Opportunity →

          </a>

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
                build_card(item)
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

def update_index_html(section_html):
    """
    Replace the automated homepage block.

    If markers do not exist, insert the section before
    the main Explore Opportunities section.
    """

    if not INDEX_FILE.exists():

        raise FileNotFoundError(
            f"Homepage not found: {INDEX_FILE}"
        )

    html = INDEX_FILE.read_text(
        encoding="utf-8"
    )

    start_position = html.find(
        START_MARKER
    )

    end_position = html.find(
        END_MARKER
    )

    # ========================================================
    # Existing markers
    # ========================================================

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

        return new_html, "replaced"

    # ========================================================
    # Missing markers
    # ========================================================

    # Insert immediately before the first Explore
    # Opportunities section.
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
            + "\n"
        )

        new_html = (
            html[:match.start()]
            + insertion
            + html[match.start():]
        )

        return new_html, "inserted"

    # ========================================================
    # Fallback: before </main>
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
            + "\n"
        )

        new_html = (
            html[:main_end]
            + insertion
            + html[main_end:]
        )

        return new_html, "inserted-before-main-close"

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
    Add CSS required by automatically generated opportunity cards.

    The CSS is inserted before </style> only once.
    """

    if (
        AUTO_CSS_MARKER_START in html
        and AUTO_CSS_MARKER_END in html
    ):
        return html, False

    style_end = html.lower().rfind(
        "</style>"
    )

    if style_end == -1:
        return html, False

    new_html = (
        html[:style_end]
        + "\n\n"
        + AUTO_CSS
        + "\n\n"
        + html[style_end:]
    )

    return new_html, True


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=============================================="
    )

    print(
        "OpportunityBridge Homepage Updater"
    )

    print(
        "=============================================="
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

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    approved = load_approved_opportunities()

    print(
        f"Approved records loaded: {len(approved)}"
    )

    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

    approved = deduplicate_opportunities(
        approved
    )

    print(
        f"After deduplication: {len(approved)}"
    )

    # --------------------------------------------------------
    # Prepare
    # --------------------------------------------------------

    items = prepare_homepage_items(
        approved
    )

    print(
        "Valid homepage opportunities: "
        f"{len(items)}"
    )

    # --------------------------------------------------------
    # Display selected items
    # --------------------------------------------------------

    for index, item in enumerate(
        items,
        start=1
    ):

        print(
            f"{index}. "
            f"{item['title']} "
            f"-> "
            f"{item['article_url']}"
        )

    print()

    # --------------------------------------------------------
    # Build section
    # --------------------------------------------------------

    section_html = build_homepage_section(
        items
    )

    # --------------------------------------------------------
    # Read homepage
    # --------------------------------------------------------

    original_html = INDEX_FILE.read_text(
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # Add CSS
    # --------------------------------------------------------

    html_with_css, css_added = ensure_css(
        original_html
    )

    if css_added:

        print(
            "Added automatic opportunity card CSS."
        )

    # --------------------------------------------------------
    # Update homepage section
    # --------------------------------------------------------

    updated_html, action = update_index_html(
        section_html
    )

    # IMPORTANT:
    #
    # update_index_html() was based on original_html.
    # If CSS was added, run the section update against
    # the CSS-updated document so we do not lose the CSS.
    #

    if css_added:

        updated_html, action = update_index_html(
            section_html
        )

        # Re-apply CSS if update_index_html used
        # the original document.
        updated_html, css_was_present = ensure_css(
            updated_html
        )

    # --------------------------------------------------------
    # Avoid unnecessary write
    # --------------------------------------------------------

    if updated_html == original_html:

        print(
            "Homepage already up to date."
        )

        print(
            "No file changes required."
        )

        print(
            "OPPORTUNITYBRIDGE HOMEPAGE UPDATE COMPLETE"
        )

        return

    # --------------------------------------------------------
    # Write
    # --------------------------------------------------------

    INDEX_FILE.write_text(
        updated_html,
        encoding="utf-8"
    )

    print(
        f"Homepage update action: {action}"
    )

    print(
        f"Published cards: {len(items)}"
    )

    print(
        "index.html updated successfully."
    )

    print(
        "OPPORTUNITYBRIDGE HOMEPAGE UPDATE COMPLETE"
    )


if __name__ == "__main__":
    main()
