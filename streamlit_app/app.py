
import html
import itertools
import os
import re
import textwrap
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher

import plotly.graph_objects as go
import requests
import streamlit as st

# ---------------- CONFIGURATION ----------------
st.set_page_config(
    page_title="Post-Sales AI Platform",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = os.getenv("API_BASE", "http://localhost:8000").rstrip("/")
OVERVIEW = f"{API_BASE}/dashboard/overview"
SYNC = f"{API_BASE}/dashboard/sync"
TRENDS_W = f"{API_BASE}/dashboard/trends/weekly"
TRENDS_M = f"{API_BASE}/dashboard/trends/monthly"

# Muonekano tu (si data)
PAGES = {
    "Overview": {"icon": "▦", "title": "Post-Sales Feedback — Weekly Report", "bg": "#d1fae5", "fg": "#047857"},
    "Analysis": {"icon": "◈", "title": "Analysis — Feedback Classification", "bg": "#dbeafe", "fg": "#1d4ed8"},
    "Products": {"icon": "▤", "title": "Products — Where Complaints Come From", "bg": "#e0e7ff", "fg": "#4338ca"},
    "Alerts": {"icon": "⚠", "title": "Alerts — What Needs Attention Now", "bg": "#fee2e2", "fg": "#b91c1c"},
    "Trends": {"icon": "◐", "title": "Trends — Weekly & Monthly Feedback Volume", "bg": "#ede9fe", "fg": "#6d28d9"},
}
FONT = "Source Sans, Source Sans Pro, Source Sans 3, sans-serif"
TEAL, INDIGO, AMBER, RED, BLUE, SLATE = "#0d9488", "#6366f1", "#f59e0b", "#ef4444", "#3b82f6", "#94a3b8"
PALETTE = ["#0d9488", "#6366f1", "#f59e0b", "#ef4444", "#0ea5e9", "#a855f7", "#84cc16", "#94a3b8"]
SEVERITY_COLORS = {"critical": "#dc2626", "high": "#ea580c", "medium": "#eab308", "low": "#10b981"}
SENTIMENT_COLORS = {"positive": "#10b981", "neutral": "#94a3b8", "negative": "#ef4444"}
ALERT_KINDS = {
    "device": {"label": "Device-specific", "color": RED},
    "pattern": {"label": "Systemic patterns", "color": AMBER},
    "general": {"label": "General", "color": BLUE},
}
SAFETY_WORDS = ("smoke", "spark", "smell", "burn", "fire", "shock", "safety")

# ---------------- SESSION STATE ----------------
st.session_state.setdefault("page", "Overview")
if st.session_state.page not in PAGES:
    st.session_state.page = "Overview"


# ---------------- SMALL HELPERS ----------------
def esc(x):
    return html.escape("" if x is None else str(x))


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def num(x, default=0):
    if isinstance(x, bool) or x is None:
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def fmt(x):
    n = num(x)
    return f"{int(n):,}" if float(n).is_integer() else f"{n:,.1f}"


def pretty(s):
    s = str(s).replace("_", " ").strip()
    return s[:1].upper() + s[1:]


def hex_rgba(h, a):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{a})"


def clean_list(x):
    return [i for i in (x or []) if isinstance(i, dict)]


def sorted_by(x, key):
    return sorted(clean_list(x), key=lambda i: num(i.get(key)), reverse=True)


def empty_note(text):
    return f'<div class="empty">{esc(text)}</div>'


# ---------------- DATA (PIPELINE API) ----------------
@st.cache_data(ttl=20, show_spinner=False)
def _get(url):
    r = requests.get(url, timeout=8)
    r.raise_for_status()
    return r.json()


def fetch(url):
    """Rudisha (data, error). Makosa hayahifadhiwi kwenye cache."""
    try:
        return _get(url), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


LABEL_KEYS = ("label", "period", "week", "month", "date", "name", "x", "bucket",
              "week_start", "month_start", "week_label", "month_label", "week_ending")
VALUE_KEYS = ("count", "complaints", "total", "value", "volume", "feedback", "feedback_count",
              "total_complaints", "records", "n", "y")
PAR_LABELS = ("labels", "periods", "x", "weeks", "months", "dates", "categories")
PAR_VALUES = ("values", "counts", "y", "totals", "complaints", "volumes")


def _rows_to_series(rows):
    labels, values = [], []
    for i, row in enumerate(rows):
        if isinstance(row, dict):
            lab_key = next((k for k in LABEL_KEYS if k in row), None)
            if lab_key is None:
                lab_key = next((k for k, v in row.items() if isinstance(v, str)), None)
            rest = {k: v for k, v in row.items() if k != lab_key}
            val = next((rest[k] for k in VALUE_KEYS if is_num(rest.get(k))), None)
            if val is None:
                val = next((v for v in rest.values() if is_num(v)), None)
            if val is None:
                continue
            labels.append(str(row[lab_key]) if lab_key else str(i + 1))
            values.append(num(val))
        elif isinstance(row, (list, tuple)) and len(row) == 2 and is_num(row[1]):
            labels.append(str(row[0]))
            values.append(num(row[1]))
        elif is_num(row):
            labels.append(str(i + 1))
            values.append(num(row))
    return labels, values


def extract_series(payload, prefer=None, depth=0):
    """Geuza majibu ya trends (muundo wowote wa kawaida) kuwa (labels, values)."""
    if payload is None or depth > 4:
        return [], []
    if isinstance(payload, list):
        return _rows_to_series(payload)
    if isinstance(payload, dict):
        lk = next((k for k in PAR_LABELS if isinstance(payload.get(k), list) and payload[k]
                   and not isinstance(payload[k][0], (dict, list))), None)
        vk = next((k for k in PAR_VALUES if isinstance(payload.get(k), list) and payload[k]
                   and is_num(payload[k][0])), None)
        if lk and vk:
            return [str(a) for a in payload[lk]], [num(b) for b in payload[vk]]
        keys = sorted(payload.keys(), key=lambda k: 0 if (prefer and prefer in str(k).lower()) else 1)
        for k in keys:
            v = payload[k]
            if isinstance(v, (list, dict)):
                lab, val = extract_series(v, prefer, depth + 1)
                if val:
                    return lab, val
        if payload and all(is_num(v) for v in payload.values()):
            return [str(k) for k in payload], [num(v) for v in payload.values()]
    return [], []


def describe_payload(payload):
    if payload is None:
        return "no response"
    if isinstance(payload, dict):
        return "object with keys: " + ", ".join(list(payload.keys())[:8]) if payload else "empty object"
    if isinstance(payload, list):
        if not payload:
            return "empty list"
        first = payload[0]
        return f"list of {len(payload)}; first item: " + (
            "keys " + ", ".join(list(first.keys())[:8]) if isinstance(first, dict) else type(first).__name__)
    return type(payload).__name__


