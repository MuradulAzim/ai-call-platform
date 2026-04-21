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
