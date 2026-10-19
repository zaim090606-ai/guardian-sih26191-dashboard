"""Overview KPI strip: pure number builders plus a self-contained HTML block.

The cards are pre-rendered with their final numbers (the static fallback);
a few lines of JS then count them up once, slowly, unless the visitor prefers
reduced motion. Every figure comes from the computed pipeline result.
"""

import html

import palette
from ui import views

TIERS = ["immediate", "short-term", "medium-term"]
ZONES = ["Red", "Amber", "Green"]


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def build_kpis(result):
    """Four KPI dicts: label, value (int), note, and bars [{label, value, color}]."""
    hab = result["habitations"]
    grid = result["grid"]
    tier_n = hab["rpi_tier"].value_counts()
    tier_pop = hab.groupby("rpi_tier")["population"].sum()
    zone_n = grid["zone_tier"].value_counts()
    total_pop = _int(hab["population"].sum())
    n_inc = _int(len(result["incidents"]))
    n_unloc = _int((result.get("unlocated_stats") or {}).get("count", 0))
    comms = _int(result.get("region_comms_degraded", 0))
    zone_color = {"Red": palette.RED, "Amber": palette.AMBER, "Green": palette.GREEN}

    return [
        {"label": "Habitations assessed", "value": _int(len(hab)), "note": "by tier of relocation priority",
         "bars": [{"label": views.tier_label(t), "value": _int(tier_n.get(t, 0)), "color": palette.RPI_TIER_COLORS[t]} for t in TIERS]},
        {"label": "Residents in immediate tier", "value": _int(tier_pop.get("immediate", 0)),
         "note": f"of {total_pop:,} residents in the demo data",
         "bars": [{"label": views.tier_label(t), "value": _int(tier_pop.get(t, 0)), "color": palette.RPI_TIER_COLORS[t]} for t in TIERS]},
        {"label": "Red-zone cells", "value": _int(zone_n.get("Red", 0)), "note": f"of {_int(len(grid))} grid cells",
         "bars": [{"label": views.tier_label(z), "value": _int(zone_n.get(z, 0)), "color": zone_color[z]} for z in ZONES]},
        {"label": "Ground reports", "value": n_inc + n_unloc,
         "note": f"{comms} arrived with degraded comms",
         "bars": [{"label": "Located", "value": n_inc, "color": "#14213D"},
                  {"label": "Unlocated", "value": n_unloc, "color": "#A8782A"},
                  {"label": "Comms-degraded", "value": comms, "color": "#2F6F73"}]},
    ]


def _bars_svg(bars):
    peak = max([b["value"] for b in bars] + [1])
    w, h, gap = 28, 34, 6
    parts = []
    for i, b in enumerate(bars):
        bh = max(2, round(h * b["value"] / peak)) if b["value"] else 2
        x = i * (w + gap)
        parts.append(f'<rect x="{x}" y="{h - bh}" width="{w}" height="{bh}" rx="2" fill="{b["color"]}">'
                     f'<title>{html.escape(b["label"])}: {b["value"]:,}</title></rect>')
    total_w = len(bars) * (w + gap) - gap
    desc = html.escape(", ".join("%s %s" % (b["label"], format(b["value"], ",")) for b in bars))
    return ('<svg class="bars" viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="%s">%s</svg>'
            % (total_w, h, total_w, h, desc, "".join(parts)))


def _legend(bars):
    return "".join(f'<span><i style="background:{b["color"]}"></i>{html.escape(b["label"])} {b["value"]:,}</span>' for b in bars)


_CSS = """
html,body{margin:0;background:transparent;font-family:Inter,'Segoe UI',system-ui,sans-serif;color:#14213D}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:4px 2px 10px}
.card{background:#FFFDF8;border:1px solid #E1D8C3;border-top:2px solid #A8782A;border-radius:8px;padding:14px 16px 12px;
 box-shadow:0 1px 2px rgba(20,33,61,.05),0 4px 14px rgba(20,33,61,.06);transition:transform .4s cubic-bezier(.25,.1,.25,1),box-shadow .4s cubic-bezier(.25,.1,.25,1)}
.card:hover{transform:translateY(-3px);box-shadow:0 2px 4px rgba(20,33,61,.06),0 10px 24px rgba(20,33,61,.10)}
.lab{font-variant:small-caps;letter-spacing:.07em;color:#4A5568;font-weight:600;font-size:14px}
.num{font-family:'Cormorant Garamond',Georgia,serif;font-weight:700;font-size:46px;line-height:1.05;margin:2px 0 2px;font-variant-numeric:lining-nums}
.note{color:#4A5568;font-size:13px;line-height:1.35;min-height:2.7em}
.bars{display:block;margin-top:8px}
.leg{display:flex;flex-wrap:wrap;gap:2px 10px;margin-top:6px;font-size:11.5px;color:#4A5568}
.leg i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:4px}
@media (max-width:760px){.grid{grid-template-columns:repeat(2,1fr);gap:10px}.num{font-size:36px}.card{padding:12px 12px 10px}}
@media (prefers-reduced-motion:reduce){.card{transition:none}.card:hover{transform:none}}
"""

_JS = """
(function(){
 var els=document.querySelectorAll('[data-final]');
 if(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches)return;
 var t0=null,dur=1400;
 function ease(t){return 1-Math.pow(1-t,3);}
 function step(ts){if(t0===null)t0=ts;var p=Math.min(1,(ts-t0)/dur);
  els.forEach(function(e){e.textContent=Math.round(Number(e.getAttribute('data-final'))*ease(p)).toLocaleString('en-US');});
  if(p<1)requestAnimationFrame(step);}
 els.forEach(function(e){e.textContent='0';});
 requestAnimationFrame(step);
})();
"""


def build_kpi_html(kpis):
    cards = "".join(
        f'<div class="card"><div class="lab">{html.escape(k["label"])}</div>'
        f'<div class="num" data-final="{k["value"]}">{k["value"]:,}</div>'
        f'<div class="note">{html.escape(k["note"])}</div>{_bars_svg(k["bars"])}'
        f'<div class="leg">{_legend(k["bars"])}</div></div>'
        for k in kpis
    )
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<style>{_CSS}</style></head><body><div class="grid">{cards}</div><script>{_JS}</script></body></html>')