def last_sync_raw(data):
    runs = (data or {}).get("pipeline_runs") or []
    if runs and isinstance(runs[0], dict):
        return runs[0].get("last_synced_at")
    return None


def last_sync_short(data):
    ts = last_sync_raw(data)
    return str(ts).replace("T", " ")[:16] if ts else "—"


def snapshot_pretty(data):
    ts = last_sync_raw(data)
    if not ts:
        return "—"
    try:
        return datetime.fromisoformat(str(ts)).strftime("%d %b %Y, %H:%M")
    except ValueError:
        return str(ts).replace("T", " ")[:16]


def run_sync():
    try:
        r = requests.post(SYNC, timeout=120)
        if r.status_code == 405:
            r = requests.get(SYNC, timeout=120)
        r.raise_for_status()
        return True, "Sync complete. Dashboard updated."
    except Exception as e:  # noqa: BLE001
        return False, f"Sync failed: {e}"


def do_sync():
    with st.spinner("Syncing latest feedback data..."):
        ok, msg = run_sync()
    st.session_state.flash = (msg, "✅" if ok else "⚠️")
    if ok:
        st.cache_data.clear()
    st.rerun()


# Symptoms-by-product: pipeline inaweza kutuma kwa muundo tofauti; tunatafuta kwa akili
PRODUCT_KEYS = ("product", "product_name", "device", "model")
SYMPTOM_KEYS = ("symptom", "symptom_label", "label", "name")
COUNT_KEYS = ("count", "complaints", "records", "links", "total", "n")


def _first_num(d, keys):
    return next((num(d[k]) for k in keys if is_num(d.get(k))), None)


def extract_product_symptoms(data):
    """Rudisha list ya (product, symptom, count) au [] ikiwa pipeline haitumi."""
    rows = []
    # 1) ndani ya kila product: {"product":..,"symptoms":[{label,count}]}
    for p in clean_list(data.get("products")):
        pname = p.get("product") or p.get("name")
        for k in ("symptoms", "top_symptoms", "symptom_breakdown"):
            if isinstance(p.get(k), list) and pname:
                for s in clean_list(p[k]):
                    sname = next((s[x] for x in SYMPTOM_KEYS if s.get(x)), None)
                    c = _first_num(s, COUNT_KEYS)
                    if sname and c is not None:
                        rows.append((str(pname), pretty(sname), c))
    if rows:
        return rows
    # 2) list bapa: [{product, symptom, count}]
    for k, v in data.items():
        if k in ("products", "alerts", "symptoms") or not isinstance(v, list):
            continue
        items = clean_list(v)
        if not items:
            continue
        s0 = items[0]
        pk = next((x for x in PRODUCT_KEYS if x in s0), None)
        sk = next((x for x in SYMPTOM_KEYS if x in s0 and isinstance(s0[x], str)), None)
        if pk and sk and _first_num(s0, COUNT_KEYS) is not None:
            for it in items:
                c = _first_num(it, COUNT_KEYS)
                if it.get(pk) and it.get(sk) and c is not None:
                    rows.append((str(it[pk]), pretty(it[sk]), c))
            if rows:
                return rows
    # 3) dict ya dict: {"product_symptoms": {"AC": {"error code": 12}}}
    for k, v in data.items():
        if isinstance(v, dict) and "symptom" in k.lower() and v and all(isinstance(x, dict) for x in v.values()):
            for p, sd in v.items():
                for s, c in sd.items():
                    if is_num(c):
                        rows.append((str(p), pretty(s), num(c)))
            if rows:
                return rows
    return rows


def extract_magnitude(msg):
    m = re.search(r"(\d[\d,]*)\s+(high[- ]severity\s+)?(complaints?|records?|cases?|reports?|incidents?)", msg or "", re.I)
    if m:
        return int(m.group(1).replace(",", "")), ("high-sev " if m.group(2) else "") + m.group(3).lower()
    m = re.search(r"(\d[\d,]*)", msg or "")
    return (int(m.group(1).replace(",", "")), "") if m else (None, "")


def parse_alerts(alerts):
    items = []
    for a in clean_list(alerts):
        t = str(a.get("type", ""))
        kind = "device" if a.get("product") else ("pattern" if "pattern" in t else "general")
        title = str(a.get("product") or pretty(re.sub(r"^pattern[_ ]", "", t)) or "Alert")
        msg = str(a.get("message", ""))
        mag, unit = extract_magnitude(msg)
        safety = any(w in (t + " " + msg).lower() for w in SAFETY_WORDS)
        items.append({"kind": kind, "title": title, "message": msg, "mag": mag, "unit": unit, "safety": safety})
    return items


# ---------------- RECOMMENDATION ENGINE (inatokana na data ya sasa) ----------------
PRI_ORDER = {"high": 0, "medium": 1, "low": 2}


def rec(priority, message, action):
    return {"priority": priority, "message": message, "action": action}


def tier(value, high, medium):
    return "high" if value >= high else ("medium" if value >= medium else "low")


def pct_change(values):
    if len(values) < 2 or values[-2] == 0:
        return None
    return (values[-1] - values[-2]) / values[-2] * 100


def finish(recs, limit=5):
    return sorted(recs, key=lambda r: PRI_ORDER[r["priority"]])[:limit]


def recs_overview(data, wv):
    out, m = [], data.get("metrics") or {}
    total, hs = num(m.get("total_complaints")), num(m.get("high_severity"))
    neg, ana = num(m.get("negative_sentiment")), num(m.get("analyzed_complaints"))
    prods, syms = sorted_by(data.get("products"), "complaints"), sorted_by(data.get("symptoms"), "count")
    if prods and total:
        p = prods[0]
        sh = num(p.get("complaints")) / total * 100
        out.append(rec(tier(sh, 30, 15), f"{p.get('product')} drives {sh:.0f}% of complaints ({fmt(p.get('complaints'))}).",
                       "Inspect its recent production batches and QA logs."))
    if hs and total:
        sh = hs / total * 100
        out.append(rec(tier(sh, 5, 2), f"{fmt(hs)} high-severity cases ({sh:.1f}% of all feedback).",
                       "Triage these first in a QA review."))
    if syms and total:
        s = syms[0]
        out.append(rec("medium", f"“{s.get('label')}” is the top symptom ({fmt(s.get('count'))} reports).",
                       "Start root-cause analysis on this symptom."))
    chg = pct_change(wv)
    if chg is not None and chg >= 5:
        out.append(rec(tier(chg, 15, 5), f"Weekly volume is up {chg:.0f}% vs last week.",
                       "Add QA/support capacity; check for a new batch or release."))
    elif chg is not None and chg <= -10:
        out.append(rec("low", f"Weekly volume is down {abs(chg):.0f}% vs last week.",
                       "Keep monitoring and record what changed."))
    if neg and total and neg / total >= 0.10:
        sh = neg / total * 100
        out.append(rec(tier(sh, 20, 10), f"{sh:.0f}% of feedback is negative.",
                       "Review negative themes and follow up with affected customers."))
    if total and ana < total * 0.95:
        out.append(rec("medium", f"{fmt(total - ana)} complaints are not analyzed yet.", "Run Sync to process the backlog."))
    return finish(out)


