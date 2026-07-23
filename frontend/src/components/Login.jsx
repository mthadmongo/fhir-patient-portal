import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Login({ onLogin }) {
  const [tenants, setTenants] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.tenants().then(setTenants).catch((e) => setError(e.message));
  }, []);

  const pick = async (id) => {
    try {
      localStorage.setItem("tenantId", id);
      const me = await api.login(id);
      onLogin(me);
    } catch (e) {
      localStorage.removeItem("tenantId");
      setError(e.message);
    }
  };

  return (
    <div className="login-wrap">
      <h1>FHIR Patient Portal</h1>
      <p className="sub">
        One platform, four products. Patient data is stored as FHIR in MongoDB Atlas and
        exposed through tenant-specific APIs. Choose a tenant to sign in.
      </p>
      {error && <p className="error">{error}</p>}
      <div className="tenant-grid">
        {tenants.map((t) => (
          <button key={t.id} className="tenant-card" style={{ "--tc": t.theme.primary }}
                  onClick={() => pick(t.id)}>
            <span className="badge">{t.type}</span>
            <h3>{t.name}</h3>
            <p>{t.tagline}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
