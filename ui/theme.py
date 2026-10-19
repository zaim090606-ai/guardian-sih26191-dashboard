"""Classic editorial theme: one CSS block injected once per run.

Ivory paper, ink-navy text, antique-gold rules, serif headings. Presentation
only; no scoring or data logic lives here. Motion is slow and subtle and is
switched off entirely under prefers-reduced-motion.
"""

import streamlit as st

import palette

IVORY = "#FAF6EE"
SURFACE = "#FFFDF8"
INK = "#14213D"
GOLD = "#A8782A"
GOLD_TEXT = "#8A6220"  # darker gold for text on ivory (>= 4.5:1)
SLATE = "#2F6F73"
RULE = "#E1D8C3"
MUTED = "#4A5568"
PANEL = "#F2ECDD"

FONTS_URL = (
    "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700"
    "&family=Inter:wght@400;500;600&display=swap"
)

# Faint paper grain: tiny inline SVG noise, no network request.
GRAIN = (
    "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E"
    "%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/%3E"
    "%3CfeColorMatrix values='0 0 0 0 .35 0 0 0 0 .28 0 0 0 0 .15 0 0 0 .07 0'/%3E%3C/filter%3E"
    "%3Crect width='160' height='160' filter='url(%23n)'/%3E%3C/svg%3E\")"
)


