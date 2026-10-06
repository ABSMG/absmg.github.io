from pathlib import Path
from urllib.parse import urlparse
import json
from datetime import datetime, timezone


# ============================================================
# OPPORTUNITYBRIDGE APPROVAL ENGINE
# ============================================================
#
# Purpose:
#
#   Read verified opportunities from:
#
#       data/verified_opportunities.json
#
#   Apply a second, stricter publication-quality gate.
#
#   Only opportunities that have enough evidence to be
#   automatically published are placed in:
#
#       data/approved_opportunities.json
#
# IMPORTANT:
#
#   This file is the final automatic approval gate before
#   article generation and homepage publication.
#
# ============================================================


ROOT = Path(__file__).resolve().parents[1]

INPUT = ROOT / "data" / "verified_opportunities.json"

OUTPUT = ROOT / "data" / "approved_opportunities.json"


# ============================================================
# REQUIRED OPPORTUNITY KEYWORDS
# ============================================================

REQUIRED_KEYWORDS = {
    "scholarship",
    "scholarships",
    "fellowship",
    "fellowships",
    "grant",
    "grants",
    "funding",
    "funded",
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
    "opportunity",
    "opportunities",
    "application",
    "applications",
    "apply",
    "eligibility",
    "deadline",
    "research",
    "competition",
    "competitions",
    "volunteer",
    "volunteering",
}


# ============================================================
# STRONG OPPORTUNITY EVIDENCE
# ============================================================
#
# These signals are stronger than generic words such as
# "job", "career", "students", or "opportunity".
#
# An actual opportunity page will normally contain some
# combination of these signals.
# ============================================================

STRONG_APPROVAL_SIGNALS = {
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
}


# ============================================================
# NEWS / GENERAL CONTENT SIGNALS
# ============================================================
#
# These are warning signals.
#
# A page with these phrases is not automatically rejected,
# because an opportunity page can also contain some news-like
# language.
#
# However, a page dominated by news signals with weak
# opportunity evidence must NOT be automatically approved.
# ============================================================

NEWS_SIGNALS = {
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
}


# ============================================================
# APPROVED VERIFICATION LEVELS
# ============================================================
#
# IMPORTANT:
#
# The verification engine currently produces:
#
#   verified
#   review
#   failed
#
# Only "verified" is automatically eligible here.
#
# The legacy values "source_checked" and "page_checked"
# are preserved for compatibility with older verification
# records.
#
# "review" is intentionally NOT allowed because records
# requiring review must not be automatically published.
# ============================================================

ALLOWED_VERIFICATION_LEVELS = {
    "verified",
    "source_checked",
    "page_checked",
}


# ============================================================
# APPROVED CLASSIFICATIONS
# ============================================================
#
# IMPORTANT:
#
# "possible_opportunity" is intentionally NOT here.
#
# It requires human review and must never reach automatic
# publication.
# ============================================================

AUTO_APPROVABLE_CLASSIFICATIONS = {
    "confirmed_opportunity",
    "trusted_opportunity",
}


# ============================================================
# REJECTED CLASSIFICATIONS
# ============================================================

REJECTED_CLASSIFICATIONS = {
    "failed",
    "likely_news_or_general_content",
    "insufficient_opportunity_evidence",
    "possible_opportunity",
    "expired_opportunity",
}


# ============================================================
# MINIMUM SCORE
# ============================================================
#
# The verifier calculates the evidence score.
#
# A score below this threshold is not strong enough for
# automatic publication.
# ============================================================

MINIMUM_AUTO_APPROVAL_SCORE = 10


# ============================================================
# STRONG EVIDENCE REQUIREMENT
# ============================================================
#
# An opportunity must contain at least one strong evidence
# signal OR a concrete application/deadline/eligibility signal.
# ============================================================

REQUIRE_STRONG_EVIDENCE = True


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean(value):
    """
    Convert values to clean strings.
    """

    if value is None:
        return ""

    return str(value).strip()


def clean_lower(value):
    """
    Clean and lowercase text.
    """

    return clean(
        value
    ).lower()


