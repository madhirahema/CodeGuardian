"""Runs inside GitHub Actions on every pull_request event.

Flow:
  1. Read PR context from environment variables (set by the workflow).
  2. Fetch the list of changed files + their diffs from the GitHub REST API.
  3. Skip files CodeGuardian shouldn't review (binary, lockfiles, huge diffs).
  4. Send each file's diff to CodeGuardian's review engine (Groq LLM).
  5. Combine results into one PR review:
       - REQUEST_CHANGES if any file has a Critical/High finding
       - COMMENT otherwise
  6. Post the review to GitHub via the Pulls "create a review" endpoint.

Required env vars (all provided automatically by the workflow, except the
two secrets):
  GITHUB_TOKEN     - provided by Actions, needs `pull-requests: write`
  GITHUB_REPOSITORY- e.g. "owner/repo", provided by Actions
  PR_NUMBER        - the pull request number, passed in by the workflow
  GROQ_API_KEY     - repository secret, your Groq key
"""

import os
import sys
import traceback

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reviewer.ai_reviewer import review_code
from reviewer.language_detector import detect_by_filename

GITHUB_API = "https://api.github.com"

# Don't waste LLM calls (or noise the PR) on these.
SKIP_SUFFIXES = (
    ".lock", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".pdf",
    ".zip", ".min.js", ".min.css",
)
SKIP_EXACT = {"package-lock.json", "yarn.lock", "poetry.lock", "Pipfile.lock"}