def recs_analysis(data):
    out = []
    preds = sorted_by(data.get("predictions"), "probability")
    links = sorted_by(data.get("symptom_failure_links"), "links")
    sev = clean_list(data.get("severity"))
    cats = sorted_by(data.get("categories"), "count")
    if preds:
        p = preds[0]
        pr = num(p.get("probability"))
        out.append(rec(tier(pr, 60, 40), f"{p.get('cause')} is the likeliest root cause ({pr:.0f}% confidence).",
                       "Confirm with engineering; inspect linked parts and batches."))
        if pr < 50:
            out.append(rec("medium", "Evidence is thin: no cause is above 50%.", "Collect more diagnostic data before acting."))
    if links:
        l = links[0]
        out.append(rec("medium", f"Strongest link: {pretty(l.get('symptom'))} → {pretty(l.get('failure'))} ({fmt(l.get('links'))} cases).",
                       "Add a targeted diagnostic check for this pair in service."))
    sev_total = sum(num(s.get("count")) for s in sev)
    crit = next((num(s.get("count")) for s in sev if str(s.get("label", "")).lower() == "critical"), 0)
    if crit and sev_total:
        sh = crit / sev_total * 100
        out.append(rec(tier(sh, 10, 3), f"{fmt(crit)} critical cases ({sh:.0f}% of classified).", "Escalate critical cases to QA today."))
    cat_total = sum(num(c.get("count")) for c in cats)
    if cats and cat_total and num(cats[0].get("count")) / cat_total >= 0.30:
        sh = num(cats[0].get("count")) / cat_total * 100
        out.append(rec("medium", f"{pretty(cats[0].get('label'))} is the top failure area ({sh:.0f}%).",
                       "Give this area a named engineering owner and fix plan."))
    return finish(out)


def recs_products(data, ps_rows):
    out, m = [], data.get("metrics") or {}
    prods = sorted_by(data.get("products"), "complaints")
    total = num(m.get("total_complaints")) or sum(num(p.get("complaints")) for p in prods)
    if len(prods) >= 3 and total:
        sh = sum(num(p.get("complaints")) for p in prods[:3]) / total * 100
        out.append(rec(tier(sh, 70, 50), f"Top 3 products = {sh:.0f}% of complaints.", "Focus QA effort on these three first."))
    if len(prods) >= 2 and num(prods[1].get("complaints")):
        ratio = num(prods[0].get("complaints")) / num(prods[1].get("complaints"))
        if ratio >= 1.3:
            out.append(rec("medium", f"{prods[0].get('product')} has {ratio:.1f}× the complaints of {prods[1].get('product')}.",
                           "Compare their builds and suppliers to find the gap."))
    if prods and ps_rows:
        top = str(prods[0].get("product"))
        mine = defaultdict(float)
        for p, s, c in ps_rows:
            if p == top:
                mine[s] += c
        tot = sum(mine.values())
        if tot:
            s, c = max(mine.items(), key=lambda kv: kv[1])
            if c / tot >= 0.30:
                out.append(rec("medium", f"“{s}” is {c / tot * 100:.0f}% of {top} complaints.", "Prepare a fix guide and spare parts for it."))
    return finish(out)


def recs_alerts(items):
    out = []
    safety = [a for a in items if a["safety"]]
    if safety:
        n = sum(a["mag"] or 0 for a in safety)
        out.append(rec("high", f"Safety symptoms reported" + (f" ({fmt(n)} cases)." if n else "."),
                       "Run an immediate safety review; consider a customer advisory."))
    dev = sorted([a for a in items if a["kind"] == "device"], key=lambda a: a["mag"] or 0, reverse=True)
    if dev:
        a = dev[0]
        out.append(rec("high", f"{a['title']} has the biggest device alert" + (f" ({fmt(a['mag'])} {a['unit']})." if a["mag"] else "."),
                       "Escalate to the product owner and QA."))
    pat = sorted([a for a in items if a["kind"] == "pattern"], key=lambda a: a["mag"] or 0, reverse=True)
    if pat:
        a = pat[0]
        out.append(rec("medium", f"Systemic pattern: {a['title']}" + (f" ({fmt(a['mag'])} {a['unit']})." if a["mag"] else "."),
                       "Check shared components and suppliers across products."))
    if not items:
        out.append(rec("low", "No active alerts in this snapshot.", "Keep monitoring."))
    return finish(out)


def recs_trends(wl, wv, ml, mv):
    out = []
    chg = pct_change(wv)
    if wv and len(wv) >= 3 and wv[-1] == max(wv):
        out.append(rec("high", f"Latest week is the highest on record ({fmt(wv[-1])}).", "Investigate a new batch or release now."))
    elif chg is not None and abs(chg) >= 5:
        out.append(rec(tier(chg, 15, 5) if chg > 0 else "low", f"Weekly volume {'up' if chg > 0 else 'down'} {abs(chg):.0f}% vs last week.",
                       "Add QA capacity." if chg > 0 else "Keep monitoring what changed."))
    if len(wv) >= 8:
        recent, prior = sum(wv[-4:]) / 4, sum(wv[-8:-4]) / 4
        if prior:
            c4 = (recent - prior) / prior * 100
            if abs(c4) >= 10:
                out.append(rec("high" if c4 >= 20 else ("medium" if c4 > 0 else "low"),
                               f"4-week average {'up' if c4 > 0 else 'down'} {abs(c4):.0f}% vs the 4 weeks before.",
                               "Plan extra capacity for the coming weeks." if c4 > 0 else "Verify fixes are holding."))
    if wv and max(wv) > 0 and wv[-1] < max(wv) * 0.8:
        pk = wl[wv.index(max(wv))]
        out.append(rec("low", f"Latest week is {(1 - wv[-1] / max(wv)) * 100:.0f}% below the peak ({pk}).",
                       "Identify what changed after the peak and repeat it."))
    if len(mv) >= 3:
        pk = ml[mv.index(max(mv))]
        out.append(rec("medium", f"Peak month so far: {pk} ({fmt(max(mv))}).", "Staff up ahead of this period next year."))
        mchg = pct_change(mv)
        if mchg is not None and abs(mchg) >= 10:
            out.append(rec("medium" if mchg > 0 else "low", f"Latest month {'up' if mchg > 0 else 'down'} {abs(mchg):.0f}% vs the month before.",
                           "Review capacity and open root-cause work."))
    return finish(out)


