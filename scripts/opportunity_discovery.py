from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import re
import time
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "discovered_opportunities.json"


# ============================================================
# GOOGLE NEWS FEEDS
# ============================================================

FEEDS = {
    "Google News - Scholarships":
        "https://news.google.com/rss/search?q=scholarships+Africa+students&hl=en&gl=US&ceid=US:en",

    "Google News - Jobs Tanzania":
        "https://news.google.com/rss/search?q=jobs+Tanzania&hl=en&gl=US&ceid=US:en",

    "Google News - Internships Africa":
        "https://news.google.com/rss/search?q=internships+Africa+students&hl=en&gl=US&ceid=US:en",

    "Google News - Free Courses":
        "https://news.google.com/rss/search?q=free+online+courses+students&hl=en&gl=US&ceid=US:en",
}


# ============================================================
# DISCOVERY KEYWORDS
# ============================================================

KEYWORDS = [
    "scholarship",
    "scholarships",
    "fully funded",
    "fellowship",
    "grant",
    "internship",
    "internships",
    "job",
    "jobs",
    "career",
    "course",
    "courses",
    "training",
    "students",
    "africa",
    "tanzania",
    "international students",
]


# ============================================================
# DISCOVERY SETTINGS
# ============================================================

FEED_TIMEOUT = 20
ARTICLE_TIMEOUT = 15

FEED_RETRIES = 3
ARTICLE_RETRIES = 2

MAX_DISCOVERIES = 300

USER_AGENT = (
    "OpportunityBridge Opportunity Discovery Bot/2.0 "
    "(+https://absmg.github.io/OpportunityBridge/)"
)


# ============================================================
# URL HELPERS
# ============================================================

def normalize_url(url):
    """
    Normalize a URL without changing its destination.

    This is used mainly for deduplication and comparison.
    """

    if not url:
        return ""

    url = str(url).strip()

    if not url:
        return ""

    # Remove surrounding whitespace and quotes.
    url = url.strip(
        "\"'<> "
    )

    # Decode HTML entities that sometimes appear in feeds.
    url = (
        url
        .replace("&amp;", "&")
        .replace("&quot;", "\"")
        .replace("&#39;", "'")
    )

    # Ensure a valid scheme.
    if url.startswith("//"):
        url = "https:" + url

    if not re.match(
        r"^https?://",
        url,
        re.IGNORECASE
    ):
        return url

    try:

        parsed = urllib.parse.urlsplit(
            url
        )

        scheme = parsed.scheme.lower()
        hostname = (
            parsed.hostname.lower()
            if parsed.hostname
            else ""
        )

        if not hostname:
            return url

        # Preserve explicit port when present.
        netloc = hostname

        try:

            port = parsed.port

            if port:
                default_port = (
                    443
                    if scheme == "https"
                    else 80
                )

                if port != default_port:
                    netloc = (
                        f"{hostname}:{port}"
                    )

        except Exception:
            pass

        path = parsed.path or "/"

        # Remove repeated trailing slashes.
        if path != "/":
            path = path.rstrip("/")

        # Remove common tracking parameters.
        tracking_parameters = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "utm_id",
            "gclid",
            "fbclid",
            "mc_cid",
            "mc_eid",
            "ref",
            "referrer",
        }

        query_pairs = []

        for key, value in urllib.parse.parse_qsl(
            parsed.query,
            keep_blank_values=True
        ):

            if key.lower() in tracking_parameters:
                continue

            query_pairs.append(
                (
                    key,
                    value
                )
            )

        query = urllib.parse.urlencode(
            query_pairs,
            doseq=True
        )

        normalized = urllib.parse.urlunsplit(
            (
                scheme,
                netloc,
                path,
                query,
                "",
            )
        )

        return normalized

    except Exception:

        return url


def is_http_url(url):
    """
    Return True only for HTTP/HTTPS URLs.
    """

    if not url:
        return False

    try:

        parsed = urllib.parse.urlparse(
            url
        )

        return (
            parsed.scheme.lower()
            in {
                "http",
                "https",
            }
            and bool(parsed.netloc)
        )

    except Exception:

        return False


