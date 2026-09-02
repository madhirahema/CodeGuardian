# 🛡️ CodeGuardian

Multilingual AI code review assistant, powered by Groq. Works two ways:

1. **Streamlit app** — paste code, get an instant review.
2. **GitHub PR bot** — opens automatically on every pull request and posts the
   review as a real PR review (comment or "request changes"), no copy/paste
   needed.

## ⚠️ First: rotate your key

The old `main.py` had a Gemini API key hardcoded in it and pushed to GitHub.
That key is public in your commit history. Go revoke it in
[Google AI Studio](https://aistudio.google.com/app/apikey) now — this project
no longer uses Gemini at all, so nothing needs that key going forward.

## Setup

```bash
pip install -r requirements.txt
```

Create a Groq API key at [console.groq.com](https://console.groq.com), then
create a `.env` file (never committed — see `.gitignore`) based on
`.env.example`:

```
GROQ_API_KEY=your_real_key_here
```

## Run the local app

```bash
streamlit run app.py
```

Pick a language (or leave "Auto Detect"), paste code, click **Review Code**.

## Enable automatic PR reviews

1. In your GitHub repo, go to **Settings → Secrets and variables → Actions**.
2. Add a repository secret named `GROQ_API_KEY` with your Groq key.
3. That's it — `.github/workflows/codeguardian.yml` already triggers on every
   `pull_request` (opened, updated, or reopened) and runs
   `github/pr_reviewer.py`, which:
   - Fetches the PR's changed files via the GitHub API
   - Reviews each file's diff with the same engine as the Streamlit app
   - Posts one combined review to the PR
   - Uses **REQUEST_CHANGES** if any file has a Critical/High finding,
     otherwise **COMMENT** (it never auto-merges or auto-approves)

## Project structure

```
CodeGuardian/
├── app.py                       # Streamlit UI
├── reviewer/
│   ├── ai_reviewer.py           # Groq call + severity parsing (shared)
│   └── language_detector.py     # extension + keyword based detection
├── github/
│   └── pr_reviewer.py           # GitHub PR bot logic
├── prompts/
│   └── review_prompt.txt        # shared review prompt template
├── .github/workflows/
│   └── codeguardian.yml         # Actions workflow
├── .env.example
├── .gitignore
└── requirements.txt
```

## Roadmap (from the original design)

- [x] Level 1 — Groq + Streamlit single-shot review
- [x] Level 2 — Multi-language support
- [ ] Level 3 — Combine LLM review with static analyzers (Ruff/Bandit for
      Python, ESLint for JS, Semgrep as a general fallback)
- [x] Level 4 — GitHub PR integration (comments/request-changes on PRs)
- [ ] Level 5 — Split into specialized agents (bug / security / quality) with
      a verification pass before the final review
