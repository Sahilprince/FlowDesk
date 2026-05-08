import { useState, useEffect, useRef } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8080";

// ── VOICE HOOK ───────────────────────────────────────────────────────────────
function useVoice(onTranscript) {
  const recRef = useRef(null);
  const [listening, setListening] = useState(false);

  const start = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return alert("Speech API not supported");
    recRef.current = new SR();
    recRef.current.continuous = false;
    recRef.current.interimResults = false;
    recRef.current.onresult = (e) => onTranscript(e.results[0][0].transcript);
    recRef.current.onend = () => setListening(false);
    recRef.current.start();
    setListening(true);
  };

  const stop = () => { recRef.current?.stop(); setListening(false); };
  return { listening, start, stop };
}

function speak(text) {
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 1.1;
  window.speechSynthesis.speak(u);
}

// ── COMPONENTS ───────────────────────────────────────────────────────────────

function ApprovalCard({ item, onAction }) {
  return (
    <div style={styles.card}>
      <div style={styles.cardBadge}>⏳ Pending Approval</div>
      <p style={styles.cardText}>{item.payload?.raw || JSON.stringify(item.payload)}</p>
      <div style={styles.cardActions}>
        <button style={styles.btnApprove} onClick={() => onAction(item.id, "approve")}>✓ Approve</button>
        <button style={styles.btnReject} onClick={() => onAction(item.id, "reject")}>✗ Reject</button>
      </div>
    </div>
  );
}

function WorkflowChip({ wf, onDelete }) {
  return (
    <div style={styles.chip}>
      <span>⚡ {wf.name || wf.id}</span>
      <button style={styles.chipDel} onClick={() => onDelete(wf.id)}>×</button>
    </div>
  );
}

// ── MAIN APP ─────────────────────────────────────────────────────────────────

