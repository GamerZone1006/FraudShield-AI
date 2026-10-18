import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip,
  XAxis, YAxis, BarChart, Bar
} from "recharts";
import "./App.css";

const API = "http://127.0.0.1:8000";
const TYPES = ["PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT", "CASH_IN"];
const money = (value) => new Intl.NumberFormat("en-IN", {
  style: "currency", currency: "INR", maximumFractionDigits: 0
}).format(Number(value || 0));
const percent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;

function StatCard({ label, value, hint, accent = "" }) {
  return <article className={`stat-card ${accent}`}>
    <p className="stat-label">{label}</p>
    <h3>{value}</h3>
    <p className="stat-hint">{hint}</p>
  </article>;
}

function RiskPill({ level }) {
  return <span className={`risk-pill ${(level || "low").toLowerCase()}`}>{level || "LOW"}</span>;
}

export default function App() {
  const [form, setForm] = useState({ step: 10, type: "TRANSFER", amount: "25000" });
  const [result, setResult] = useState(null);
  const [stats, setStats] = useState({});
  const [transactions, setTransactions] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [filter, setFilter] = useState("ALL");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [apiOnline, setApiOnline] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [statsRes, txRes, metricRes] = await Promise.all([
        fetch(`${API}/api/stats`),
        fetch(`${API}/api/transactions?limit=100`),
        fetch(`${API}/api/model-metrics`)
      ]);
      if (!statsRes.ok || !txRes.ok) throw new Error("Could not load dashboard data.");
      setStats(await statsRes.json());
      setTransactions(await txRes.json());
      setMetrics(metricRes.ok ? await metricRes.json() : null);
      setApiOnline(true);
      setError("");
    } catch {
      setApiOnline(false);
      setError("Cannot reach the backend. Start FastAPI at http://127.0.0.1:8000.");
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  async function submitTransaction(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch(`${API}/api/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          step: Number(form.step),
          type: form.type,
          amount: Number(form.amount)
        })
      });
      const payload = await response.json();
      if (!response.ok) {
        const detail = Array.isArray(payload.detail)
          ? payload.detail.map((item) => item.msg).join(", ")
          : payload.detail;
        throw new Error(detail || `Request failed (${response.status})`);
      }
      setResult(payload);
      await refresh();
    } catch (err) {
      setError(err.message || "Prediction failed. Check the backend.");
    } finally {
      setLoading(false);
    }
  }

  const filteredTransactions = useMemo(() => transactions.filter((tx) => (
    filter === "ALL" || tx.decision === filter
  )), [transactions, filter]);

  const chartData = useMemo(() => {
    const grouped = {};
    [...transactions].reverse().forEach((tx) => {
      const key = new Date(tx.created_at).toLocaleTimeString([], {
        hour: "2-digit", minute: "2-digit"
      });
      grouped[key] = (grouped[key] || 0) + Number(tx.amount || 0);
    });
    return Object.entries(grouped).map(([time, amount]) => ({
      time, amount: Math.round(amount)
    })).slice(-12);
  }, [transactions]);

  const typeData = useMemo(() => {
    const grouped = {};
    transactions.forEach((tx) => {
      grouped[tx.transaction_type] ||= { type: tx.transaction_type, flagged: 0, total: 0 };
      grouped[tx.transaction_type].total += 1;
      if (tx.decision === "REVIEW") grouped[tx.transaction_type].flagged += 1;
    });
    return Object.values(grouped);
  }, [transactions]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#">
          <span className="brand-mark">F</span>
          <span>FraudShield <b>AI</b><small>TRANSACTION INTELLIGENCE</small></span>
        </a>
        <div className="connection"><span className={apiOnline ? "dot online" : "dot"} />
          {apiOnline ? "API connected" : "API disconnected"}
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">FRAUD CONTROL WORKSPACE</p>
          <h1>Transaction risk <span>overview.</span></h1>
          <p className="hero-copy">Screen a transaction, inspect its estimated risk, and explore the recorded review activity.</p>
        </div>
        <div className="hero-chip"><span className="pulse" /> MODEL-ASSISTED SCREENING</div>
      </section>

      {error && <div className="alert" role="alert">{error}</div>}

      <section className="stats-grid">
        <StatCard label="TOTAL SCREENED" value={stats.total_transactions ?? "—"} hint="Recorded transaction checks" />
        <StatCard label="FLAGGED FOR REVIEW" value={stats.flagged_transactions ?? "—"} hint="Requires further assessment" accent="purple" />
        <StatCard label="APPROVED BY RULE" value={stats.approved_transactions ?? "—"} hint="Low-score recommendation" accent="green" />
        <StatCard label="FLAGGED AMOUNT" value={money(stats.flagged_amount)} hint="Value flagged, not confirmed loss" accent="amber" />
      </section>

      <div className="main-grid">
        <section className="panel simulator-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">LIVE SIMULATION</p><h2>Screen a transaction</h2></div>
            <span className="panel-icon">↗</span>
          </div>
          <p className="muted">Enter sample transaction details to request a model score.</p>
          <form className="transaction-form" onSubmit={submitTransaction}>
            <label>Transaction amount (₹)
              <input type="number" min="0.01" max="1000000000" step="0.01" required value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })} />
            </label>
            <div className="form-row">
              <label>Transaction type
                <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                  {TYPES.map((type) => <option key={type}>{type}</option>)}
                </select>
              </label>
              <label>Time step
                <input type="number" min="1" step="1" required value={form.step}
                  onChange={(e) => setForm({ ...form, step: e.target.value })} />
              </label>
            </div>
            <button className="primary-button" disabled={loading}>
              {loading ? <><span className="spinner" /> Screening...</> : "Run risk assessment →"}
            </button>
          </form>

          {result ? (
            <div className="result-card">
              <div className="result-top"><span className="eyebrow">SCREENING RESULT</span><RiskPill level={result.risk_level} /></div>
              <div className="score-line"><strong>{Number(result.fraud_probability_percent).toFixed(2)}%</strong><span>estimated fraud-class score</span></div>
              <div className="score-track"><span style={{ width: `${Math.min(100, Math.max(0, result.fraud_probability_percent))}%` }} /></div>
              <div className={`decision ${result.decision === "REVIEW" ? "review" : "approve"}`}>
                <span>{result.decision === "REVIEW" ? "!" : "✓"}</span>
                <div><b>{result.decision}</b><small>{result.decision === "REVIEW" ? "Manual review recommended" : "Low-risk recommendation"}</small></div>
              </div>
              <p className="result-note">Record #{result.id} · {new Date(result.created_at).toLocaleString()}</p>
            </div>
          ) : (
            <div className="empty-result"><div className="empty-symbol">⌁</div><b>Your result appears here</b><span>Submit a transaction to see its screening outcome.</span></div>
          )}
        </section>

        <section className="panel chart-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">RECENT ACTIVITY</p><h2>Transaction amount trend</h2></div>
            <span className="chart-tag">LATEST RECORDS</span>
          </div>
          {chartData.length ? <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs><linearGradient id="amountFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#5b8cff" stopOpacity={0.32} />
                  <stop offset="100%" stopColor="#5b8cff" stopOpacity={0.02} />
                </linearGradient></defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#202c40" vertical={false} />
                <XAxis dataKey="time" tick={{ fill: "#8794aa", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#8794aa", fontSize: 11 }} axisLine={false} tickLine={false}
                  tickFormatter={(value) => value >= 1000 ? `${Math.round(value / 1000)}k` : value} />
                <Tooltip contentStyle={{ background: "#111c2d", border: "1px solid #293951", borderRadius: 10 }}
                  formatter={(value) => [money(value), "Amount"]} />
                <Area type="monotone" dataKey="amount" stroke="#6c98ff" strokeWidth={2.5} fill="url(#amountFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div> : <div className="chart-empty">Screen transactions to build your activity chart.</div>}

          <div className="subchart-heading"><h3>Flagged by transaction type</h3><span>Recent records</span></div>
          {typeData.length ? <div className="bar-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={typeData} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#202c40" vertical={false} />
                <XAxis dataKey="type" tick={{ fill: "#8794aa", fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fill: "#8794aa", fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "#111c2d", border: "1px solid #293951", borderRadius: 10 }} />
                <Bar dataKey="flagged" name="Flagged for review" fill="#9b8cff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div> : <p className="muted">No transaction types to summarize yet.</p>}
        </section>
      </div>

      <section className="panel table-panel">
        <div className="panel-heading table-heading">
          <div><p className="eyebrow">AUDIT TRAIL</p><h2>Transaction history</h2></div>
          <div className="table-actions">
            <select aria-label="Filter transactions" value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="ALL">All decisions</option><option value="REVIEW">Review only</option><option value="APPROVE">Approve only</option>
            </select>
            <button className="secondary-button" onClick={refresh}>↻ Refresh</button>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr><th>RECORD</th><th>TYPE</th><th>AMOUNT</th><th>MODEL SCORE</th><th>RISK</th><th>DECISION</th><th>TIME</th></tr></thead>
            <tbody>
              {filteredTransactions.map((tx) => <tr key={tx.id}>
                <td className="record-id">#{tx.id}</td><td>{tx.transaction_type}</td><td>{money(tx.amount)}</td>
                <td><div className="table-score"><span>{percent(tx.fraud_probability)}</span><div><i style={{ width: `${Math.min(100, tx.fraud_probability * 100)}%` }} /></div></div></td>
                <td><RiskPill level={tx.risk_level} /></td>
                <td><span className={`decision-text ${tx.decision === "REVIEW" ? "review-text" : "approve-text"}`}>{tx.decision}</span></td>
                <td className="date-cell">{new Date(tx.created_at).toLocaleString()}</td>
              </tr>)}
              {!filteredTransactions.length && <tr><td colSpan="7" className="no-rows">No transactions found. Submit a transaction to begin.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <footer className="footer">
        <span>FraudShield AI <b>·</b> Transaction screening prototype</span>
        <span className="footer-note">Model scores are estimates; flagged amount is not confirmed loss.</span>
      </footer>
    </main>
  );
}
