"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";

const MEMORY_TYPES = ["all", "preference", "contact", "knowledge", "personal", "conversation"];

export default function MemoryPanel() {
  const { data: session } = useSession();
  const [memories, setMemories] = useState([]);
  const [selectedType, setSelectedType] = useState("all");
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const authHeaders = () => ({
    "Content-Type": "application/json",
    ...(session?.accessToken
      ? { Authorization: `Bearer ${session.accessToken}` }
      : {}),
  });

  const fetchMemories = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/fazle/memory/search`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          query: searchQuery || "all memories",
          memory_type: selectedType !== "all" ? selectedType : null,
          limit: 20,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setMemories(data.results || []);
      }
    } catch {
      console.error("Failed to fetch memories");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMemories();
  }, [selectedType]);

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-gray-800 p-4">
        <h2 className="text-lg font-semibold text-gray-200">Memory Dashboard</h2>
        <p className="text-xs text-gray-500">View and search Fazle&apos;s memories</p>
      </div>

      <div className="p-4 border-b border-gray-800 space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search memories..."
            className="flex-1 bg-[#1a1a2e] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-fazle-500"
          />
          <button
            onClick={fetchMemories}
            className="bg-fazle-600 hover:bg-fazle-700 text-white px-4 py-2 rounded-lg text-sm"
          >
            Search
          </button>
        </div>
        <div className="flex gap-2 flex-wrap">
          {MEMORY_TYPES.map((type) => (
            <button
              key={type}
              onClick={() => setSelectedType(type)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                selectedType === type
                  ? "bg-fazle-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-gray-200"
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {loading ? (
          <p className="text-gray-500 text-sm animate-pulse">Loading memories...</p>
        ) : memories.length === 0 ? (
          <p className="text-gray-500 text-sm">No memories found.</p>
        ) : (
          memories.map((memory, i) => (
            <div
              key={memory.id || i}
              className="bg-[#1a1a2e] border border-gray-700/50 rounded-xl p-4 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-fazle-700/20 text-fazle-300">
                  {memory.type}
                </span>
                <span className="text-xs text-gray-500">{memory.created_at?.split("T")[0]}</span>
              </div>
              <p className="text-sm text-gray-200">{memory.text}</p>
              {memory.score && (
                <p className="text-xs text-gray-500">Relevance: {(memory.score * 100).toFixed(0)}%</p>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