def valid_url(url):
    """
    Validate HTTP/HTTPS URL.
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
            and bool(
                parsed.netloc
            )
        )

    except Exception:

        return False


def get_domain(url):
    """
    Extract the hostname from a URL.
    """

    try:

        parsed = urlparse(
            clean(url)
        )

        return (
            parsed.netloc
            .lower()
            .split(":")[0]
            .strip(".")
        )

    except Exception:

        return ""


def normalize_url(url):
    """
    Normalize a URL for comparisons.
    """

    return clean(
        url
    ).rstrip(
        "/"
    ).lower()


# ============================================================
# DEADLINE PARSING
# ============================================================

def parse_deadline_date(value):
    """
    Parse common deadline formats into a timezone-aware UTC
    datetime.

    Returns None when the value cannot be parsed.
    """

    value = clean(
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
    Return True when a detected deadline has already passed.
    """

    parsed = parse_deadline_date(
        value
    )

    if parsed is None:
        return False

    return (
        parsed
        < datetime.now(
            timezone.utc
        )
    )


# ============================================================
# KEYWORD CHECK
# ============================================================

def get_text_for_keyword_check(item):
    """
    Build a combined text field from all useful verification
    information.

    This is more reliable than checking only the original
    title and description.
    """

    title = clean(
        item.get(
            "title"
        )
    )

    description = clean(
        item.get(
            "description"
        )
        or item.get(
            "summary"
        )
    )

    page_title = clean(
        item.get(
            "page_title"
        )
    )

    page_description = clean(
        item.get(
            "page_description"
        )
    )

    matched_keywords = item.get(
        "matched_keywords",
        []
    )

    strong_signals = item.get(
        "strong_opportunity_signals",
        []
    )

    verification_evidence = item.get(
        "verification_evidence",
        []
    )

    pieces = [
        title,
        description,
        page_title,
        page_description,
    ]

    if isinstance(
        matched_keywords,
        list
    ):

        pieces.extend(
            clean(keyword)
            for keyword in matched_keywords
        )

    if isinstance(
        strong_signals,
        list
    ):

        pieces.extend(
            clean(signal)
            for signal in strong_signals
        )

    if isinstance(
        verification_evidence,
        list
    ):

        pieces.extend(
            clean(evidence)
            for evidence in verification_evidence
        )

    return " ".join(
        pieces
    ).lower()


def has_opportunity_keyword(item):
    """
    Confirm that the record contains at least one recognized
    opportunity keyword.
    """

    combined = get_text_for_keyword_check(
        item
    )

    if not combined:
        return False

    return any(
        keyword in combined
        for keyword in REQUIRED_KEYWORDS
    )


def get_matching_required_keywords(item):
    """
    Return recognized opportunity keywords found in the item.
    """

    combined = get_text_for_keyword_check(
        item
    )

    matches = []

    for keyword in sorted(
        REQUIRED_KEYWORDS
    ):

        if keyword in combined:

            matches.append(
                keyword
            )

    return matches


# ============================================================
# STRONG EVIDENCE CHECK
# ============================================================

def get_strong_evidence(item):
    """
    Collect strong opportunity evidence.

    Evidence may come from:
      - verifier signals
      - detected deadline
      - application URL
      - verification evidence
      - page metadata
    """

    evidence = []

    # --------------------------------------------------------
    # Existing strong signals from verifier
    # --------------------------------------------------------

    strong_signals = item.get(
        "strong_opportunity_signals",
        []
    )

    if isinstance(
        strong_signals,
        list
    ):

        for signal in strong_signals:

            signal = clean_lower(
                signal
            )

            if signal and signal not in evidence:

                evidence.append(
                    signal
                )

    # --------------------------------------------------------
    # Detected deadline
    # --------------------------------------------------------

    deadline = clean(
        item.get(
            "detected_deadline"
        )
    )

    if deadline:

        evidence.append(
            "detected deadline"
        )

    # --------------------------------------------------------
    # Application URL
    # --------------------------------------------------------

    application_url = clean(
        item.get(
            "application_url"
        )
    )

    if valid_url(
        application_url
    ):

        evidence.append(
            "application URL"
        )

    # --------------------------------------------------------
    # Verification evidence
    # --------------------------------------------------------

    verification_evidence = item.get(
        "verification_evidence",
        []
    )

    if isinstance(
        verification_evidence,
        list
    ):

        for value in verification_evidence:

            value = clean(
                value
            )

            if not value:
                continue

            lowered = value.lower()

            # Keep only evidence that indicates actual
            # opportunity characteristics.
            if any(
                keyword in lowered
                for keyword in [
                    "apply",
                    "application",
                    "deadline",
                    "eligibility",
                    "funding",
                    "stipend",
                    "requirements",
                    "opportunity",
                ]
            ):

                if value not in evidence:

                    evidence.append(
                        value
                    )

    return evidence


