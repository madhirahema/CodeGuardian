"""Lightweight language detection: by file extension first (used for GitHub PR
files, which always have a filename), with a small keyword-based fallback for
pasted code that has no filename (used by the Streamlit app's Auto Detect)."""

EXTENSION_MAP = {
    ".py": "Python",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".swift": "Swift",
    ".sql": "SQL",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".rb": "Ruby",
    ".sh": "Shell",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
}

LANGUAGES = [
    "Auto Detect", "Python", "Java", "JavaScript", "TypeScript", "C", "C++",
    "C#", "Go", "Rust", "PHP", "Kotlin", "Swift", "Ruby", "SQL", "HTML",
    "CSS", "Other",
]


def detect_by_filename(filename: str) -> str:
    """Return a language name based on a file's extension. Falls back to
    'Other' for unrecognized or extensionless files (e.g. Dockerfile)."""
    for ext, lang in EXTENSION_MAP.items():
        if filename.lower().endswith(ext):
            return lang
    return "Other"


def detect_by_keywords(code: str) -> str:
    """Very rough heuristic fallback for pasted code with no filename."""
    snippet = code.strip()
    checks = [
        ("Python", ("def ", "import ", "print(", "self.", "elif ")),
        ("Java", ("public class", "System.out.println", "public static void main")),
        ("C++", ("#include", "std::", "cout <<")),
        ("C", ("#include", "printf(", "int main(")),
        ("JavaScript", ("function ", "const ", "let ", "=>", "console.log")),
        ("TypeScript", ("interface ", ": string", ": number")),
        ("Go", ("package main", "func main(", "fmt.Println")),
        ("Rust", ("fn main(", "let mut", "println!")),
        ("PHP", ("<?php",)),
        ("HTML", ("<!DOCTYPE", "<html")),
        ("SQL", ("SELECT ", "INSERT INTO", "CREATE TABLE")),
    ]
    for lang, markers in checks:
        if any(m in snippet for m in markers):
            return lang
    return "Other"
