from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse
import re


# =============================================================
# OPPORTUNITYBRIDGE SEO CHECKER v3.0
# =============================================================
#
# Purpose:
#
# 1. Validate technical SEO on OpportunityBridge HTML pages.
# 2. Distinguish indexable pages from intentionally noindex pages.
# 3. Validate canonical URLs.
# 4. Validate Open Graph URLs.
# 5. Detect legacy /OpportunityBridge/ URLs.
# 6. Detect duplicate titles and canonical URLs.
# 7. Validate robots directives.
# 8. Validate generated OpportunityBridge articles.
# 9. Validate sitemap consistency.
# 10. Keep warnings non-blocking while genuine SEO errors
#     remain deployment-blocking.
#
# Important:
#
# Pages intentionally marked:
#
#     <meta name="robots" content="noindex, follow">
#
# are treated differently from normal indexable pages.
#
# =============================================================


ROOT = Path(__file__).resolve().parents[1]


BASE_URL = "https://absmg.github.io"


SITEMAP_FILE = ROOT / "sitemap.xml"


# =============================================================
# PAGES THAT SHOULD NOT BE CHECKED
# =============================================================

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
}


# =============================================================
# KNOWN INTENTIONAL NOINDEX PAGES
#
# These are old/news/general-content pages that should not
# compete with the main OpportunityBridge opportunity content.
# =============================================================

INTENTIONAL_NOINDEX_FILES = {
    "121-east-african-students-win-sh3-billion-global-scholarships-putting-education-at-heart-of-africas.html",

    "tanzania-economic-update-2026-making-jobs-work-world-bank-group.html",

    "tanzanian-billionaire-mo-dewji-pledges-to-invest-250-million-to-mozambique-and-create-20000-jobs-bil.html",

    "tanzanias-billionaire-led-metl-plans-250-million-mozambique-expansion-targeting-20000-jobs-business.html",

    "tanzanias-billionaire-led-metl-plans-250-million-mozambique-expansion-targeting-20000-jobs-cedirates.html",

    "tanzania-and-world-bank-finalize-kazi-mpa-central-corridor-jobs-programme-to-boost-youth-employment.html",

    "tanzania-to-host-2nd-doha-dialogue-to-boost-safe-overseas-job-opportunities-for-citizens-ippmediacot.html",

    "tanzania-urged-to-turn-economic-growth-into-better-jobs-channel-africa.html",

    "tanzania-must-risk-becoming-broke-to-create-20-million-jobs-uchumi360com.html",

    "tanzania-netherlands-deepen-partnership-around-investment-jobs-skills-ippmediacotz.html",

    "somalia-tanzania-discuss-youth-jobs-and-digital-government-cooperation-shabelle-media-network.html",

    "tanzanias-economy-gains-momentum-but-better-jobs-hold-the-key-to-broader-national-prosperity-devdisc.html",

    "tanzanias-kagera-coffee-nights-expose-a-deeper-jobs-and-skills-gap-pan-african-visions.html",

    "teagtl-inspires-future-professionals-through-career-day-engagements-at-udsm-thecitizencotz.html",

    "tra-doubles-jobs-for-disabled-workers-dailynewscotz.html",
}


# =============================================================
# DUPLICATE / REPLACED FILES
#
# Old duplicate URLs should not be treated as competing
# indexable pages.
# =============================================================

DUPLICATE_FILES = {
    "cfas-canon-collins-rmtf-scholarships-for-postgraduate-study-fundsforngos.html",

    "free-it-certifications-and-courses-to-elevate-your-career-coursera.html",

    "scholarship-opportunities-for-students-graduates-researchers-fundsforngos.html",

    "tom-queba-and-pegasys-scholarships-for-social-change-south-africa-fundsforngos.html",
}


# =============================================================
# DUPLICATE -> PREFERRED FILE MAP
# =============================================================

