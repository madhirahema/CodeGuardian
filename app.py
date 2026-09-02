import streamlit as st
from dotenv import load_dotenv

from reviewer.ai_reviewer import review_code
from reviewer.language_detector import LANGUAGES, detect_by_keywords

load_dotenv()

st.set_page_config(page_title="CodeGuardian", page_icon="🛡️", layout="wide")

st.title("🛡️ CodeGuardian")
st.write(
    "Multilingual AI Code Review Assistant — analyzes source code for bugs, "
    "security issues, code-quality problems, and possible improvements."
)

language = st.selectbox("Programming Language", LANGUAGES)

code = st.text_area(
    "Paste your code",
    height=400,
    placeholder="Paste source code here...",
)

if st.button("🔍 Review Code"):
    if not code.strip():
        st.warning("Please enter some code.")
        st.stop()

    effective_language = language
    if language == "Auto Detect":
        effective_language = detect_by_keywords(code)
        st.caption(f"Detected language: **{effective_language}**")

    with st.spinner("CodeGuardian is analyzing your code..."):
        try:
            result = review_code(code, effective_language)
        except RuntimeError as e:
            st.error(str(e))
            st.stop()

    severity_badge = {
        "Critical": "🔴 Critical",
        "High": "🟠 High",
        "Medium": "🟡 Medium",
        "Low": "🔵 Low",
        "None": "🟢 No significant issues",
    }.get(result["severity"], result["severity"])

    st.subheader(f"📝 Review — {severity_badge}")
    st.markdown(result["review"])
