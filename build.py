#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Lushin First Time Conversations — call library generator
#
# Run:  python3 build.py
# Out:  site/index.html  +  site/calls/<slug>.html  (one per call)
#
# TO ADD A VIDEO: put the YouTube ID next to the call's filename in YT_IDS
# below and re-run. That is the only edit needed.
# ---------------------------------------------------------------------------
import os, re, json, html, shutil, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "site")

# ===========================================================================
# 1. VIDEO IDS  —  "<transcript filename without .txt>": "<YouTube ID>"
#    Leave as "" until the video is uploaded. Pages handle blanks gracefully.
# ===========================================================================
YT_IDS = {}
_ytfile = os.path.join(HERE, "yt_ids.json")
if os.path.exists(_ytfile):
    YT_IDS.update(json.load(open(_ytfile, encoding="utf-8")))

# Per-call seconds offset, if a trimmed upload starts later than the
# transcript clock.  e.g. "2024_09_13_RL_...": -231
TIME_OFFSET = {}

# ===========================================================================
# 2. LOOKUPS
# ===========================================================================
COACHES = {
    "AP": ("Aaron Prickel",  "#4f46e5", "#7c3aed"),
    "RL": ("Rob Lime",       "#0891b2", "#06b6d4"),
    "ST": ("Shad Tidler",    "#059669", "#10b981"),
    "BK": ("Brian Kavicky",  "#d97706", "#f59e0b"),
    "ES": ("Emily Shaw",     "#e11d48", "#f43f5e"),
}

MILESTONE_TYPES = [
    ("up-front-contract", "Up-Front Contract",                 "#4f46e5", "#7c3aed"),
    ("pain-problem",      "Pain: What's the Problem",          "#e11d48", "#f43f5e"),
    ("pain-why",          "Pain: Why It Matters",              "#ea580c", "#f97316"),
    ("pain-impact",       "Pain: Impact",                      "#d97706", "#f59e0b"),
    ("pain-commitment",   "Pain: Commitment to Fixing It",     "#db2777", "#ec4899"),
    ("decision-process",  "Decision Process",                  "#2563eb", "#3b82f6"),
    ("decision-criteria", "Decision Criteria",                 "#0891b2", "#06b6d4"),
    ("budget",            "Budget / Money Conversation",       "#059669", "#10b981"),
    ("next-step",         "Clear Next Step",                   "#7c3aed", "#a855f7"),
    ("ufc-next",          "Up-Front Contract for Next Meeting","#475569", "#64748b"),
]
MS_NAME  = {k: n for k, n, _a, _b in MILESTONE_TYPES}
MS_COLOR = {k: a for k, _n, a, _b in MILESTONE_TYPES}
MS_ORDER = {k: i for i, (k, _n, _a, _b) in enumerate(MILESTONE_TYPES)}

TRACK_CATS = {
    "open":    ("Setting up the call",      "#4f46e5"),
    "pain":    ("Finding the problem",      "#e11d48"),
    "money":   ("Money",                    "#059669"),
    "diff":    ("Differentiation",          "#7c3aed"),
    "obj":     ("Objections",               "#ea580c"),
    "fit":     ("Fit and permission",       "#0891b2"),
    "process": ("Decision process",         "#2563eb"),
    "next":    ("Next step",                "#d97706"),
    "human":   ("Disarming",                "#8b94a3"),
}
CAT_ORDER = ["open", "pain", "money", "diff", "obj", "fit", "process", "next", "human"]

OUTCOMES = {
    "advanced": ("Advanced",   "#059669"),
    "closed":   ("Closed",     "#4f46e5"),
    "stalled":  ("Stalled",    "#d97706"),
    "no-fit":   ("No fit",     "#64748b"),
    "unclear":  ("Unclear",    "#8b94a3"),
}

# ===========================================================================
# 3. LOAD DATA
# ===========================================================================
DOCS   = {d["stem"]: d for d in json.load(open(os.path.join(HERE, "docs.json"), encoding="utf-8"))}
ANALY  = {a["stem"]: a for a in json.load(open(os.path.join(HERE, "analysis_all.json"), encoding="utf-8"))}
TRACKS = json.load(open(os.path.join(HERE, "talk_tracks.json"), encoding="utf-8"))

def esc(s):  return html.escape(str(s or ""))
def mmss(s):
    s = int(s or 0); h, r = divmod(s, 3600); m, x = divmod(r, 60)
    return f"{h}:{m:02d}:{x:02d}" if h else f"{m}:{x:02d}"

def slugify(s):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", str(s)).strip("-").lower()
    return re.sub(r"-{2,}", "-", s) or "call"

# ---- build the canonical call list ---------------------------------------
CALLS = []
for stem, d in DOCS.items():
    a = ANALY[stem]
    x = d.get("x") or {}
    company = (a.get("company") or x.get("company") or "Unknown").strip()
    date = d["date"]
    CALLS.append({
        "stem": stem,
        "slug": f"{slugify(company)}-{date}",
        "date": date,
        "coach": a.get("coach") or d["trainer"],
        "company": company,
        "company_note": a.get("company_note", ""),
        "headline": a.get("headline", ""),
        "summary": a.get("summary", ""),
        "outcome": a.get("outcome", "unclear"),
        "outcome_note": a.get("outcome_note", ""),
        "dur": x.get("dur") or d.get("duration") or "",
        "tenure": x.get("tenure", ""),
        "ctype": x.get("ctype", ""),
        "ff": x.get("ff", ""),
        "arc": a.get("arc", []),
        "milestones": sorted(a.get("milestones", []), key=lambda m: m["sec"]),
        "moments": sorted(a.get("moments", []), key=lambda m: m["sec"]),
        "notes": a.get("coaching_notes", []),
        "coach_speaker": a.get("_cs") or a.get("coach_speaker", ""),
        "other_speakers": a.get("other_speakers", []),
        "confidence": a.get("coach_confidence", ""),
        "yt": YT_IDS.get(stem, ""),
        "off": TIME_OFFSET.get(stem, 0),
        "end_sec": d["end_sec"],
        "utts": d["utts"],
    })
