"""Runs inside GitHub Actions on every pull_request event.

Flow:
  1. Read PR context from environment variables.
  2. Fetch the list of changed files + their diffs from the GitHub REST API.
  3. Skip files CodeGuardian shouldn't review.
  4. Send each file's diff to CodeGuardian's review engine.
  5. Combine results into one PR review.
  6. Post the review to GitHub.

Required environment variables:
  GITHUB_TOKEN      - provided by GitHub Actions; needs pull-requests: write
  GITHUB_REPOSITORY - e.g. "owner/repo"
  PR_NUMBER         - pull request number
  GROQ_API_KEY      - repository secret containing your Groq API key
"""

import os
import sys
import traceback

import requests

# Allow imports from the project root.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reviewer.ai_reviewer import review_code
from reviewer.language_detector import detect_by_filename


GITHUB_API = "https://api.github.com"


# Don't waste LLM calls on files that CodeGuardian shouldn't review.
SKIP_SUFFIXES = (
    ".lock",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".pdf",
    ".zip",
    ".min.js",
    ".min.css",
)

SKIP_EXACT = {
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
}


# Cap per-file diff size sent to the model.
MAX_PATCH_CHARS = 8000


SEVERITY_RANK = {
    "Critical": 4,
    "High": 3,
    "Medium": 2,
    "Low": 1,
    "None": 0,
}


def _headers(token: str) -> dict:
    """Build standard GitHub API request headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_changed_files(
    repo: str,
    pr_number: str,
    token: str,
) -> list[dict]:
    """Fetch all changed files for a pull request.

    GitHub returns a maximum of 100 files per page, so pagination is handled
    until an empty response is received.
    """
    files = []
    page = 1

    while True:
        url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/files"

        resp = requests.get(
            url,
            headers=_headers(token),
            params={
                "per_page": 100,
                "page": page,
            },
            timeout=30,
        )

        resp.raise_for_status()

        batch = resp.json()

        if not batch:
            break

        files.extend(batch)
        page += 1

    return files


def should_skip(filename: str) -> bool:
    """Return True if the file should not be reviewed."""
    base = filename.rsplit("/", 1)[-1]

    if base in SKIP_EXACT:
        return True

    return filename.lower().endswith(SKIP_SUFFIXES)


def post_review(
    repo: str,
    pr_number: str,
    token: str,
    body: str,
    event: str,
) -> None:
    """Post a pull-request review to GitHub."""
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/reviews"

    resp = requests.post(
        url,
        headers=_headers(token),
        json={
            "body": body,
            "event": event,
        },
        timeout=30,
    )

    resp.raise_for_status()


def main() -> None:
    """Run the CodeGuardian pull-request review."""
    # Read required environment variables.
    repo = os.environ["GITHUB_REPOSITORY"]
    pr_number = os.environ["PR_NUMBER"]
    token = os.environ["GITHUB_TOKEN"]

    print(f"Fetching changed files for {repo} PR #{pr_number}...")

    files = get_changed_files(
        repo,
        pr_number,
        token,
    )

    if not files:
        print("No changed files found; nothing to review.")
        return

    print(f"Found {len(files)} changed file(s).")

    sections = []
    worst_severity = "None"

    for file_data in files:
        filename = file_data["filename"]

        # GitHub may omit patch for binary files or very large diffs.
        patch = file_data.get("patch")

        if should_skip(filename):
            print(f"Skipping {filename}: excluded file type.")
            continue

        if not patch:
            print(f"Skipping {filename}: no textual diff available.")
            continue

        language = detect_by_filename(filename)

        # Prevent extremely large diffs from being sent to the LLM.
        diff_text = patch[:MAX_PATCH_CHARS]

        if len(patch) > MAX_PATCH_CHARS:
            print(
                f"Truncating diff for {filename} "
                f"from {len(patch)} to {MAX_PATCH_CHARS} characters."
            )

        print(f"Reviewing {filename} ({language})...")

        try:
            result = review_code(
                diff_text,
                language,
            )

        except Exception as exc:  # noqa: BLE001
            print(
                f"--- Full traceback for {filename} ---",
                flush=True,
            )

            traceback.print_exc(file=sys.stdout)

            cause = getattr(exc, "__cause__", None)

            if cause is not None:
                print(
                    f"UNDERLYING CAUSE: "
                    f"{type(cause).__name__}: {cause}",
                    flush=True,
                )
            else:
                print(
                    "UNDERLYING CAUSE: "
                    "none captured on the exception object",
                    flush=True,
                )

            print(
                "--- end traceback ---",
                flush=True,
            )

            sections.append(
                f"### `{filename}`\n\n"
                f"⚠️ Review failed: {exc}\n"
            )

            continue

        # Safely read severity from the LLM response.
        severity = result.get("severity", "None")

        if (
            SEVERITY_RANK.get(severity, 0)
            > SEVERITY_RANK.get(worst_severity, 0)
        ):
            worst_severity = severity

        badge = {
            "Critical": "🔴 Critical",
            "High": "🟠 High",
            "Medium": "🟡 Medium",
            "Low": "🔵 Low",
            "None": "🟢 Clean",
        }.get(
            severity,
            severity,
        )

        review_text = result.get(
            "review",
            "No review details were returned.",
        )

        sections.append(
            f"### `{filename}` — {badge}\n\n"
            f"{review_text}\n"
        )

    if not sections:
        print(
            "No reviewable files "
            "(all skipped or had no textual diff)."
        )
        return

    # Build the final GitHub review body.
    header = "## 🛡️ CodeGuardian Review\n\n"

    footer = (
        "\n---\n"
        "*Automated review by CodeGuardian. "
        "This does not replace human review — "
        "please verify findings before acting on them.*"
    )

    body = (
        header
        + "\n".join(sections)
        + footer
    )

    # Request changes only when the highest severity is Critical or High.
    event = (
        "REQUEST_CHANGES"
        if worst_severity in ("Critical", "High")
        else "COMMENT"
    )

    print(
        f"Posting GitHub review as {event} "
        f"(worst severity: {worst_severity})..."
    )

    post_review(
        repo,
        pr_number,
        token,
        body,
        event,
    )

    print(
        f"Posted review as {event} "
        f"(worst severity: {worst_severity})."
    )


if __name__ == "__main__":
    main()