def is_google_news_url(url):
    """
    Detect Google News URLs.

    Google News URLs are useful as a fallback, but the system
    should prefer the resolved publisher/article URL whenever
    possible.
    """

    if not url:
        return False

    try:

        hostname = (
            urllib.parse.urlparse(
                url
            ).hostname
            or ""
        ).lower()

        return (
            hostname == "news.google.com"
            or hostname.endswith(
                ".news.google.com"
            )
        )

    except Exception:

        return False


def looks_like_homepage(url):
    """
    Detect obvious publisher homepages.

    This does NOT reject the URL completely because some valid
    opportunities can genuinely be hosted on a homepage. It is
    mainly used to prefer an article URL over a publisher root.
    """

    if not url:
        return True

    try:

        parsed = urllib.parse.urlparse(
            url
        )

        path = (
            parsed.path
            or ""
        ).strip("/")

        return (
            bool(parsed.netloc)
            and path == ""
            and not parsed.query
        )

    except Exception:

        return False


def choose_best_url(
    google_news_url="",
    resolved_url="",
    publisher_url="",
):
    """
    Select the best URL for verification.

    Priority:

    1. Resolved article URL
    2. Google News URL as fallback

    Publisher homepage is deliberately NOT used as the
    primary source URL because that was one of the causes
    of verification failures.
    """

    candidates = [
        resolved_url,
        google_news_url,
        publisher_url,
    ]

    # Prefer resolved non-Google article URLs.
    for candidate in candidates:

        normalized = normalize_url(
            candidate
        )

        if not is_http_url(
            normalized
        ):
            continue

        if is_google_news_url(
            normalized
        ):
            continue

        if looks_like_homepage(
            normalized
        ):
            continue

        return normalized

    # If the resolved URL is a homepage but is the only
    # usable publisher URL, keep it as a secondary fallback.
    if is_http_url(
        resolved_url
    ):

        return normalize_url(
            resolved_url
        )

    # Google News is still better than losing the discovery.
    if is_http_url(
        google_news_url
    ):

        return normalize_url(
            google_news_url
        )

    if is_http_url(
        publisher_url
    ):

        return normalize_url(
            publisher_url
        )

    return ""


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = re.sub(
        r"<[^>]+>",
        " ",
        str(text)
    )

    text = (
        text
        .replace("&amp;", "&")
        .replace("&nbsp;", " ")
        .replace("&quot;", "\"")
        .replace("&#39;", "'")
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def parse_date(value):
    if not value:
        return ""

    try:

        parsed = parsedate_to_datetime(
            value
        )

        if parsed.tzinfo is None:

            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        ).isoformat()

    except Exception:

        return value


# ============================================================
# HTTP HELPERS
# ============================================================

def build_request(url):
    return urllib.request.Request(
        url,
        headers={
            "User-Agent":
                USER_AGENT,

            "Accept":
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8",

            "Accept-Language":
                "en-US,en;q=0.9",
        },
    )


def fetch_bytes(
    url,
    timeout,
    retries,
):
    """
    Fetch bytes with retries.

    Returns:
        (content, final_url, error_message)
    """

    last_error = ""

    for attempt in range(
        1,
        retries + 1
    ):

        try:

            request = build_request(
                url
            )

            with urllib.request.urlopen(
                request,
                timeout=timeout
            ) as response:

                content = response.read()

                final_url = (
                    response.geturl()
                    or url
                )

                return (
                    content,
                    normalize_url(
                        final_url
                    ),
                    "",
                )

        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
        ) as error:

            last_error = str(
                error
            )

            if attempt < retries:

                time.sleep(
                    min(
                        attempt,
                        3
                    )
                )

        except Exception as error:

            last_error = str(
                error
            )

            if attempt < retries:

                time.sleep(
                    min(
                        attempt,
                        3
                    )
                )

    return (
        b"",
        "",
        last_error,
    )