# ---------------- CHARTS ----------------
def base(fig, height, l=10, r=10, t=10, b=10):
    fig.update_layout(
        height=height, margin=dict(l=l, r=r, t=t, b=b),
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        font=dict(family=FONT, color="#334155", size=12), showlegend=False,
        hoverlabel=dict(font_family=FONT),
    )
    return fig


def label_margin(labels, extra=16, cap=280):
    """Nafasi ya kushoto kwa majina marefu ya y-axis (px)."""
    return int(min(cap, max([len(str(x)) for x in labels] + [4]) * 7.6 + extra))


def show(fig, key):
    st.plotly_chart(fig, theme=None, key=key, config={"displayModeBar": False})


def short_label(l):
    """2026-07-08 / 2026-07-08T00:00:00 -> '08 Jul'; lebo nyingine zinabaki kama zilivyo."""
    l = str(l)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}([T ].*)?", l):
        try:
            return datetime.fromisoformat(l[:10]).strftime("%d %b")
        except ValueError:
            return l
    return l


def volume_fig(labels, values, color, height=300, unit="feedback"):
    labels = [short_label(l) for l in labels]
    avg = sum(values) / len(values)
    fig = go.Figure(go.Scatter(
        x=labels, y=values, mode="lines+markers",
        line=dict(color=color, width=3, shape="spline", smoothing=0.5), marker=dict(size=7, color=color),
        fill="tozeroy", fillcolor=hex_rgba(color, 0.13),
        hovertemplate="%{x}<br><b>%{y:,.0f}</b> " + unit + "<extra></extra>",
    ))
    base(fig, height, l=44, t=24, b=34)
    fig.update_xaxes(showgrid=False, type="category", automargin=True, range=[-0.4, len(labels) - 0.6],
                     tickangle=-30 if (len(labels) > 8 and max(len(l) for l in labels) > 9) else 0)
    fig.update_yaxes(gridcolor="#eef2f6", rangemode="tozero", range=[0, max(values) * 1.3], automargin=True)
    fig.add_hline(y=avg, line_dash="dot", line_color="#94a3b8", line_width=1,
                  annotation_text=f"avg {fmt(avg)}", annotation_position="bottom left", annotation_xshift=6,
                  annotation_font=dict(size=11, color="#64748b"))
    last_i, peak_i = len(values) - 1, values.index(max(values))
    chg = pct_change(values)
    now_txt = f"<b>Now {fmt(values[-1])}</b>" + (f" ({chg:+.0f}%)" if chg is not None else "")
    if peak_i == last_i:
        now_txt = "<b>Peak · " + now_txt.replace("<b>", "").replace("</b>", "") + "</b>"
    up_bad = chg is not None and chg > 0
    fig.add_annotation(x=labels[last_i], y=values[last_i], text=now_txt, showarrow=True, arrowhead=2, arrowcolor="#64748b",
                       ax=-34, ay=-40, font=dict(size=12, color="#b91c1c" if up_bad else "#047857"),
                       bgcolor="#ffffff", bordercolor="#e2e8f0", borderpad=4)
    if peak_i != last_i and len(values) > 2:
        fig.add_annotation(x=labels[peak_i], y=values[peak_i], text=f"<b>Peak {fmt(values[peak_i])}</b>", showarrow=True,
                           arrowhead=2, arrowcolor="#b45309", ax=0, ay=-38, font=dict(size=12, color="#b45309"),
                           bgcolor="#fffbeb", bordercolor="#fde68a", borderpad=4)
    return fig


def donut_fig(labels, values, colors, center_big, center_small, height=300):
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.66, sort=False, direction="clockwise",
        marker=dict(colors=colors, line=dict(color="#ffffff", width=3)),
        textinfo="label+percent", textposition="outside", insidetextorientation="horizontal",
        hovertemplate="%{label}: <b>%{value:,}</b> (%{percent})<extra></extra>",
    ))
    base(fig, height, l=50, r=50, t=20, b=20)
    fig.add_annotation(text=f"<b>{center_big}</b><br><span style='font-size:12px;color:#64748b'>{center_small}</span>",
                       x=0.5, y=0.5, showarrow=False, font=dict(size=26, color="#0f172a"))
    return fig


def hbar_fig(labels, values, colors, height=300, unit="", extra_text=None, r=70):
    text = extra_text or [fmt(v) for v in values]
    fig = go.Figure(go.Bar(
        y=labels, x=values, orientation="h", marker=dict(color=colors, line=dict(width=0)),
        text=text, textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: <b>%{x:,.0f}</b> " + unit + "<extra></extra>",
    ))
    base(fig, height, l=label_margin(labels), r=r, t=6, b=6)
    fig.update_yaxes(autorange="reversed", automargin=True, showgrid=False)
    fig.update_xaxes(showgrid=False, showticklabels=False, range=[0, max(values) * 1.18 if values else 1])
    return fig


def sym_by_product_fig(rows, height=340):
    ptot, stot, cell = defaultdict(float), defaultdict(float), defaultdict(float)
    for p, s, c in rows:
        ptot[p] += c
        stot[s] += c
        cell[(p, s)] += c
    top_syms = [s for s, _ in sorted(stot.items(), key=lambda kv: -kv[1])[:6]]
    rest = [s for s in stot if s not in top_syms]
    prods = sorted(ptot, key=lambda p: -ptot[p])[:8]
    mx = max(ptot[p] for p in prods) or 1
    fig = go.Figure()
    for i, s in enumerate(top_syms + (["Other"] if rest else [])):
        xs = [cell[(p, s)] if s != "Other" else sum(cell[(p, x)] for x in rest) for p in prods]
        fig.add_trace(go.Bar(
            name=s, y=prods, x=xs, orientation="h", marker=dict(color=PALETTE[i % len(PALETTE)], line=dict(color="#fff", width=1)),
            text=[fmt(x) if x >= mx * 0.09 else "" for x in xs], textposition="inside", insidetextanchor="middle",
            textfont=dict(color="#ffffff", size=11),
            hovertemplate="%{y}<br>" + s + ": <b>%{x:,.0f}</b><extra></extra>",
        ))
    for p in prods:
        fig.add_annotation(x=ptot[p], y=p, text=f"<b>{fmt(ptot[p])}</b>", showarrow=False, xanchor="left", xshift=6,
                           font=dict(size=12, color="#0f172a"))
    base(fig, height, l=label_margin(prods), r=40, t=6, b=50)
    fig.update_layout(barmode="stack", showlegend=True,
                      legend=dict(orientation="h", y=-0.08, x=0, font=dict(size=11), traceorder="normal"))
    fig.update_yaxes(autorange="reversed", automargin=True, showgrid=False)
    fig.update_xaxes(showgrid=False, showticklabels=False, range=[0, mx * 1.12])
    return fig


