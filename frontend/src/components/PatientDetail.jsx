import { useEffect, useState } from "react";
import { api } from "../api.js";
import Specialized from "./Specialized.jsx";

function Tag({ value }) {
  if (!value) return null;
  return <span className={`tag ${String(value).toLowerCase()}`}>{value}</span>;
}

export default function PatientDetail({ me, patientId }) {
  const [p, setP] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setP(null); setError(null);
    api.getPatient(patientId).then(setP).catch((e) => setError(e.message));
  }, [patientId]);

  if (error) return <div className="card"><div className="bd error">{error}</div></div>;
  if (!p) return <div className="card"><div className="bd loading">Loading patient…</div></div>;

  const activeConds = (p.conditions || []).filter(
    (c) => c.clinicalStatus === "active" && c.category === "clinical");
  const activeMeds = (p.medications || []).filter((m) => m.status === "active");
  const labs = (p.observations || []).slice(0, 12);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="card">
        <div className="bd">
          <div className="pd-header">
            <h2>{p.name.full}</h2>
            <span className="sub">{p.age != null ? `${p.age} yo` : ""} {p.gender}
              {p.address?.city ? ` · ${p.address.city}, ${p.address.state}` : ""}
              {p.identifiers?.mrn ? ` · MRN ${p.identifiers.mrn}` : ""}</span>
          </div>
          <div className="summary">{p.summaryText}</div>
          <div className="section-grid">
            <div>
              <h4>Active Conditions</h4>
              <table className="data">
                <tbody>
                  {activeConds.slice(0, 10).map((c, i) => (
                    <tr key={i}><td>{c.display}</td><td style={{ textAlign: "right" }}>{c.onsetDate}</td></tr>
                  ))}
                  {activeConds.length === 0 && <tr><td className="empty">None</td></tr>}
                </tbody>
              </table>
            </div>
            <div>
              <h4>Active Medications</h4>
              <table className="data">
                <tbody>
                  {activeMeds.slice(0, 10).map((m, i) => (
                    <tr key={i}><td>{m.display}</td></tr>
                  ))}
                  {activeMeds.length === 0 && <tr><td className="empty">None</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
          <div style={{ marginTop: 14 }}>
            <h4>Recent Labs & Vitals</h4>
            <table className="data">
              <thead><tr><th>Test</th><th>Value</th><th>Date</th><th></th></tr></thead>
              <tbody>
                {labs.map((o, i) => (
                  <tr key={i}>
                    <td>{o.display}</td>
                    <td>{o.value} {o.unit}</td>
                    <td>{o.effectiveDate}</td>
                    <td><Tag value={o.interpretation} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <Specialized me={me} patientId={patientId} />
    </div>
  );
}