DUPLICATE_PREFERRED = {
    "cfas-canon-collins-rmtf-scholarships-for-postgraduate-study-fundsforngos.html":
        "cfas-canon-collins-rmtf-scholarships-for-postgraduate-study-fundsforngosorg.html",

    "free-it-certifications-and-courses-to-elevate-your-career-coursera.html":
        "free-it-certifications-and-courses-to-elevate-your-career-courseraorg.html",

    "scholarship-opportunities-for-students-graduates-researchers-fundsforngos.html":
        "scholarship-opportunities-for-students-graduates-researchers-fundsforngosorg.html",

    "tom-queba-and-pegasys-scholarships-for-social-change-south-africa-fundsforngos.html":
        "tom-queba-and-pegasys-scholarships-for-social-change-south-africa-fundsforngosor.html",
}


# =============================================================
# HTML PARSER
# =============================================================

class SEOParser(HTMLParser):

    def __init__(self):

        super().__init__()

        self.title = ""

        self.h1_count = 0

        self.lang = ""

        self.meta_description = False

        self.meta_robots = False

        self.robots_content = ""

        self.og_title = False

        self.og_description = False

        self.og_url = ""

        self.canonical = ""

        self.article_schema = False

        self.breadcrumb_schema = False

        self.in_title = False

        self.in_script = False

        self.current_script_type = ""

        self.script_buffer = ""


    # =========================================================
    # START TAG
    # =========================================================

    def handle_starttag(
        self,
        tag,
        attrs
    ):

        tag = tag.lower()

        attributes = dict(attrs)


        # -----------------------------------------------------
        # HTML LANG
        # -----------------------------------------------------

        if tag == "html":

            self.lang = (
                attributes.get(
                    "lang",
                    ""
                )
                or ""
            ).strip()


        # -----------------------------------------------------
        # TITLE
        # -----------------------------------------------------

        elif tag == "title":

            self.in_title = True


        # -----------------------------------------------------
        # H1
        # -----------------------------------------------------

        elif tag == "h1":

            self.h1_count += 1


        # -----------------------------------------------------
        # META
        # -----------------------------------------------------

        elif tag == "meta":

            name = (
                attributes.get(
                    "name",
                    ""
                )
                or ""
            ).lower().strip()


            property_name = (
                attributes.get(
                    "property",
                    ""
                )
                or ""
            ).lower().strip()


            content = (
                attributes.get(
                    "content",
                    ""
                )
                or ""
            ).strip()


            # -------------------------------------------------
            # DESCRIPTION
            # -------------------------------------------------

            if (
                name == "description"
                and content
            ):

                self.meta_description = True


            # -------------------------------------------------
            # ROBOTS
            # -------------------------------------------------

            if (
                name == "robots"
                and content
            ):

                self.meta_robots = True

                self.robots_content = (
                    content.lower().strip()
                )


            # -------------------------------------------------
            # OG TITLE
            # -------------------------------------------------

            if (
                property_name == "og:title"
                and content
            ):

                self.og_title = True


            # -------------------------------------------------
            # OG DESCRIPTION
            # -------------------------------------------------

            if (
                property_name == "og:description"
                and content
            ):

                self.og_description = True


            # -------------------------------------------------
            # OG URL
            # -------------------------------------------------

            if (
                property_name == "og:url"
                and content
            ):

                self.og_url = content


        # -----------------------------------------------------
        # LINK
        # -----------------------------------------------------

        elif tag == "link":

            rel = (
                attributes.get(
                    "rel",
                    ""
                )
                or ""
            ).lower().strip()


            href = (
                attributes.get(
                    "href",
                    ""
                )
                or ""
            ).strip()


            # -------------------------------------------------
            # CANONICAL
            # -------------------------------------------------

            if (
                "canonical" in rel.split()
                and href
            ):

                self.canonical = href


        # -----------------------------------------------------
        # SCRIPT
        # -----------------------------------------------------

        elif tag == "script":

            self.in_script = True

            self.current_script_type = (
                attributes.get(
                    "type",
                    ""
                )
                or ""
            ).lower().strip()

            self.script_buffer = ""


    # =========================================================
    # END TAG
    # =========================================================

    def handle_endtag(
        self,
        tag
    ):

        tag = tag.lower()


        if tag == "title":

            self.in_title = False


        elif tag == "script":

            script_content = (
                self.script_buffer
                or ""
            ).lower()


            # -------------------------------------------------
            # DETECT ARTICLE JSON-LD
            # -------------------------------------------------

            if (
                self.current_script_type
                == "application/ld+json"
            ):

                if (
                    '"article"' in script_content
                    or '"newsarticle"' in script_content
                    or '"blogposting"' in script_content
                ):

                    self.article_schema = True


                # -------------------------------------------------
                # DETECT BREADCRUMB JSON-LD
                # -------------------------------------------------

                if (
                    '"breadcrumb"' in script_content
                ):

                    self.breadcrumb_schema = True


            self.in_script = False

            self.current_script_type = ""

            self.script_buffer = ""


    # =========================================================
    # DATA
    # =========================================================

    def handle_data(
        self,
        data
    ):

        if self.in_title:

            self.title += data


        if self.in_script:

            self.script_buffer += data


