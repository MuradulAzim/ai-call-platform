"use client";

import { useState, useMemo } from "react";
import { useWbomList, formatCell } from "../../../../lib/wbom-api";
import WbomTable, { StatusBadge, MetaBar } from "../../../../lib/wbom-table";

const PRIORITY_COLORS = {
  critical: "bg-red-900/60 text-red-300 border border-red-700",
  high:     "bg-orange-900/60 text-orange-300",
  medium:   "bg-yellow-900/60 text-yellow-300",
  low:      "bg-gray-700 text-gray-300",
};

function PriorityBadge({ priority }) {
  const cls = PRIORITY_COLORS[priority] || "bg-gray-700 text-gray-300";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {priority === "critical" && "🔴 "}{priority}
    </span>
  );
}

function SlaCell({ sla_due_at, status }) {
  if (!sla_due_at || status === "resolved" || status === "closed") {
    return <span className="text-gray-500 text-xs">—</span>;
  }
  const due = new Date(sla_due_at);
  const now = new Date();
  const diffHours = (due - now) / 3600000;
  const isBreached = diffHours < 0;
  const isSoon = diffHours >= 0 && diffHours < 4;
  const label = isBreached
    ? `⚠ ${Math.abs(Math.round(diffHours))}h overdue`
    : `${Math.round(diffHours)}h left`;
  return (
    <span
      className={`text-xs font-medium ${
        isBreached ? "text-red-400" : isSoon ? "text-orange-400" : "text-gray-400"
      }`}
    >
      {label}
    </span>
  );
}

function SlaAlertBar({ rows }) {
  const breached = rows.filter((r) => {
    if (!r.sla_due_at || r.status === "resolved" || r.status === "closed") return false;
    return new Date(r.sla_due_at) < new Date();
  });
  if (breached.length === 0) return null;
  return (
    <div className="bg-red-950/30 border border-red-800 rounded p-3 mb-5 text-sm text-red-300">
      🔴 <strong>{breached.length} SLA breach{breached.length > 1 ? "es" : ""}</strong> — immediate action required
    </div>
  );
}

const COLUMNS = [
  { key: "complaint_id",   label: "ID" },
  { key: "complaint_type", label: "Type" },
  { key: "category",       label: "Category" },
  { key: "priority",       label: "Priority", render: (v) => <PriorityBadge priority={v} /> },
  { key: "status",         label: "Status",   render: (v) => <StatusBadge status={v} /> },
  { key: "reporter_phone", label: "Reporter" },
  {
    key: "sla_due_at",
    label: "SLA",
    render: (v, row) => <SlaCell sla_due_at={v} status={row?.status} />,
  },
  { key: "created_at", label: "Opened", render: (v) => formatCell(v, "created_at") },
];

export default function ComplaintsPage() {
  const { rows, meta, loading, error, reload } = useWbomList(
    "/complaints?limit=100", [], "complaints"
  );
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("open");
  const [priorityFilter, setPriorityFilter] = useState("");

  const filtered = useMemo(() => {
    let out = rows;
    if (statusFilter)   out = out.filter((r) => r.status === statusFilter);
    if (priorityFilter) out = out.filter((r) => r.priority === priorityFilter);
    if (search) {
      const q = search.toLowerCase();
      out = out.filter(
        (r) =>
          (r.reporter_phone || "").includes(q) ||
          (r.category || "").toLowerCase().includes(q) ||
          (r.description || "").toLowerCase().includes(q)
      );
    }
    return out;
  }, [rows, search, statusFilter, priorityFilter]);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <h1 className="text-xl font-bold text-white">Complaints</h1>
        <div className="flex flex-wrap gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white w-36"
          >
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="investigating">Investigating</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white w-32"
          >
            <option value="">All priorities</option>
            <option value="critical">🔴 Critical</option>
            <option value="high">🟠 High</option>
            <option value="medium">🟡 Medium</option>
            <option value="low">Low</option>
          </select>
          <input
            type="text"
            placeholder="Search phone / category…"
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

      {!loading && <SlaAlertBar rows={rows} />}

      <MetaBar meta={meta} entityName="complaints" />

      <WbomTable
        rows={filtered}
        columns={COLUMNS}
        loading={loading}
        error={error}
        emptyMsg="No complaints in this filter"
      />

      <p className="mt-4 text-xs text-gray-600">
        SLA hours: critical=4h, high=24h, medium=72h, low=168h.
      </p>
    </div>
  );
}


function PriorityBadge({ priority }) {
  const cls = PRIORITY_COLORS[priority] || "bg-gray-700 text-gray-300";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {priority}
    </span>
  );
}

function SlaCell({ sla_due_at, status }) {
  if (!sla_due_at || status === "resolved" || status === "closed") {
    return <span className="text-gray-500 text-xs">—</span>;
  }
  const due = new Date(sla_due_at);
  const now = new Date();
  const diffHours = (due - now) / 3600000;
  const isBreached = diffHours < 0;
  const isSoon = diffHours >= 0 && diffHours < 4;
  const label = isBreached
    ? `Breached ${Math.abs(Math.round(diffHours))}h ago`
    : `${Math.round(diffHours)}h left`;
  return (
    <span
      className={`text-xs ${isBreached ? "text-red-400 font-semibold" : isSoon ? "text-orange-400" : "text-gray-400"}`}
    >
      {label}
    </span>
  );
}

const COLUMNS = [
  { key: "complaint_id",   label: "ID" },
  { key: "complaint_type", label: "Type" },
  { key: "category",       label: "Category" },
  { key: "priority",       label: "Priority", render: (v) => <PriorityBadge priority={v} /> },
  { key: "status",         label: "Status",   render: (v) => <StatusBadge status={v} /> },
  { key: "reporter_phone", label: "Reporter" },
  {
    key: "sla_due_at",
    label: "SLA",
    render: (v, row) => <SlaCell sla_due_at={v} status={row?.status} />,
  },
  { key: "created_at", label: "Opened", render: (v) => formatCell(v, "created_at") },
];

export default function ComplaintsPage() {
  const { rows, meta, loading, error, reload } = useWbomList(
    "/complaints?limit=100", [], "complaints"
  );
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");

  const filtered = useMemo(() => {
    let out = rows;
    if (statusFilter)   out = out.filter((r) => r.status === statusFilter);
    if (priorityFilter) out = out.filter((r) => r.priority === priorityFilter);
    if (search) {
      const q = search.toLowerCase();
      out = out.filter(
        (r) =>
          (r.reporter_phone || "").includes(q) ||
          (r.category || "").toLowerCase().includes(q) ||
          (r.description || "").toLowerCase().includes(q)
      );
    }
    return out;
  }, [rows, search, statusFilter, priorityFilter]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Complaints</h1>
        <div className="flex gap-2 flex-wrap">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white w-36"
          >
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="investigating">Investigating</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white w-32"
          >
            <option value="">All priorities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <input
            type="text"
            placeholder="Search phone / category…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 w-52"
          />
        </div>
      </div>

      <MetaBar meta={meta} entityName="complaints" />

      <WbomTable
        rows={filtered}
        columns={COLUMNS}
        loading={loading}
        error={error}
        emptyMsg="No open complaints"
      />

      <p className="mt-4 text-xs text-gray-600">
        Source of truth: <code>wbom_complaints</code>. SLA hours: critical=4, high=24, medium=72, low=168.
      </p>
    </div>
  );
}
