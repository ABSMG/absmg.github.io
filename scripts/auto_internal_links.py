from pathlib import Path
from html.parser import HTMLParser
import re


ROOT = Path(__file__).resolve().parents[1]


LINKS = {
    "scholarship": ("scholarships.html", "Scholarships"),
    "scholarships": ("scholarships.html", "Scholarships"),

    "job": ("jobs.html", "Jobs"),
    "jobs": ("jobs.html", "Jobs"),

    "internship": ("internships.html", "Internships"),
    "internships": ("internships.html", "Internships"),

    "course": ("courses.html", "Courses"),
    "courses": ("courses.html", "Courses"),

    "training": ("courses.html", "Courses"),

    "opportunity": ("opportunities.html", "Opportunities"),
    "opportunities": ("opportunities.html", "Opportunities"),

    "digital skills": ("digital-skills.html", "Digital Skills"),
    "career skills": ("career-skills.html", "Career Skills"),
}


EXCLUDED = {
    "404.html",
    "login.html",
    "logout.html",
    "register.html",
    "dashboard.html",
    "forgot-password.html",
    "reset-password.html",
    "privacy.html",
    "disclaimer.html",
    "contact.html",
}


MAX_CONTEXTUAL_LINKS = 5


class LinkParser(HTMLParser):

    def __init__(self):
        super().__init__()

        self.links = set()

        self.in_script = False
        self.in_style = False

    def handle_starttag(self, tag, attrs):

        tag = tag.lower()

        if tag == "script":
            self.in_script = True

        elif tag == "style":
            self.in_style = True

        if tag != "a":
            return

        for key, value in attrs:

            if key.lower() != "href":
                continue

            if not value:
                continue

            clean = (
                value
                .split("#")[0]
                .split("?")[0]
                .strip()
            )

            if clean:
                self.links.add(clean)

    def handle_endtag(self, tag):

        tag = tag.lower()

        if tag == "script":
            self.in_script = False

        elif tag == "style":
            self.in_style = False


def get_existing_links(html):

    parser = LinkParser()

    try:
        parser.feed(html)
    except Exception:
        pass

    return parser.links


def remove_old_related_section(html):

    pattern = re.compile(
        r"""
        <section
        \s+
        class=["'][^"']*\brelated-opportunities\b[^"']*["']
        .*?
        </section>
        """,
        flags=re.I | re.S | re.X,
    )

    return pattern.sub("", html)


def detect_topics(html):

    text = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        html,
        flags=re.I | re.S,
    )

    text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        text,
        flags=re.I | re.S,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.lower()


def page_exists(filename):

    return (
        ROOT / filename
    ).exists()


def choose_links(html, current_page):

    existing_links = get_existing_links(html)

    text = detect_topics(html)

    selected = []
    selected_files = set()

    for keyword, (
        filename,
        label
    ) in LINKS.items():

        if filename == current_page:
            continue

        if not page_exists(filename):
            continue

        if filename in existing_links:
            continue

        if filename in selected_files:
            continue

        if keyword not in text:
            continue

        selected.append(
            (
                filename,
                label
            )
        )

        selected_files.add(filename)

        if len(selected) >= MAX_CONTEXTUAL_LINKS:
            return selected

    fallback = [
        ("opportunities.html", "Opportunities"),
        ("scholarships.html", "Scholarships"),
        ("jobs.html", "Jobs"),
        ("internships.html", "Internships"),
        ("courses.html", "Courses"),
    ]

    for filename, label in fallback:

        if len(selected) >= MAX_CONTEXTUAL_LINKS:
            break

        if filename == current_page:
            continue

        if not page_exists(filename):
            continue

        if filename in existing_links:
            continue

        if filename in selected_files:
            continue

        selected.append(
            (
                filename,
                label
            )
        )

        selected_files.add(filename)

    return selected


def create_related_section(links):

    if not links:
        return ""

    items = []

    for filename, label in links:

        items.append(
            f"""
            <li>
                <a href="{filename}">
                    {label}
                </a>
            </li>
            """
        )

    return f"""
<section
    class="related-opportunities"
    aria-label="Related opportunities"
>
    <h2>Explore More Opportunities</h2>

    <ul>
        {''.join(items)}
    </ul>
</section>
"""


def insert_before_body(html, block):

    match = re.search(
        r"</body\s*>",
        html,
        flags=re.I,
    )

    if not match:
        return html + block

    position = match.start()

    return (
        html[:position]
        + block
        + "\n"
        + html[position:]
    )


def process_file(path):

    if path.name in EXCLUDED:
        return False

    if path.name.startswith("_"):
        return False

    try:
        html = path.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        return False

    original = html

    # Remove the old automatically generated
    # related section first.
    html = remove_old_related_section(html)

    links = choose_links(
        html,
        path.name
    )

    if links:

        block = create_related_section(
            links
        )

        html = insert_before_body(
            html,
            block
        )

    if html == original:
        return False

    path.write_text(
        html,
        encoding="utf-8"
    )

    return True


def main():

    print("=" * 70)
    print(
        "OPPORTUNITYBRIDGE INTERNAL LINKING ENGINE v2.0"
    )
    print("=" * 70)

    changed = []

    for path in sorted(
        ROOT.glob("*.html")
    ):

        if process_file(path):

            changed.append(
                path.name
            )

    print()

    if changed:

        print("Updated pages:")

        for page in changed:
            print(f"- {page}")

    else:

        print(
            "No pages required internal-link updates."
        )

    print()
    print(
        f"Pages updated: {len(changed)}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