def has_strong_evidence(item):
    """
    Determine whether the opportunity has enough concrete
    evidence for automatic approval.
    """

    strong_evidence = get_strong_evidence(
        item
    )

    return bool(
        strong_evidence
    )


# ============================================================
# NEWS SIGNAL CHECK
# ============================================================

def get_news_signals(item):
    """
    Return news/general-content signals.
    """

    signals = item.get(
        "news_signals",
        []
    )

    result = []

    if isinstance(
        signals,
        list
    ):

        for signal in signals:

            signal = clean_lower(
                signal
            )

            if signal:

                result.append(
                    signal
                )

    # Also inspect verification evidence if needed.
    verification_evidence = item.get(
        "verification_evidence",
        []
    )

    if isinstance(
        verification_evidence,
        list
    ):

        for evidence in verification_evidence:

            lowered = clean_lower(
                evidence
            )

            for news_signal in NEWS_SIGNALS:

                if news_signal in lowered:

                    if news_signal not in result:

                        result.append(
                            news_signal
                        )

    return result


def is_news_heavy(item):
    """
    Determine whether the item has enough news/general
    signals to require rejection/review.
    """

    signals = get_news_signals(
        item
    )

    score = item.get(
        "opportunity_score",
        0
    )

    try:

        score = float(
            score
        )

    except (
        TypeError,
        ValueError
    ):

        score = 0

    # Many news signals + weak opportunity score.
    if (
        len(signals) >= 3
        and score < 12
    ):

        return True

    return False


# ============================================================
# VERIFICATION STATUS CHECK
# ============================================================

def passed_verification_engine(item):
    """
    Check whether the verifier itself considers the source
    sufficiently verified.
    """

    verification_level = clean(
        item.get(
            "verification_level"
        )
    )

    if verification_level not in (
        ALLOWED_VERIFICATION_LEVELS
    ):

        return False

    source_verified = bool(
        item.get(
            "source_verified",
            False
        )
    )

    page_reachable = bool(
        item.get(
            "page_reachable",
            False
        )
    )

    opportunity_relevant = bool(
        item.get(
            "opportunity_relevant",
            False
        )
    )

    if not source_verified:
        return False

    if not page_reachable:
        return False

    if not opportunity_relevant:
        return False

    return True


# ============================================================
# HUMAN REVIEW CHECK
# ============================================================

def requires_human_review(item):
    """
    Any item explicitly marked for human review must not be
    automatically approved.
    """

    return bool(
        item.get(
            "needs_human_review",
            False
        )
    )


# ============================================================
# CLASSIFICATION CHECK
# ============================================================

def is_auto_approvable_classification(item):
    """
    Only confirmed/trusted opportunity classifications may
    pass automatic publication.
    """

    classification = clean(
        item.get(
            "opportunity_classification"
        )
    )

    return (
        classification
        in AUTO_APPROVABLE_CLASSIFICATIONS
    )


# ============================================================
# SCORE CHECK
# ============================================================

def get_score(item):
    """
    Safely read the verifier opportunity score.
    """

    value = item.get(
        "opportunity_score",
        0
    )

    try:

        return float(
            value
        )

    except (
        TypeError,
        ValueError
    ):

        return 0.0


def passes_score_threshold(item):
    """
    Check minimum automatic approval score.
    """

    score = get_score(
        item
    )

    return (
        score
        >= MINIMUM_AUTO_APPROVAL_SCORE
    )


# ============================================================
# URL CHECK
# ============================================================

def get_source_url(item):
    """
    Prefer the resolved official URL produced by the
    verification engine.

    Fall back to the original source URL.
    """

    official_url = clean(
        item.get(
            "official_url"
        )
    )

    if valid_url(
        official_url
    ):

        return official_url

    source_url = clean(
        item.get(
            "source_url"
        )
        or item.get(
            "url"
        )
        or item.get(
            "link"
        )
    )

    return source_url


