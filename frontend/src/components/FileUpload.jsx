import React, { useRef, useState } from "react";
import { ingestFile } from "../api.js";

const ACCEPT = ".pdf,.docx,.txt,.md";

export default function FileUpload({ namespace, onNamespaceChange, onIngested }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    const file = inputRef.current?.files?.[0];
    if (!file) {
      setStatus({ kind: "error", text: "Please choose a file first." });
      return;
    }
    setBusy(true);
    setStatus({ kind: "info", text: `Uploading ${file.name}…` });
    try {
      const res = await ingestFile(file, namespace || "default");
      setStatus({
        kind: "success",
        text: `Indexed ${res.chunks_ingested} chunks from ${res.filename}.`,
      });
      onIngested?.(res);
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      const detail =
        err?.response?.data?.detail || err?.message || "Upload failed";
      setStatus({ kind: "error", text: detail });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={handleSubmit}>
      <div className="brand">
        <span className="brand-dot" />
        <h1>DocuMind</h1>
      </div>
      <p className="muted">
        Upload a PDF, DOCX, TXT, or MD file and ask questions about its
        contents.
      </p>

      <div>
        <label htmlFor="namespace">Namespace</label>
        <input
          id="namespace"
          type="text"
          value={namespace}
          placeholder="default"
          onChange={(e) => onNamespaceChange(e.target.value)}
        />
      </div>

      <div>
        <label htmlFor="file">Document</label>
        <input ref={inputRef} id="file" type="file" accept={ACCEPT} />
      </div>

      <div className="row">
        <button type="submit" disabled={busy}>
          {busy ? "Uploading…" : "Upload & index"}
        </button>
      </div>

      {status && (
        <div className={`status ${status.kind === "error" ? "error" : status.kind === "success" ? "success" : ""}`}>
          {status.text}
        </div>
      )}
    </form>
  );
}