def fetch_feed(url):
    """
    Fetch a Google News RSS feed.
    """

    content, _, error = fetch_bytes(
        url,
        timeout=FEED_TIMEOUT,
        retries=FEED_RETRIES,
    )

    if error:

        raise RuntimeError(
            f"Feed request failed: {error}"
        )

    return content


def resolve_article_url(
    news_url
):
    """
    Resolve a Google News RSS URL to the
    actual publisher/article URL.

    Google News RSS links normally redirect
    to the publisher article. The final URL
    is captured from the HTTP response.

    Returns:
        (resolved_url, error)
    """

    if not is_http_url(
        news_url
    ):

        return (
            "",
            "Invalid article URL"
        )

    if not is_google_news_url(
        news_url
    ):

        return (
            normalize_url(
                news_url
            ),
            "",
        )

    content, final_url, error = fetch_bytes(
        news_url,
        timeout=ARTICLE_TIMEOUT,
        retries=ARTICLE_RETRIES,
    )

    # Content itself is not required here.
    # We only need the final redirected URL.
    del content

    if final_url and is_http_url(
        final_url
    ):

        normalized = normalize_url(
            final_url
        )

        if (
            normalized
            and not is_google_news_url(
                normalized
            )
        ):

            return (
                normalized,
                "",
            )

    return (
        "",
        error or "Could not resolve Google News URL"
    )


# ============================================================
# FEED PARSING
# ============================================================

def parse_feed(
    xml_data,
    source_name,
):
    """
    Parse one RSS feed.

    Every discovered item keeps both:
    - news_url
    - source_url

    source_url now points to the resolved article URL
    whenever Google News can be resolved.

    publisher_url is preserved separately.
    """

    root = ET.fromstring(
        xml_data
    )

    items = []

    for item in root.findall(
        ".//item"
    ):

        title = clean_text(
            item.findtext(
                "title",
                default=""
            )
        )

        news_url = clean_text(
            item.findtext(
                "link",
                default=""
            )
        )

        description = clean_text(
            item.findtext(
                "description",
                default=""
            )
        )

        published = parse_date(
            item.findtext(
                "pubDate",
                default=""
            )
        )

        # Google News RSS normally provides publisher
        # information inside the <source> element.
        source_element = item.find(
            "source"
        )

        publisher_name = ""
        publisher_url = ""

        if source_element is not None:

            publisher_name = clean_text(
                source_element.text or ""
            )

            publisher_url = clean_text(
                source_element.get(
                    "url",
                    ""
                )
            )

        combined = (
            f"{title} {description}"
        ).lower()

        matched_keywords = [
            keyword
            for keyword in KEYWORDS
            if keyword.lower()
            in combined
        ]

        if not matched_keywords:
            continue

        # ----------------------------------------------------
        # RESOLVE GOOGLE NEWS URL
        # ----------------------------------------------------

        resolved_url = ""
        resolution_error = ""

        if is_google_news_url(
            news_url
        ):

            (
                resolved_url,
                resolution_error,
            ) = resolve_article_url(
                news_url
            )

        else:

            resolved_url = normalize_url(
                news_url
            )

        # ----------------------------------------------------
        # SELECT BEST SOURCE URL
        # ----------------------------------------------------

        source_url = choose_best_url(
            google_news_url=news_url,
            resolved_url=resolved_url,
            publisher_url=publisher_url,
        )

        # ----------------------------------------------------
        # DISCOVERY ITEM
        # ----------------------------------------------------

        item_data = {
            "title":
                title,

            "source":
                source_name,

            "publisher_name":
                publisher_name,

            "publisher_url":
                normalize_url(
                    publisher_url
                ),

            "news_url":
                normalize_url(
                    news_url
                ),

            "resolved_url":
                normalize_url(
                    resolved_url
                ),

            "article_url":
                normalize_url(
                    resolved_url
                ),

            "source_url":
                source_url,

            "published":
                published,

            "matched_keywords":
                matched_keywords,

            "url_resolution":
                (
                    "resolved"
                    if resolved_url
                    and not is_google_news_url(
                        resolved_url
                    )
                    else "fallback"
                ),

            "url_resolution_error":
                resolution_error,

            "discovered_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "status":
                "needs_verification",
        }

        items.append(
            item_data
        )

    return items


