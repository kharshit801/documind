import axios from "axios";

const baseURL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const client = axios.create({
  baseURL,
  timeout: 60_000,
});

export async function ingestFile(file, namespace = "default") {
  const form = new FormData();
  form.append("file", file);
  form.append("namespace", namespace);
  const { data } = await client.post("/ingest", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function askQuestion({ question, namespace = "default", topK }) {
  const body = { question, namespace };
  if (topK) body.top_k = topK;
  const { data } = await client.post("/query", body);
  return data;
}

export async function checkHealth() {
  const { data } = await client.get("/health");
  return data;
}

export { baseURL };