# Cap per-file diff size sent to the model to keep this fast/cheap.
MAX_PATCH_CHARS = 8000
SEVERITY_RANK = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, "None": 0}


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_changed_files(repo: str, pr_number: str, token: str) -> list[dict]:
    files = []
    page = 1
    while True:
        url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/files"
        resp = requests.get(
            url, headers=_headers(token), params={"per_page": 100, "page": page}
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        files.extend(batch)
        page += 1
    return files


def should_skip(filename: str) -> bool:
    base = filename.rsplit("/", 1)[-1]
    if base in SKIP_EXACT:
        return True
    return filename.lower().endswith(SKIP_SUFFIXES)


def post_review(repo: str, pr_number: str, token: str, body: str, event: str) -> None:
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/reviews"
    resp = requests.post(
        url, headers=_headers(token), json={"body": body, "event": event}
    )
    resp.raise_for_status()


def main() -> None:
    repo = os.environ["GITHUB_REPOSITORY"]
    pr_number = os.environ["PR_NUMBER"]
    token = os.environ["GITHUB_TOKEN"]

    files = get_changed_files(repo, pr_number, token)
    if not files:
        print("No changed files found; nothing to review.")
        return

    sections = []
    worst_severity = "None"

    for f in files:
        filename = f["filename"]
        patch = f.get("patch")  # unified diff for this file; absent for binaries/large files

        if should_skip(filename) or not patch:
            continue

        language = detect_by_filename(filename)
        diff_text = patch[:MAX_PATCH_CHARS]

        print(f"Reviewing {filename} ({language})...")
        try:
            result = review_code(diff_text, language)
        except Exception as e:  # noqa: BLE001 - surface any API failure per-file
            print(f"--- Full traceback for {filename} ---", flush=True)
            traceback.print_exc(file=sys.stdout)
            cause = getattr(e, "__cause__", None)
            if cause is not None:
                print(f"UNDERLYING CAUSE: {type(cause).__name__}: {cause}", flush=True)
            else:
                print("UNDERLYING CAUSE: none captured on the exception object", flush=True)
            print("--- end traceback ---", flush=True)
            sections.append(f"### `{filename}`\n\n⚠️ Review failed: {e}\n")
            continue

        if SEVERITY_RANK.get(result["severity"], 0) > SEVERITY_RANK.get(worst_severity, 0):
            worst_severity = result["severity"]

        badge = {
            "Critical": "🔴 Critical",
            "High": "🟠 High",
            "Medium": "🟡 Medium",
            "Low": "🔵 Low",
            "None": "🟢 Clean",
        }.get(result["severity"], result["severity"])

        sections.append(f"### `{filename}` — {badge}\n\n{result['review']}\n")

    if not sections:
        print("No reviewable files (all skipped or had no textual diff).")
        return

    header = "## 🛡️ CodeGuardian Review\n\n"
    footer = (
        "\n---\n*Automated review by CodeGuardian. This does not replace human "
        "review — please verify findings before acting on them.*"
    )
    body = header + "\n".join(sections) + footer

    event = "REQUEST_CHANGES" if worst_severity in ("Critical", "High") else "COMMENT"

    post_review(repo, pr_number, token, body, event)
    print(f"Posted review as {event} (worst severity: {worst_severity}).")


if __name__ == "__main__":
    main()"""Runs inside GitHub Actions on every pull_request event.

Flow:
  1. Read PR context from environment variables (set by the workflow).
  2. Fetch the list of changed files + their diffs from the GitHub REST API.
  3. Skip files CodeGuardian shouldn't review (binary, lockfiles, huge diffs).
  4. Send each file's diff to CodeGuardian's review engine (Groq LLM).
  5. Combine results into one PR review:
       - REQUEST_CHANGES if any file has a Critical/High finding
       - COMMENT otherwise
  6. Post the review to GitHub via the Pulls "create a review" endpoint.

Required env vars (all provided automatically by the workflow, except the
two secrets):
  GITHUB_TOKEN     - provided by Actions, needs `pull-requests: write`
  GITHUB_REPOSITORY- e.g. "owner/repo", provided by Actions
  PR_NUMBER        - the pull request number, passed in by the workflow
  GROQ_API_KEY     - repository secret, your Groq key
"""

import os
import sys
import traceback

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reviewer.ai_reviewer import review_code
from reviewer.language_detector import detect_by_filename

GITHUB_API = "https://api.github.com"

# Don't waste LLM calls (or noise the PR) on these.
SKIP_SUFFIXES = (
    ".lock", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".pdf",
    ".zip", ".min.js", ".min.css",
)
SKIP_EXACT = {"package-lock.json", "yarn.lock", "poetry.lock", "Pipfile.lock"}

# Cap per-file diff size sent to the model to keep this fast/cheap.
MAX_PATCH_CHARS = 8000
SEVERITY_RANK = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, "None": 0}


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_changed_files(repo: str, pr_number: str, token: str) -> list[dict]:
    files = []
    page = 1
    while True:
        url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/files"
        resp = requests.get(
            url, headers=_headers(token), params={"per_page": 100, "page": page}
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        files.extend(batch)
        page += 1
    return files


def should_skip(filename: str) -> bool:
    base = filename.rsplit("/", 1)[-1]
    if base in SKIP_EXACT:
        return True
    return filename.lower().endswith(SKIP_SUFFIXES)


def post_review(repo: str, pr_number: str, token: str, body: str, event: str) -> None:
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/reviews"
    resp = requests.post(
        url, headers=_headers(token), json={"body": body, "event": event}
    )
    resp.raise_for_status()


def main() -> None:
    repo = os.environ["GITHUB_REPOSITORY"]
    pr_number = os.environ["PR_NUMBER"]
    token = os.environ["GITHUB_TOKEN"]

    files = get_changed_files(repo, pr_number, token)
    if not files:
        print("No changed files found; nothing to review.")
        return

    sections = []
    worst_severity = "None"

    for f in files:
        filename = f["filename"]
        patch = f.get("patch")  # unified diff for this file; absent for binaries/large files

        if should_skip(filename) or not patch:
            continue

        language = detect_by_filename(filename)
        diff_text = patch[:MAX_PATCH_CHARS]

        print(f"Reviewing {filename} ({language})...")
        try:
            result = review_code(diff_text, language)
        except Exception as e:  # noqa: BLE001 - surface any API failure per-file
            print(f"--- Full traceback for {filename} ---", flush=True)
            traceback.print_exc(file=sys.stdout)
            cause = getattr(e, "__cause__", None)
            if cause is not None:
                print(f"UNDERLYING CAUSE: {type(cause).__name__}: {cause}", flush=True)
            else:
                print("UNDERLYING CAUSE: none captured on the exception object", flush=True)
            print("--- end traceback ---", flush=True)
            sections.append(f"### `{filename}`\n\n⚠️ Review failed: {e}\n")
            continue

        if SEVERITY_RANK.get(result["severity"], 0) > SEVERITY_RANK.get(worst_severity, 0):
            worst_severity = result["severity"]

        badge = {
            "Critical": "🔴 Critical",
            "High": "🟠 High",
            "Medium": "🟡 Medium",
            "Low": "🔵 Low",
            "None": "🟢 Clean",
        }.get(result["severity"], result["severity"])

        sections.append(f"### `{filename}` — {badge}\n\n{result['review']}\n")

    if not sections:
        print("No reviewable files (all skipped or had no textual diff).")
        return

    header = "## 🛡️ CodeGuardian Review\n\n"
    footer = (
        "\n---\n*Automated review by CodeGuardian. This does not replace human "
        "review — please verify findings before acting on them.*"
    )
    body = header + "\n".join(sections) + footer

    event = "REQUEST_CHANGES" if worst_severity in ("Critical", "High") else "COMMENT"

    post_review(repo, pr_number, token, body, event)
    print(f"Posted review as {event} (worst severity: {worst_severity}).")


if __name__ == "__main__":
    main()