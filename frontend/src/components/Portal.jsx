import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import PatientList from "./PatientList.jsx";
import PatientDetail from "./PatientDetail.jsx";
import Chat from "./Chat.jsx";

export default function Portal({ me, onLogout }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [tab, setTab] = useState("chat");
  const [refreshKey, setRefreshKey] = useState(0);

  const refreshStatus = useCallback(() => {
    api.ingestStatus().then(setStatus).catch(() => {});
  }, []);

  useEffect(() => { refreshStatus(); }, [refreshStatus]);

  const loadBatch = async () => {
    setLoading(true);
    try {
      await api.loadBatch(10);
      // ASP (or app-side) denormalizes; ensure embeddings exist, then refresh.
      await api.embedPending().catch(() => {});
      refreshStatus();
      setRefreshKey((k) => k + 1);
    } finally {
      setLoading(false);
    }
  };

  const openPatient = (id) => { setSelected(id); setTab("patient"); };

  return (
    <div>
      <div className="topbar">
        <div className="brand"><span className="dot" />{me.name}</div>
        <span className="type-badge">{me.type}</span>
        <div className="spacer" />
        {status && (
          <>
            <span className="pill">Raw <b>{status.fhirRawCount}</b></span>
            <span className="pill">Patients <b>{status.patientsCount}</b></span>
            <span className="pill">Embedded <b>{status.embeddedCount}</b></span>
          </>
        )}
        <button className="btn" onClick={loadBatch} disabled={loading}>
          {loading ? "Loading…" : "Load 10 patients"}
        </button>
        <button className="btn ghost small" onClick={onLogout}>Switch tenant</button>
      </div>

      <div className="layout">
        <PatientList me={me} onOpen={openPatient} selected={selected} refreshKey={refreshKey} />
        <div>
          <div className="tabs">
            <button className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}>AI Chat</button>
            <button className={tab === "patient" ? "active" : ""} onClick={() => setTab("patient")}
                    disabled={!selected}>Patient</button>
          </div>
          {tab === "chat" && <Chat me={me} onOpenPatient={openPatient} />}
          {tab === "patient" && (selected
            ? <PatientDetail me={me} patientId={selected} />
            : <div className="card"><div className="bd empty">Select a patient from the list.</div></div>)}
        </div>
      </div>
    </div>
  );
}