# =============================================================
# URL VALIDATION
# =============================================================

def valid_absolute_url(
    url
):

    try:

        parsed = urlparse(
            url
        )

        return (
            parsed.scheme
            in {
                "http",
                "https",
            }
            and bool(
                parsed.netloc
            )
        )

    except Exception:

        return False


# =============================================================
# EXPECTED PAGE URL
# =============================================================

def expected_url_for(
    path
):

    relative = (
        path.relative_to(
            ROOT
        ).as_posix()
    )


    if relative == "index.html":

        return BASE_URL + "/"


    return (
        BASE_URL
        + "/"
        + relative
    )


# =============================================================
# NORMALIZE ROBOTS
# =============================================================

def normalize_robots(
    robots
):

    if not robots:

        return set()


    tokens = re.split(
        r"[\s,]+",
        robots.lower().strip()
    )


    return {
        token.strip()
        for token in tokens
        if token.strip()
    }


# =============================================================
# IS NOINDEX PAGE?
# =============================================================

def is_noindex_page(
    parser,
    path
):

    robots = normalize_robots(
        parser.robots_content
    )


    if "noindex" in robots:

        return True


    if path.name in INTENTIONAL_NOINDEX_FILES:

        return True


    if path.name in DUPLICATE_FILES:

        return True


    return False


# =============================================================
# IS INDEXABLE PAGE?
# =============================================================

def is_indexable_page(
    parser,
    path
):

    return not is_noindex_page(
        parser,
        path
    )


# =============================================================
# IS GENERATED ARTICLE?
# =============================================================

def is_generated_article(
    content
):

    lowered = (
        content.lower()
    )


    markers = [

        "opportunitybridge generated article",

        "opportunitybridge_generated_article",

        "opportunitybridge article",

        "approved opportunity",

    ]


    return any(
        marker in lowered
        for marker in markers
    )


# =============================================================
# READ PAGE
# =============================================================

def read_page(
    path
):

    try:

        return path.read_text(
            encoding="utf-8"
        )

    except Exception:

        return ""


# =============================================================
# CHECK PAGE
# =============================================================

