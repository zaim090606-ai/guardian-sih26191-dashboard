"""Brief tab: computed-numbers summary + an on-demand Gemini/template brief
for a state disaster management authority."""

import streamlit as st

import brief
import pipeline


def render_brief_tab(result):
    summary = pipeline.build_brief_summary(result)
    cluster_summaries = brief.summarize_clusters(result["incidents"])

    st.subheader("Computed summary (this is ALL Gemini ever sees)")
    st.json(summary)
    if cluster_summaries:
        st.write("**Corroborated incident clusters (structured fields only):**")
        st.json(cluster_summaries)

    st.caption(
        "Reads GEMINI_API_KEY from the environment; falls back to a plain template "
        "brief with no API call if the key is missing or the call fails."
    )

    if st.button("Generate briefing", key="generate_brief_button"):
        with st.spinner("Drafting briefing..."):
            text = brief.generate_brief(summary, cluster_summaries)
        st.session_state["last_brief_text"] = text

    text = st.session_state.get("last_brief_text")
    if text:
        st.subheader("Briefing for the State Disaster Management Authority")
        st.text(text)
        st.download_button("Download briefing (.txt)", data=text, file_name="guardian_brief.txt")
