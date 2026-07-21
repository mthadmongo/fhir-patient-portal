import { useEffect, useState } from "react";
import { api } from "./api.js";
import Login from "./components/Login.jsx";
import Portal from "./components/Portal.jsx";

function applyTheme(theme) {
  if (!theme) return;
  document.documentElement.style.setProperty("--tenant", theme.primary);
  document.documentElement.style.setProperty("--tenant-accent", theme.accent || theme.primary);
}

export default function App() {
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const id = localStorage.getItem("tenantId");
    if (!id) return setLoading(false);
    api.me().then((m) => { setMe(m); applyTheme(m.theme); })
      .catch(() => localStorage.removeItem("tenantId"))
      .finally(() => setLoading(false));
  }, []);

  const onLogin = (m) => { setMe(m); applyTheme(m.theme); };
  const onLogout = () => { localStorage.removeItem("tenantId"); setMe(null); };

  if (loading) return null;
  if (!me) return <Login onLogin={onLogin} />;
  return <Portal me={me} onLogout={onLogout} />;
}
