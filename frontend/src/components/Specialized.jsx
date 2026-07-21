import { useState } from "react";
import { api } from "../api.js";

const LOINCS = [
  ["4548-4", "Hemoglobin A1c"], ["2339-0", "Glucose"], ["8480-6", "Systolic BP"],
  ["2093-3", "Total cholesterol"], ["38483-4", "Creatinine"], ["39156-5", "BMI"],
];

function Tag({ value }) {
  if (!value) return null;
  return <span className={`tag ${String(value).toLowerCase()}`}>{value}</span>;
}

function Empty({ children }) { return <div className="empty">{children}</div>; }

function renderResult(featureId, data) {
  if (!data) return null;
  switch (featureId) {
    case "refill-insights":
      return data.refills.length === 0 ? <Empty>No active medications.</Empty> : (
        <table className="data"><thead><tr><th>Medication</th><th>Next refill</th><th>Refills left</th><th></th></tr></thead>
          <tbody>{data.refills.map((r, i) => (
            <tr key={i}><td>{r.medication}</td><td>{r.nextRefillDue || "—"}</td>
              <td>{r.refillsRemaining}</td><td><Tag value={r.status} /></td></tr>))}
          </tbody></table>);
    case "immunization-eligibility":
      return data.recommended.length === 0 ? <Empty>Up to date.</Empty> : (
        <table className="data"><tbody>{data.recommended.map((r, i) => (
          <tr key={i}><td>{r.vaccine}</td><td className="empty">{r.reason}</td></tr>))}</tbody></table>);
    case "drug-interactions":
      return data.interactions.length === 0 ? <Empty>No interactions detected.</Empty> : (
        data.interactions.map((it, i) => (
          <div key={i} style={{ marginBottom: 8 }}>
            <div><b>{it.drugA}</b> + <b>{it.drugB}</b> <Tag value={it.severity} /></div>
            <div className="empty">{it.note}</div>
          </div>)));
    case "medication-adherence":
      return (<div>
        <div className="kv"><span className="k">Adherence score</span>
          <span><b>{data.adherenceScore ?? "—"}</b></span></div>
        <div style={{ marginTop: 6 }}>MedSync candidates: {data.medSyncCandidates.join(", ") || "—"}</div>
        {data.gaps.length > 0 && <div style={{ marginTop: 6 }}>Gaps: {data.gaps.map((g) =>
          `${g.medication} (${g.daysLate}d late)`).join(", ")}</div>}
      </div>);
    case "clinic-visits":
      return data.visits.length === 0 ? <Empty>No outpatient visits.</Empty> : (
        <table className="data"><thead><tr><th>Type</th><th>Date</th><th>Provider</th></tr></thead>
          <tbody>{data.visits.map((v, i) => (
            <tr key={i}><td>{v.type}</td><td>{v.start}</td><td>{v.provider}</td></tr>))}</tbody></table>);
    case "care-gaps":
      return data.careGaps.length === 0 ? <Empty>No care gaps evaluated.</Empty> : (
        <table className="data"><tbody>{data.careGaps.map((g, i) => (
          <tr key={i}><td>{g.measure}</td><td><Tag value={g.status} /></td>
            <td className="empty">{g.detail}</td></tr>))}</tbody></table>);
    case "risk-stratification":
      return (<div>
        <div className="kv"><span className="k">Risk score</span>
          <span><b>{data.riskScore}</b> <Tag value={data.riskTier} /></span></div>
        <div style={{ marginTop: 6 }} className="empty">
          {data.contributors.map((c) => `${c.factor} (+${c.weight})`).join(", ") || "No major factors."}</div>
      </div>);
    case "coverage-check":
      return (<div className="kv">
        <span className="k">Drug</span><span>{data.drug}</span>
        <span className="k">Tier</span><span>{data.tier}</span>
        <span className="k">Prior auth</span><span>{data.priorAuth ? "Required" : "Not required"}</span>
        <span className="k">Copay</span><span>{data.copay}</span>
      </div>);
    case "lab-trends":
      return data.count === 0 ? <Empty>No results for this lab.</Empty> : (<div>
        <div className="kv"><span className="k">{data.label}</span>
          <span>{data.count} results · trend <b>{data.trend}</b></span></div>
        <table className="data" style={{ marginTop: 8 }}><thead><tr><th>Date</th><th>Value</th><th></th></tr></thead>
          <tbody>{data.series.slice(-8).map((s, i) => (
            <tr key={i}><td>{s.date}</td><td>{s.value} {s.unit}</td><td><Tag value={s.flag} /></td></tr>))}
          </tbody></table></div>);
    case "abnormal-flags":
      return data.abnormal.length === 0 ? <Empty>No abnormal results.</Empty> : (
        <table className="data"><tbody>{data.abnormal.map((a, i) => (
          <tr key={i}><td>{a.display}</td><td>{a.value} {a.unit}</td>
            <td><Tag value={a.flag} /></td><td>{a.date}</td></tr>))}</tbody></table>);
    case "test-recommendations":
      return (<table className="data"><tbody>{data.recommendations.map((r, i) => (
        <tr key={i}><td>{r.test}</td><td className="empty">{r.reason}</td></tr>))}</tbody></table>);
    default:
      return <pre style={{ fontSize: 12, overflow: "auto" }}>{JSON.stringify(data, null, 2)}</pre>;
  }
}

function FeatureCard({ feature, patientId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [drug, setDrug] = useState("Ozempic");
  const [loinc, setLoinc] = useState("4548-4");

  const run = async () => {
    setBusy(true); setError(null);
    try {
      let query = null;
      if (feature.id === "coverage-check") query = `drug=${encodeURIComponent(drug)}`;
      if (feature.id === "lab-trends") query = `loinc=${loinc}`;
      setData(await api.callFeature(feature.path, patientId, query));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card feature-card">
      <div className="hd">{feature.label}
        <button className="btn small" onClick={run} disabled={busy}>{busy ? "…" : "Run"}</button>
      </div>
      <div className="bd">
        <div className="feature-desc">{feature.desc}</div>
        {feature.id === "coverage-check" && (
          <input className="search-input" style={{ marginBottom: 10 }} value={drug}
                 onChange={(e) => setDrug(e.target.value)} placeholder="Drug name" />
        )}
        {feature.id === "lab-trends" && (
          <select className="search-input" style={{ marginBottom: 10 }} value={loinc}
                  onChange={(e) => setLoinc(e.target.value)}>
            {LOINCS.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          </select>
        )}
        {error && <div className="error">{error}</div>}
        {data ? renderResult(feature.id, data) : !error && <div className="empty">Click Run.</div>}
      </div>
    </div>
  );
}

export default function Specialized({ me, patientId }) {
  return (
    <div>
      <h3 style={{ margin: "4px 2px 10px" }}>{me.name} tools</h3>
      <div className="spec-grid">
        {me.specialized.map((f) => (
          <FeatureCard key={f.id} feature={f} patientId={patientId} />
        ))}
      </div>
    </div>
  );
}