def heatmap_fig(rows, height=340):
    ptot, stot, cell = defaultdict(float), defaultdict(float), defaultdict(float)
    for p, s, c in rows:
        ptot[p] += c
        stot[s] += c
        cell[(p, s)] += c
    prods = sorted(ptot, key=lambda p: -ptot[p])[:10]
    syms = sorted(stot, key=lambda s: -stot[s])[:8]
    z = [[cell[(p, s)] for s in syms] for p in prods]
    zmax = max((v for r in z for v in r), default=1) or 1
    fig = go.Figure(go.Heatmap(
        z=z, x=syms, y=prods, colorscale=[[0, "#f1f5f9"], [0.5, "#5eead4"], [1, "#0f766e"]], showscale=False, xgap=3, ygap=3,
        hovertemplate="%{y} · %{x}<br><b>%{z:,.0f}</b> complaints<extra></extra>",
    ))
    for pi, p in enumerate(prods):
        for si, s_ in enumerate(syms):
            v = z[pi][si]
            if v:
                fig.add_annotation(x=s_, y=p, text=fmt(v), showarrow=False,
                                   font=dict(size=12, color="#ffffff" if v / zmax > 0.62 else "#0f172a"))
    base(fig, height, l=label_margin(prods), r=10, t=6, b=10)
    fig.update_yaxes(autorange="reversed", automargin=True)
    fig.update_xaxes(side="top", automargin=True)
    return fig


def norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", str(s).lower()).strip()


def match_pred(failure, preds):
    f, best, score = norm(failure), None, 0
    for p in preds:
        c = norm(p.get("cause", ""))
        if not c or not f:
            continue
        s = 1 if f == c else (0.9 if (f in c or c in f) else SequenceMatcher(None, f, c).ratio())
        if s > score:
            best, score = p, s
    return best if score >= 0.6 else None


def conf_color(p):
    if p is None:
        return "#cbd5e1"
    pr = num(p.get("probability"))
    return "#0f766e" if pr >= 65 else ("#14b8a6" if pr >= 50 else "#5eead4")


def sankey_fig(links, preds, height=None):
    links = sorted(links, key=lambda l: -num(l.get("links")))
    syms = list(dict.fromkeys(pretty(l.get("symptom", "")) for l in links))
    causes = list(dict.fromkeys(pretty(l.get("failure", "")) for l in links))
    match = {c: match_pred(c, preds) for c in causes}
    cause_labels = [f"{c} · {num(match[c].get('probability')):.0f}%" if match[c] else c for c in causes]
    node_colors = [INDIGO] * len(syms) + [conf_color(match[c]) for c in causes]
    src, tgt, val, lcol, hov = [], [], [], [], []
    for l in links:
        s, c = pretty(l.get("symptom", "")), pretty(l.get("failure", ""))
        src.append(syms.index(s))
        tgt.append(len(syms) + causes.index(c))
        val.append(num(l.get("links")))
        lcol.append(hex_rgba(conf_color(match[c]) if match[c] else INDIGO, 0.32))
        hov.append(f"{s} → {c}<br>{fmt(l.get('links'))} linked cases")
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=syms + cause_labels, color=node_colors, pad=22, thickness=20, line=dict(color="#ffffff", width=1),
                  hovertemplate="%{label}<br><b>%{value:,.0f}</b> linked cases<extra></extra>"),
        link=dict(source=src, target=tgt, value=val, color=lcol, customdata=hov, hovertemplate="%{customdata}<extra></extra>"),
        textfont=dict(family=FONT, size=13, color="#0f172a"),
    ))
    base(fig, height or max(320, 52 * max(len(syms), len(causes)) + 60), l=6, r=6, t=8, b=8)
    return fig


def evidence_fig(preds, height=300):
    preds = sorted(preds, key=lambda p: -num(p.get("probability")))
    labels = [pretty(p.get("cause", "")) for p in preds]
    probs = [max(0, min(100, num(p.get("probability")))) for p in preds]
    text = [f"<b>{pr:.0f}%</b> · {fmt(p.get('predictions'))} cases" for pr, p in zip(probs, preds)]
    fig = go.Figure(go.Bar(
        y=labels, x=probs, orientation="h", marker=dict(color=[conf_color(p) for p in preds]),
        text=text, textposition="outside", cliponaxis=False,
        customdata=[[str(p.get("evidence") or "")] for p in preds],
        hovertemplate="%{y}<br>%{customdata[0]}<extra></extra>",
    ))
    base(fig, height, l=label_margin(labels), r=90, t=6, b=6)
    fig.update_yaxes(autorange="reversed", automargin=True, showgrid=False)
    fig.update_xaxes(range=[0, 100], showgrid=False, showticklabels=False)
    fig.add_vline(x=50, line_dash="dot", line_color="#94a3b8", line_width=1)
    return fig


def alerts_fig(items, height=None):
    ordered = sorted(items, key=lambda a: -(a["mag"] or 0))
    order = [a["title"] for a in ordered]
    fig = go.Figure()
    for kind, meta in ALERT_KINDS.items():
        sub = [a for a in ordered if a["kind"] == kind]
        if not sub:
            continue
        fig.add_trace(go.Bar(
            name=meta["label"], y=[a["title"] for a in sub], x=[a["mag"] or 0 for a in sub], orientation="h",
            marker=dict(color=meta["color"]),
            text=[(f"<b>{fmt(a['mag'])}</b> {a['unit']}" if a["mag"] else "flagged") + ("  ⚠ safety" if a["safety"] else "") for a in sub],
            textposition="outside", cliponaxis=False,
            customdata=[[textwrap.fill(a["message"], 46).replace("\n", "<br>")] for a in sub],
            hovertemplate="<b>%{y}</b><br>%{customdata[0]}<extra></extra>",
        ))
    mx = max([a["mag"] or 0 for a in items] + [1])
    base(fig, height or max(260, 58 * len(items) + 70), l=label_margin(order), r=150, t=30, b=6)
    fig.update_layout(barmode="overlay", showlegend=True, legend=dict(orientation="h", y=1.12, x=0, font=dict(size=12)))
    fig.update_yaxes(autorange="reversed", categoryorder="array", categoryarray=order, automargin=True, showgrid=False)
    fig.update_xaxes(showgrid=False, showticklabels=False, range=[0, mx * 1.25])
    return fig


# ---------------- FLASH MESSAGE (baada ya sync) ----------------
_flash = st.session_state.pop("flash", None)
if _flash:
    st.toast(_flash[0], icon=_flash[1])