export default function FlowDesk() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "FlowDesk routes requests into read-only checks, one-time actions, or reusable workflows. Write actions are staged for approval; read-only actions run directly.",
    }
  ]);
  const [approvals, setApprovals] = useState([]);
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  const { listening, start, stop } = useVoice((transcript) => {
    setInput(transcript);
    handleSend(transcript);
  });

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const handleSend = async (text) => {
    const msg = text || input;
    if (!msg.trim()) return;
    setInput("");
    setMessages(m => [...m, { role: "user", text: msg }]);
    setLoading(true);

    try {
      const res = await fetch(`${API}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: msg }),
      });
      const data = await res.json();
      const reply = data.summary || "Done!";
      setMessages(m => [...m, { role: "assistant", text: reply }]);
      setApprovals(data.pending_approvals || []);
      setWorkflows(data.workflows || []);
      speak(reply.slice(0, 200));
    } catch {
      setMessages(m => [...m, { role: "assistant", text: "Backend offline. Start the FastAPI server on port 8080." }]);
    }
    setLoading(false);
  };

  const handleApproval = async (id, action) => {
    await fetch(`${API}/approvals/${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    setApprovals(a => a.filter(x => x.id !== id));
    speak(action === "approve" ? "Done, executed!" : "Okay, cancelled.");
  };

  const handleDeleteWorkflow = async (id) => {
    await fetch(`${API}/workflows/${id}`, { method: "DELETE" });
    setWorkflows(w => w.filter(x => x.id !== id));
  };

  return (
    <div style={styles.root}>
      {/* SIDEBAR */}
      <aside style={styles.sidebar}>
        <div style={styles.logo}>⚡ FlowDesk</div>

        <section style={styles.section}>
          <div style={styles.sectionTitle}>PENDING APPROVALS</div>
          {approvals.length === 0
            ? <p style={styles.empty}>All clear</p>
            : approvals.map(a => <ApprovalCard key={a.id} item={a} onAction={handleApproval} />)
          }
        </section>

        <section style={styles.section}>
          <div style={styles.sectionTitle}>SAVED WORKFLOWS</div>
          {workflows.length === 0
            ? <p style={styles.empty}>No workflows yet</p>
            : workflows.map(w => <WorkflowChip key={w.id} wf={w} onDelete={handleDeleteWorkflow} />)
          }
        </section>
      </aside>

      {/* CHAT */}
      <main style={styles.main}>
        <div style={styles.messages}>
          {messages.map((m, i) => (
            <div key={i} style={m.role === "user" ? styles.userMsg : styles.botMsg}>
              {m.role === "assistant" && <span style={styles.avatar}>⚡</span>}
              <span>{m.text}</span>
            </div>
          ))}
          {loading && (
            <div style={styles.botMsg}>
              <span style={styles.avatar}>⚡</span>
              <span style={styles.typing}>Thinking<span className="dots">...</span></span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* INPUT BAR */}
        <div style={styles.inputBar}>
          <button
            style={{ ...styles.voiceBtn, background: listening ? "#ef4444" : "#22c55e" }}
            onClick={listening ? stop : start}
            title={listening ? "Stop" : "Speak"}
          >
            {listening ? "⏹" : "🎤"}
          </button>
          <input
            style={styles.input}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSend()}
            placeholder="Type or speak... e.g. 'Send John a meeting invite for Friday 3pm'"
          />
          <button style={styles.sendBtn} onClick={() => handleSend()}>Send</button>
        </div>
      </main>
    </div>
  );
}

// ── STYLES ───────────────────────────────────────────────────────────────────

const styles = {
  root: { display: "flex", height: "100vh", fontFamily: "'IBM Plex Mono', monospace", background: "#0a0a0f", color: "#e2e8f0" },
  sidebar: { width: 300, background: "#0f0f1a", borderRight: "1px solid #1e1e3f", padding: 20, overflowY: "auto", flexShrink: 0 },
  logo: { fontSize: 22, fontWeight: 700, color: "#818cf8", marginBottom: 28, letterSpacing: 1 },
  section: { marginBottom: 28 },
  sectionTitle: { fontSize: 10, letterSpacing: 2, color: "#4a4a7a", marginBottom: 10, fontWeight: 600 },
  empty: { fontSize: 12, color: "#2d2d50", margin: 0 },
  card: { background: "#13132a", border: "1px solid #2d2d6b", borderRadius: 10, padding: 12, marginBottom: 10 },
  cardBadge: { fontSize: 10, color: "#fbbf24", marginBottom: 6 },
  cardText: { fontSize: 12, color: "#a5b4fc", margin: "0 0 10px 0", lineHeight: 1.5 },
  cardActions: { display: "flex", gap: 8 },
  btnApprove: { flex: 1, padding: "6px 0", background: "#16a34a", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12 },
  btnReject: { flex: 1, padding: "6px 0", background: "#dc2626", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12 },
  chip: { display: "flex", justifyContent: "space-between", alignItems: "center", background: "#13132a", border: "1px solid #2d2d6b", borderRadius: 20, padding: "6px 12px", marginBottom: 8, fontSize: 12, color: "#a5b4fc" },
  chipDel: { background: "none", border: "none", color: "#4a4a7a", cursor: "pointer", fontSize: 16, lineHeight: 1 },
  main: { flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" },
  messages: { flex: 1, overflowY: "auto", padding: "24px 32px", display: "flex", flexDirection: "column", gap: 16 },
  userMsg: { alignSelf: "flex-end", background: "#1e1b4b", color: "#c7d2fe", padding: "10px 16px", borderRadius: "16px 16px 4px 16px", maxWidth: "70%", fontSize: 14, lineHeight: 1.5 },
  botMsg: { alignSelf: "flex-start", display: "flex", gap: 10, alignItems: "flex-start", maxWidth: "75%" },
  avatar: { fontSize: 20, flexShrink: 0, marginTop: 2 },
  typing: { color: "#6366f1", fontSize: 14 },
  inputBar: { display: "flex", gap: 10, padding: "16px 24px", borderTop: "1px solid #1e1e3f", background: "#0a0a0f" },
  voiceBtn: { width: 44, height: 44, borderRadius: "50%", border: "none", fontSize: 18, cursor: "pointer", flexShrink: 0 },
  input: { flex: 1, background: "#0f0f1a", border: "1px solid #2d2d6b", borderRadius: 10, padding: "10px 16px", color: "#e2e8f0", fontSize: 14, outline: "none" },
  sendBtn: { padding: "10px 20px", background: "#4f46e5", color: "#fff", border: "none", borderRadius: 10, cursor: "pointer", fontWeight: 600, fontSize: 14 },
};
