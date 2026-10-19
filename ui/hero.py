"""Engraved-plate hero: an original Three.js scene of schematic terrain with
glowing points for the highest-priority villages of the current run.

build_hero_payload() is pure (DataFrame in, JSON-able dict out) and unit
tested; render_hero() wraps the HTML in a components iframe. Presentation only:
nothing here changes scoring or allocation.
"""

import json
import math

import palette
import scoring

THREE_URL = "https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js"
THREE_SRI = "sha512-vnmn/Qqn6aG0POAc9mIGzjq0IybrvxJXYDafNvp9JSnDGxeF3pbkSqLvf+YGd5ku63pT7sa/jxHn7/d0mU8+tA=="
HERO_HEIGHT = 360
DEFAULT_TOP_N = 12

CAPTION = ("Schematic terrain, not to scale. Points show the highest-priority villages from the "
           "current run; demo data is illustrative.")

TIER_LABELS = {"immediate": "Immediate", "short-term": "Short-term", "medium-term": "Medium-term"}
# Shape + label next to the colour, so tiers do not rely on colour alone.
TIER_GLYPHS = {"immediate": "▲", "short-term": "◆", "medium-term": "●"}


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def build_hero_payload(df, n=DEFAULT_TOP_N):
    """Top-n habitations by Relocation Priority Index as a small JSON-able dict.

    Only whitelisted, non-personal fields are emitted (a village label, RPI,
    tier, colour and a 0-1 map position). Missing/empty input gives an empty
    point list rather than an error.
    """
    legend = [{"tier": t, "label": TIER_LABELS[t], "glyph": TIER_GLYPHS[t], "color": c}
              for t, c in palette.RPI_TIER_COLORS.items()]
    payload = {"points": [], "legend": legend, "caption": CAPTION}
    try:
        n = max(0, int(n))
    except (TypeError, ValueError):
        n = DEFAULT_TOP_N
    if df is None or len(df) == 0 or "rpi" not in df.columns or n == 0:
        return payload

    rows = []
    for _, row in df.iterrows():
        rpi = _num(row.get("rpi"))
        if rpi is not None:
            rows.append((rpi, row))
    rows.sort(key=lambda t: -t[0])
    rows = rows[:n]

    has_geo = "lat" in df.columns and "lon" in df.columns
    lats = [v for v in (_num(x) for x in df["lat"]) if v is not None] if has_geo else []
    lons = [v for v in (_num(x) for x in df["lon"]) if v is not None] if has_geo else []
    lat0, lat1 = (min(lats), max(lats)) if lats else (0.0, 1.0)
    lon0, lon1 = (min(lons), max(lons)) if lons else (0.0, 1.0)

    for rank, (rpi, row) in enumerate(rows):
        tier = row.get("rpi_tier") if "rpi_tier" in df.columns else None
        if tier not in palette.RPI_TIER_COLORS:
            tier = scoring.rpi_tier(rpi)
        lat, lon = _num(row.get("lat")), _num(row.get("lon"))
        if lat is not None and lon is not None:
            x = (lon - lon0) / ((lon1 - lon0) or 1.0)
            y = (lat - lat0) / ((lat1 - lat0) or 1.0)
        else:  # no coordinates: deterministic golden-angle spread
            a = rank * 2.399963
            r = 0.15 + 0.3 * ((rank + 1) / (len(rows) + 1))
            x, y = 0.5 + r * math.cos(a), 0.5 + r * math.sin(a)
        label = row.get("name") if "name" in df.columns else None
        if not isinstance(label, str) or not label.strip():
            hid = row.get("habitation_id") if "habitation_id" in df.columns else None
            label = str(hid) if hid is not None else f"Village {rank + 1}"
        payload["points"].append({
            "rank": rank + 1, "label": label.strip()[:40], "rpi": round(rpi, 1), "tier": tier,
            "tier_label": TIER_LABELS[tier], "color": palette.RPI_TIER_COLORS[tier],
            "x": round(min(max(x, 0.0), 1.0), 4), "y": round(min(max(y, 0.0), 1.0), 4),
        })
    return payload


