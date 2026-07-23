import { useRef, useState } from "react";
import { api } from "../api.js";

const SUGGESTIONS = [
  "Which patients have diabetes with poor glucose control?",
  "Who is on statins for heart disease?",
  "List patients with hypertension.",
  "Which patients have abnormal cholesterol?",
];

export default function Chat({ me, onOpenPatient }) {
  const [messages, setMessages] = useState([
    { role: "bot", text: `Hi! I'm the ${me.name} assistant. Ask me about the loaded patients.` },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  const send = async (text) => {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setBusy(true);
    try {
      const r = await api.chat(q);
      setMessages((m) => [...m, { role: "bot", text: r.answer, cites: r.citations }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "bot", text: `Error: ${e.message}` }]);
    } finally {
      setBusy(false);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  };

  return (
    <div className="card chat">
      <div className="msgs">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.text}
            {m.cites?.length > 0 && (
              <div className="cites">
                {m.cites.map((c) => (
                  <span key={c.patientId} className="cite" onClick={() => onOpenPatient(c.patientId)}>
                    {c.name}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="msg bot">Thinking…</div>}
        <div ref={endRef} />
      </div>
      <div className="suggestions">
        {SUGGESTIONS.map((s) => <button key={s} onClick={() => send(s)}>{s}</button>)}
      </div>
      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input placeholder="Ask about patients…" value={input}
               onChange={(e) => setInput(e.target.value)} />
        <button className="btn" type="submit" disabled={busy}>Send</button>
      </form>
    </div>
  );
}