def build_css():
    return f"""
@import url('{FONTS_URL}');
:root {{
  --ivory:{IVORY}; --surface:{SURFACE}; --ink:{INK}; --gold:{GOLD}; --gold-text:{GOLD_TEXT};
  --slate:{SLATE}; --rule:{RULE}; --muted:{MUTED}; --panel:{PANEL};
  --red:{palette.RED}; --amber:{palette.AMBER}; --green:{palette.GREEN};
  --serif:'Cormorant Garamond','Playfair Display',Georgia,'Times New Roman',serif;
  --sans:Inter,'Source Sans 3','Segoe UI',system-ui,sans-serif;
  --shadow:0 1px 2px rgba(20,33,61,.05),0 4px 14px rgba(20,33,61,.06);
  --shadow-up:0 2px 4px rgba(20,33,61,.06),0 10px 24px rgba(20,33,61,.10);
  --ease:cubic-bezier(.25,.1,.25,1);
}}
::selection {{ background:rgba(168,120,42,.28); color:var(--ink); }}
html {{ scrollbar-color:#C9BC9C var(--ivory); scrollbar-width:thin; }}
*::-webkit-scrollbar {{ width:10px; height:10px; }}
*::-webkit-scrollbar-track {{ background:var(--ivory); }}
*::-webkit-scrollbar-thumb {{ background:#CBBE9F; border-radius:6px; border:2px solid var(--ivory); }}
*::-webkit-scrollbar-thumb:hover {{ background:var(--gold); }}

html, body, .stApp, [data-testid="stAppViewContainer"] {{ background-color:var(--ivory); color:var(--ink); }}
[data-testid="stAppViewContainer"] {{ background-image:{GRAIN}; }}
.stApp, .stApp p, .stApp li, .stApp label, .stApp td, .stApp th, .stApp input, .stApp button {{ font-family:var(--sans); }}
[data-testid="stIconMaterial"], .material-icons, [class*="material-symbols"] {{ font-family:'Material Symbols Rounded' !important;
  font-variant:normal !important; letter-spacing:normal !important; text-transform:none !important; font-feature-settings:"liga" !important; }}
.stApp p, .stApp li, .stApp label, [data-testid="stMarkdownContainer"] {{ font-size:1rem; line-height:1.65; }}

/* chrome: drop the generic Streamlit furniture, keep everything functional */
footer, [data-testid="stFooter"], [data-testid="stDecoration"], [data-testid="stAppDeployButton"],
.stDeployButton, [data-testid="stStatusWidget"] {{ display:none !important; }}
[data-testid="stHeader"] {{ background:#FAF6EE; border-bottom:1px solid var(--rule); }}
.block-container {{ padding-top:4.6rem; max-width:78rem; animation:gd-fade .9s var(--ease) both; }}

/* headings: serif display face with a short brass ornament under sections */
h1, h2, h3, h4, .stApp [data-testid="stHeading"] *, .stApp [data-testid="stHeadingWithActionElements"] * {{
  font-family:var(--serif) !important; color:var(--ink); font-weight:600; letter-spacing:.005em;
}}
h1 {{ font-size:2.5rem; line-height:1.15; }}
h2, h3 {{ position:relative; border-bottom:1px solid var(--rule); padding-bottom:.45rem; margin-top:1.6rem; }}
h2::after, h3::after {{ content:""; position:absolute; left:0; bottom:-1px; width:3.2rem; height:2px; background:var(--gold); }}
h2 {{ font-size:1.9rem; }} h3 {{ font-size:1.5rem; }}
a {{ color:var(--slate); transition:color .25s var(--ease); }}
a:hover {{ color:var(--ink); }}
.stApp [data-testid="stCaptionContainer"], .stApp small {{ color:var(--muted); opacity:1; }}
hr {{ border:0; border-top:1px solid var(--rule); }}

.gd-title {{ font-family:var(--serif); font-size:2.7rem; font-weight:700; line-height:1.1; margin:1rem 0 .1rem; color:var(--ink); }}
.gd-subtitle {{ font-family:var(--serif); font-style:italic; font-size:1.3rem; color:var(--muted); margin:0 0 .8rem;
  padding-bottom:.7rem; border-bottom:1px solid var(--rule); position:relative; }}
.gd-subtitle::after {{ content:""; position:absolute; left:0; bottom:-1px; width:4.5rem; height:2px; background:var(--gold); }}
.gd-smallcaps {{ font-variant:small-caps; letter-spacing:.08em; color:var(--gold-text); font-weight:600; }}
.gd-lede {{ font-family:var(--serif); font-size:1.5rem; line-height:1.35; color:var(--ink); margin:.2rem 0 .3rem; font-weight:600; }}

/* sticky tab bar with a slow brass underline */
.stTabs [role="tablist"] {{ gap:.15rem; border-bottom:1px solid var(--rule); position:sticky; top:3.75rem; z-index:40;
  background:var(--ivory); padding-top:.2rem; overflow-x:auto; flex-wrap:nowrap; scrollbar-width:none; }}
.stTabs [role="tablist"]::-webkit-scrollbar {{ display:none; }}
[role="tab"] {{ background:transparent; color:var(--muted); font-weight:500; padding:.55rem .95rem; white-space:nowrap;
  position:relative; transition:color .3s var(--ease); border-bottom:0 !important; }}
[role="tab"] p {{ color:inherit; }}
[role="tab"]::after {{ content:""; position:absolute; left:.95rem; right:.95rem; bottom:-1px; height:3px; background:var(--gold);
  transform:scaleX(0); transform-origin:left; transition:transform .5s var(--ease); }}
[role="tab"]:hover {{ color:var(--ink); background:transparent; }}
[role="tab"]:hover::after {{ transform:scaleX(.4); }}
[role="tab"][aria-selected="true"] {{ color:var(--ink); font-weight:600; }}
[role="tab"][aria-selected="true"]::after {{ transform:scaleX(1); }}
[role="tab"]:focus-visible {{ outline:2px solid var(--slate); outline-offset:-2px; }}
[role="tabpanel"] {{ animation:gd-fade .6s var(--ease) both; }}

/* cards */
[data-testid="stMetric"] {{ background:var(--surface); border:1px solid var(--rule); border-top:2px solid var(--gold); border-radius:8px;
  padding:.85rem 1rem; box-shadow:var(--shadow); transition:transform .35s var(--ease),box-shadow .35s var(--ease); }}
[data-testid="stMetric"]:hover {{ transform:translateY(-2px); box-shadow:var(--shadow-up); }}
[data-testid="stMetricLabel"] {{ font-variant:small-caps; letter-spacing:.06em; color:var(--muted); }}
[data-testid="stMetricValue"] {{ font-family:var(--serif); color:var(--ink); font-weight:700; font-size:2.2rem; }}

.stButton > button, .stDownloadButton > button {{ background:var(--surface); color:var(--ink); border:1px solid var(--gold);
  border-radius:6px; font-weight:500;
  transition:background .3s var(--ease),color .3s var(--ease),box-shadow .3s var(--ease),transform .3s var(--ease); }}
.stButton > button:hover, .stDownloadButton > button:hover {{ background:var(--ink); color:#fff; border-color:var(--ink);
  box-shadow:var(--shadow); transform:translateY(-1px); }}
.stButton > button:focus-visible {{ outline:2px solid var(--slate); outline-offset:2px; }}

[data-testid="stExpander"] {{ background:var(--surface); border:1px solid var(--rule); border-radius:8px; box-shadow:var(--shadow);
  transition:box-shadow .35s var(--ease),border-color .35s var(--ease); overflow:hidden; }}
[data-testid="stExpander"]:hover {{ box-shadow:var(--shadow-up); border-color:#D3C6A6; }}
[data-testid="stExpander"] summary {{ font-weight:600; transition:background .3s var(--ease); }}
[data-testid="stExpander"] summary:hover {{ background:rgba(168,120,42,.07); }}
[data-testid="stDataFrame"] {{ border:1px solid var(--rule); border-radius:8px; background:var(--surface); box-shadow:var(--shadow); overflow:hidden; }}
[data-testid="stAlert"] {{ border-radius:8px; }}
[data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"] {{ background:var(--surface); border:1px solid var(--rule);
  border-radius:8px; padding:.6rem .6rem .2rem; box-shadow:var(--shadow); }}
[data-baseweb="select"] > div, [data-baseweb="input"] > div {{ border-radius:6px; transition:border-color .25s var(--ease); }}

/* sidebar as a control panel */
[data-testid="stSidebar"] {{ background:var(--panel); border-right:1px solid var(--rule); }}
[data-testid="stSidebar"] h1 {{ font-size:1.6rem; margin:.2rem 0 0; }}
[data-testid="stSidebar"] [data-testid="stExpander"] {{ box-shadow:none; border-radius:6px; background:var(--surface); }}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {{ font-variant:small-caps; letter-spacing:.05em; font-size:1.05rem; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{ font-size:.88rem; }}

iframe {{ border:0; }}

/* overview: three-step "how it works" */
.gd-steps {{ display:grid; grid-template-columns:repeat(3,1fr); gap:1rem; margin:.6rem 0 1.4rem; }}
.gd-step {{ background:var(--surface); border:1px solid var(--rule); border-top:2px solid var(--gold); border-radius:8px;
  padding:1.1rem 1.2rem 1.2rem; box-shadow:var(--shadow);
  transition:transform .4s var(--ease),box-shadow .4s var(--ease); animation:gd-rise .9s var(--ease) both; }}
.gd-step:nth-child(2) {{ animation-delay:.18s; }} .gd-step:nth-child(3) {{ animation-delay:.36s; }}
.gd-step:hover {{ transform:translateY(-3px); box-shadow:var(--shadow-up); }}
.gd-step svg {{ width:34px; height:34px; stroke:var(--gold-text); fill:none; stroke-width:1.5; stroke-linecap:round; stroke-linejoin:round; }}
.gd-step .gd-num {{ font-variant:small-caps; letter-spacing:.12em; color:var(--gold-text); font-weight:600; font-size:.88rem; margin-top:.5rem; }}
.gd-step .gd-h {{ font-family:var(--serif); font-size:1.6rem; font-weight:700; line-height:1.15; margin:.1rem 0 .35rem; }}
.gd-step p {{ margin:0; color:var(--muted); font-size:1rem; line-height:1.55; }}

/* tier pills: label and glyph carry the meaning, colour reinforces it */
.gd-pill {{ display:inline-block; padding:.05rem .6rem; border-radius:999px; border:1px solid currentColor;
  font-size:.85rem; font-weight:600; white-space:nowrap; }}
.gd-pill-immediate {{ color:var(--red); background:rgba(185,28,28,.07); }}
.gd-pill-short-term {{ color:var(--amber); background:rgba(163,90,6,.08); }}
.gd-pill-medium-term {{ color:var(--green); background:rgba(21,128,61,.07); }}
.gd-selected {{ background:var(--surface); border:1px solid var(--rule); border-left:3px solid var(--gold); border-radius:6px;
  padding:.8rem 1.1rem; margin:.4rem 0 1rem; box-shadow:var(--shadow); }}
.gd-selected .nm {{ font-family:var(--serif); font-size:1.55rem; font-weight:700; line-height:1.2; }}
.gd-status {{ display:inline-block; padding:.05rem .6rem; border:1px solid var(--rule); border-radius:999px; font-size:.85rem;
  font-weight:600; color:var(--ink); background:var(--surface); margin-right:.4rem; }}

@keyframes gd-fade {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
@keyframes gd-rise {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:none; }} }}

@media (max-width:900px) {{ .gd-steps {{ grid-template-columns:1fr; }} }}
@media (max-width:640px) {{
  .block-container {{ padding-left:1rem; padding-right:1rem; }}
  .gd-title {{ font-size:1.9rem; }} .gd-subtitle {{ font-size:1.1rem; }}
  [role="tab"] {{ padding:.45rem .7rem; }}
  .st-key-gd-kpi [data-testid="stElementContainer"] {{ height:auto !important; }}
  .st-key-gd-kpi iframe {{ height:540px !important; }}
  .st-key-gd-hero iframe {{ height:270px !important; }}
  h2 {{ font-size:1.6rem; }} h3 {{ font-size:1.3rem; }}
}}
@media (prefers-reduced-motion:reduce) {{
  *, *::before, *::after {{ animation:none !important; transition:none !important; scroll-behavior:auto !important; }}
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
