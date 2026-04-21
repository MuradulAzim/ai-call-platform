"use client";

import { useState, useMemo } from "react";
import { useWbomList, formatCell } from "../../../../lib/wbom-api";
import WbomTable, { StatusBadge, MetaBar } from "../../../../lib/wbom-table";

const FUNNEL_ORDER = [
  "new", "collecting", "scored", "assigned",
  "contacted", "interviewed", "hired", "rejected", "dropped",
];

const FUNNEL_COLORS = {
  new:         "bg-gray-700 text-gray-300",
  collecting:  "bg-blue-900/40 text-blue-300",
  scored:      "bg-purple-900/40 text-purple-300",
  assigned:    "bg-indigo-900/40 text-indigo-300",
  contacted:   "bg-cyan-900/40 text-cyan-300",
  interviewed: "bg-yellow-900/40 text-yellow-300",
  hired:       "bg-green-900/60 text-green-300",
  rejected:    "bg-red-900/40 text-red-300",
  dropped:     "bg-gray-800 text-gray-500",
};

function FunnelBadge({ stage }) {
  const cls = FUNNEL_COLORS[stage] || "bg-gray-700 text-gray-300";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {stage}
    </span>
  );
}

function ScoreBar({ score }) {
  const pct = Math.min(100, Math.max(0, score || 0));
  const color = pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-yellow-500" : "bg-red-500";
  const label = pct >= 70 ? "🔥 Hot" : pct >= 40 ? "Warm" : "Cold";
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-400">{pct}</span>
      <span className="text-xs text-gray-600">{label}</span>
    </div>
  );
}

function WaButton({ phone }) {
  if (!phone) return null;
  const clean = phone.replace(/\D/g, "");
  return (
    <a
      href={`https://wa.me/${clean}`}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-xs text-green-400 hover:text-green-300"
      title="Open WhatsApp"
      onClick={(e) => e.stopPropagation()}
    >
      💬 WA
    </a>
  );
}

function isOverdueFollowUp(row) {
  if (!row.next_followup_at) return false;
  return new Date(row.next_followup_at) < new Date();
}

const COLUMNS = [
  { key: "candidate_id",  label: "ID" },
  { key: "full_name",     label: "Name" },
  {
    key: "phone",
    label: "Phone",
    render: (v) => (
      <div className="flex items-center gap-2">
        <span className="text-sm">{v}</span>
        <WaButton phone={v} />
      </div>
    ),
  },
  { key: "job_preference", label: "Preference" },
  { key: "funnel_stage", label: "Stage", render: (v) => <FunnelBadge stage={v} /> },
  { key: "score",        label: "Score",  render: (v) => <ScoreBar score={v} /> },
  { key: "source",       label: "Source" },
  {
    key: "created_at",
    label: "Added",
    render: (v, row) => (
      <span className={isOverdueFollowUp(row) ? "text-orange-400" : ""}>
        {formatCell(v, "created_at")}
        {isOverdueFollowUp(row) && <span className="ml-1 text-xs">⚠ overdue</span>}
      </span>
    ),
  },
];

