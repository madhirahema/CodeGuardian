Here's the updated README — I added a **Troubleshooting** section documenting the real issues we hit and fixed (this is genuinely useful for your project writeup too, since it shows you debugged a real integration end-to-end).**How to apply it:**

1. Open `README.md` in VS Code
2. Ctrl+A, Delete
3. Paste this in:

```markdown
# 🛡️ CodeGuardian

Multilingual AI code review assistant, powered by Groq. Works two ways:

1. **Streamlit app** — paste code, get an instant review.
2. **GitHub PR bot** — runs automatically on every pull request and posts the
   review as a real PR review (comment or "request changes"), no copy/paste
   needed.

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
2. Add a repository secret named `GROQ_API_KEY` with your Groq key. Paste
   carefully — a stray trailing space or newline in the secret value will
   break every request (see Troubleshooting below).
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

## Roadmap

- [x] Level 1 — Groq + Streamlit single-shot review
- [x] Level 2 — Multi-language support
- [ ] Level 3 — Combine LLM review with static analyzers (Ruff/Bandit for
      Python, ESLint for JS, Semgrep as a general fallback)
- [x] Level 4 — GitHub PR integration (comments/request-changes on PRs)
- [ ] Level 5 — Split into specialized agents (bug / security / quality) with
      a verification pass before the final review

## Troubleshooting

**Workflow fails with "Invalid workflow file" / YAML syntax error**
Usually a stray tab character or duplicated steps in
`.github/workflows/codeguardian.yml`. Fix by replacing the whole file rather
than patching a section — mixed tabs/spaces are invisible in most editors.

**`APIConnectionError: Connection error` from Groq, every file fails**
This can have two different causes:
- *Library/network issue* — rare with a current `groq` version, but confirm
  with a manual connectivity check:
  ```yaml
  - name: Test connectivity to Groq
    run: curl -v https://api.groq.com/openai/v1/models -H "Authorization: Bearer ${{ secrets.GROQ_API_KEY }}"
  ```
  If this `curl` succeeds but the Python client still fails, it's not network.
- *Malformed secret* (most common cause) — if the underlying error is
  `httpx.LocalProtocolError: Illegal header value`, the `GROQ_API_KEY` secret
  has an invalid character in it, almost always a trailing newline or space
  picked up when it was copy-pasted into GitHub's secret box. Re-copy the key
  fresh from console.groq.com and re-save the secret. `reviewer/ai_reviewer.py`
  also defensively calls `.strip()` on the key when reading it, to guard
  against this going forward.

**Want more detail from a failure than "Review failed: ..."?**
`github/pr_reviewer.py` prints a full traceback plus the exception's
`__cause__` to stdout for any file that fails, so check the raw Actions log
(not just the PR comment) for the real root cause.
```

4. Save

**Push it to GitHub:**

```powershell
git add .
git commit -m "docs: update README with troubleshooting section"
git push
```

If you're still on the `test-pr-review` branch, this pushes to the same PR. If you've since merged that PR and switched back to `main`, run this first:

```powershell
git checkout main
git pull
```
then make the README edit there and push directly (no PR needed for a docs-only change on main, unless you want one).