# ---------------- LOAD DATA ----------------
data, data_err = fetch(OVERVIEW)

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.markdown(
        '<div class="brand"><span class="brand-mark">◈</span>Post-Sales AI</div>'
        '<div class="brand-sub">Feedback analysis & failure prediction</div>',
        unsafe_allow_html=True,
    )
    for name, meta in PAGES.items():
        if st.button(f"{meta['icon']}  {name}", key=f"nav_{name}"):
            st.session_state.page = name
            st.rerun()

    st.markdown(
        f'<div class="side-sync"><div class="k">Last sync</div><div class="v">{esc(last_sync_short(data))}</div></div>',
        unsafe_allow_html=True,
    )
    if st.button("⟳  Sync This Week", key="sync_side", type="primary"):
        do_sync()

    st.markdown('<div class="side-gap"></div>', unsafe_allow_html=True)
    autohide = st.toggle(
        "Auto-hide (hover)", key="autohide",
        help="Sidebar inajificha. Weka mouse kwenye ukingo wa kushoto wa skrini ili kuirudisha.",
    )
    if autohide:
        st.caption("Hover the left edge to bring it back. Turn this off to pin the sidebar again.")

page = st.session_state.page
active = PAGES[page]

# ---------------- CSS ----------------
BASE_CSS = """
.stApp {
    background: #e9eff1;
}
.block-container {
    padding: 1.2rem 1.6rem 2rem 1.6rem;
    max-width: 1500px;
}

/* Hide Streamlit chrome */
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stAppDeployButton"], [data-testid="stMainMenu"], #MainMenu { display:none !important; }
footer { visibility:hidden; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #dbe3e7;
}
section[data-testid="stSidebar"] .brand {
    display:flex; align-items:center; gap:9px;
    font-size:18px; font-weight:800; color:#18262b;
    margin:4px 0 2px 0;
}
section[data-testid="stSidebar"] .brand-mark {
    width:28px; height:28px; border-radius:8px;
    display:flex; align-items:center; justify-content:center;
    background:#e4f5f2; color:#0b8f82; font-size:17px;
}
section[data-testid="stSidebar"] .brand-sub {
    font-size:11px; color:#718087; margin:0 0 18px 37px;
}
[class*="st-key-nav_"] button {
    width:100%; justify-content:flex-start;
    background:transparent; border:0; box-shadow:none;
    color:#516068; border-radius:9px;
    padding:.48rem .72rem; font-size:13px; font-weight:600;
}
[class*="st-key-nav_"] button:hover {
    background:#eef7f5; color:#087f74;
}
[class*="st-key-nav_"] button * {
    justify-content:flex-start; text-align:left; color:inherit !important;
}
.side-sync {
    margin:22px 0 9px 0; padding:10px 12px;
    background:#f7fafb; border:1px solid #e1e8eb; border-radius:9px;
}
.side-sync .k { font-size:10px; color:#829098; font-weight:700; text-transform:uppercase; letter-spacing:.05em; }
.side-sync .v { font-size:12px; color:#26363c; font-weight:700; margin-top:2px; }
.side-gap { height:8px; }

.st-key-sync_side button, .st-key-sync_top button {
    width:100%; background:#0b8f82 !important; border:none !important;
    color:#fff !important; font-weight:700; border-radius:8px;
    box-shadow:0 2px 6px rgba(11,143,130,.18);
}
.st-key-sync_side button:hover, .st-key-sync_top button:hover {
    background:#08766c !important;
}
.st-key-sync_side button *, .st-key-sync_top button * { color:#fff !important; }

/* Header */
.main-header {
    background:#ffffff; border:1px solid #dce5e8;
    border-radius:13px; padding:13px 17px;
    box-shadow:0 2px 8px rgba(31,50,58,.04);
}
.main-header h1 {
    margin:0; font-size:19px; font-weight:800;
    color:#1c2b31; line-height:1.25;
}
.main-header .meta {
    font-size:11px; color:#7a8990; margin-top:4px;
}
.main-header .meta b { color:#0b8f82; }

/* Cards */
[class*="st-key-card_"] {
    background:#fff;
    border:1px solid #dce5e8;
    border-radius:12px;
    padding:13px 14px 11px 14px;
    box-shadow:0 2px 8px rgba(31,50,58,.045);
}
.ct {
    font-size:13.5px; font-weight:800; color:#1d2b30;
    line-height:1.25;
}
.cs {
    font-size:10.5px; color:#7b8990;
    margin-top:3px; line-height:1.35;
}
.mini { font-size:10.5px; font-weight:700; color:#56666e; margin:3px 0 0; }
.empty { font-size:11.5px; color:#7c8a91; padding:12px 0; }
.note {
    font-size:10.5px; color:#8a6412; background:#fff9e8;
    border:1px solid #f2dfa2; border-radius:7px; padding:6px 8px;
}

/* KPI */
.kpi {
    background:#fff; border:1px solid #dce5e8; border-radius:10px;
    padding:10px 12px; box-shadow:0 2px 7px rgba(31,50,58,.035);
}
.kpi .l { font-size:10px; color:#7b8990; font-weight:700; }
.kpi .v {
    font-size:24px; font-weight:850; color:#1b2b31;
    line-height:1.12; font-variant-numeric:tabular-nums; margin-top:2px;
}
.kpi .v.bad { color:#c0392b; }
.kpi .s { font-size:9.5px; color:#87949a; margin-top:2px; }

/* Recommendation panel */
.rec-box {
    border-radius:8px; padding:8px 9px; margin:0 0 7px 0;
    border-left:3px solid;
}
.rec-box.high { background:#fff2f1; border-color:#e5534b; color:#94352e; }
.rec-box.medium { background:#fff8e5; border-color:#e5ad27; color:#8b6411; }
.rec-box.low { background:#eef9f1; border-color:#46a36b; color:#2f7248; }
.rec-box .msg { font-size:10.5px; font-weight:750; line-height:1.3; }
.rec-box .act { font-size:9.5px; margin-top:3px; font-weight:500; line-height:1.3; }

/* Compact insight rows */
.insight-row {
    display:grid; grid-template-columns: 1fr auto;
    gap:8px; align-items:center;
    padding:6px 0; border-bottom:1px solid #eef2f3;
}
.insight-row:last-child { border-bottom:0; }
.insight-name { font-size:10.5px; color:#44545b; font-weight:650; }
.insight-value { font-size:10.5px; color:#1c2b31; font-weight:800; text-align:right; }
.pill {
    display:inline-block; padding:2px 6px; border-radius:20px;
    font-size:8.5px; font-weight:800; margin-left:5px;
}
.pill.red { background:#fee5e2; color:#b9382f; }
.pill.amber { background:#fff1c9; color:#8a6410; }
.pill.green { background:#e3f5e9; color:#2e7b4b; }
.section-label {
    font-size:9px; text-transform:uppercase; letter-spacing:.06em;
    font-weight:800; color:#94a0a5; margin:7px 0 4px;
}

/* Make Plotly cards compact */
.js-plotly-plot, .plot-container { border-radius:9px; }
"""
HOVER_CSS = """
section[data-testid="stSidebar"] {
    position:fixed !important; top:0; left:0; height:100vh !important;
    z-index:1000; transform:translateX(calc(-100% + 16px)) !important;
    transition:transform .22s ease, box-shadow .22s ease;
    border-right:3px solid #0b8f82 !important;
}
section[data-testid="stSidebar"]:hover {
    transform:translateX(0) !important;
    box-shadow:8px 0 28px rgba(22,40,48,.16);
}
section[data-testid="stSidebar"]::after {
    content:"›"; position:absolute; top:50%; right:2px;
    transform:translateY(-50%); color:#0b8f82; font-size:21px;
    font-weight:800; pointer-events:none;
}
section[data-testid="stSidebar"]:hover::after { display:none; }
[data-testid="stSidebarCollapseButton"] { display:none !important; }
.block-container { padding-left:2.55rem !important; }
"""
ACTIVE_CSS = (
    f".st-key-nav_{page} button {{ background:{active['bg']} !important; "
    f"color:{active['fg']} !important; font-weight:800 !important; }}"
)
st.markdown(f"<style>{BASE_CSS}{ACTIVE_CSS}{HOVER_CSS if autohide else ''}</style>", unsafe_allow_html=True)