def check_page(
    path
):

    parser = SEOParser()


    try:

        content = path.read_text(
            encoding="utf-8"
        )


        parser.feed(
            content
        )


    except Exception as error:

        return [
            f"READ ERROR: {error}"
        ], [], parser, ""


    errors = []

    warnings = []


    title = (
        parser.title
        .strip()
    )


    expected_url = (
        expected_url_for(
            path
        )
    )


    noindex = is_noindex_page(
        parser,
        path
    )


    indexable = not noindex


    generated_article = (
        is_generated_article(
            content
        )
    )


    # =========================================================
    # REQUIRED SEO ELEMENTS
    # =========================================================

    if not title:

        errors.append(
            "Missing <title>"
        )


    if not parser.meta_description:

        errors.append(
            "Missing meta description"
        )


    if parser.h1_count == 0:

        errors.append(
            "Missing <h1>"
        )

    elif parser.h1_count > 1:

        errors.append(
            f"Multiple <h1> tags ({parser.h1_count})"
        )


    if not parser.lang:

        errors.append(
            'Missing <html lang="">'
        )


    # =========================================================
    # ROBOTS DIRECTIVE
    # =========================================================

    robots = normalize_robots(
        parser.robots_content
    )


    if not parser.meta_robots:

        # -----------------------------------------------------
        # Missing robots is only a warning for normal pages.
        # -----------------------------------------------------

        warnings.append(
            "Missing robots meta tag"
        )

    else:

        if (
            "noindex" in robots
            and "index" in robots
        ):

            errors.append(
                "Robots meta contains both index and noindex"
            )


        # -----------------------------------------------------
        # INTENTIONAL NOINDEX PAGE
        # -----------------------------------------------------

        if noindex:

            if "noindex" not in robots:

                warnings.append(
                    "Page is configured as intentional "
                    "noindex but robots meta does not explicitly "
                    "contain noindex"
                )


        # -----------------------------------------------------
        # INDEXABLE PAGE
        # -----------------------------------------------------

        else:

            if "noindex" in robots:

                errors.append(
                    "Page appears indexable but robots contains noindex"
                )


    # =========================================================
    # CANONICAL
    # =========================================================

    if not parser.canonical:

        errors.append(
            "Missing canonical URL"
        )

    else:

        canonical = (
            parser.canonical
            .strip()
        )


        if not valid_absolute_url(
            canonical
        ):

            errors.append(
                "Canonical is not an absolute URL"
            )

        elif canonical != expected_url:

            errors.append(
                "Canonical does not match expected page URL "
                f"(expected: {expected_url}, found: {canonical})"
            )


        if (
            "/OpportunityBridge/"
            in canonical
        ):

            errors.append(
                "Canonical still contains /OpportunityBridge/"
            )


    # =========================================================
    # OPEN GRAPH URL
    # =========================================================

    if not parser.og_url:

        warnings.append(
            "Missing og:url"
        )

    else:

        og_url = (
            parser.og_url
            .strip()
        )


        if not valid_absolute_url(
            og_url
        ):

            errors.append(
                "og:url is not an absolute URL"
            )

        elif og_url != expected_url:

            errors.append(
                "og:url does not match expected page URL "
                f"(expected: {expected_url}, found: {og_url})"
            )


        if (
            "/OpportunityBridge/"
            in og_url
        ):

            errors.append(
                "og:url still contains /OpportunityBridge/"
            )


    # =========================================================
    # TITLE LENGTH
    # =========================================================

    if title:

        if len(title) > 65:

            warnings.append(
                f"Title is long ({len(title)} characters)"
            )

        elif len(title) < 20:

            warnings.append(
                f"Title is short ({len(title)} characters)"
            )


    # =========================================================
    # OPTIONAL OPEN GRAPH ELEMENTS
    # =========================================================

    if not parser.og_title:

        warnings.append(
            "Missing og:title"
        )


    if not parser.og_description:

        warnings.append(
            "Missing og:description"
        )


    # =========================================================
    # GENERATED ARTICLE VALIDATION
    # =========================================================

    if generated_article:

        if not parser.meta_robots:

            errors.append(
                "Generated article is missing robots meta tag"
            )


        if noindex:

            errors.append(
                "Generated OpportunityBridge article "
                "is marked noindex"
            )


        if not parser.og_url:

            errors.append(
                "Generated article is missing og:url"
            )


        if not parser.canonical:

            errors.append(
                "Generated article is missing canonical URL"
            )


        if not parser.article_schema:

            warnings.append(
                "Generated article is missing Article JSON-LD"
            )


        if not parser.breadcrumb_schema:

            warnings.append(
                "Generated article is missing BreadcrumbList JSON-LD"
            )


    # =========================================================
    # NOINDEX PAGE INFORMATION
    # =========================================================

    if noindex:

        warnings.append(
            "Intentional noindex page"
        )


    return (
        errors,
        warnings,
        parser,
        content
    )