_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{margin:0;height:100%;background:#FAF6EE;font-family:Inter,'Segoe UI',system-ui,sans-serif}
.plate{position:relative;box-sizing:border-box;height:calc(100% - 4px);margin:2px;border:1.5px solid #A8782A;
 border-radius:12px;overflow:hidden;background:radial-gradient(ellipse at 50% 35%,#223559 0%,#14213D 55%,#0C1527 100%);
 box-shadow:inset 0 0 0 4px #14213D,inset 0 0 0 5px rgba(168,120,42,.45)}
canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
.fallback{position:absolute;inset:0;display:none;background:
 repeating-linear-gradient(115deg,rgba(168,120,42,0) 0 22px,rgba(168,120,42,.18) 22px 23px),
 linear-gradient(160deg,#2B4068 0%,#14213D 60%,#0C1527 100%)}
.legend{position:absolute;left:14px;top:12px;color:#EDE4CF;font-size:12px;line-height:1.6;
 background:rgba(12,21,39,.6);border:1px solid rgba(168,120,42,.5);border-radius:6px;padding:6px 10px}
.legend b{font-variant:small-caps;letter-spacing:.08em;font-weight:600;color:#E3C27E}
.sw{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:6px;vertical-align:-1px;
 border:1.5px solid #FAF6EE}
.caption{position:absolute;left:0;right:0;bottom:0;padding:18px 16px 8px;color:#EDE4CF;font-size:12px;line-height:1.4;
 background:linear-gradient(0deg,rgba(12,21,39,.9),rgba(12,21,39,0))}
</style></head><body>
<div class="plate" id="plate">
 <div class="fallback" id="fallback"></div>
 <canvas id="c" aria-hidden="true"></canvas>
 <div class="legend" id="legend"></div>
 <div class="caption" id="caption"></div>
</div>
<script>window.__HERO__=__PAYLOAD__;</script>
<script>
(function(){
 var D=window.__HERO__, plate=document.getElementById('plate');
 document.getElementById('caption').textContent=D.caption;
 var lg='<b>Relocation priority</b><br>';
 D.legend.forEach(function(l){lg+='<span class="sw" style="background:'+l.color+'"></span>'+l.glyph+' '+l.label+'<br>';});
 document.getElementById('legend').innerHTML=lg;
 function fallback(){document.getElementById('fallback').style.display='block';document.getElementById('c').style.display='none';}
 function start(){
  if(typeof THREE==='undefined'){fallback();return;}
  var canvas=document.getElementById('c'),renderer;
  try{renderer=new THREE.WebGLRenderer({canvas:canvas,antialias:true,alpha:true});}catch(e){fallback();return;}
  var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  var narrow=plate.clientWidth<520;
  var N=narrow?32:56;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,narrow?1.5:2));
  var scene=new THREE.Scene(), cam=new THREE.PerspectiveCamera(34,1,0.1,100);
  function h2(i,j){var s=Math.sin(i*127.1+j*311.7)*43758.5453;return s-Math.floor(s);}
  function vn(x,y){var i=Math.floor(x),j=Math.floor(y),fx=x-i,fy=y-j,u=fx*fx*(3-2*fx),v=fy*fy*(3-2*fy);
   return (h2(i,j)*(1-u)+h2(i+1,j)*u)*(1-v)+(h2(i,j+1)*(1-u)+h2(i+1,j+1)*u)*v;}
  function ht(x,y){var a=0.5,f=2.2,s=0,k;for(k=0;k<4;k++){s+=a*vn(x*f+7.3,y*f+2.1);f*=2;a*=0.5;}
   var d=Math.hypot(x-0.5,y-0.5);return Math.max(0,(s-0.18)*1.05)*(1-Math.min(1,d*d*1.6));}
  var SIZE=6,HS=2.3;
  var g=new THREE.PlaneGeometry(SIZE,SIZE,N,N);g.rotateX(-Math.PI/2);
  var pos=g.attributes.position,hv=new Float32Array(pos.count),i;
  for(i=0;i<pos.count;i++){var u=pos.getX(i)/SIZE+0.5,v=pos.getZ(i)/SIZE+0.5,hh=ht(u,v);hv[i]=hh;pos.setY(i,hh*HS);}
  g.setAttribute('h',new THREE.BufferAttribute(hv,1));
  var mat=new THREE.ShaderMaterial({
   vertexShader:'attribute float h;varying float vH;varying vec3 vP;void main(){vH=h;vP=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
   fragmentShader:'varying float vH;varying vec3 vP;void main(){'+
    'vec3 n=normalize(cross(dFdx(vP),dFdy(vP)));float l=0.55+0.45*clamp(dot(n,normalize(vec3(-0.5,0.8,0.4))),0.0,1.0);'+
    'vec3 lo=vec3(0.10,0.17,0.31),hi=vec3(0.36,0.46,0.58);vec3 c=mix(lo,hi,clamp(vH*1.7,0.0,1.0))*l;'+
    'float f=vH*14.0;float w=fwidth(f);float line=1.0-smoothstep(0.0,w*1.2,abs(fract(f-0.5)-0.5));'+
    'c=mix(c,vec3(0.80,0.60,0.27),line*0.85*step(0.02,vH));gl_FragColor=vec4(c,1.0);}'
  });
  var group=new THREE.Group();scene.add(group);
  group.add(new THREE.Mesh(g,mat));
  var grid=new THREE.GridHelper(SIZE,12,0xA8782A,0xA8782A);grid.material.transparent=true;grid.material.opacity=0.18;grid.position.y=-0.02;group.add(grid);
  var cv=document.createElement('canvas');cv.width=cv.height=64;var cx=cv.getContext('2d'),gr=cx.createRadialGradient(32,32,0,32,32,32);
  gr.addColorStop(0,'rgba(255,255,255,1)');gr.addColorStop(0.35,'rgba(255,255,255,0.45)');gr.addColorStop(1,'rgba(255,255,255,0)');
  cx.fillStyle=gr;cx.fillRect(0,0,64,64);var tex=new THREE.CanvasTexture(cv);
  var pts=D.points.slice(0,narrow?8:D.points.length);
  var rings=[];
  pts.forEach(function(p){
   var x=(p.x-0.5)*SIZE*0.8,z=(0.5-p.y)*SIZE*0.8,gh=ht(x/SIZE+0.5,z/SIZE+0.5)*HS;
   var col=new THREE.Color(p.color),top=gh+0.25+(p.rpi/100)*0.9;
   var beam=new THREE.Mesh(new THREE.CylinderGeometry(0.012,0.012,top-gh,6),new THREE.MeshBasicMaterial({color:0xFAF6EE}));
   beam.position.set(x,(top+gh)/2,z);group.add(beam);
   var glow=new THREE.Sprite(new THREE.SpriteMaterial({map:tex,color:col,blending:THREE.AdditiveBlending,transparent:true,depthWrite:false}));
   glow.scale.setScalar(0.55+0.4*p.rpi/100);glow.position.set(x,top,z);group.add(glow);
   var core=new THREE.Mesh(new THREE.SphereGeometry(0.055,12,10),new THREE.MeshBasicMaterial({color:col}));core.position.set(x,top,z);group.add(core);
   var ring=new THREE.Mesh(new THREE.RingGeometry(0.07,0.095,20),new THREE.MeshBasicMaterial({color:0xFAF6EE,side:THREE.DoubleSide}));
   ring.position.set(x,top,z);group.add(ring);rings.push(ring);
  });
  var mx=0,my=0;
  window.addEventListener('pointermove',function(e){mx=(e.clientX/window.innerWidth-0.5);my=(e.clientY/window.innerHeight-0.5);});
  function size(){var w=plate.clientWidth,hgt=plate.clientHeight;renderer.setSize(w,hgt,false);cam.aspect=w/hgt;cam.updateProjectionMatrix();}
  size();
  var rot=0.6,visible=true,raf=0;
  function draw(){
   cam.position.set(Math.sin(mx*0.4)*0.9,4.4-my*0.5,8.6);cam.lookAt(0,0.5,0);
   group.rotation.y=rot;rings.forEach(function(r){r.lookAt(cam.position);});
   renderer.render(scene,cam);
  }
  if('ResizeObserver' in window)new ResizeObserver(function(){size();draw();}).observe(plate);
  function loop(){raf=0;if(!visible||document.hidden)return;rot+=0.0016;draw();raf=requestAnimationFrame(loop);}
  function kick(){if(!reduce&&!raf&&visible&&!document.hidden)raf=requestAnimationFrame(loop);}
  draw();
  if(!reduce){
   if('IntersectionObserver' in window)new IntersectionObserver(function(es){visible=es[0].isIntersecting;kick();}).observe(plate);
   document.addEventListener('visibilitychange',kick);kick();
  }
 }
 var s=document.createElement('script');s.src='__THREE_URL__';s.integrity='__THREE_SRI__';s.crossOrigin='anonymous';
 s.onload=start;s.onerror=fallback;document.head.appendChild(s);
})();
</script></body></html>"""


def build_hero_html(payload):
    """Self-contained HTML for the hero iframe (JSON embedded, '<' escaped)."""
    data = json.dumps(payload).replace("<", "\\u003c")
    return (_HTML.replace("__PAYLOAD__", data)
                 .replace("__THREE_URL__", THREE_URL)
                 .replace("__THREE_SRI__", THREE_SRI))


def render_hero(habitations_df, n=DEFAULT_TOP_N, height=HERO_HEIGHT):
    import streamlit as st
    html = build_hero_html(build_hero_payload(habitations_df, n))
    if hasattr(st, "iframe"):  # components.v1.html is deprecated in newer Streamlit
        st.iframe(html, height=height)
    else:
        import streamlit.components.v1 as components
        components.html(html, height=height)
