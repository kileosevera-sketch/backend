"""
Post-Sales Feedback Dashboard — Cloud-Safe Version.
No pandas, no requests, no external DLLs. Mock data embedded in code.
Works even when Application Control Policy blocks native libraries.
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from random import Random

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Post-Sales Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# DARK THEME
# ============================================================
st.markdown("""
<style>
    header[data-testid="stHeader"] { display: none !important; }
    div[data-testid="stToolbar"] { display: none !important; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    div[data-testid="stDecoration"] { display: none !important; }

    .stApp { background-color: #0b1220; }
    .block-container { padding: 0.5rem 0.8rem 0.3rem 0.8rem; max-width: 100%; }
    div[data-testid="stVerticalBlock"] > div { gap: 0.3rem; }
    div[data-testid="column"] { padding: 0 4px; }

    .dash-header {
        background: linear-gradient(135deg, #0f766e 0%, #0d9488 100%);
        padding: 14px 22px; border-radius: 10px; color: white; margin-bottom: 6px;
    }
    .dash-header h1 { margin: 0; font-size: 20px; font-weight: 700; color: white; }
    .dash-header .meta { font-size: 14px; color: #ccfbf1; margin-top: 6px; }
    .dash-header .meta b { color: #fff; }
    .dash-header .up { color: #86efac; font-weight: 700; }
    .dash-header .down { color: #fca5a5; font-weight: 700; }
    .dash-header .flat { color: #cbd5e1; font-weight: 700; }

    .card {
        background: #111c2e; border: 1px solid #1e293b;
        border-radius: 10px; padding: 12px 14px; height: 100%;
    }
    .card-title { font-size: 15px; font-weight: 700; color: #5eead4; margin-bottom: 8px; }
    .card-sub { font-size: 12px; color: #94a3b8; margin-bottom: 8px; }

    .pipeline-step {
        display: inline-block; text-align: center;
        padding: 8px 10px; background: #0f2a2a;
        border: 1px solid #134e4a; border-radius: 6px;
        margin: 3px; min-width: 78px;
    }
    .pipeline-step .num { font-size: 10px; color: #5eead4; font-weight: 600; }
    .pipeline-step .val { font-size: 17px; font-weight: 700; color: #ccfbf1; }
    .pipeline-step .lbl { font-size: 10px; color: #94a3b8; }

    .alert-box {
        background: #2a1215; border-left: 3px solid #dc2626;
        padding: 8px 10px; border-radius: 6px; margin-bottom: 6px;
    }
    .alert-box.info { background: #142a3a; border-left-color: #3b82f6; }
    .alert-box .title { font-weight: 700; color: #fca5a5; font-size: 13px; }
    .alert-box.info .title { color: #93c5fd; }
    .alert-box .desc { color: #fecaca; font-size: 12px; margin-top: 3px; line-height: 1.4; }
    .alert-box.info .desc { color: #bfdbfe; }

    .evidence-box {
        background: #0f2a2a; border: 1px solid #134e4a;
        border-radius: 8px; padding: 12px 14px; height: 100%;
    }
    .evidence-box h4 { color: #5eead4; margin: 0 0 6px 0; font-size: 15px; }
    .evidence-box p { font-size: 13px; color: #cbd5e1; margin: 4px 0; line-height: 1.4; }
    .evidence-box .prob { color: #5eead4; font-weight: 700; }

    .chart-note { font-size: 11px; color: #64748b; font-style: italic; margin-top: 3px; }
    h3, h4, h5, p, span, label { color: #e2e8f0; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# MOCK DATA — no pandas, plain Python
# ============================================================
def generate_mock_data():
    rng = Random(42)
    today = datetime.utcnow()

    # Weekly trend — 12 weeks
    weeks = []
    for i in range(11, -1, -1):
        d = today - timedelta(weeks=i)
        weeks.append({
            "label": d.strftime("%d %b"),
            "count": rng.randint(280, 380),
        })

    symptoms = [
        ("Error code on display", 34),
        ("Not cooling", 31),
        ("Not heating", 31),
        ("Water leakage", 29),
        ("Vibration / shaking", 29),
        ("Strange smell from unit", 29),
        ("Slow cycle time", 26),
        ("Stopped working completely", 24),
    ]

    products = [
        ("Air Conditioner AC-1000", 78, 15),
        ("Refrigerator R-200", 65, 9),
        ("Washing Machine X200", 58, 11),
        ("Microwave M-50", 47, 10),
        ("Water Heater WH-30", 42, 10),
    ]

    sentiment = {"Positive": 92, "Neutral": 115, "Negative": 143}
    severity = {"Critical": 78, "High": 53, "Medium": 146, "Low": 26}

    symptom_cause = {
        "Error code on display": {"Software fault": 60, "Sensor malfunction": 40},
        "Not cooling": {"Compressor overheating": 65, "Refrigerant leak": 25, "Thermostat fault": 10},
        "Not heating": {"Compressor overheating": 55, "Thermostat fault": 30, "Sensor malfunction": 15},
        "Water leakage": {"Water pump failure": 75, "Seal/gasket failure": 25},
        "Vibration / shaking": {"Drum imbalance": 55, "Loose mounting": 30, "Motor bearing failure": 15},
        "Strange smell from unit": {"Electrical short circuit": 60, "Overheating component": 30, "Burnt wiring": 10},
        "Slow cycle time": {"Sensor malfunction": 50, "Software fault": 30, "Motor controller fault": 20},
        "Stopped working completely": {"Software fault": 45, "Electrical short circuit": 35, "Motor controller fault": 20},
    }

    predictions = [
        {"Component": "Compressor overheating", "Confidence": 66.7, "Cases": 16, "Evidence": "16 out of 24 historical cases with this symptom resulted in this cause."},
        {"Component": "Water pump failure", "Confidence": 63.6, "Cases": 14, "Evidence": "14 out of 22 historical cases with this symptom resulted in this cause."},
        {"Component": "Software fault", "Confidence": 50.0, "Cases": 18, "Evidence": "18 out of 36 historical cases with this symptom resulted in this cause."},
    ]

    alerts = [
        {"product": "Air Conditioner AC-1000", "type": "high_severity_cluster", "message": "15 high-severity complaints recorded for Air Conditioner AC-1000. Review urgently."},
        {"product": "Microwave M-50", "type": "high_severity_cluster", "message": "10 high-severity complaints recorded for Microwave M-50. Review urgently."},
        {"product": "Water Heater WH-30", "type": "high_severity_cluster", "message": "10 high-severity complaints recorded for Water Heater WH-30. Review urgently."},
        {"product": "", "type": "safety_symptom", "message": "12 complaints report dangerous symptoms (smell / smoke / sparks). Safety review recommended."},
    ]

    return {
        "snapshot": today.strftime("%d %B %Y, %H:%M"),
        "this_week": 350,
        "last_week": 308,
        "change": 42,
        "active_alerts": 6,
        "weeks": weeks,
        "symptoms": symptoms,
        "products": products,
        "sentiment": sentiment,
        "severity": severity,
        "symptom_cause": symptom_cause,
        "predictions": predictions,
        "alerts": alerts,
        "pipeline": {
            "source": 350,
            "ingest": 2450,
            "analyze": 2450,
            "predict": 10,
            "alert": 6,
        },
    }


data = generate_mock_data()


# ============================================================
# HEADER
# ============================================================
change = data["change"]
if change > 0:
    change_html = f'<span class="up">▲ {change} vs last week</span>'
elif change < 0:
    change_html = f'<span class="down">▼ {abs(change)} vs last week</span>'
else:
    change_html = '<span class="flat">↔ same as last week</span>'

st.markdown(f"""
<div class="dash-header">
    <h1>📊 Post-Sales Feedback — Weekly Report</h1>
    <div class="meta">
        <b>Snapshot:</b> {data['snapshot']} &nbsp;·&nbsp;
        <b>This week:</b> {data['this_week']:,} feedback &nbsp;·&nbsp;
        {change_html} &nbsp;·&nbsp;
        <b>Active alerts:</b> {data['active_alerts']}
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# HELPERS
# ============================================================
def card(title, subtitle=""):
    sub = f'<div class="card-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(f'<div class="card"><div class="card-title">{title}</div>{sub}', unsafe_allow_html=True)


def end_card(note=""):
    if note:
        st.markdown(f'<div class="chart-note">{note}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def dark(fig, height=220):
    fig.update_layout(
        height=height,
        margin=dict(l=4, r=4, t=4, b=4),
        paper_bgcolor="#111c2e",
        plot_bgcolor="#111c2e",
        font=dict(color="#e2e8f0", size=13),
        showlegend=False,
    )
    return fig


# ============================================================
# ROW 0 — WEEKLY TRENDS
# ============================================================
card("Weekly Feedback Trends", "Last 12 weeks — are things improving or getting worse?")
weeks = data["weeks"]
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=[w["label"] for w in weeks],
    y=[w["count"] for w in weeks],
    mode="lines+markers",
    line=dict(color="#14b8a6", width=3),
    marker=dict(size=10, color="#14b8a6"),
    fill="tozeroy",
    fillcolor="rgba(20, 184, 166, 0.15)",
    hovertemplate="<b>%{x}</b><br>%{y} feedback<extra></extra>",
))
fig.add_trace(go.Scatter(
    x=[weeks[-1]["label"]], y=[weeks[-1]["count"]],
    mode="markers",
    marker=dict(size=18, color="#f97316", line=dict(color="#fff", width=2)),
    showlegend=False,
    hovertemplate="<b>This week: %{y}</b><extra></extra>",
))
fig = dark(fig, 230)
fig.update_layout(
    xaxis=dict(showgrid=False, tickfont=dict(size=12)),
    yaxis=dict(showgrid=True, gridcolor="#1e293b", tickfont=dict(size=12)),
)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})
end_card("Orange dot = this week's snapshot.")


# ============================================================
# ROW 1 — SYMPTOMS · PRODUCTS · SENTIMENT
# ============================================================
r1c1, r1c2, r1c3 = st.columns([1.1, 1.1, 1])

with r1c1:
    card("Top Symptoms", "This week's most reported problems")
    sym_labels = [s[0] for s in data["symptoms"]]
    sym_counts = [s[1] for s in data["symptoms"]]
    fig = go.Figure(go.Bar(
        x=sym_counts[::-1], y=sym_labels[::-1], orientation="h",
        marker_color="#0d9488",
        text=sym_counts[::-1], textposition="outside",
        textfont=dict(color="#e2e8f0", size=13),
        hovertemplate="<b>%{y}</b><br>%{x} complaints<extra></extra>",
    ))
    fig = dark(fig, 230)
    fig.update_layout(
        xaxis=dict(showgrid=True, gridcolor="#1e293b", tickfont=dict(size=12)),
        yaxis=dict(showgrid=False, tickfont=dict(size=12)),
        margin=dict(l=4, r=36, t=4, b=4),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})
    end_card("Extracted from customer feedback text.")

with r1c2:
    card("Top Products", "Which devices get the most complaints")
    prod_labels = [p[0] for p in data["products"]]
    prod_counts = [p[1] for p in data["products"]]
    prod_high = [p[2] for p in data["products"]]
    fig = go.Figure(go.Bar(
        x=prod_counts[::-1], y=prod_labels[::-1], orientation="h",
        marker_color="#f59e0b",
        text=prod_counts[::-1], textposition="outside",
        textfont=dict(color="#e2e8f0", size=13),
        customdata=prod_high[::-1],
        hovertemplate="<b>%{y}</b><br>Total: %{x}<br>High-severity: %{customdata}<extra></extra>",
    ))
    fig = dark(fig, 230)
    fig.update_layout(
        xaxis=dict(showgrid=True, gridcolor="#1e293b", tickfont=dict(size=12)),
        yaxis=dict(showgrid=False, tickfont=dict(size=12)),
        margin=dict(l=4, r=36, t=4, b=4),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})
    end_card("Hover to see high-severity counts per product.")

with r1c3:
    card("Sentiment", "Customer tone this week")
    s = data["sentiment"]
    fig = go.Figure(go.Pie(
        labels=list(s.keys()), values=list(s.values()), hole=0.6,
        marker_colors=["#16a34a", "#94a3b8", "#dc2626"],
        textinfo="label+value",
        textfont=dict(size=13, color="white"),
        hovertemplate="<b>%{label}</b><br>%{value} feedback<extra></extra>",
    ))
    fig = dark(fig, 230)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})
    end_card("Positive / Neutral / Negative split.")


# ============================================================
# ROW 2 — SYMPTOM → CAUSE · ALERTS · SEVERITY
# ============================================================
r2c1, r2c2, r2c3 = st.columns([1.1, 1.1, 1])

with r2c1:
    card("Symptom → Predicted Cause", "What each symptom most likely means")
    sc = data["symptom_cause"]
    syms = list(sc.keys())[::-1]
    all_causes = sorted({c for v in sc.values() for c in v})
    palette = ["#0d9488", "#f97316", "#3b82f6", "#a855f7", "#ef4444", "#eab308"]

    fig = go.Figure()
    for i, cause in enumerate(all_causes):
        fig.add_trace(go.Bar(
            name=cause,
            y=syms,
            x=[sc[s].get(cause, 0) for s in syms],
            orientation="h",
            marker_color=palette[i % len(palette)],
            hovertemplate="<b>%{y}</b><br>" + cause + ": %{x} cases<extra></extra>",
        ))
    fig.update_layout(
        barmode="stack",
        height=230,
        margin=dict(l=4, r=4, t=4, b=4),
        paper_bgcolor="#111c2e",
        plot_bgcolor="#111c2e",
        font=dict(color="#e2e8f0", size=12),
        xaxis=dict(showgrid=True, gridcolor="#1e293b", tickfont=dict(size=11)),
        yaxis=dict(showgrid=False, tickfont=dict(size=11)),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font=dict(size=10, color="#cbd5e1"),
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})
    end_card("Longer segments = more historical support for that cause.")

with r2c2:
    card("Early Warnings", "Anomalies flagged this snapshot")
    for a in data["alerts"][:4]:
        product = a.get("product", "")
        if not product:
            st.markdown(f"""
            <div class="alert-box info">
                <div class="title">🌐 General — {a['type']}</div>
                <div class="desc">{a['message']}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="alert-box">
                <div class="title">🚨 {product}</div>
                <div class="desc">{a['message']}</div>
            </div>
            """, unsafe_allow_html=True)
    end_card("Red = device-specific · Blue = system-wide.")

with r2c3:
    card("Severity", "How urgent this week's feedback is")
    sev = data["severity"]
    color_map = {"Critical": "#dc2626", "High": "#f97316", "Medium": "#eab308", "Low": "#16a34a"}
    labels = list(sev.keys())
    values = list(sev.values())
    colors = [color_map[l] for l in labels]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.6,
        marker_colors=colors,
        textinfo="label+value",
        textfont=dict(size=13, color="white"),
        hovertemplate="<b>%{label}</b><br>%{value} complaints<extra></extra>",
    ))
    fig = dark(fig, 230)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})
    end_card("Red = critical · Yellow = medium · Green = low.")


# ============================================================
# ROW 3 — PIPELINE
# ============================================================
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
card("AI / NLP Pipeline", "Weekly sync — new records this week vs totals")
p = data["pipeline"]
st.markdown(f"""
<div style="text-align:center; margin-top:6px;">
    <div class="pipeline-step"><div class="num">① SOURCE</div><div class="val">{p['source']}</div><div class="lbl">new this week</div></div>
    <div class="pipeline-step"><div class="num">② INGEST</div><div class="val">{p['ingest']:,}</div><div class="lbl">total in DB</div></div>
    <div class="pipeline-step"><div class="num">③ ANALYZE</div><div class="val">{p['analyze']:,}</div><div class="lbl">insights</div></div>
    <div class="pipeline-step"><div class="num">④ PREDICT</div><div class="val">{p['predict']}</div><div class="lbl">causes</div></div>
    <div class="pipeline-step"><div class="num">⑤ ALERT</div><div class="val">{p['alert']}</div><div class="lbl">active</div></div>
</div>
""", unsafe_allow_html=True)
end_card("Each sync adds a week of records and refreshes every stage.")


# ============================================================
# ROW 4 — ROOT CAUSE EVIDENCE
# ============================================================
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
card("Root Cause Evidence", "Why the AI reached each prediction")
ev_cols = st.columns(3)
for i, p in enumerate(data["predictions"]):
    with ev_cols[i]:
        st.markdown(f"""
        <div class="evidence-box">
            <h4>{p['Component']}</h4>
            <p><span class="prob">Confidence: {p['Confidence']}%</span> · {p['Cases']} historical cases</p>
            <p>{p['Evidence']}</p>
        </div>
        """, unsafe_allow_html=True)
end_card("Each prediction shows its evidence so engineers can verify.")


# ============================================================
# FOOTER
# ============================================================
st.markdown(
    f"<div style='text-align:center;color:#64748b;font-size:11px;margin-top:6px;'>"
    f"Snapshot: {data['snapshot']} · Weekly cadence · "
    f"All insights generated by the AI/NLP pipeline above."
    f"</div>",
    unsafe_allow_html=True,
)