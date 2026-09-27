"""Core CodeGuardian review engine.

Both the Streamlit app (app.py) and the GitHub PR bot
(github/pr_reviewer.py) call review_code() so feedback is generated
the same way everywhere.
"""

import os
import re
import time
from pathlib import Path

from groq import Groq


MODEL = os.getenv("CODEGUARDIAN_MODEL", "openai/gpt-oss-120b")

MAX_RETRIES = int(os.getenv("CODEGUARDIAN_MAX_RETRIES", "3"))
REQUEST_TIMEOUT = float(os.getenv("CODEGUARDIAN_TIMEOUT", "60"))

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "prompts"
    / "review_prompt.txt"
)

_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")

_SYSTEM_PROMPT = (
    "You are CodeGuardian, a professional multilingual code reviewer. "
    "Analyze code carefully for security vulnerabilities, bugs, reliability "
    "issues, and code-quality problems. Do not invent vulnerabilities."
)

_SEVERITY_LINE_RE = re.compile(
    r"OVERALL_SEVERITY:\s*(Critical|High|Medium|Low|None)",
    re.IGNORECASE,
)


def _get_client() -> Groq:
    """Create a Groq client using the configured API key."""

    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Put it in a .env file locally, "
            "or as a repository secret named GROQ_API_KEY for GitHub Actions."
        )

    return Groq(
        api_key=api_key,
        timeout=REQUEST_TIMEOUT,
        max_retries=0,
    )


def _call_groq(client: Groq, prompt: str):
    """Call Groq with explicit retry handling."""

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": _SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.2,
                max_tokens=4000,
                include_reasoning=False,
            )

        except Exception as exc:
            last_error = exc

            if attempt >= MAX_RETRIES:
                raise

            wait_seconds = 2 ** (attempt - 1)

            print(
                f"Groq request failed "
                f"(attempt {attempt}/{MAX_RETRIES}): "
                f"{type(exc).__name__}: {exc}"
            )
            print(f"Retrying in {wait_seconds}s...")

            time.sleep(wait_seconds)

    raise last_error


def review_code(code: str, language: str = "Auto Detect") -> dict:
    """Send code or a diff to Groq and return the review.

    Returns:
        {
            "review": full markdown review text,
            "severity": one of Critical/High/Medium/Low/None,
        }
    """

    if not code or not code.strip():
        return {
            "review": "No code provided.",
            "severity": "None",
        }

    try:
        prompt = _PROMPT_TEMPLATE.format(
            language=language,
            code=code,
        )
    except KeyError as exc:
        raise RuntimeError(
            f"Invalid placeholder in review_prompt.txt: {exc}"
        ) from exc

    client = _get_client()

    response = _call_groq(client, prompt)

    if not response.choices:
        raise RuntimeError("Groq returned no choices.")

    text = response.choices[0].message.content or ""

    severity = "None"

    match = _SEVERITY_LINE_RE.search(text)

    if match:
        severity = match.group(1).capitalize()
        text = _SEVERITY_LINE_RE.sub("", text).strip()

    return {
        "review": text,
        "severity": severity,
    }