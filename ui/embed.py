"""Embed a self-contained HTML block (st.iframe on current Streamlit, else components.html)."""


def embed_html(st, html, height):
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:
        import streamlit.components.v1 as components
        components.html(html, height=height)