export default function RecruitmentPage() {
  const { rows, meta, loading, error, reload } = useWbomList(
    "/recruitment/candidates?limit=200", [], "candidates"
  );
  const [search, setSearch]       = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [bucketFilter, setBucketFilter] = useState("");

  const filtered = useMemo(() => {
    let out = rows;
    if (stageFilter)  out = out.filter((r) => r.funnel_stage === stageFilter);
    if (bucketFilter) out = out.filter((r) => r.score_bucket === bucketFilter);
    if (search) {
      const q = search.toLowerCase();
      out = out.filter(
        (r) =>
          (r.full_name || "").toLowerCase().includes(q) ||
          (r.phone || "").includes(q) ||
          (r.job_preference || "").toLowerCase().includes(q)
      );
    }
    return out;
  }, [rows, search, stageFilter, bucketFilter]);

  // Funnel summary counts
  const stageCount = useMemo(() => {
    const counts = {};
    for (const s of FUNNEL_ORDER) counts[s] = 0;
    rows.forEach((r) => {
      if (r.funnel_stage in counts) counts[r.funnel_stage]++;
    });
    return counts;
  }, [rows]);

  const overdueCount = useMemo(
    () => rows.filter(isOverdueFollowUp).length,
    [rows]
  );

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <h1 className="text-xl font-bold text-white">Recruitment</h1>
          {overdueCount > 0 && !loading && (
            <p className="text-xs text-orange-400 mt-0.5">⚠ {overdueCount} overdue follow-up{overdueCount > 1 ? "s" : ""}</p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value={bucketFilter}
            onChange={(e) => setBucketFilter(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white w-28"
          >
            <option value="">All buckets</option>
            <option value="hot">🔥 Hot</option>
            <option value="warm">Warm</option>
            <option value="cold">Cold</option>
          </select>
          <select
            value={stageFilter}
            onChange={(e) => setStageFilter(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white w-36"
          >
            <option value="">All stages</option>
            {FUNNEL_ORDER.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Search name / phone…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 w-44"
          />
          <button
            onClick={reload}
            className="text-xs text-gray-400 hover:text-white px-2 py-2"
          >
            ↻
          </button>
        </div>
      </div>

      {/* Funnel summary bar — click to filter */}
      {!loading && (
        <div className="flex flex-wrap gap-2 mb-5">
          {FUNNEL_ORDER.map((s) => (
            <button
              key={s}
              onClick={() => setStageFilter(stageFilter === s ? "" : s)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs border transition-colors ${
                stageFilter === s
                  ? "border-blue-500 bg-blue-900/30 text-blue-300"
                  : "border-gray-700 text-gray-400 hover:border-gray-500"
              }`}
            >
              <span className="font-semibold">{stageCount[s]}</span>
              <span>{s}</span>
            </button>
          ))}
        </div>
      )}

      <MetaBar meta={meta} entityName="candidates" />

      <WbomTable
        rows={filtered}
        columns={COLUMNS}
        loading={loading}
        error={error}
        emptyMsg="No candidates found"
      />

      <p className="mt-4 text-xs text-gray-600">
        Score ≥70 = Hot, 40-69 = Warm, &lt;40 = Cold.
      </p>
    </div>
  );
}


function FunnelBadge({ stage }) {
  const cls = FUNNEL_COLORS[stage] || "bg-gray-700 text-gray-300";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {stage}
    </span>
  );
}

function ScoreBar({ score }) {
  const pct = Math.min(100, Math.max(0, score || 0));
  const color = pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-400">{pct}</span>
    </div>
  );
}

const COLUMNS = [
  { key: "candidate_id", label: "ID" },
  { key: "full_name",    label: "Name" },
  { key: "phone",        label: "Phone" },
  { key: "job_preference", label: "Preference" },
  { key: "funnel_stage", label: "Stage", render: (v) => <FunnelBadge stage={v} /> },
  { key: "score",        label: "Score",  render: (v) => <ScoreBar score={v} /> },
  { key: "score_bucket", label: "Bucket" },
  { key: "source",       label: "Source" },
  { key: "created_at",   label: "Added",  render: (v) => formatCell(v, "created_at") },
];

export default function RecruitmentPage() {
  const { rows, meta, loading, error, reload } = useWbomList(
    "/recruitment/candidates?limit=200", [], "candidates"
  );
  const [search, setSearch] = useState("");
  const [stageFilter, setStageFilter] = useState("");

  const filtered = useMemo(() => {
    let out = rows;
    if (stageFilter) out = out.filter((r) => r.funnel_stage === stageFilter);
    if (search) {
      const q = search.toLowerCase();
      out = out.filter(
        (r) =>
          (r.full_name || "").toLowerCase().includes(q) ||
          (r.phone || "").includes(q) ||
          (r.job_preference || "").toLowerCase().includes(q)
      );
    }
    return out;
  }, [rows, search, stageFilter]);

  // Funnel summary counts
  const stageCount = useMemo(() => {
    const counts = {};
    for (const s of FUNNEL_ORDER) counts[s] = 0;
    rows.forEach((r) => {
      if (r.funnel_stage in counts) counts[r.funnel_stage]++;
    });
    return counts;
  }, [rows]);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-white">Recruitment</h1>
        <div className="flex gap-2">
          <select
            value={stageFilter}
            onChange={(e) => setStageFilter(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white w-40"
          >
            <option value="">All stages</option>
            {FUNNEL_ORDER.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Search name / phone…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 w-52"
          />
        </div>
      </div>

      {/* Funnel summary bar */}
      {!loading && (
        <div className="flex flex-wrap gap-2 mb-5">
          {FUNNEL_ORDER.map((s) => (
            <button
              key={s}
              onClick={() => setStageFilter(stageFilter === s ? "" : s)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs border transition-colors ${
                stageFilter === s
                  ? "border-blue-500 bg-blue-900/30 text-blue-300"
                  : "border-gray-700 text-gray-400 hover:border-gray-500"
              }`}
            >
              <span className="font-medium">{stageCount[s]}</span>
              <span>{s}</span>
            </button>
          ))}
        </div>
      )}

      <MetaBar meta={meta} entityName="candidates" />

      <WbomTable
        rows={filtered}
        columns={COLUMNS}
        loading={loading}
        error={error}
        emptyMsg="No candidates found"
      />

      <p className="mt-4 text-xs text-gray-600">
        Source of truth: <code>wbom_candidates</code>. Legacy applications available
        read-only at <code>GET /api/wbom/job-applications</code>.
      </p>
    </div>
  );
}
