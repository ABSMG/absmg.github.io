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


def clean(value):
    return str(value or "").strip()


def slugify(text):
    text = clean(text).lower()

    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")

    return text[:100].strip("-")


def source_hash(source_url):
    return hashlib.sha1(
        clean(source_url).encode("utf-8")
    ).hexdigest()[:8]


def valid_url(url):
    try:
        parsed = urlparse(clean(url))
        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.netloc)
        )
    except Exception:
        return False


def article_files():
    return {
        path.name: path
        for path in ROOT.glob("*.html")
    }


def find_existing_article(source_url):
    """
    Find an existing generated article containing the same source URL.
    This prevents the same opportunity from generating multiple articles.
    """

    source_url = clean(source_url)

    if not source_url:
        return None

    for path in ROOT.glob("*.html"):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")

            if source_url in content:
                return path

        except Exception:
            continue

    return None


def unique_article_path(title, source_url):
    """
    Generate a collision-safe article filename.
    """

    base_slug = slugify(title)

    if not base_slug:
        base_slug = "opportunity"

    candidate = ROOT / f"{base_slug}.html"

    if not candidate.exists():
        return candidate

    # Same title but different source.
    # Add a stable hash rather than creating random filenames.
    hashed_slug = f"{base_slug}-{source_hash(source_url)}"

    candidate = ROOT / f"{hashed_slug}.html"

    if not candidate.exists():
        return candidate

    return candidate


def escape(value):
    return html.escape(clean(value), quote=True)


def build_description(item):
    description = clean(
        item.get("description")
        or item.get("summary")
        or item.get("content")
    )

    if description:
        return description[:300]

    title = clean(item.get("title"))

    return (
        f"{title}. Find eligibility, application information, "
        f"deadline details and the official source."
    )


def build_keywords(item):
    keywords = item.get("matched_keywords", [])

    if not isinstance(keywords, list):
        keywords = []

    cleaned = [
        clean(keyword)
        for keyword in keywords
        if clean(keyword)
    ]

    if not cleaned:
        cleaned = [
            "opportunities",
            "scholarships",
            "jobs",
            "internships",
            "courses",
        ]

    return ", ".join(dict.fromkeys(cleaned))


def build_json_ld(
    title,
    description,
    article_url,
    source_url,
    publisher,
    published_date,
    modified_date,
):
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
            "name": "OpportunityBridge",
            "url": BASE_URL,
        },
        "publisher": {
            "@type": "Organization",
            "name": "OpportunityBridge",
            "url": BASE_URL,
        },
        "isPartOf": {
            "@type": "WebSite",
            "name": "OpportunityBridge",
            "url": BASE_URL,
        },
    }

    if publisher:
        data["about"] = {
            "@type": "Thing",
            "name": publisher,
        }

    if source_url:
        data["citation"] = source_url

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    )