def has_valid_source_url(item):
    """
    Confirm that the final source URL is valid.
    """

    source_url = get_source_url(
        item
    )

    return valid_url(
        source_url
    )


# ============================================================
# APPLICATION URL CHECK
# ============================================================

def get_application_url(item):
    """
    Return a valid application URL when available.
    """

    application_url = clean(
        item.get(
            "application_url"
        )
    )

    if valid_url(
        application_url
    ):

        return application_url

    return ""


# ============================================================
# OPPORTUNITY METADATA
# ============================================================

def get_category(item):
    """
    Preserve the category detected by the verification
    engine.
    """

    category = clean(
        item.get(
            "detected_category"
        )
        or item.get(
            "opportunity_type"
        )
        or item.get(
            "category"
        )
        or item.get(
            "type"
        )
    )

    if category:
        return category

    return "opportunities"


def get_location(item):
    """
    Preserve detected geographic information.
    """

    return clean(
        item.get(
            "detected_location"
        )
        or item.get(
            "location"
        )
        or item.get(
            "country"
        )
        or item.get(
            "region"
        )
    )


def get_deadline(item):
    """
    Preserve detected deadline information.
    """

    return clean(
        item.get(
            "detected_deadline"
        )
        or item.get(
            "deadline"
        )
        or item.get(
            "application_deadline"
        )
        or item.get(
            "closing_date"
        )
    )


# ============================================================
# APPROVAL DECISION
# ============================================================

def approve(item):

    title = clean(
        item.get(
            "title"
        )
    )

    # --------------------------------------------------------
    # 1. Title
    # --------------------------------------------------------

    if not title:

        return False, (
            "Missing title"
        )

    # --------------------------------------------------------
    # 2. Source URL
    # --------------------------------------------------------

    source_url = get_source_url(
        item
    )

    if not valid_url(
        source_url
    ):

        return False, (
            "Invalid or missing official/source URL"
        )

    # --------------------------------------------------------
    # 3. Verification engine
    # --------------------------------------------------------

    if not passed_verification_engine(
        item
    ):

        return False, (
            "Opportunity did not pass "
            "the verification engine"
        )

    # --------------------------------------------------------
    # 4. Explicit human-review protection
    # --------------------------------------------------------

    if requires_human_review(
        item
    ):

        return False, (
            "Human review is required; "
            "automatic approval is blocked"
        )

    # --------------------------------------------------------
    # 5. Deadline protection
    # --------------------------------------------------------

    deadline = get_deadline(
        item
    )

    if deadline and deadline_is_expired(
        deadline
    ):

        return False, (
            "The detected application deadline "
            "has already passed"
        )

    # --------------------------------------------------------
    # 6. Classification
    # --------------------------------------------------------

    classification = clean(
        item.get(
            "opportunity_classification"
        )
    )

    if classification in REJECTED_CLASSIFICATIONS:

        return False, (
            f"Classification '{classification}' "
            "is not eligible for automatic approval"
        )

    if not is_auto_approvable_classification(
        item
    ):

        return False, (
            "Opportunity classification is not "
            "approved for automatic publication"
        )

    # --------------------------------------------------------
    # 7. Source verification
    # --------------------------------------------------------

    source_verified = bool(
        item.get(
            "source_verified",
            False
        )
    )

    if not source_verified:

        return False, (
            "Source has not passed "
            "source verification"
        )

    # --------------------------------------------------------
    # 8. Page reachability
    # --------------------------------------------------------

    page_reachable = bool(
        item.get(
            "page_reachable",
            False
        )
    )

    if not page_reachable:

        return False, (
            "Source page is not reachable"
        )

    # --------------------------------------------------------
    # 9. Opportunity relevance
    # --------------------------------------------------------

    opportunity_relevant = bool(
        item.get(
            "opportunity_relevant",
            False
        )
    )

    if not opportunity_relevant:

        return False, (
            "Source page is not recognized "
            "as a sufficiently relevant opportunity"
        )

    # --------------------------------------------------------
    # 10. Required opportunity keyword
    # --------------------------------------------------------

    if not has_opportunity_keyword(
        item
    ):

        return False, (
            "No recognized opportunity keyword "
            "was detected"
        )

    # --------------------------------------------------------
    # 11. Score
    # --------------------------------------------------------

    score = get_score(
        item
    )

    if not passes_score_threshold(
        item
    ):

        return False, (
            "Opportunity evidence score "
            f"{score:g} is below the minimum "
            f"automatic approval threshold of "
            f"{MINIMUM_AUTO_APPROVAL_SCORE}"
        )

    # --------------------------------------------------------
    # 12. Strong evidence
    # --------------------------------------------------------

    if REQUIRE_STRONG_EVIDENCE:

        if not has_strong_evidence(
            item
        ):

            return False, (
                "No strong opportunity evidence "
                "was detected for automatic publication"
            )

    # --------------------------------------------------------
    # 13. News protection
    # --------------------------------------------------------

    if is_news_heavy(
        item
    ):

        return False, (
            "Content contains strong news/general-reporting "
            "signals without enough opportunity evidence"
        )

    # --------------------------------------------------------
    # 14. Source URL sanity
    # --------------------------------------------------------

    final_url = clean(
        item.get(
            "final_url"
        )
    )

    official_url = clean(
        item.get(
            "official_url"
        )
    )

    if final_url and not valid_url(
        final_url
    ):

        return False, (
            "Final resolved URL is invalid"
        )

    if official_url and not valid_url(
        official_url
    ):

        return False, (
            "Official URL is invalid"
        )

    # --------------------------------------------------------
    # 15. Approval
    # --------------------------------------------------------

    if classification == (
        "confirmed_opportunity"
    ):

        return True, (
            "Approved: confirmed opportunity with "
            "valid source, reachable page, strong "
            f"evidence and score {score:g}"
        )

    if classification == (
        "trusted_opportunity"
    ):

        return True, (
            "Approved: trusted opportunity with "
            "valid source, reachable page, strong "
            f"evidence and score {score:g}"
        )

    return False, (
        "Opportunity did not satisfy the final "
        "automatic publication rules"
    )