# de-duplicate slugs
_seen = {}
for c in sorted(CALLS, key=lambda c: (c["date"], c["stem"])):
    if c["slug"] in _seen:
        _seen[c["slug"]] += 1
        c["slug"] = f"{c['slug']}-{_seen[c['slug']]}"
    else:
        _seen[c["slug"]] = 1
CALLS.sort(key=lambda c: (c["date"], c["company"]))
BY_STEM = {c["stem"]: c for c in CALLS}

# flag calls whose filename says one thing and whose content says another
FLAG_WORDS = ("not a first", "not a first-time", "mislabel", "is not an ftc",
              "wrong company", "company is", "not a prospect", "roles reversed",
              "scrambled", "swapped", "truncat", "dead air", "hiring interview",
              "is not a sales call", "chronologically swapped")
for c in CALLS:
    hits = [n for n in c["notes"] if any(w in n.lower() for w in FLAG_WORDS)]
    c["flags"] = hits

TOTAL_MOMENTS = sum(len(c["moments"]) for c in CALLS)

# ===========================================================================
# 4. SHARED SHELL
# ===========================================================================
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{
 --bg:#f6f7fb; --card:#ffffff; --ink:#111827; --ink2:#4b5563; --ink3:#9ca3af;
 --line:#e5e7eb; --shadow:0 1px 3px rgba(16,24,40,.06),0 8px 24px rgba(16,24,40,.05);
 --radius:18px;
}
html[data-t="dark"]{
 --bg:#0b0e14; --card:#141922; --ink:#e8eaf0; --ink2:#9ba3b4; --ink3:#6b7383;
 --line:#222938; --shadow:0 1px 3px rgba(0,0,0,.4),0 8px 28px rgba(0,0,0,.35);
}
body{background:var(--bg);color:var(--ink);
 font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;
 -webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.wrap{max-width:1100px;margin:0 auto;padding:0 20px}
.top{position:sticky;top:0;z-index:50;background:var(--bg);border-bottom:1px solid var(--line)}
.top .wrap{display:flex;align-items:center;gap:6px;height:58px;flex-wrap:wrap}
.brand{font-weight:600;font-size:15px;margin-right:14px;color:var(--ink2)}
.nav{display:flex;gap:2px;flex:1;flex-wrap:wrap}
.nav a{padding:7px 12px;border-radius:9px;font-size:13.5px;color:var(--ink2);font-weight:500}
.nav a:hover{background:var(--line)}
.nav a.on{background:var(--ink);color:var(--bg)}
.tbtn{border:1px solid var(--line);background:var(--card);color:var(--ink2);
 width:34px;height:34px;border-radius:9px;cursor:pointer;font-size:14px}
h1{font-size:19px;font-weight:600;letter-spacing:-.01em}
h2{font-size:15px;font-weight:600;margin-bottom:12px}
.eyebrow{font-size:12.5px;color:var(--ink3);font-weight:500;margin-bottom:2px}
.sect{padding:34px 0}
.muted{color:var(--ink2)}
.tiny{font-size:12.5px;color:var(--ink3)}

/* hub tiles */
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(248px,1fr));gap:16px}
.tile{border-radius:var(--radius);padding:30px 26px;min-height:168px;color:#fff;
 display:flex;flex-direction:column;justify-content:flex-end;position:relative;overflow:hidden}
.tile .big{font-size:27px;font-weight:650;letter-spacing:-.02em;line-height:1.12}
.tile .n{position:absolute;top:22px;right:24px;font-size:13px;opacity:.72;font-weight:600}

/* cards */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
 padding:18px 20px;box-shadow:var(--shadow);display:block}
.card:hover{border-color:var(--ink3)}
.card .co{font-size:17px;font-weight:600;letter-spacing:-.01em;margin-bottom:3px}
.card .hl{font-size:13.5px;color:var(--ink2);line-height:1.45}
.row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.chip{font-size:11.5px;font-weight:600;padding:3px 9px;border-radius:999px;color:#fff;white-space:nowrap}
.chip.g{background:transparent;color:var(--ink3);border:1px solid var(--line);font-weight:500}

/* table */
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;
 color:var(--ink3);font-weight:600;padding:8px 10px;border-bottom:1px solid var(--line);
 cursor:pointer;user-select:none;white-space:nowrap}
td{padding:11px 10px;border-bottom:1px solid var(--line);vertical-align:top}
tr:hover td{background:rgba(127,127,127,.045)}

/* collapsible */
.acc{background:var(--card);border:1px solid var(--line);border-radius:14px;margin-bottom:10px;overflow:hidden}
.acc>.hd{padding:15px 18px;cursor:pointer;display:flex;align-items:center;gap:11px;font-weight:600;font-size:14.5px}
.acc>.hd .cv{margin-left:auto;color:var(--ink3);transition:transform .18s;font-size:12px}
.acc.open>.hd .cv{transform:rotate(90deg)}
.acc>.bd{display:none;padding:0 18px 18px}
.acc.open>.bd{display:block}

