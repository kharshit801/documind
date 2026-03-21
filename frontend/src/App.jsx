import React, { useEffect, useState } from "react";
import FileUpload from "./components/FileUpload.jsx";
import ChatInterface from "./components/ChatInterface.jsx";
import { checkHealth, baseURL } from "./api.js";

export default function App() {
  const [namespace, setNamespace] = useState("default");
  const [health, setHealth] = useState({ status: "checking" });

  useEffect(() => {
    checkHealth()
      .then((d) => setHealth(d))
      .catch(() => setHealth({ status: "unreachable" }));
  }, []);

  return (
    <div className="app">
      <FileUpload
        namespace={namespace}
        onNamespaceChange={setNamespace}
        onIngested={() => {}}
      />
      <ChatInterface namespace={namespace} />

      <div
        style={{
          position: "fixed",
          bottom: 8,
          right: 12,
          fontSize: 11,
          color: "var(--muted)",
        }}
      >
        backend: {baseURL} · {health.status}
        {health.version ? ` · v${health.version}` : ""}
      </div>
    </div>
  );
}