# ============================================================
# ENRICH APPROVED RECORD
# ============================================================

def enrich_approved_item(
    item,
    reason
):
    """
    Preserve the complete verified record and add explicit
    approval metadata used by the article generator and
    homepage updater.
    """

    updated = dict(
        item
    )

    source_url = get_source_url(
        item
    )

    application_url = get_application_url(
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

    score = get_score(
        item
    )

    updated[
        "approval_status"
    ] = "approved"

    updated[
        "approval_reason"
    ] = reason

    updated[
        "approval_score"
    ] = score

    updated[
        "approval_category"
    ] = category

    updated[
        "approval_location"
    ] = location

    updated[
        "approval_deadline"
    ] = deadline

    updated[
        "official_url"
    ] = (
        clean(
            item.get(
                "official_url"
            )
        )
        or source_url
    )

    updated[
        "application_url"
    ] = application_url

    updated[
        "approval_evidence"
    ] = get_strong_evidence(
        item
    )

    updated[
        "approved_for_homepage"
    ] = True

    updated[
        "approved_for_article_generation"
    ] = True

    return updated


# ============================================================
# ENRICH REJECTED RECORD
# ============================================================

def enrich_rejected_item(
    item,
    reason
):
    """
    Preserve rejected records for diagnostics.

    Rejected records are NOT written into approved_items.
    """

    updated = dict(
        item
    )

    updated[
        "approval_status"
    ] = "rejected"

    updated[
        "approval_reason"
    ] = reason

    updated[
        "approved_for_homepage"
    ] = False

    updated[
        "approved_for_article_generation"
    ] = False

    return updated


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=" * 60
    )

    print(
        "OPPORTUNITYBRIDGE APPROVAL ENGINE v3.0"
    )

    print(
        "=" * 60
    )

    print(
        f"Input: {INPUT}"
    )

    print(
        f"Output: {OUTPUT}"
    )

    print()

    # ========================================================
    # INPUT CHECK
    # ========================================================

    if not INPUT.exists():

        raise SystemExit(
            "ERROR: verified_opportunities.json "
            "was not found."
        )

    # ========================================================
    # READ JSON
    # ========================================================

    try:

        data = json.loads(
            INPUT.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:

        raise SystemExit(
            "ERROR: Could not read verification data: "
            f"{error}"
        )

    # ========================================================
    # GET ITEMS
    # ========================================================

    items = data.get(
        "items",
        []
    )

    if not isinstance(
        items,
        list
    ):

        raise SystemExit(
            "ERROR: Verification JSON does not "
            "contain a valid 'items' list."
        )

    approved = []

    rejected = []

    # ========================================================
    # COUNTERS
    # ========================================================

    confirmed_count = 0

    trusted_count = 0

    possible_count = 0

    failed_count = 0

    human_review_count = 0

    news_rejected_count = 0

    low_score_count = 0

    no_strong_evidence_count = 0

    invalid_url_count = 0

    keyword_failed_count = 0

    verification_failed_count = 0

    expired_deadline_count = 0

    # ========================================================
    # PROCESS ITEMS
    # ========================================================

    for index, item in enumerate(
        items,
        start=1
    ):

        title = clean(
            item.get(
                "title"
            )
        )

        classification = clean(
            item.get(
                "opportunity_classification"
            )
        )

        score = get_score(
            item
        )

        print()

        print(
            "-" * 60
        )

        print(
            f"[{index}/{len(items)}] {title}"
        )

        print(
            f"Classification: {classification}"
        )

        print(
            f"Score: {score:g}"
        )

        print(
            "Verification level: "
            f"{clean(item.get('verification_level'))}"
        )

        print(
            "Source trusted: "
            f"{bool(item.get('source_domain_trusted', False))}"
        )

        print(
            "Page reachable: "
            f"{bool(item.get('page_reachable', False))}"
        )

        print(
            "Relevant: "
            f"{bool(item.get('opportunity_relevant', False))}"
        )

        print(
            "Human review: "
            f"{bool(item.get('needs_human_review', False))}"
        )

        # ----------------------------------------------------
        # Approval
        # ----------------------------------------------------

        is_approved, reason = approve(
            item
        )

        if is_approved:

            approved_item = (
                enrich_approved_item(
                    item,
                    reason
                )
            )

            approved.append(
                approved_item
            )

            if classification == (
                "confirmed_opportunity"
            ):

                confirmed_count += 1

            elif classification == (
                "trusted_opportunity"
            ):

                trusted_count += 1

            print(
                "STATUS: APPROVED"
            )

            print(
                f"Reason: {reason}"
            )

        else:

            rejected_item = (
                enrich_rejected_item(
                    item,
                    reason
                )
            )

            rejected.append(
                rejected_item
            )

            # ------------------------------------------------
            # Diagnostic counters
            # ------------------------------------------------

            if classification == (
                "possible_opportunity"
            ):

                possible_count += 1

            if classification in {
                "failed",
                "likely_news_or_general_content",
                "insufficient_opportunity_evidence",
                "expired_opportunity",
            }:

                failed_count += 1

            if bool(
                item.get(
                    "needs_human_review",
                    False
                )
            ):

                human_review_count += 1

            if is_news_heavy(
                item
            ):

                news_rejected_count += 1

            if not passes_score_threshold(
                item
            ):

                low_score_count += 1

            if (
                REQUIRE_STRONG_EVIDENCE
                and not has_strong_evidence(
                    item
                )
            ):

                no_strong_evidence_count += 1

            if not has_valid_source_url(
                item
            ):

                invalid_url_count += 1

            if not has_opportunity_keyword(
                item
            ):

                keyword_failed_count += 1

            if not passed_verification_engine(
                item
            ):

                verification_failed_count += 1

            deadline = get_deadline(
                item
            )

            if deadline and deadline_is_expired(
                deadline
            ):

                expired_deadline_count += 1

            print(
                "STATUS: REJECTED"
            )

            print(
                f"Reason: {reason}"
            )

    # ========================================================
    # GENERATION TIME
    # ========================================================

    generated_at = datetime.now(
        timezone.utc
    ).isoformat()

    # ========================================================
    # OUTPUT
    # ========================================================
    #
    # IMPORTANT:
    #
    # approved_items contains ONLY automatically approved
    # opportunities.
    #
    # rejected_items is included for diagnostics, but article
    # generation should use approved_items only.
    # ========================================================

    result = {

        "approval_engine_version": "3.0",

        "generated_at": generated_at,

        "verification_generated_at": data.get(
            "generated_at",
            ""
        ),

        "total_checked": len(
            items
        ),

        "approved_count": len(
            approved
        ),

        "rejected_count": len(
            rejected
        ),

        "confirmed_opportunity_count": (
            confirmed_count
        ),

        "trusted_opportunity_count": (
            trusted_count
        ),

        "possible_opportunity_count": (
            possible_count
        ),

        "failed_count": (
            failed_count
        ),

        "human_review_required_count": (
            human_review_count
        ),

        "news_rejected_count": (
            news_rejected_count
        ),

        "low_score_rejected_count": (
            low_score_count
        ),

        "no_strong_evidence_rejected_count": (
            no_strong_evidence_count
        ),

        "invalid_url_rejected_count": (
            invalid_url_count
        ),

        "keyword_failed_count": (
            keyword_failed_count
        ),

        "verification_failed_count": (
            verification_failed_count
        ),

        "expired_deadline_count": (
            expired_deadline_count
        ),

        "minimum_auto_approval_score": (
            MINIMUM_AUTO_APPROVAL_SCORE
        ),

        "require_strong_evidence": (
            REQUIRE_STRONG_EVIDENCE
        ),

        "auto_approvable_classifications": (
            sorted(
                AUTO_APPROVABLE_CLASSIFICATIONS
            )
        ),

        "allowed_verification_levels": (
            sorted(
                ALLOWED_VERIFICATION_LEVELS
            )
        ),

        "approved_items": approved,

        "rejected_items": rejected,
    }

    # ========================================================
    # CREATE OUTPUT DIRECTORY
    # ========================================================

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # ========================================================
    # WRITE OUTPUT
    # ========================================================

    OUTPUT.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    # ========================================================
    # FINAL REPORT
    # ========================================================

    print()

    print(
        "=" * 60
    )

    print(
        "APPROVAL COMPLETE"
    )

    print(
        "=" * 60
    )

    print(
        f"Checked: {len(items)}"
    )

    print(
        f"Approved: {len(approved)}"
    )

    print(
        f"Rejected: {len(rejected)}"
    )

    print(
        f"Confirmed opportunities: "
        f"{confirmed_count}"
    )

    print(
        f"Trusted opportunities: "
        f"{trusted_count}"
    )

    print(
        f"Possible opportunities rejected: "
        f"{possible_count}"
    )

    print(
        f"Failed classifications: "
        f"{failed_count}"
    )

    print(
        f"Human review required: "
        f"{human_review_count}"
    )

    print(
        f"News/general content rejected: "
        f"{news_rejected_count}"
    )

    print(
        f"Low-score rejections: "
        f"{low_score_count}"
    )

    print(
        f"No strong evidence rejections: "
        f"{no_strong_evidence_count}"
    )

    print(
        f"Invalid URL rejections: "
        f"{invalid_url_count}"
    )

    print(
        f"Keyword failures: "
        f"{keyword_failed_count}"
    )

    print(
        f"Verification failures: "
        f"{verification_failed_count}"
    )

    print(
        f"Expired deadline rejections: "
        f"{expired_deadline_count}"
    )

    print()

    print(
        f"Minimum auto-approval score: "
        f"{MINIMUM_AUTO_APPROVAL_SCORE}"
    )

    print(
        f"Strong evidence required: "
        f"{REQUIRE_STRONG_EVIDENCE}"
    )

    print()

    print(
        "Allowed verification levels: "
        f"{sorted(ALLOWED_VERIFICATION_LEVELS)}"
    )

    print(
        "Auto-approvable classifications: "
        f"{sorted(AUTO_APPROVABLE_CLASSIFICATIONS)}"
    )

    print()

    print(
        f"Saved: {OUTPUT}"
    )

    print(
        "=" * 60
    )

    print(
        "OPPORTUNITYBRIDGE APPROVAL "
        "ENGINE COMPLETE"
    )


if __name__ == "__main__":
    main()