# ============================================================
# DUPLICATE HELPERS
# ============================================================

def normalize_title_for_dedupe(
    title
):
    """
    Normalize title for fallback title-based deduplication.
    """

    title = clean_text(
        title
    ).lower()

    title = re.sub(
        r"[^a-z0-9\s]",
        " ",
        title
    )

    title = re.sub(
        r"\s+",
        " ",
        title
    )

    return title.strip()


def remove_duplicates(
    items
):
    """
    Deduplicate primarily by URL.

    Previous implementation deduplicated only by title.
    This could allow the same article to appear under
    different URLs or discard useful items with slightly
    different titles.

    New order:
        1. normalized resolved/article/source URL
        2. normalized title fallback
    """

    unique_by_url = {}
    unique_by_title = {}

    for item in items:

        resolved_url = normalize_url(
            item.get(
                "resolved_url",
                ""
            )
        )

        source_url = normalize_url(
            item.get(
                "source_url",
                ""
            )
        )

        article_url = normalize_url(
            item.get(
                "article_url",
                ""
            )
        )

        news_url = normalize_url(
            item.get(
                "news_url",
                ""
            )
        )

        title_key = normalize_title_for_dedupe(
            item.get(
                "title",
                ""
            )
        )

        # Prefer actual resolved/article URL.
        url_candidates = [
            resolved_url,
            article_url,
            source_url,
        ]

        selected_url = ""

        for candidate in url_candidates:

            if not candidate:
                continue

            if is_google_news_url(
                candidate
            ):
                continue

            selected_url = candidate
            break

        # If no publisher/article URL exists,
        # use Google News URL as last-resort identity.
        if not selected_url:

            if news_url:

                selected_url = news_url

        # ----------------------------------------------------
        # URL DEDUPLICATION
        # ----------------------------------------------------

        if selected_url:

            if selected_url in unique_by_url:

                existing = unique_by_url[
                    selected_url
                ]

                # Prefer an item with a resolved URL.
                if (
                    item.get(
                        "resolved_url",
                        ""
                    )
                    and not existing.get(
                        "resolved_url",
                        ""
                    )
                ):

                    unique_by_url[
                        selected_url
                    ] = item

                continue

            unique_by_url[
                selected_url
            ] = item

            continue

        # ----------------------------------------------------
        # TITLE FALLBACK DEDUPLICATION
        # ----------------------------------------------------

        if title_key:

            if title_key not in unique_by_title:

                unique_by_title[
                    title_key
                ] = item

    # Merge URL-based and title-based discoveries.
    results = list(
        unique_by_url.values()
    )

    url_identity_titles = {
        normalize_title_for_dedupe(
            item.get(
                "title",
                ""
            )
        )
        for item in results
    }

    for title_key, item in unique_by_title.items():

        if (
            title_key
            and title_key not in url_identity_titles
        ):

            results.append(
                item
            )

    return results


# ============================================================
# DISCOVERY QUALITY SORTING
# ============================================================

def discovery_priority(
    item
):
    """
    Give resolved article URLs priority when sorting.

    Newer articles remain important, but URL quality also
    matters because verification depends on reaching the
    actual opportunity page.
    """

    score = 0

    resolved_url = normalize_url(
        item.get(
            "resolved_url",
            ""
        )
    )

    source_url = normalize_url(
        item.get(
            "source_url",
            ""
        )
    )

    if (
        resolved_url
        and not is_google_news_url(
            resolved_url
        )
    ):

        score += 100

    if (
        source_url
        and not is_google_news_url(
            source_url
        )
    ):

        score += 50

    if item.get(
        "matched_keywords"
    ):

        score += min(
            len(
                item.get(
                    "matched_keywords",
                    []
                )
            ),
            10
        )

    published = item.get(
        "published",
        ""
    )

    return (
        score,
        published,
    )


