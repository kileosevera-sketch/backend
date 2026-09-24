import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api";
import "./styles.css";

const navigation = [
  ["home", "Home", "⌂"],
  ["load", "Load & Analyze Data", "↻"],
  ["symptoms", "Symptoms & Problems", "⌁"],
  ["sentiment", "Sentiment & Severity", "◒"],
  ["risk", "Risk Analysis", "△"],
  ["evidence", "Evidence", "▤"],
  ["decision", "Decision Support", "◆"],
];

const number = (value) => new Intl.NumberFormat().format(Number(value || 0));
const title = (value) => String(value || "Unknown").replaceAll("_", " ");

function App() {
  const [step, setStep] = useState("home");
  const [data, setData] = useState(null);
  const [trends, setTrends] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");

  const loadData = async () => {
    setLoading(true);
    setError("");
    try {
      const [overview, weekly, monthly, recs] = await Promise.all([
        api.overview(),
        api.weeklyTrend(),
        api.monthlyTrend(),
        api.recommendations(),
      ]);
      setData(overview);
      setTrends({ weekly, monthly });
      setRecommendations(Array.isArray(recs) ? recs : recs.recommendations || []);
    } catch (requestError) {
      setError(requestError.message || "Unable to connect to backend");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const sync = async () => {
    setSyncing(true);
    setError("");
    try {
      await api.sync();
      await loadData();
    } catch (requestError) {
      setError(requestError.message || "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">✦</span><div><strong>POST-SALES</strong><small>AI INTELLIGENCE</small></div></div>
        <div className="side-label">WORKSPACE</div>
        <nav>{navigation.map(([id, label, icon]) => <button key={id} className={step === id ? "nav-item active" : "nav-item"} onClick={() => setStep(id)}><span>{icon}</span>{label}</button>)}</nav>
        <div className="sidebar-footer"><span className="status-dot" /> Backend data connected</div>
      </aside>
      <main className="content">
        <header className="topbar"><div><p className="eyebrow">CUSTOMER SIGNALS / OPERATIONS</p><h1>{navigation.find(([id]) => id === step)?.[1]}</h1></div><button className="sync-button" onClick={sync} disabled={syncing}>{syncing ? "Syncing..." : "↻ Sync latest data"}</button></header>
        {error && <div className="error-banner"><strong>Backend unavailable.</strong> {error}<button onClick={loadData}>Retry</button></div>}
        {loading ? <Loading /> : data ? <Page step={step} data={data} trends={trends} recommendations={recommendations} onLoad={() => setStep("load")} /> : <Empty message="No data available." />}
      </main>
    </div>
  );
}

function Loading() { return <div className="loading"><div className="loader" /><p>Loading live feedback intelligence...</p></div>; }
function Empty({ message }) { return <div className="empty-state"><h2>{message}</h2><p>Run the backend and refresh to view PostgreSQL and AI results.</p></div>; }

function Page({ step, data, trends, recommendations, onLoad }) {
  if (step === "home") return <Home data={data} onLoad={onLoad} />;
  if (step === "load") return <Load data={data} />;
  if (step === "symptoms") return <Symptoms data={data} />;
  if (step === "sentiment") return <Sentiment data={data} />;
  if (step === "risk") return <Risk data={data} />;
  if (step === "evidence") return <Evidence data={data} />;
  return <Decision recommendations={recommendations} />;
}

function Home({ data, onLoad }) {
  const metrics = data.metrics || {};
  return <><section className="hero"><div><p className="eyebrow">WELCOME TO POST-SALES AI</p><h2>Turn customer feedback into better decisions.</h2><p>Monitor feedback, surface emerging issues, predict failure patterns, and give every team a clearer next action.</p><button className="primary" onClick={onLoad}>Explore live data <span>→</span></button></div><div className="hero-art"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="hero-number">{number(metrics.total_complaints)}<small>total complaints</small></div></div></section><section className="metric-grid"><Metric label="Analyzed complaints" value={metrics.analyzed_complaints} /><Metric label="High severity" value={metrics.high_severity} tone="red" /><Metric label="Negative sentiment" value={metrics.negative_sentiment} tone="amber" /><Metric label="Active alerts" value={metrics.active_alerts} tone="blue" /></section><section className="section-heading"><div><p className="eyebrow">LIVE SNAPSHOT</p><h2>What you can do here</h2></div></section><div className="feature-grid"><Feature icon="⌁" title="Symptoms & problems" text="See the issues customers describe most often." /><Feature icon="◒" title="Sentiment & severity" text="Understand emotional tone and urgency in the dataset." /><Feature icon="△" title="Risk analysis" text="Review predicted causes and active early warnings." /><Feature icon="◆" title="Decision support" text="Turn the latest evidence into focused actions." /></div></>;
}

function Load({ data }) { return <><SectionIntro eyebrow="DATA PIPELINE" heading="Load & Analyze Data" text="This view is backed by the current PostgreSQL snapshot and the analysis pipeline." /><div className="metric-grid"><Metric label="This week" value={data.metrics.this_week_complaints} /><Metric label="Last week" value={data.metrics.last_week_complaints} /><Metric label="Analyzed" value={data.metrics.analyzed_complaints} /><Metric label="Total records" value={data.metrics.total_complaints} /></div><Table title="Recent pipeline runs" rows={data.pipeline_runs} columns={["source_type", "records_processed", "status", "last_synced_at"]} /></>; }
function Symptoms({ data }) { return <><SectionIntro eyebrow="PATTERN DETECTION" heading="Symptoms & Problems" text="The most common symptoms extracted from complaint insights, with the strongest observed failure links." /><div className="two-col"><BarList title="Top symptoms" rows={data.symptoms} labelKey="label" valueKey="count" /><Table title="Symptom to failure evidence" rows={data.symptom_failure_links} columns={["symptom", "failure", "links"]} /></div></>; }
function Sentiment({ data }) { return <><SectionIntro eyebrow="CLASSIFICATION" heading="Sentiment & Severity" text="A live view of how the AI pipeline classifies customer feedback." /><div className="two-col"><BarList title="Sentiment" rows={data.sentiment} labelKey="label" valueKey="count" /><BarList title="Severity" rows={data.severity} labelKey="label" valueKey="count" /></div><BarList title="Categories" rows={data.categories} labelKey="label" valueKey="count" /></>; }
function Risk({ data }) { return <><SectionIntro eyebrow="EARLY WARNING" heading="Risk Analysis" text="Predicted failure causes and unresolved alerts from the backend." /><div className="two-col"><Table title="Failure predictions" rows={data.predictions} columns={["cause", "probability", "predictions"]} /><Table title="Active alerts" rows={data.alerts} columns={["type", "severity", "product", "message"]} /></div></>; }
function Evidence({ data }) { return <><SectionIntro eyebrow="TRACEABLE SIGNALS" heading="Evidence" text="Inspect the products and source channels behind the complaint volume." /><div className="two-col"><BarList title="Complaints by product" rows={data.products} labelKey="product" valueKey="complaints" /><BarList title="Channels" rows={data.channels} labelKey="channel" valueKey="complaints" /></div></>; }
function Decision({ recommendations }) { return <><SectionIntro eyebrow="NEXT ACTIONS" heading="Decision Support" text="Recommendations generated from the current feedback, trend, alert, and prediction signals." /><div className="recommendations">{recommendations.length ? recommendations.map((item, index) => <article className="recommendation" key={`${item.title || item.message || "rec"}-${index}`}><span className={`rec-badge ${item.priority || item.tier || "medium"}`}>{title(item.priority || item.tier || "focus")}</span><h3>{item.title || item.message || item.recommendation || "Recommendation"}</h3><p>{item.action || item.description || item.detail || "Review the linked evidence in the dashboard."}</p></article>) : <Empty message="No recommendations available." />}</div></>; }

function SectionIntro({ eyebrow, heading, text }) { return <div className="section-intro"><p className="eyebrow">{eyebrow}</p><h2>{heading}</h2><p>{text}</p></div>; }
function Metric({ label, value, tone = "teal" }) { return <div className={`metric ${tone}`}><span>{label}</span><strong>{number(value)}</strong></div>; }
function Feature({ icon, title: featureTitle, text }) { return <article className="feature"><span className="feature-icon">{icon}</span><h3>{featureTitle}</h3><p>{text}</p></article>; }
function BarList({ title: listTitle, rows, labelKey, valueKey }) { const items = Array.isArray(rows) ? rows : []; const max = Math.max(...items.map((row) => Number(row[valueKey] || 0)), 1); return <section className="panel"><div className="panel-heading"><h3>{listTitle}</h3><span>{items.length} groups</span></div>{items.length ? items.map((row, index) => <div className="bar-row" key={`${row[labelKey]}-${index}`}><div><span>{title(row[labelKey])}</span><strong>{number(row[valueKey])}</strong></div><div className="bar-track"><i style={{ width: `${Math.max((Number(row[valueKey] || 0) / max) * 100, 3)}%` }} /></div></div>) : <p className="muted">No data available.</p>}</section>; }
function Table({ title: tableTitle, rows, columns }) { const items = Array.isArray(rows) ? rows : []; return <section className="panel table-panel"><div className="panel-heading"><h3>{tableTitle}</h3><span>{items.length} records</span></div>{items.length ? <div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column}>{title(column)}</th>)}</tr></thead><tbody>{items.map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{typeof row[column] === "object" ? JSON.stringify(row[column]) : String(row[column] ?? "—")}</td>)}</tr>)}</tbody></table></div> : <p className="muted">No data available.</p>}</section>; }

createRoot(document.getElementById("root")).render(<App />);