# =============================================================
# GOOGLE VERIFICATION
# =============================================================

def is_google_verification(
    path
):

    return (
        path.name.lower().startswith(
            "google"
        )
        and
        path.name.lower().endswith(
            ".html"
        )
    )


# =============================================================
# HTML FILE
# =============================================================

def is_html_file(
    path
):

    return (
        path.is_file()
        and
        path.suffix.lower()
        == ".html"
    )


# =============================================================
# SITEMAP URL EXTRACTION
# =============================================================

def get_sitemap_urls():

    if not SITEMAP_FILE.exists():

        return set()


    try:

        content = SITEMAP_FILE.read_text(
            encoding="utf-8"
        )

    except Exception:

        return set()


    urls = set(
        re.findall(
            r"<loc>\s*(.*?)\s*</loc>",
            content,
            flags=re.IGNORECASE
            | re.DOTALL
        )
    )


    return {
        url.strip()
        for url in urls
        if url.strip()
    }


# =============================================================
# CHECK SITEMAP
# =============================================================

def check_sitemap(
    pages
):

    errors = []

    warnings = []


    sitemap_urls = get_sitemap_urls()


    if not SITEMAP_FILE.exists():

        errors.append(
            "sitemap.xml is missing"
        )

        return (
            errors,
            warnings
        )


    # ---------------------------------------------------------
    # CHECK INDEXABLE PAGES
    # ---------------------------------------------------------

    for page in pages:

        try:

            content = read_page(
                page
            )


            parser = SEOParser()

            parser.feed(
                content
            )

        except Exception:

            continue


        if not is_indexable_page(
            parser,
            page
        ):

            continue


        expected_url = (
            expected_url_for(
                page
            )
        )


        if expected_url not in sitemap_urls:

            warnings.append(
                "Indexable page missing from sitemap: "
                f"{page.name}"
            )


    # ---------------------------------------------------------
    # CHECK NOINDEX PAGES
    # ---------------------------------------------------------

    for page in pages:

        try:

            content = read_page(
                page
            )


            parser = SEOParser()

            parser.feed(
                content
            )

        except Exception:

            continue


        if not is_noindex_page(
            parser,
            page
        ):

            continue


        expected_url = (
            expected_url_for(
                page
            )
        )


        if expected_url in sitemap_urls:

            errors.append(
                "Noindex page is present in sitemap: "
                f"{page.name}"
            )


    return (
        errors,
        warnings
    )


# =============================================================
# MAIN
# =============================================================