# ============================================================
# MAIN DISCOVERY PIPELINE
# ============================================================

def main():

    print("=" * 60)
    print(
        "OPPORTUNITYBRIDGE DISCOVERY SYSTEM"
    )
    print("=" * 60)

    print("")
    print(
        "Discovery mode: Google News RSS "
        "with article URL resolution"
    )

    print(
        f"Maximum discoveries saved: "
        f"{MAX_DISCOVERIES}"
    )

    all_items = []

    resolution_success = 0
    resolution_failures = 0

    for source_name, feed_url in FEEDS.items():

        print(
            f"\nChecking: {source_name}"
        )

        print(
            f"Feed: {feed_url}"
        )

        try:

            xml_data = fetch_feed(
                feed_url
            )

            items = parse_feed(
                xml_data,
                source_name
            )

            print(
                f"Found: {len(items)} relevant items"
            )

            for item in items:

                if item.get(
                    "url_resolution"
                ) == "resolved":

                    resolution_success += 1

                else:

                    resolution_failures += 1

            all_items.extend(
                items
            )

        except Exception as error:

            print(
                f"ERROR: {error}"
            )

    print("")
    print(
        "Resolving/deduplicating discovery URLs..."
    )

    before_dedupe = len(
        all_items
    )

    all_items = remove_duplicates(
        all_items
    )

    after_dedupe = len(
        all_items
    )

    print(
        f"Before deduplication: "
        f"{before_dedupe}"
    )

    print(
        f"After deduplication: "
        f"{after_dedupe}"
    )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    all_items.sort(
        key=discovery_priority,
        reverse=True,
    )

    # --------------------------------------------------------
    # LIMIT
    # --------------------------------------------------------

    saved_items = all_items[
        :MAX_DISCOVERIES
    ]

    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------

    resolved_count = sum(
        1
        for item in saved_items
        if (
            item.get(
                "resolved_url",
                ""
            )
            and not is_google_news_url(
                item.get(
                    "resolved_url",
                    ""
                )
            )
        )
    )

    fallback_count = sum(
        1
        for item in saved_items
        if (
            not item.get(
                "resolved_url",
                ""
            )
            or is_google_news_url(
                item.get(
                    "resolved_url",
                    ""
                )
            )
        )
    )

    publisher_homepage_count = sum(
        1
        for item in saved_items
        if looks_like_homepage(
            item.get(
                "source_url",
                ""
            )
        )
    )

    # --------------------------------------------------------
    # OUTPUT PAYLOAD
    # --------------------------------------------------------

    payload = {
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "total":
            len(saved_items),

        "discovery_limit":
            MAX_DISCOVERIES,

        "total_before_limit":
            len(all_items),

        "feed_count":
            len(FEEDS),

        "url_resolution": {
            "resolved_articles":
                resolved_count,

            "fallback_google_news":
                fallback_count,

            "publisher_homepage_sources":
                publisher_homepage_count,

            "resolution_successes":
                resolution_success,

            "resolution_failures":
                resolution_failures,
        },

        "items":
            saved_items,
    }

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # FINAL LOG
    # --------------------------------------------------------

    print("\n" + "=" * 60)

    print(
        f"Saved {len(saved_items)} discoveries."
    )

    print(
        f"Total before limit: {len(all_items)}"
    )

    print(
        f"Resolved article URLs: {resolved_count}"
    )

    print(
        f"Fallback Google News URLs: {fallback_count}"
    )

    print(
        f"Publisher homepage source URLs: "
        f"{publisher_homepage_count}"
    )

    print(
        f"URL resolution successes: "
        f"{resolution_success}"
    )

    print(
        f"URL resolution failures: "
        f"{resolution_failures}"
    )

    print(
        f"Output: {OUTPUT}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()