# ---------------- LAYOUT HELPERS ----------------
_ids = itertools.count()


def card(title, sub=None):
    box = st.container(key=f"card_{next(_ids)}")
    with box:
        head = f'<div class="ct">{esc(title)}</div>'
        if sub:
            head += f'<div class="cs">{esc(sub)}</div>'
        st.markdown(head, unsafe_allow_html=True)
    return box


def html_block(s):
    st.markdown(s, unsafe_allow_html=True)


def kpi(col, label, value, bad=False, sub=None, color=None):
    top = f' style="border-top:4px solid {color}"' if color else ""
    s = f'<div class="s">{esc(sub)}</div>' if sub else ""
    col.markdown(
        f'<div class="kpi"{top}><div class="l">{esc(label)}</div>'
        f'<div class="v{" bad" if bad else ""}">{fmt(value)}</div>{s}</div>',
        unsafe_allow_html=True,
    )


def recs_card(recs, title="Recommendations"):
    with card(title, "Calculated from the current data"):
        if not recs:
            html_block(empty_note("Nothing to recommend yet: not enough data from the pipeline."))
            return
        out = ""
        for r in recs:
            act = f'<div class="act">→ {esc(r["action"])}</div>' if r.get("action") else ""
            out += f'<div class="rec-box {r["priority"]}"><div class="msg">{esc(r["message"])}</div>{act}</div>'
        html_block(out)


def trend_card(title, sub, labels, values, err, payload, color, key, unit_word):
    with card(title, sub):
        if values:
            show(volume_fig(labels, values, color, 280), key)
        else:
            html_block(empty_note(
                f"No {unit_word} trend data. Endpoint returned: {describe_payload(payload)}." + (f" Error: {err}" if err else "")))


# ---------------- HEADER + LOAD DATA ----------------
metrics = (data or {}).get("metrics", {}) or {}
hl, hr = st.columns([6.2, 1], vertical_alignment="center")
with hl:
    html_block(
        f'<div class="main-header"><h1>{esc(active["title"])}</h1>'
        f'<div class="meta"><b>Snapshot:</b> {esc(snapshot_pretty(data))} &nbsp;·&nbsp; '
        f'<b>Total feedback:</b> {fmt(metrics.get("total_complaints"))} &nbsp;·&nbsp; '
        f'<b>Active alerts:</b> {fmt(metrics.get("active_alerts"))}</div></div>'
    )
with hr:
    if st.button("⟳  Sync", key="sync_top", type="primary"):
        do_sync()

if data is None:
    with card("Pipeline unavailable"):
        html_block(empty_note(f"Could not load data from {API_BASE}. Start the API, then retry. Details: {data_err}"))
        if st.button("Retry", key="retry"):
            st.cache_data.clear()
            st.rerun()
    st.stop()

# ---------------- PAGE DATA ----------------
w_payload, w_err = fetch(TRENDS_W)
wl, wv = extract_series(w_payload, "week")
ps_rows = extract_product_symptoms(data)
MAIN_W, SIDE_W = 3.35, 1.0
total_all = num(metrics.get("total_complaints"))

def pct_of(n):
    return f"{n / total_all * 100:.1f}% of total" if total_all else None

def metric_strip():
    ana = num(metrics.get("analyzed_complaints"))
    k1, k2, k3, k4 = st.columns(4, gap="small")
    kpi(k1, "TOTAL FEEDBACK", metrics.get("total_complaints"), sub="all records received", color="#0b8f82")
    kpi(k2, "ANALYZED", ana, sub=f"{ana / total_all * 100:.0f}% of total" if total_all else None, color="#5b78d1")
    kpi(k3, "HIGH SEVERITY", metrics.get("high_severity"), bad=True,
        sub=pct_of(num(metrics.get("high_severity"))), color="#e5534b")
    kpi(k4, "NEGATIVE SENTIMENT", metrics.get("negative_sentiment"), bad=True,
        sub=pct_of(num(metrics.get("negative_sentiment"))), color="#e5534b")

def compact_rows(items, label_key="label", value_key="count", limit=5, percent=False):
    items = sorted(clean_list(items), key=lambda x: num(x.get(value_key)), reverse=True)[:limit]
    if not items:
        html_block(empty_note("No data available from the pipeline."))
        return
    html = ""
    total = sum(num(x.get(value_key)) for x in items) or 1
    for x in items:
        name = pretty(x.get(label_key, "Unknown"))
        val = num(x.get(value_key))
        extra = f'<span class="pill amber">{val/total*100:.0f}%</span>' if percent else ""
        html += f'<div class="insight-row"><div class="insight-name">{esc(name)}</div><div class="insight-value">{fmt(val)}{extra}</div></div>'
    html_block(html)