/* moments */
.mo{border-left:3px solid var(--line);padding:9px 0 9px 15px;margin-bottom:3px}
.mo:hover{border-left-color:var(--ink3)}
.mo .tt{font-size:12.5px;font-weight:650;font-variant-numeric:tabular-nums;cursor:pointer}
.mo .ti{font-size:14px;font-weight:600;margin:1px 0 3px}
.mo .q{font-size:14.5px;line-height:1.55;font-style:italic;color:var(--ink)}
.mo .w{font-size:12.5px;color:var(--ink3);margin-top:4px}
.star{cursor:pointer;color:var(--ink3);font-size:14px;background:none;border:none;padding:0 4px}
.star.on{color:#f59e0b}

/* player */
.player{position:relative;width:100%;aspect-ratio:16/9;background:#000;
 border-radius:14px;overflow:hidden;margin-bottom:16px}
.player iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.novid{background:var(--card);border:1px dashed var(--line);border-radius:14px;
 padding:28px 22px;text-align:center;color:var(--ink3);font-size:13.5px;margin-bottom:16px}

/* transcript */
.tr{font-size:14px;line-height:1.65;max-height:560px;overflow-y:auto;padding-right:6px}
.tr .u{margin-bottom:9px;display:flex;gap:11px}
.tr .u .s{flex:0 0 58px;font-size:11.5px;color:var(--ink3);font-variant-numeric:tabular-nums;
 padding-top:3px;cursor:pointer}
.tr .u.c .x{font-weight:500}
.tr .u:not(.c) .x{color:var(--ink2)}
mark{background:#fde68a;color:#111;border-radius:3px;padding:0 2px}
html[data-t="dark"] mark{background:#92400e;color:#fde68a}

input.search{width:100%;padding:11px 15px;border:1px solid var(--line);border-radius:11px;
 background:var(--card);color:var(--ink);font-size:14.5px;margin-bottom:14px}
input.search:focus{outline:none;border-color:var(--ink3)}
.fil{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}
.fil button{border:1px solid var(--line);background:var(--card);color:var(--ink2);
 padding:7px 13px;border-radius:999px;font-size:13px;cursor:pointer;font-weight:500}
.fil button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.empty{text-align:center;padding:50px 20px;color:var(--ink3);font-size:14px}
.view{display:none}
.view.on{display:block}
@media(max-width:640px){
 .tile{min-height:132px;padding:22px 20px}
 .tile .big{font-size:22px}
 .top .wrap{height:auto;padding-top:9px;padding-bottom:9px}
 .tr .u{flex-direction:column;gap:1px}
}
"""

JS_SHELL = """
(function(){
 var T=localStorage;
 function g(k,d){try{return JSON.parse(T.getItem(k))||d}catch(e){return d}}
 function s(k,v){try{T.setItem(k,JSON.stringify(v))}catch(e){}}
 window.Store={
  done:{all:function(){return g('ftc_done',{})},
        is:function(k){return !!this.all()[k]},
        toggle:function(k){var o=this.all();o[k]?delete o[k]:o[k]=1;s('ftc_done',o);return !!o[k]},
        count:function(){return Object.keys(this.all()).length}},
  fav:{all:function(){return g('ftc_fav',{})},
       is:function(k){return !!this.all()[k]},
       toggle:function(k,m){var o=this.all();o[k]?delete o[k]:o[k]=(m||1);s('ftc_fav',o);return !!o[k]},
       del:function(k){var o=this.all();delete o[k];s('ftc_fav',o)},
       count:function(){return Object.keys(this.all()).length}}
 };
 try{var th=T.getItem('ftc_theme');if(th)document.documentElement.setAttribute('data-t',JSON.parse(th))}catch(e){}
 window.flipTheme=function(){
   var d=document.documentElement,n=d.getAttribute('data-t')==='dark'?'light':'dark';
   d.setAttribute('data-t',n);s('ftc_theme',n);
   var b=document.getElementById('tbtn');if(b)b.textContent=n==='dark'?'\\u2600':'\\u263E';
 };
 window.addEventListener('DOMContentLoaded',function(){
   var b=document.getElementById('tbtn');
   if(b)b.textContent=document.documentElement.getAttribute('data-t')==='dark'?'\\u2600':'\\u263E';
   document.querySelectorAll('.acc>.hd').forEach(function(h){
     h.addEventListener('click',function(){h.parentNode.classList.toggle('open')});
   });
 });
})();
"""

NAV = [("index.html#home","Home"),("index.html#calls","Calls"),("index.html#list","List"),
       ("index.html#coaches","Coaches"),("index.html#tracks","Talk Tracks"),
       ("index.html#moments","Moments"),("index.html#milestones","Milestones"),
       ("index.html#saved","Saved")]

def shell(title, body, depth=0, extra_js=""):
    up = "../" * depth
    nav = "".join(f'<a href="{up}{h}">{esc(l)}</a>' for h, l in NAV)
    return f"""<!doctype html><html lang="en" data-t="light"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style><script>{JS_SHELL}</script></head><body>
<div class="top"><div class="wrap">
<a class="brand" href="{up}index.html#home">First Time Conversations</a>
<nav class="nav">{nav}</nav>
<button class="tbtn" id="tbtn" onclick="flipTheme()">&#9790;</button>
</div></div>
{body}
<script>{extra_js}</script></body></html>"""

# ===========================================================================
# 5. FRAGMENTS
# ===========================================================================
def coach_chip(code):
    name, a, _b = COACHES.get(code, (code, "#64748b", "#94a3b8"))
    return f'<span class="chip" style="background:{a}">{esc(name)}</span>'

def outcome_chip(o):
    lab, col = OUTCOMES.get(o, (o, "#8b94a3"))
    return f'<span class="chip" style="background:{col}">{esc(lab)}</span>'

def yt_src(c, sec=None, auto=False):
    if not c["yt"]: return ""
    q = []
    if sec is not None:
        q.append(f"start={max(0,int(sec)+c['off'])}")
    if auto: q.append("autoplay=1")
    q.append("rel=0")
    return f"https://www.youtube.com/embed/{c['yt']}?" + "&".join(q)

def moment_html(c, m, idx, with_src=False):
    key = f"{c['stem']}@{m['sec']}"
    meta = json.dumps({"c": c["company"], "t": m["t"], "s": c["slug"],
                       "ti": m.get("title", ""), "q": (m.get("quote") or "")[:400],
                       "co": c["coach"], "sec": m["sec"], "stem": c["stem"]})
    src = ""
    if with_src:
        src = (f'<div class="tiny" style="margin-bottom:3px">'
               f'<a href="calls/{c["slug"]}.html" style="color:var(--ink3)">'
               f'{esc(c["company"])} &middot; {esc(COACHES.get(c["coach"],[c["coach"]])[0])}</a></div>')
    q = f'<div class="q">&ldquo;{esc(m["quote"])}&rdquo;</div>' if m.get("quote") else ""
    w = f'<div class="w">{esc(m["why"])}</div>' if m.get("why") else ""
    jump = (f'onclick="seek({m["sec"]})"' if c["yt"] and not with_src else
            (f'onclick="location.href=\'calls/{c["slug"]}.html#t{m["sec"]}\'"' if with_src else ""))
    return (f'<div class="mo" data-k="{esc(key)}">{src}'
            f'<div class="row"><span class="tt" {jump}>{esc(m["t"])}</span>'
            f'<button class="star" data-fav="{esc(key)}" data-meta=\'{esc(meta)}\'>&#9733;</button></div>'
            f'<div class="ti">{esc(m.get("title",""))}</div>{q}{w}</div>')

FAV_JS = """
function paintStars(){
  document.querySelectorAll('[data-fav]').forEach(function(b){
    b.classList.toggle('on', Store.fav.is(b.getAttribute('data-fav')));
    if(!b._b){b._b=1;b.addEventListener('click',function(e){
      e.preventDefault();e.stopPropagation();
      var m={};try{m=JSON.parse(b.getAttribute('data-meta')||'{}')}catch(err){}
      Store.fav.toggle(b.getAttribute('data-fav'),m);
      b.classList.toggle('on');
      if(window.afterFav)window.afterFav();
    })}
  });
}
window.addEventListener('DOMContentLoaded',paintStars);
"""

# ===========================================================================
# 6. CALL PAGES
# ===========================================================================
def call_page(c):
    coach_name = COACHES.get(c["coach"], (c["coach"],))[0]
    b = [f'<div class="wrap sect">']
    b.append(f'<div class="eyebrow">{esc(coach_name)} &middot; {esc(c["date"])} &middot; {esc(c["dur"])}</div>')
    b.append(f'<h1 style="font-size:26px;margin-bottom:6px">{esc(c["company"])}</h1>')
    b.append(f'<div class="muted" style="font-size:15px;margin-bottom:6px">{esc(c["headline"])}</div>')
    if c["company_note"]:
        b.append(f'<div class="tiny" style="margin-bottom:14px">{esc(c["company_note"])}</div>')
    b.append('<div class="row" style="margin-bottom:20px">')
    b.append(coach_chip(c["coach"])); b.append(outcome_chip(c["outcome"]))
    if c["ctype"]:  b.append(f'<span class="chip g">{esc(c["ctype"])}</span>')
    if c["tenure"] and c["tenure"] != "NA":
        b.append(f'<span class="chip g">Tenure at meeting: {esc(c["tenure"])}</span>')
    b.append(f'<button class="chip g" id="donebtn" style="cursor:pointer">Mark listened</button>')
    b.append('</div>')

    # player
    if c["yt"]:
        b.append(f'<div class="player"><iframe id="pl" src="{yt_src(c)}" '
                 f'allow="accelerometer;autoplay;encrypted-media;picture-in-picture" '
                 f'allowfullscreen></iframe></div>')
    else:
        ff = (f'<br><a href="{esc(c["ff"])}" target="_blank" rel="noopener" '
              f'style="text-decoration:underline">Open in Fireflies</a>') if c["ff"] else ""
        b.append(f'<div class="novid">Video not linked yet. Timestamps below still work '
                 f'against the recording.{ff}</div>')

    b.append(f'<p style="font-size:15.5px;line-height:1.65;margin-bottom:8px">{esc(c["summary"])}</p>')
    if c["outcome_note"]:
        b.append(f'<p class="muted" style="font-size:14.5px;margin-bottom:22px">{esc(c["outcome_note"])}</p>')

    if c["flags"]:
        b.append('<div class="acc"><div class="hd" style="color:#d97706">'
                 'Worth knowing before you listen<span class="cv">&#10095;</span></div><div class="bd">')
        b.append("".join(f'<p style="font-size:14px;margin-bottom:7px">{esc(f)}</p>' for f in c["flags"]))
        b.append('</div></div>')

    # moments
    b.append('<div class="acc open"><div class="hd">Key moments'
             f' <span class="tiny" style="font-weight:400">{len(c["moments"])}</span>'
             '<span class="cv">&#10095;</span></div><div class="bd">')
    b.append("".join(moment_html(c, m, i) for i, m in enumerate(c["moments"])))
    b.append('</div></div>')

    # milestones
    if c["milestones"]:
        b.append('<div class="acc"><div class="hd">Milestones<span class="cv">&#10095;</span></div><div class="bd">')
        for m in c["milestones"]:
            col = MS_COLOR.get(m["id"], "#64748b")
            txt = f'&ldquo;{esc(m["text"])}&rdquo;' if m.get("quote") else esc(m["text"])
            style = "font-style:italic" if m.get("quote") else ""
            jump = f'onclick="seek({m["sec"]})"' if c["yt"] else ""
            b.append(f'<div class="mo" style="border-left-color:{col}">'
                     f'<div class="row"><span class="tt" {jump}>{esc(m["t"])}</span>'
                     f'<span class="chip" style="background:{col}">{esc(MS_NAME.get(m["id"],m["id"]))}</span></div>'
                     f'<div style="font-size:14.5px;line-height:1.55;margin-top:4px;{style}">{txt}</div></div>')
        b.append('</div></div>')

    # arc
    if c["arc"]:
        b.append('<div class="acc"><div class="hd">How the call ran<span class="cv">&#10095;</span></div><div class="bd">')
        for p in c["arc"]:
            jump = f'onclick="seek({p["sec"]})"' if c["yt"] else ""
            b.append(f'<div class="row" style="padding:7px 0;border-bottom:1px solid var(--line)">'
                     f'<span class="tt" style="font-size:12.5px;font-weight:650;min-width:58px" {jump}>{esc(p["t"])}</span>'
                     f'<span style="font-size:14.5px">{esc(p["label"])}</span></div>')
        b.append('</div></div>')

    # notes
    if c["notes"]:
        b.append('<div class="acc"><div class="hd">Coaching notes<span class="cv">&#10095;</span></div><div class="bd">')
        for n in c["notes"]:
            b.append(f'<p style="font-size:14.5px;line-height:1.6;margin-bottom:9px">{esc(n)}</p>')
        b.append('</div></div>')

    # transcript
    b.append('<div class="acc"><div class="hd">Transcript<span class="cv">&#10095;</span></div><div class="bd">')
    b.append('<input class="search" id="tq" placeholder="Search this transcript">')
    b.append('<div class="tr" id="tr">')
    for u in c["utts"]:
        is_coach = (u["spk"] == c["coach_speaker"])
        jump = f'onclick="seek({u["sec"]})"' if c["yt"] else ""
        b.append(f'<div class="u{" c" if is_coach else ""}" data-s="{u["sec"]}">'
                 f'<span class="s" {jump}>{mmss(u["sec"])}</span>'
                 f'<span class="x">{esc(u["t"])}</span></div>')
    b.append('</div></div></div>')

    b.append(f'<p class="tiny" style="margin-top:26px">Bold lines in the transcript are '
             f'{esc(coach_name)}. Source file: {esc(c["stem"])}.txt</p>')
    b.append('</div>')

    js = FAV_JS + f"""
var YT={json.dumps(c['yt'])}, OFF={c['off']}, KEY={json.dumps(c['stem'])};
function seek(s){{
  if(!YT)return;
  var f=document.getElementById('pl');
  if(f)f.src='https://www.youtube.com/embed/'+YT+'?start='+Math.max(0,s+OFF)+'&autoplay=1&rel=0';
  window.scrollTo({{top:0,behavior:'smooth'}});
}}
window.addEventListener('DOMContentLoaded',function(){{
  var btn=document.getElementById('donebtn');
  function paint(){{
    var on=Store.done.is(KEY);
    btn.textContent=on?'Listened':'Mark listened';
    btn.style.background=on?'#059669':'';
    btn.style.color=on?'#fff':'';
    btn.style.borderColor=on?'#059669':'';
  }}
  btn.addEventListener('click',function(){{Store.done.toggle(KEY);paint()}});
  paint();
  var q=document.getElementById('tq'),tr=document.getElementById('tr');
  if(q)q.addEventListener('input',function(){{
    var v=q.value.trim().toLowerCase();
    tr.querySelectorAll('.u').forEach(function(u){{
      var x=u.querySelector('.x'), t=x.textContent;
      u.style.display=(!v||t.toLowerCase().indexOf(v)>=0)?'':'none';
    }});
  }});
  function fromHash(){{
    var h=location.hash.match(/^#t(\\d+)$/);
    if(h)seek(parseInt(h[1],10));
  }}
  window.addEventListener('hashchange',fromHash);
  fromHash();
}});
"""
    return shell(f"{c['company']} — {c['date']}", "".join(b), depth=1, extra_js=js)

# ===========================================================================
# 7. INDEX VIEWS
# ===========================================================================
def v_home():
    done_tiles = [
        ("#calls",      "Calls",       len(CALLS),      "#4f46e5", "#7c3aed"),
        ("#tracks",     "Talk Tracks", len(TRACKS),     "#0891b2", "#06b6d4"),
        ("#moments",    "Moments",     TOTAL_MOMENTS,   "#059669", "#10b981"),
        ("#coaches",    "Coaches",     len({c["coach"] for c in CALLS}), "#d97706", "#f59e0b"),
        ("#milestones", "Milestones",  len(MILESTONE_TYPES), "#e11d48", "#f43f5e"),
        ("#list",       "List",        len(CALLS),      "#475569", "#64748b"),
    ]
    t = []
    for href, label, n, a, bcol in done_tiles:
        t.append(f'<a class="tile" href="{href}" style="background:linear-gradient(135deg,{a},{bcol});'
                 f'box-shadow:0 14px 40px {a}44"><span class="n">{n}</span>'
                 f'<span class="big">{esc(label)}</span></a>')
    return f'<div class="wrap sect"><div class="tiles">{"".join(t)}</div></div>'

def v_calls():
    cards = []
    for c in CALLS:
        cards.append(
            f'<a class="card" href="calls/{c["slug"]}.html" data-co="{esc(c["coach"])}" '
            f'data-o="{esc(c["outcome"])}" data-k="{esc(c["stem"])}" '
            f'data-s="{esc((c["company"]+" "+c["headline"]+" "+c["summary"]).lower())}">'
            f'<div class="co">{esc(c["company"])}</div>'
            f'<div class="hl">{esc(c["headline"])}</div>'
            f'<div class="row" style="margin-top:11px">{coach_chip(c["coach"])}'
            f'{outcome_chip(c["outcome"])}'
            f'<span class="chip g">{esc(c["dur"])}</span>'
            f'<span class="chip g dot" style="display:none">Listened</span></div></a>')
    btns = '<button class="on" data-f="all">All</button>' + "".join(
        f'<button data-f="{k}">{esc(COACHES[k][0])}</button>'
        for k in ["AP", "RL", "ST", "BK"] if any(c["coach"] == k for c in CALLS))
    return (f'<div class="wrap sect">'
            f'<input class="search" id="cq" placeholder="Search company, headline or summary">'
            f'<div class="fil" id="cf">{btns}</div>'
            f'<div class="grid" id="cg">{"".join(cards)}</div>'
            f'<div class="empty" id="ce" style="display:none">Nothing matches.</div></div>')

def v_list():
    rows = []
    for c in CALLS:
        rows.append(
            f'<tr data-k="{esc(c["stem"])}"><td data-v="{esc(c["date"])}">{esc(c["date"])}</td>'
            f'<td data-v="{esc(c["company"])}"><a href="calls/{c["slug"]}.html" '
            f'style="font-weight:600">{esc(c["company"])}</a>'
            f'<div class="tiny">{esc(c["headline"])}</div></td>'
            f'<td data-v="{esc(c["coach"])}">{esc(COACHES.get(c["coach"],[c["coach"]])[0])}</td>'
            f'<td data-v="{esc(c["outcome"])}">{outcome_chip(c["outcome"])}</td>'
            f'<td data-v="{len(c["moments"])}">{len(c["moments"])}</td>'
            f'<td data-v="{esc(c["dur"])}">{esc(c["dur"])}</td>'
            f'<td class="dot tiny"></td></tr>')
    return (f'<div class="wrap sect"><table id="lt"><thead><tr>'
            f'<th data-c="0">Date</th><th data-c="1">Company</th><th data-c="2">Coach</th>'
            f'<th data-c="3">Outcome</th><th data-c="4">Moments</th><th data-c="5">Length</th>'
            f'<th data-c="6">Listened</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')

def v_coaches():
    out = []
    for code in ["AP", "RL", "ST", "BK"]:
        mine = [c for c in CALLS if c["coach"] == code]
        if not mine: continue
        name, a, bcol = COACHES[code]
        tr = [t for t in TRACKS if any(i["coach"] == code for i in t["inst"])]
        out.append(f'<div class="acc"><div class="hd">'
                   f'<span class="chip" style="background:{a}">{esc(name)}</span>'
                   f'<span class="tiny" style="font-weight:400">{len(mine)} calls &middot; '
                   f'{sum(len(c["moments"]) for c in mine)} moments &middot; '
                   f'{len(tr)} talk tracks</span><span class="cv">&#10095;</span></div><div class="bd">')
        out.append('<div class="grid">')
        for c in mine:
            out.append(f'<a class="card" href="calls/{c["slug"]}.html">'
                       f'<div class="co">{esc(c["company"])}</div>'
                       f'<div class="hl">{esc(c["headline"])}</div>'
                       f'<div class="row" style="margin-top:10px">{outcome_chip(c["outcome"])}'
                       f'<span class="chip g">{esc(c["date"])}</span></div></a>')
        out.append('</div></div></div>')
    return f'<div class="wrap sect">{"".join(out)}</div>'

def v_tracks():
    out = []
    order = {k: i for i, k in enumerate(CAT_ORDER)}
    for t in sorted(TRACKS, key=lambda t: order.get(t["cat"], 99)):
        cat_name, col = TRACK_CATS.get(t["cat"], (t["cat"], "#64748b"))
        coaches = sorted({i["coach"] for i in t["inst"]})
        out.append(f'<div class="acc" id="tk-{esc(t["id"])}"><div class="hd">'
                   f'<span class="chip" style="background:{col}">{esc(cat_name)}</span>'
                   f'<span>{esc(t["label"])}</span>'
                   f'<span class="tiny" style="font-weight:400">{len(t["inst"])} across '
                   f'{len(coaches)} coaches</span><span class="cv">&#10095;</span></div><div class="bd">')
        out.append(f'<p style="font-size:14.5px;line-height:1.6;margin-bottom:9px">{esc(t["desc"])}</p>')
        if t.get("variants"):
            out.append(f'<p class="muted" style="font-size:14px;line-height:1.6;margin-bottom:16px">'
                       f'{esc(t["variants"])}</p>')
        for i in t["inst"]:
            c = BY_STEM.get(i["stem"])
            if not c: continue
            key = f"{c['stem']}@{i['sec']}"
            meta = json.dumps({"c": c["company"], "t": i["t"], "s": c["slug"],
                               "ti": t["label"], "q": i["quote"][:400],
                               "co": c["coach"], "sec": i["sec"], "stem": c["stem"]})
            cname = COACHES.get(i["coach"], (i["coach"],))[0]
            link = f'calls/{c["slug"]}.html#t{i["sec"]}'
            out.append(
                f'<div class="mo" style="border-left-color:{col}">'
                f'<div class="row"><a class="tt" href="{link}">{esc(i["t"])}</a>'
                f'<span class="tiny">{esc(cname)} &middot; '
                f'<a href="calls/{c["slug"]}.html" style="text-decoration:underline">'
                f'{esc(i.get("company") or c["company"])}</a></span>'
                f'<button class="star" data-fav="{esc(key)}" data-meta=\'{esc(meta)}\'>&#9733;</button></div>'
                f'<div class="q" style="margin-top:4px">&ldquo;{esc(i["quote"])}&rdquo;</div>'
                + (f'<div class="w">{esc(i["note"])}</div>' if i.get("note") else "") +
                f'</div>')
        out.append('</div></div>')
    return f'<div class="wrap sect">{"".join(out)}</div>'

def v_moments():
    items = []
    for c in CALLS:
        for i, m in enumerate(c["moments"]):
            blob = f'{c["company"]} {m.get("title","")} {m.get("quote","")} {m.get("why","")}'.lower()
            items.append(f'<div data-co="{esc(c["coach"])}" data-s="{esc(blob)}">'
                         + moment_html(c, m, i, with_src=True) + '</div>')
    btns = '<button class="on" data-f="all">All</button>' + "".join(
        f'<button data-f="{k}">{esc(COACHES[k][0])}</button>' for k in ["AP", "RL", "ST", "BK"])
    return (f'<div class="wrap sect">'
            f'<input class="search" id="mq" placeholder="Search {TOTAL_MOMENTS} moments">'
            f'<div class="fil" id="mf">{btns}</div>'
            f'<div id="mg">{"".join(items)}</div>'
            f'<div class="empty" id="me" style="display:none">Nothing matches.</div></div>')

def v_milestones():
    out = []
    for key, name, a, bcol in MILESTONE_TYPES:
        hits = []
        for c in CALLS:
            for m in c["milestones"]:
                if m["id"] == key: hits.append((c, m))
        miss = [c for c in CALLS if not any(m["id"] == key for m in c["milestones"])]
        out.append(f'<div class="acc"><div class="hd">'
                   f'<span class="chip" style="background:{a}">{esc(name)}</span>'
                   f'<span class="tiny" style="font-weight:400">in {len(CALLS)-len(miss)} of '
                   f'{len(CALLS)} calls</span><span class="cv">&#10095;</span></div><div class="bd">')
        for c, m in hits:
            txt = f'&ldquo;{esc(m["text"])}&rdquo;' if m.get("quote") else esc(m["text"])
            st = "font-style:italic" if m.get("quote") else ""
            out.append(f'<div class="mo" style="border-left-color:{a}">'
                       f'<div class="tiny"><a href="calls/{c["slug"]}.html" '
                       f'style="color:var(--ink3)">{esc(c["company"])} &middot; '
                       f'{esc(COACHES.get(c["coach"],[c["coach"]])[0])}</a></div>'
                       f'<div class="row"><a class="tt" href="calls/{c["slug"]}.html#t{m["sec"]}">'
                       f'{esc(m["t"])}</a></div>'
                       f'<div style="font-size:14.5px;line-height:1.55;margin-top:3px;{st}">{txt}</div></div>')
        if miss:
            out.append(f'<p class="tiny" style="margin-top:14px">Not reached in: '
                       + ", ".join(esc(c["company"]) for c in miss[:18])
                       + (f' and {len(miss)-18} more' if len(miss) > 18 else "") + '</p>')
        out.append('</div></div>')
    return f'<div class="wrap sect">{"".join(out)}</div>'

def v_saved():
    return ('<div class="wrap sect">'
            '<div class="fil" id="sf"><button class="on" data-f="fav">Favorites</button>'
            '<button data-f="done">Listened</button></div>'
            '<div id="sg"></div>'
            '<div class="empty" id="se">Nothing saved yet. Star a moment, or mark a call listened.</div>'
            '</div>')

def build_index():
    views = [("home", v_home()), ("calls", v_calls()), ("list", v_list()),
             ("coaches", v_coaches()), ("tracks", v_tracks()), ("moments", v_moments()),
             ("milestones", v_milestones()), ("saved", v_saved())]
    body = "".join(f'<div class="view" id="v-{k}">{h}</div>' for k, h in views)

    call_map = {c["stem"]: {"c": c["company"], "s": c["slug"],
                            "co": COACHES.get(c["coach"], (c["coach"],))[0]} for c in CALLS}
    js = FAV_JS + f"""
var CALLMAP={json.dumps(call_map)};
function route(){{
  var h=(location.hash||'#home').replace('#','').split('?')[0];
  if(!document.getElementById('v-'+h))h='home';
  document.querySelectorAll('.view').forEach(function(v){{v.classList.remove('on')}});
  document.getElementById('v-'+h).classList.add('on');
  document.querySelectorAll('.nav a').forEach(function(a){{
    a.classList.toggle('on',(a.getAttribute('href')||'').indexOf('#'+h)>=0);
  }});
  if(h==='saved')renderSaved();
  paintDone();paintStars();
  window.scrollTo(0,0);
}}
window.addEventListener('hashchange',route);

function filt(inputId,wrapId,emptyId,filterId,sel){{
  var q=document.getElementById(inputId), w=document.getElementById(wrapId),
      e=document.getElementById(emptyId), f=document.getElementById(filterId), cur='all';
  function run(){{
    var v=q?q.value.trim().toLowerCase():'', n=0;
    w.querySelectorAll(sel).forEach(function(el){{
      var ok=(cur==='all'||el.getAttribute('data-co')===cur)&&
             (!v||(el.getAttribute('data-s')||'').indexOf(v)>=0);
      el.style.display=ok?'':'none'; if(ok)n++;
    }});
    e.style.display=n?'none':'';
  }}
  if(q)q.addEventListener('input',run);
  if(f)f.addEventListener('click',function(ev){{
    var b=ev.target.closest('button'); if(!b)return;
    cur=b.getAttribute('data-f');
    f.querySelectorAll('button').forEach(function(x){{x.classList.toggle('on',x===b)}});
    run();
  }});
  return run;
}}

function paintDone(){{
  document.querySelectorAll('#cg .card').forEach(function(a){{
    var d=a.querySelector('.dot');
    if(d)d.style.display=Store.done.is(a.getAttribute('data-k'))?'':'none';
  }});
  document.querySelectorAll('#lt tbody tr').forEach(function(r){{
    var d=r.querySelector('.dot');
    if(d)d.textContent=Store.done.is(r.getAttribute('data-k'))?'\\u2713':'';
  }});
}}

var savedTab='fav';
function renderSaved(){{
  var g=document.getElementById('sg'), e=document.getElementById('se'), out='';
  if(savedTab==='fav'){{
    var all=Store.fav.all(), ks=Object.keys(all);
    ks.sort();
    ks.forEach(function(k){{
      var m=all[k]; if(typeof m!=='object')return;
      out+='<div class="mo"><div class="tiny"><a href="calls/'+m.s+'.html" style="color:var(--ink3)">'+
           (m.c||'')+'</a></div><div class="row">'+
           '<a class="tt" href="calls/'+m.s+'.html#t'+m.sec+'">'+(m.t||'')+'</a>'+
           '<button class="star on" data-unfav="'+k+'">\\u2605</button></div>'+
           '<div class="ti">'+(m.ti||'')+'</div>'+
           (m.q?'<div class="q">\\u201C'+m.q+'\\u201D</div>':'')+'</div>';
    }});
    if(!ks.length)out='';
  }} else {{
    var d=Store.done.all();
    Object.keys(d).forEach(function(k){{
      var m=CALLMAP[k]; if(!m)return;
      out+='<a class="card" style="margin-bottom:10px" href="calls/'+m.s+'.html">'+
           '<div class="co">'+m.c+'</div><div class="hl">'+m.co+'</div></a>';
    }});
  }}
  g.innerHTML=out; e.style.display=out?'none':'';
  g.querySelectorAll('[data-unfav]').forEach(function(b){{
    b.addEventListener('click',function(){{Store.fav.del(b.getAttribute('data-unfav'));renderSaved()}});
  }});
}}
window.afterFav=function(){{if(location.hash==='#saved')renderSaved()}};

window.addEventListener('DOMContentLoaded',function(){{
  filt('cq','cg','ce','cf','.card');
  filt('mq','mg','me','mf','[data-co]');
  var sf=document.getElementById('sf');
  sf.addEventListener('click',function(ev){{
    var b=ev.target.closest('button'); if(!b)return;
    savedTab=b.getAttribute('data-f');
    sf.querySelectorAll('button').forEach(function(x){{x.classList.toggle('on',x===b)}});
    renderSaved();
  }});
  var lt=document.getElementById('lt'), dir=1, last=-1;
  lt.querySelectorAll('th[data-c]').forEach(function(th){{
    th.addEventListener('click',function(){{
      var ci=+th.getAttribute('data-c');
      dir=(ci===last)?-dir:1; last=ci;
      var tb=lt.querySelector('tbody'), rs=[].slice.call(tb.querySelectorAll('tr'));
      rs.sort(function(a,b){{
        var x=a.children[ci].getAttribute('data-v')||a.children[ci].textContent,
            y=b.children[ci].getAttribute('data-v')||b.children[ci].textContent,
            nx=parseFloat(x), ny=parseFloat(y);
        if(!isNaN(nx)&&!isNaN(ny))return (nx-ny)*dir;
        return x.localeCompare(y)*dir;
      }});
      rs.forEach(function(r){{tb.appendChild(r)}});
    }});
  }});
  route();
}});
"""
    return shell("First Time Conversations", body, depth=0, extra_js=js)

# ===========================================================================
# 8. WRITE
# ===========================================================================
def main():
    if os.path.exists(OUT): shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "calls"), exist_ok=True)
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(build_index())
    for c in CALLS:
        open(os.path.join(OUT, "calls", f"{c['slug']}.html"), "w", encoding="utf-8").write(call_page(c))
    n_vid = sum(1 for c in CALLS if c["yt"])
    print(f"built {len(CALLS)} call pages + index")
    print(f"videos linked: {n_vid}/{len(CALLS)}")
    print(f"moments: {TOTAL_MOMENTS} | milestones: {sum(len(c['milestones']) for c in CALLS)} "
          f"| talk tracks: {len(TRACKS)} ({sum(len(t['inst']) for t in TRACKS)} instances)")
    print(f"flagged calls: {sum(1 for c in CALLS if c['flags'])}")

if __name__ == "__main__":
    main()