def build_article(item, article_path, published_date, modified_date):
    title = clean(item.get("title"))

    source_url = clean(
        item.get("source_url")
        or item.get("url")
        or item.get("link")
    )

    publisher = clean(
        item.get("publisher")
        or item.get("source")
        or item.get("source_name")
    )

    description = build_description(item)
    keywords = build_keywords(item)

    slug = article_path.stem
    article_url = f"{BASE_URL}/{article_path.name}"

    json_ld = build_json_ld(
        title=title,
        description=description,
        article_url=article_url,
        source_url=source_url,
        publisher=publisher,
        published_date=published_date,
        modified_date=modified_date,
    )

    safe_title = escape(title)
    safe_description = escape(description)
    safe_keywords = escape(keywords)
    safe_publisher = escape(publisher or "OpportunityBridge")
    safe_source_url = escape(source_url)

    source_link = ""

    if valid_url(source_url):
        source_link = f"""
        <p>
            <a
                href="{safe_source_url}"
                target="_blank"
                rel="noopener noreferrer"
            >
                View the official/source opportunity page
            </a>
        </p>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>{safe_title} | OpportunityBridge</title>

    <meta
        name="description"
        content="{safe_description}"
    >

    <meta
        name="keywords"
        content="{safe_keywords}"
    >

    <link
        rel="canonical"
        href="{article_url}"
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
        content="{article_url}"
    >

    <meta
        property="og:site_name"
        content="OpportunityBridge"
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
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.7;
            margin: 0;
            background: #f7f9fc;
            color: #1f2937;
        }}

        main {{
            max-width: 900px;
            margin: 40px auto;
            padding: 30px;
            background: #ffffff;
        }}

        h1 {{
            line-height: 1.25;
        }}

        .meta {{
            color: #64748b;
            font-size: 14px;
        }}

        .notice {{
            padding: 16px;
            margin: 25px 0;
            border-left: 4px solid #2563eb;
            background: #eff6ff;
        }}

        a {{
            color: #2563eb;
        }}
    </style>
</head>

<body>

<main>

    <article>

        <h1>{safe_title}</h1>

        <p class="meta">
            Published: {published_date}
            <br>
            Updated: {modified_date}
            <br>
            Source: {safe_publisher}
        </p>

        <p>
            {safe_description}
        </p>

        <div class="notice">
            <strong>Important:</strong>
            OpportunityBridge provides information about opportunities.
            Always confirm eligibility, deadline, funding details and
            application requirements on the official source before applying.
        </div>

        <h2>Opportunity Details</h2>

        <p>
            This opportunity was discovered and processed through the
            OpportunityBridge opportunity discovery and verification system.
        </p>

        <h2>Official Source</h2>

        {source_link}

        <h2>Before You Apply</h2>

        <ul>
            <li>Check the official eligibility requirements.</li>
            <li>Confirm the application deadline.</li>
            <li>Review all required documents.</li>
            <li>Confirm whether the opportunity is fully funded, partially funded,
                paid or unpaid.</li>
            <li>Apply through the official source whenever possible.</li>
        </ul>

    </article>

</main>

</body>
</html>
"""


def process_item(item):
    title = clean(item.get("title"))

    source_url = clean(
        item.get("source_url")
        or item.get("url")
        or item.get("link")
    )

    if not title:
        return None, "Skipped: missing title"

    if not valid_url(source_url):
        return None, f"Skipped: invalid source URL for '{title}'"

    # IMPORTANT:
    # Check source URL before creating a new article.
    existing = find_existing_article(source_url)

    now = datetime.now(timezone.utc).isoformat()

    if existing:
        try:
            content = existing.read_text(
                encoding="utf-8",
                errors="ignore"
            )

            # Update modification date when the same source
            # appears again in a later automation run.
            content = re.sub(
                r'(<meta\s+name="dateModified"\s+content=")[^"]*(")',
                rf'\g<1>{escape(now)}\g<2>',
                content,
            )

            existing.write_text(
                content,
                encoding="utf-8"
            )

        except Exception:
            pass

        return existing, f"Updated existing article: {existing.name}"

    article_path = unique_article_path(
        title,
        source_url,
    )

    published_date = clean(
        item.get("published_at")
        or item.get("published")
        or item.get("date")
    )

    if not published_date:
        published_date = now

    modified_date = now

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

    return article_path, f"Created article: {article_path.name}"


def main():
    print("=" * 70)
    print("OPPORTUNITYBRIDGE ARTICLE GENERATOR v2.0")
    print("=" * 70)

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
            f"ERROR: Could not read approved opportunities: {error}"
        )

    items = data.get("approved_items", [])

    if not isinstance(items, list):
        raise SystemExit(
            "ERROR: approved_items is not a list."
        )

    created = 0
    updated = 0
    skipped = 0

    for item in items:
        path, message = process_item(item)

        print(message)

        if path is None:
            skipped += 1
        elif "Updated existing" in message:
            updated += 1
        else:
            created += 1

    print()
    print("-" * 70)
    print(f"Approved opportunities: {len(items)}")
    print(f"New articles:          {created}")
    print(f"Updated articles:      {updated}")
    print(f"Skipped:               {skipped}")
    print("-" * 70)
    print()
    print("Article generation completed.")
    print("=" * 70)


if __name__ == "__main__":
    main()