# ============================================================
# OVERVIEW
# ============================================================
if page == "Overview":
    metric_strip()
    main, side = st.columns([MAIN_W, SIDE_W], gap="medium")

    with main:
        with card("Feedback Volume", "Weekly feedback movement — spikes can point to a bad batch, release, or service issue."):
            if wv:
                show(volume_fig(wl, wv, TEAL, 245), "ov_volume")
            else:
                html_block(empty_note("No weekly trend data from the pipeline."))

        c1, c2 = st.columns([1.7, 1], gap="medium")
        with c1:
            if ps_rows:
                with card("Top Symptoms by Product", "See which symptoms are concentrated in which products."):
                    show(sym_by_product_fig(ps_rows, 315), "ov_sym_prod")
            else:
                with card("Top Symptoms", "Most frequently reported customer problems."):
                    compact_rows(data.get("symptoms"), limit=6, percent=True)

        with c2:
            with card("Customer Sentiment", "Current customer mood from analyzed feedback."):
                sent = clean_list(data.get("sentiment"))
                if sent:
                    vals = [num(s.get("count")) for s in sent]
                    tot = sum(vals) or 1
                    neg = sum(v for s, v in zip(sent, vals)
                              if str(s.get("label", "")).lower() == "negative")
                    cols = [SENTIMENT_COLORS.get(str(s.get("label", "")).lower(), SLATE) for s in sent]
                    show(donut_fig([pretty(s.get("label", "")) for s in sent],
                                   vals, cols, f"{neg / tot * 100:.0f}%", "negative", 290), "ov_sent")
                else:
                    html_block(empty_note("No sentiment data from the pipeline."))

    with side:
        recs_card(finish(recs_overview(data, wv)), "AI Recommendations")

# ============================================================
# ANALYSIS
# ============================================================
elif page == "Analysis":
    main, side = st.columns([MAIN_W, SIDE_W], gap="medium")

    with main:
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            sev = clean_list(data.get("severity"))
            with card("Severity", "Classification of feedback by urgency."):
                if sev:
                    vals = [num(s.get("count")) for s in sev]
                    urgent = sum(v for s, v in zip(sev, vals)
                                  if str(s.get("label", "")).lower() in ("critical", "high"))
                    cols = [SEVERITY_COLORS.get(str(s.get("label", "")).lower(), SLATE) for s in sev]
                    show(donut_fig([pretty(s.get("label", "")) for s in sev],
                                   vals, cols, fmt(urgent), "critical + high", 285), "an_sev")
                else:
                    html_block(empty_note("No severity data from the pipeline."))

        with c2:
            cats = sorted_by(data.get("categories"), "count")
            with card("Feedback Categories", "Main technical areas behind the feedback."):
                if cats:
                    vals = [num(c.get("count")) for c in cats]
                    tot = sum(vals) or 1
                    show(hbar_fig([pretty(c.get("label", "")) for c in cats],
                                  vals, [TEAL] + ["#7fd9d0"] * (len(vals)-1),
                                  max(285, 45 * len(vals) + 35),
                                  extra_text=[f"<b>{fmt(v)}</b> · {v/tot*100:.0f}%" for v in vals],
                                  r=105), "an_cat")
                else:
                    html_block(empty_note("No category data from the pipeline."))

        links = clean_list(data.get("symptom_failure_links"))
        preds = clean_list(data.get("predictions"))
        with card("Symptom → Most Likely Cause", "Evidence linking customer symptoms to technical failure causes."):
            if links:
                show(sankey_fig(links, preds, 360), "an_sankey")
                if preds:
                    with st.container():
                        html_block('<div class="section-label">Root-cause evidence</div>')
                        show(evidence_fig(preds[:6], 260), "an_evidence")
            else:
                html_block(empty_note("No symptom-to-cause links from the pipeline yet."))

    with side:
        recs_card(finish(recs_analysis(data)), "AI Recommendations")

# ============================================================
# PRODUCTS
# ============================================================
elif page == "Products":
    main, side = st.columns([MAIN_W, SIDE_W], gap="medium")
    with main:
        prods = sorted_by(data.get("products"), "complaints")
        with card("Complaints by Product", "Products generating the highest feedback volume."):
            if prods:
                vals = [num(p.get("complaints")) for p in prods]
                denom = total_all or sum(vals) or 1
                run, txt = 0, []
                for v in vals:
                    run += v
                    txt.append(f"<b>{fmt(v)}</b> · {run / denom * 100:.0f}% cumulative")
                cols = [INDIGO] * min(3, len(vals)) + ["#c7d2fe"] * max(0, len(vals) - 3)
                show(hbar_fig([str(p.get("product", "")) for p in prods], vals, cols,
                              48 * len(vals) + 40, extra_text=txt, r=150), "pr_bars")
            else:
                html_block(empty_note("No product data from the pipeline."))

        if ps_rows:
            with card("Product × Symptom Hot Spots", "Darker areas indicate more reported problems."):
                show(heatmap_fig(ps_rows, 345), "pr_heat")

    with side:
        recs_card(finish(recs_products(data, ps_rows)), "AI Recommendations")

# ============================================================
# ALERTS
# ============================================================
elif page == "Alerts":
    items = parse_alerts(data.get("alerts"))
    main, side = st.columns([MAIN_W, SIDE_W], gap="medium")

    with main:
        with card("Alerts — All Warnings This Snapshot", "Warnings are grouped by device, systemic pattern, and general safety signals."):
            if not items:
                html_block(empty_note("No active alerts in this snapshot."))
            else:
                for a in items:
                    kind = ALERT_KINDS.get(a["kind"], ALERT_KINDS["general"])
                    severity_class = "red" if a["safety"] else ("amber" if a["kind"] == "pattern" else "green")
                    magnitude = f'{fmt(a["mag"])} {a["unit"]}' if a["mag"] else "flagged"
                    html_block(
                        f'<div class="insight-row">'
                        f'<div><div class="insight-name">{esc(a["title"])} '
                        f'<span class="pill {severity_class}">{esc(kind["label"])}</span></div>'
                        f'<div style="font-size:9.5px;color:#7d8b91;margin-top:2px;">{esc(a["message"])}</div></div>'
                        f'<div class="insight-value">{magnitude}</div></div>'
                    )

        with card("Alert Volume by Source", "Compare the amount of feedback behind each alert."):
            if items:
                show(alerts_fig(items, max(250, 48 * len(items) + 70)), "al_bars")

    with side:
        recs_card(finish(recs_alerts(items)), "Recommended Actions")

# ============================================================
# TRENDS
# ============================================================
elif page == "Trends":
    m_payload, m_err = fetch(TRENDS_M)
    ml, mv = extract_series(m_payload, "month")
    main, side = st.columns([MAIN_W, SIDE_W], gap="medium")

    with main:
        trend_card("Weekly Volume", "Short-term movement — useful for catching sudden spikes early.",
                   wl, wv, w_err, w_payload, "#6d28d9", "tr_week", "weekly")
        trend_card("Monthly Volume", "Long-term movement — useful for spotting seasonality and planning capacity.",
                   ml, mv, m_err, m_payload, "#6d28d9", "tr_month", "monthly")

    with side:
        recs_card(finish(recs_trends(wl, wv, ml, mv)), "AI Recommendations")
