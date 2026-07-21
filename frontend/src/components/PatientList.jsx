import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function PatientList({ onOpen, selected, refreshKey }) {
  const [q, setQ] = useState("");
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(false);

  const search = (query) => {
    setLoading(true);
    api.searchPatients(query, 25)
      .then((r) => setPatients(r.patients))
      .catch(() => setPatients([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { search(q); /* eslint-disable-next-line */ }, [refreshKey]);

  const onSubmit = (e) => { e.preventDefault(); search(q); };

  return (
    <div className="card">
      <div className="hd">Patients</div>
      <div className="bd">
        <form onSubmit={onSubmit}>
          <input className="search-input" placeholder="Search (e.g. diabetes, heart disease)…"
                 value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
        {loading && <div className="loading" style={{ marginTop: 10 }}>Searching…</div>}
        <ul className="plist" style={{ marginTop: 10 }}>
          {patients.map((p) => (
            <li key={p.patientId} className={selected === p.patientId ? "active" : ""}
                onClick={() => onOpen(p.patientId)}>
              <div className="name">{p.name}</div>
              <div className="meta">{p.age != null ? `${p.age} yo` : ""} {p.gender || ""}</div>
              {p.activeConditions?.length > 0 && (
                <div className="chips">
                  {p.activeConditions.slice(0, 3).map((c, i) => <span key={i} className="chip">{c}</span>)}
                </div>
              )}
            </li>
          ))}
          {!loading && patients.length === 0 &&
            <li className="empty">No patients. Click “Load 10 patients”.</li>}
        </ul>
      </div>
    </div>
  );
}
