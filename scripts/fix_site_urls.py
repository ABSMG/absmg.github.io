from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]

OLD_BASE = "https://absmg.github.io/OpportunityBridge"
NEW_BASE = "https://absmg.github.io"


EXCLUDED = {
    "404.html",
}


def replace_urls(content):
    original = content

    # Full old URLs
    content = content.replace(
        OLD_BASE + "/",
        NEW_BASE + "/"
    )

    content = content.replace(
        OLD_BASE,
        NEW_BASE
    )

    # Protect against accidental double slashes
    content = content.replace(
        NEW_BASE + "//",
        NEW_BASE + "/"
    )

    # Canonical URLs should point to the root site.
    content = re.sub(
        r'(<link\s+rel=["\']canonical["\']\s+href=["\'])'
        r'https://absmg\.github\.io/OpportunityBridge/?'
        r'([^"\']*)'
        r'(["\'])',
        rf'\g<1>{NEW_BASE}/\g<2>\g<3>',
        content,
        flags=re.I
    )

    # Open Graph URL
    content = re.sub(
        r'(<meta\s+property=["\']og:url["\']\s+content=["\'])'
        r'https://absmg\.github\.io/OpportunityBridge/?'
        r'([^"\']*)'
        r'(["\'])',
        rf'\g<1>{NEW_BASE}/\g<2>\g<3>',
        content,
        flags=re.I
    )

    return content, content != original


def process_file(path):

    if path.name in EXCLUDED:
        return False

    try:
        content = path.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        return False

    updated, changed = replace_urls(content)

    if not changed:
        return False

    path.write_text(
        updated,
        encoding="utf-8"
    )

    return True


def main():

    print("=" * 70)
    print("OPPORTUNITYBRIDGE SITE URL REPAIR v1.0")
    print("=" * 70)

    changed = []

    for path in sorted(ROOT.glob("*.html")):

        if process_file(path):
            changed.append(path.name)

    print()

    if changed:

        print("Updated files:")

        for filename in changed:
            print(f"- {filename}")

    else:

        print(
            "No old OpportunityBridge URLs were found."
        )

    print()
    print(
        f"Files updated: {len(changed)}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
