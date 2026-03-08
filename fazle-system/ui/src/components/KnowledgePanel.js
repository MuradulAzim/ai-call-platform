"use client";

import { useState } from "react";

export default function KnowledgePanel() {
  const [text, setText] = useState("");
  const [source, setSource] = useState("manual");
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [mode, setMode] = useState("text"); // "text" or "url"

  const ingestText = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch("/api/fazle/knowledge/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, source, title }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
        setText("");
        setTitle("");
      } else {
        setResult({ error: "Failed to ingest" });
      }
    } catch {
      setResult({ error: "Service unavailable" });
    } finally {
      setLoading(false);
    }
  };

  const scrapeUrl = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch("/api/fazle/web/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: url, max_results: 1 }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult({ status: "scraped", results: data.results });
      }
    } catch {
      setResult({ error: "Failed to scrape URL" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-gray-800 p-4">
        <h2 className="text-lg font-semibold text-gray-200">Knowledge Base</h2>
        <p className="text-xs text-gray-500">Upload documents and web content for Fazle to learn</p>
      </div>

      <div className="p-4 border-b border-gray-800">
        <div className="flex gap-2">
          <button
            onClick={() => setMode("text")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === "text" ? "bg-fazle-600 text-white" : "bg-gray-800 text-gray-400"
            }`}
          >
            Text / Document
          </button>
          <button
            onClick={() => setMode("url")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === "url" ? "bg-fazle-600 text-white" : "bg-gray-800 text-gray-400"
            }`}
          >
            Web URL
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {mode === "text" ? (
          <form onSubmit={ingestText} className="space-y-4">
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Document title"
              className="w-full bg-[#1a1a2e] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-fazle-500"
            />
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="w-full bg-[#1a1a2e] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-fazle-500"
            >
              <option value="manual">Manual Input</option>
              <option value="document">Document</option>
              <option value="transcript">Voice Transcript</option>
            </select>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste text content here..."
              rows={12}
              className="w-full bg-[#1a1a2e] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-fazle-500"
              required
            />
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-fazle-600 hover:bg-fazle-700 disabled:opacity-50 text-white py-3 rounded-lg text-sm font-medium"
            >
              {loading ? "Ingesting..." : "Ingest into Knowledge Base"}
            </button>
          </form>
        ) : (
          <form onSubmit={scrapeUrl} className="space-y-4">
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/article"
              className="w-full bg-[#1a1a2e] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-fazle-500"
              required
            />
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-fazle-600 hover:bg-fazle-700 disabled:opacity-50 text-white py-3 rounded-lg text-sm font-medium"
            >
              {loading ? "Processing..." : "Extract & Store"}
            </button>
          </form>
        )}

        {result && (
          <div className="mt-6 bg-[#1a1a2e] border border-gray-700/50 rounded-xl p-4">
            <h3 className="text-sm font-medium text-gray-200 mb-2">Result</h3>
            <pre className="text-xs text-gray-400 overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
