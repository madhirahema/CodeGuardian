"""Core CodeGuardian review engine. Both the Streamlit app (app.py) and the
GitHub PR bot (github/pr_reviewer.py) call review_code() so feedback is
generated the same way everywhere."""

import os
import re
from pathlib import Path

from groq import Groq

MODEL = "llama-3.3-70b-versatile"

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "review_prompt.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")

_SYSTEM_PROMPT = "You are CodeGuardian, a professional multilingual code reviewer."

_SEVERITY_LINE_RE = re.compile(
    r"OVERALL_SEVERITY:\s*(Critical|High|Medium|Low|None)", re.IGNORECASE
)


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Put it in a .env file locally, or as a "
            "repository secret named GROQ_API_KEY for the GitHub Action."
        )
    return Groq(api_key=api_key)


def review_code(code: str, language: str = "Auto Detect") -> dict:
    """Send code (or a diff) to the LLM and return the review.

    Returns:
        {
            "review": full markdown review text (severity line stripped out),
            "severity": one of Critical/High/Medium/Low/None,
        }
    """
    if not code or not code.strip():
        return {"review": "No code provided.", "severity": "None"}

    prompt = _PROMPT_TEMPLATE.format(language=language, code=code)

    client = _get_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=4000,
    )

    text = response.choices[0].message.content or ""

    severity = "None"
    match = _SEVERITY_LINE_RE.search(text)
    if match:
        severity = match.group(1).capitalize()
        text = _SEVERITY_LINE_RE.sub("", text).strip()

    return {"review": text, "severity": severity}
