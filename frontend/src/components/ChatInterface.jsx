import React, { useEffect, useRef, useState } from "react";
import { askQuestion } from "../api.js";

export default function ChatInterface({ namespace }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const scrollerRef = useRef(null);

  useEffect(() => {
    scrollerRef.current?.scrollTo({
      top: scrollerRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, busy]);

  async function send(e) {
    e?.preventDefault?.();
    const q = input.trim();
    if (!q || busy) return;

    setError(null);
    setMessages((m) => [...m, { role: "user", text: q }]);
    setInput("");
    setBusy(true);

    try {
      const res = await askQuestion({ question: q, namespace });
      setMessages((m) => [
        ...m,
        { role: "assistant", text: res.answer, sources: res.sources || [] },
      ]);
    } catch (err) {
      const detail =
        err?.response?.data?.detail || err?.message || "Query failed";
      setError(detail);
    } finally {
      setBusy(false);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="panel chat">
      <h2>Conversation</h2>

      <div className="messages" ref={scrollerRef}>
        {messages.length === 0 && !busy && (
          <p className="muted">
            Ask a question about your indexed documents. Answers will cite the
            source files they came from.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.text}
            {m.role === "assistant" && m.sources?.length > 0 && (
              <div className="sources">
                {m.sources.map((s, j) => (
                  <span key={j} className="source-pill">
                    {s.filename} · chunk {s.chunk_index} ·{" "}
                    {Number(s.score).toFixed(2)}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && (
          <div className="msg assistant">
            <em className="muted">Thinking…</em>
          </div>
        )}
      </div>

      {error && <div className="status error">{error}</div>}

      <form className="input-row" onSubmit={send}>
        <textarea
          rows={2}
          placeholder="Ask anything about your documents…"
          value={input}
          onKeyDown={onKeyDown}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
