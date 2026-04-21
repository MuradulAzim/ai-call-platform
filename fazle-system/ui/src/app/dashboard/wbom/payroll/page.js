"use client";

import { useState, useMemo } from "react";
import { useWbomList, formatCell } from "../../../../lib/wbom-api";
import WbomTable, { StatusBadge, MetaBar } from "../../../../lib/wbom-table";

const STATUS_COLORS = {
  draft:    "bg-gray-700 text-gray-300",
  approved: "bg-blue-900/60 text-blue-300",
  paid:     "bg-green-900/60 text-green-300",
  pending:  "bg-yellow-900/60 text-yellow-300",
};

function PayrollBadge({ status }) {
  const cls = STATUS_COLORS[status] || "bg-gray-700 text-gray-300";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

function TotalsBar({ rows }) {
  const total = rows.reduce((s, r) => s + (parseFloat(r.net_salary) || 0), 0);
  const paid  = rows.filter((r) => r.status === "paid")
                    .reduce((s, r) => s + (parseFloat(r.net_salary) || 0), 0);
  const pending = total - paid;
  return (
    <div className="grid grid-cols-3 gap-3 mb-5">
      {[
        { label: "Total Payroll",   value: `৳${total.toLocaleString()}`,   color: "text-white" },
        { label: "Paid",            value: `৳${paid.toLocaleString()}`,    color: "text-green-400" },
        { label: "Unpaid / Draft",  value: `৳${pending.toLocaleString()}`, color: "text-yellow-400" },
      ].map(({ label, value, color }) => (
        <div key={label} className="bg-[#111118] rounded-lg p-4 border border-gray-800">
          <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
          <p className={`text-xl font-bold mt-1 ${color}`}>{value}</p>
        </div>
      ))}
    </div>
  );
}

function exportCsv(rows) {
  const headers = ["run_id", "employee_id", "period_month", "period_year",
                   "status", "basic_salary", "net_salary", "total_programs"];
  const lines = [
    headers.join(","),
    ...rows.map((r) =>
      headers.map((h) => JSON.stringify(r[h] ?? "")).join(",")
    ),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `payroll_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

const MONTHS = [
  "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const COLUMNS = [
  { key: "run_id",       label: "ID" },
  { key: "employee_id",  label: "Employee" },
  {
    key: "period_month",
    label: "Month / Year",
    render: (v, row) => `${MONTHS[v] || v} ${row?.period_year || ""}`,
  },
  { key: "status",       label: "Status",  render: (v) => <PayrollBadge status={v} /> },
  { key: "basic_salary", label: "Basic",   render: (v) => formatCell(v, "salary") },
  { key: "net_salary",   label: "Net Pay", render: (v) => formatCell(v, "salary") },
  { key: "total_programs", label: "Prog." },
];

export default function PayrollPage() {
  const { rows, meta, loading, error, reload } = useWbomList(
    "/payroll?limit=100", [], "payroll"
  );
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [monthFilter, setMonthFilter] = useState("");

  const filtered = useMemo(() => {
    let out = rows;
    if (statusFilter) out = out.filter((r) => r.status === statusFilter);
    if (monthFilter)  out = out.filter((r) => String(r.period_month) === monthFilter);
    if (search) {
      const q = search.toLowerCase();
      out = out.filter(
        (r) =>
          String(r.employee_id).includes(q) ||
          String(r.period_month).includes(q) ||
          String(r.period_year).includes(q)
      );
    }
    return out;
  }, [rows, search, statusFilter, monthFilter]);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <h1 className="text-xl font-bold text-white">Payroll Runs</h1>
        <div className="flex flex-wrap gap-2">
          <select
            value={monthFilter}
            onChange={(e) => setMonthFilter(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white w-28"
          >
            <option value="">All months</option>
            {MONTHS.slice(1).map((m, i) => (
              <option key={m} value={String(i + 1)}>{m}</option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white w-32"
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="approved">Approved</option>
            <option value="paid">Paid</option>
            <option value="pending">Pending</option>
          </select>
          <input
            type="text"
            placeholder="Search…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 w-40"
          />
          <button
            onClick={() => exportCsv(filtered)}
            disabled={filtered.length === 0}
            className="bg-blue-900/50 hover:bg-blue-900 text-blue-300 text-sm px-3 py-2 rounded border border-blue-800 disabled:opacity-40"
          >
            ⬇ Export CSV
          </button>
          <button
            onClick={reload}
            className="text-xs text-gray-400 hover:text-white px-2 py-2"
          >
            ↻
          </button>
        </div>
      </div>

      {!loading && <TotalsBar rows={filtered} />}

      <MetaBar meta={meta} entityName="payroll runs" />

      <WbomTable
        rows={filtered}
        columns={COLUMNS}
        loading={loading}
        error={error}
        emptyMsg="No payroll runs found"
      />

      <p className="mt-4 text-xs text-gray-600">
        Approve runs via <code className="text-gray-500">POST /api/wbom/payroll/:id/approve</code>.
        Pay via <code className="text-gray-500">POST /api/wbom/payroll/:id/pay</code>.
      </p>
    </div>
  );
}


const STATUS_COLORS = {
  draft:    "bg-gray-700 text-gray-300",
  approved: "bg-blue-900/60 text-blue-300",
  paid:     "bg-green-900/60 text-green-300",
  pending:  "bg-yellow-900/60 text-yellow-300",
};

function PayrollBadge({ status }) {
  const cls = STATUS_COLORS[status] || "bg-gray-700 text-gray-300";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

const COLUMNS = [
  { key: "run_id",       label: "Run ID" },
  { key: "employee_id",  label: "Emp ID" },
  { key: "period_month", label: "Month" },
  { key: "period_year",  label: "Year" },
  { key: "status",       label: "Status", render: (v) => <PayrollBadge status={v} /> },
  { key: "basic_salary",    label: "Basic",   render: (v) => formatCell(v, "salary") },
  { key: "net_salary",      label: "Net Pay", render: (v) => formatCell(v, "salary") },
  { key: "total_programs",  label: "Programs" },
];

export default function PayrollPage() {
  const { rows, meta, loading, error, reload } = useWbomList(
    "/payroll?limit=100", [], "payroll"
  );
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const filtered = useMemo(() => {
    let out = rows;
    if (statusFilter) out = out.filter((r) => r.status === statusFilter);
    if (search) {
      const q = search.toLowerCase();
      out = out.filter(
        (r) =>
          String(r.employee_id).includes(q) ||
          String(r.period_month).includes(q) ||
          String(r.period_year).includes(q)
      );
    }
    return out;
  }, [rows, search, statusFilter]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Payroll Runs</h1>
        <div className="flex gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white w-36"
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="approved">Approved</option>
            <option value="paid">Paid</option>
            <option value="pending">Pending</option>
          </select>
          <input
            type="text"
            placeholder="Search emp ID / month…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 w-52"
          />
        </div>
      </div>

      <MetaBar meta={meta} entityName="payroll runs" />

      <WbomTable
        rows={filtered}
        columns={COLUMNS}
        loading={loading}
        error={error}
        emptyMsg="No payroll runs found"
      />

      <p className="mt-4 text-xs text-gray-600">
        Source of truth: <code>wbom_payroll_runs</code>. Use the full payroll approval
        workflow via <code>POST /api/wbom/payroll/:id/approve</code> and
        <code>POST /api/wbom/payroll/:id/pay</code>.
      </p>
    </div>
  );
}