def main():

    print(
        "=" * 70
    )


    print(
        "OPPORTUNITYBRIDGE SEO CHECKER v3.0"
    )


    print(
        "=" * 70
    )


    pages = []


    # =========================================================
    # FIND HTML PAGES
    # =========================================================

    for path in sorted(
        ROOT.glob("*.html")
    ):

        if not is_html_file(
            path
        ):

            continue


        if path.name in EXCLUDED:

            continue


        if path.name.startswith(
            "_"
        ):

            continue


        if is_google_verification(
            path
        ):

            continue


        pages.append(
            path
        )


    total_errors = 0

    total_warnings = 0

    pages_with_errors = 0

    indexable_pages = 0

    noindex_pages = 0

    generated_articles = 0


    titles = {}

    canonicals = {}


    # =========================================================
    # CHECK EVERY PAGE
    # =========================================================

    for page in pages:

        (
            errors,
            warnings,
            parser,
            content
        ) = check_page(
            page
        )


        title = (
            parser.title
            .strip()
            .lower()
        )


        canonical = (
            parser.canonical
            .strip()
            .lower()
        )


        noindex = is_noindex_page(
            parser,
            page
        )


        if noindex:

            noindex_pages += 1

        else:

            indexable_pages += 1


        if is_generated_article(
            content
        ):

            generated_articles += 1


        # =====================================================
        # DUPLICATE TITLE TRACKING
        #
        # Only indexable pages are included.
        # Intentional noindex pages should not compete in
        # duplicate-title SEO checks.
        # =====================================================

        if (
            title
            and
            not noindex
        ):

            titles.setdefault(
                title,
                []
            ).append(
                page.name
            )


        # =====================================================
        # DUPLICATE CANONICAL TRACKING
        #
        # Only indexable pages are included.
        # =====================================================

        if (
            canonical
            and
            not noindex
        ):

            canonicals.setdefault(
                canonical,
                []
            ).append(
                page.name
            )


        # =====================================================
        # PAGE RESULT
        # =====================================================

        if errors:

            pages_with_errors += 1

            total_errors += len(
                errors
            )


            print(
                f"\n❌ {page.name}"
            )


            for error in errors:

                print(
                    f"   ERROR: {error}"
                )


        else:

            if noindex:

                print(
                    f"🟡 {page.name} "
                    "(noindex)"
                )

            else:

                print(
                    f"✅ {page.name}"
                )


        # =====================================================
        # WARNINGS
        # =====================================================

        for warning in warnings:

            total_warnings += 1


            print(
                f"   ⚠️ WARNING: {warning}"
            )


    # =========================================================
    # DUPLICATE TITLES
    # =========================================================

    for title, page_list in titles.items():

        if len(page_list) > 1:

            total_errors += 1


            print(
                "\n❌ DUPLICATE TITLE"
            )


            print(
                f"   Title: {title}"
            )


            print(
                f"   Pages: {page_list}"
            )


    # =========================================================
    # DUPLICATE CANONICALS
    # =========================================================

    for canonical, page_list in canonicals.items():

        if len(page_list) > 1:

            total_errors += 1


            print(
                "\n❌ DUPLICATE CANONICAL"
            )


            print(
                f"   Canonical: {canonical}"
            )


            print(
                f"   Pages: {page_list}"
            )


    # =========================================================
    # DUPLICATE FILE VALIDATION
    # =========================================================

    for duplicate_file in sorted(
        DUPLICATE_FILES
    ):

        duplicate_path = (
            ROOT / duplicate_file
        )


        if not duplicate_path.exists():

            continue


        content = read_page(
            duplicate_path
        )


        parser = SEOParser()

        parser.feed(
            content
        )


        robots = normalize_robots(
            parser.robots_content
        )


        if "noindex" not in robots:

            total_errors += 1


            print(
                "\n❌ DUPLICATE PAGE IS NOT NOINDEX"
            )


            print(
                f"   File: {duplicate_file}"
            )


        preferred = DUPLICATE_PREFERRED.get(
            duplicate_file
        )


        if preferred:

            expected_preferred_url = (
                BASE_URL
                + "/"
                + preferred
            )


            canonical = (
                parser.canonical
                .strip()
            )


            if canonical:

                if canonical != expected_preferred_url:

                    total_errors += 1


                    print(
                        "\n❌ DUPLICATE CANONICAL "
                        "DOES NOT POINT TO PREFERRED PAGE"
                    )


                    print(
                        f"   File: {duplicate_file}"
                    )


                    print(
                        f"   Expected: "
                        f"{expected_preferred_url}"
                    )


                    print(
                        f"   Found: "
                        f"{canonical}"
                    )


    # =========================================================
    # LEGACY URL SCAN
    # =========================================================

    legacy_files = []


    for page in pages:

        try:

            content = page.read_text(
                encoding="utf-8"
            )

        except Exception:

            continue


        if (
            "https://absmg.github.io/OpportunityBridge"
            in content
        ):

            legacy_files.append(
                page.name
            )


        if (
            "http://absmg.github.io/OpportunityBridge"
            in content
        ):

            if page.name not in legacy_files:

                legacy_files.append(
                    page.name
                )


    if legacy_files:

        total_errors += len(
            legacy_files
        )


        print(
            "\n❌ LEGACY /OpportunityBridge/ "
            "URLS FOUND"
        )


        for filename in legacy_files:

            print(
                f"   {filename}"
            )


    # =========================================================
    # HOMEPAGE AUTO SECTION VALIDATION
    # =========================================================

    homepage = ROOT / "index.html"


    if homepage.exists():

        homepage_content = read_page(
            homepage
        )


        start_marker = (
            "<!-- OPPORTUNITYBRIDGE_AUTO_OPPORTUNITIES_START -->"
        )


        end_marker = (
            "<!-- OPPORTUNITYBRIDGE_AUTO_OPPORTUNITIES_END -->"
        )


        start_count = (
            homepage_content.count(
                start_marker
            )
        )


        end_count = (
            homepage_content.count(
                end_marker
            )
        )


        if start_count > 1:

            total_errors += 1


            print(
                "\n❌ Homepage contains duplicate "
                "auto-opportunity START markers"
            )


        if end_count > 1:

            total_errors += 1


            print(
                "\n❌ Homepage contains duplicate "
                "auto-opportunity END markers"
            )


        if (
            start_count == 1
            and
            end_count == 1
        ):

            print(
                "\n✅ Homepage auto-opportunity "
                "section markers are valid"
            )


        elif (
            start_count == 0
            and
            end_count == 0
        ):

            warnings.append(
                "Homepage has no automatic "
                "opportunity section yet"
            )


            total_warnings += 1


    # =========================================================
    # SITEMAP VALIDATION
    # =========================================================

    (
        sitemap_errors,
        sitemap_warnings
    ) = check_sitemap(
        pages
    )


    if sitemap_errors:

        total_errors += len(
            sitemap_errors
        )


        print(
            "\n❌ SITEMAP VALIDATION ERRORS"
        )


        for error in sitemap_errors:

            print(
                f"   ERROR: {error}"
            )


    for warning in sitemap_warnings:

        total_warnings += 1


        print(
            f"\n   ⚠️ WARNING: {warning}"
        )


    # =========================================================
    # FINAL REPORT
    # =========================================================

    print(
        "\n"
        + "=" * 70
    )


    print(
        "OPPORTUNITYBRIDGE SEO CHECKER REPORT"
    )


    print(
        "=" * 70
    )


    print(
        f"Pages checked: {len(pages)}"
    )


    print(
        f"Indexable pages: {indexable_pages}"
    )


    print(
        f"Intentional noindex pages: {noindex_pages}"
    )


    print(
        f"Generated articles detected: "
        f"{generated_articles}"
    )


    print(
        f"Pages with errors: "
        f"{pages_with_errors}"
    )


    print(
        f"Total errors: {total_errors}"
    )


    print(
        f"SEO warnings: {total_warnings}"
    )


    print(
        "=" * 70
    )


    # =========================================================
    # FAILURE / SUCCESS
    # =========================================================

    if total_errors:

        print(
            "SEO CHECK FAILED."
        )


        print(
            "Genuine SEO errors must be fixed before "
            "deployment is considered healthy."
        )


        raise SystemExit(
            1
        )


    print(
        "SEO CHECK PASSED."
    )


    if total_warnings:

        print(
            "Warnings detected, but they do not block deployment."
        )

    else:

        print(
            "No SEO warnings detected."
        )


# =============================================================
# ENTRY POINT
# =============================================================

if __name__ == "__main__":

    main()
