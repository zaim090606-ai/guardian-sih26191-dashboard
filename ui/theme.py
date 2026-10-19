"""Classic editorial theme: one CSS block injected once per run.

Ivory page, ink-navy text, antique-gold rules, serif headings. Presentation
only; no scoring or data logic lives here.
"""

import streamlit as st

IVORY = "#FAF6EE"
SURFACE = "#FFFDF8"
INK = "#14213D"
GOLD = "#A8782A"
GOLD_TEXT = "#8A6220"  # darker gold for text on ivory (>= 4.5:1)
SLATE = "#2F6F73"
RULE = "#E1D8C3"
MUTED = "#4A5568"

FONTS_URL = (
    "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700"
    "&family=Inter:wght@400;500;600&display=swap"
)


def build_css():
    return f"""
@import url('{FONTS_URL}');
:root {{
  --ivory:{IVORY}; --surface:{SURFACE}; --ink:{INK}; --gold:{GOLD}; --gold-text:{GOLD_TEXT};
  --slate:{SLATE}; --rule:{RULE}; --muted:{MUTED};
  --serif:'Cormorant Garamond','Playfair Display',Georgia,'Times New Roman',serif;
  --sans:Inter,'Source Sans 3','Segoe UI',system-ui,sans-serif;
}}
html, body, .stApp, [data-testid="stAppViewContainer"] {{ background:var(--ivory); color:var(--ink); }}
.stApp, .stApp p, .stApp li, .stApp label, .stApp td, .stApp th, .stApp input, .stApp button {{
  font-family:var(--sans);
}}
[data-testid="stIconMaterial"], .material-icons, [class*="material-symbols"] {{ font-family:'Material Symbols Rounded' !important; }}
.stApp p, .stApp li, .stApp label, [data-testid="stMarkdownContainer"] {{ font-size:1rem; line-height:1.65; }}
[data-testid="stHeader"] {{ background:transparent; }}
.block-container {{ padding-top:1.6rem; max-width:78rem; }}

h1, h2, h3, h4, .stApp [data-testid="stHeading"] *, .stApp [data-testid="stHeadingWithActionElements"] * {{
  font-family:var(--serif) !important; color:var(--ink); font-weight:600; letter-spacing:.005em;
}}
h1 {{ font-size:2.5rem; line-height:1.15; }}
h2, h3 {{ border-bottom:1px solid var(--gold); padding-bottom:.25rem; margin-top:1.4rem; }}
h2 {{ font-size:1.8rem; }} h3 {{ font-size:1.45rem; }}
a {{ color:var(--slate); }}
.stApp [data-testid="stCaptionContainer"], .stApp small {{ color:var(--muted); opacity:1; }}
hr {{ border:0; border-top:1px solid var(--rule); }}

.gd-title {{ font-family:var(--serif); font-size:2.6rem; font-weight:700; line-height:1.1; margin:.9rem 0 .1rem; color:var(--ink); }}
.gd-subtitle {{ font-family:var(--serif); font-style:italic; font-size:1.3rem; color:var(--muted); margin:0 0 .6rem;
  padding-bottom:.6rem; border-bottom:1px solid var(--gold); }}
.gd-smallcaps {{ font-variant:small-caps; letter-spacing:.08em; color:var(--gold-text); font-weight:600; }}

[data-baseweb="tab-list"] {{ gap:.25rem; border-bottom:1px solid var(--rule); flex-wrap:wrap; }}
button[data-baseweb="tab"] {{ background:transparent; color:var(--muted); font-weight:500; padding:.5rem .9rem; }}
button[data-baseweb="tab"][aria-selected="true"] {{ color:var(--ink); font-weight:600; }}
[data-baseweb="tab-highlight"] {{ background-color:var(--gold) !important; height:3px; }}
[data-baseweb="tab-border"] {{ background-color:var(--rule) !important; }}

[data-testid="stMetric"] {{ background:var(--surface); border:1px solid var(--rule); border-radius:6px;
  padding:.8rem 1rem; box-shadow:0 1px 3px rgba(20,33,61,.06); }}
[data-testid="stMetricLabel"] {{ font-variant:small-caps; letter-spacing:.06em; color:var(--muted); }}
[data-testid="stMetricValue"] {{ font-family:var(--serif); color:var(--gold-text); font-weight:700; }}

.stButton > button, .stDownloadButton > button {{ background:var(--surface); color:var(--ink);
  border:1px solid var(--gold); border-radius:4px; font-weight:500; }}
.stButton > button:hover, .stDownloadButton > button:hover {{ background:var(--gold); color:#fff; border-color:var(--gold); }}
.stButton > button:focus-visible, button[data-baseweb="tab"]:focus-visible {{ outline:2px solid var(--slate); outline-offset:2px; }}

[data-testid="stExpander"] {{ background:var(--surface); border:1px solid var(--rule); border-radius:6px;
  box-shadow:0 1px 3px rgba(20,33,61,.05); }}
[data-testid="stExpander"] summary {{ font-weight:600; }}
[data-testid="stDataFrame"] {{ border:1px solid var(--rule); border-radius:6px; background:var(--surface); }}
[data-testid="stAlert"] {{ border-radius:6px; }}

[data-testid="stSidebar"] {{ background:#F2ECDD; border-right:1px solid var(--rule); }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 {{ font-size:1.5rem; border-bottom:1px solid var(--gold); }}

iframe {{ border:0; }}
.gd-hero-frame iframe {{ border-radius:10px; }}

@media (max-width:640px) {{
  .block-container {{ padding-left:1rem; padding-right:1rem; }}
  .gd-title {{ font-size:1.9rem; }} .gd-subtitle {{ font-size:1.1rem; }}
  button[data-baseweb="tab"] {{ padding:.4rem .6rem; }}
}}
"""


def inject_theme():
    """Inject the stylesheet. Call once, near the top of the app."""
    st.markdown(f"<style>{build_css()}</style>", unsafe_allow_html=True)


def render_masthead(title="Guardian: Adaptive Relocation Intelligence",
                    subtitle="Evidence-weighted relocation priorities, with reasons."):
    st.markdown(
        f'<div class="gd-title">{title}</div><div class="gd-subtitle">{subtitle}</div>',
        unsafe_allow_html=True,
    )
