"use client";

import { fieldLabel, formatCell } from "./wbom-api";

// ── WbomTable: Dynamic table renderer ────────────────────────
// Renders columns dynamically from data keys or explicit column config.
// Handles loading skeleton, error banner, and empty state.
//
// Props:
//   rows       - array of data objects
//   columns    - optional array of { key, label?, render? } to control column order
//                if omitted, auto-derived from Object.keys(rows[0])
//   loading    - show skeleton
//   error      - error message string
//   emptyMsg   - message when rows is empty
//   actions    - optional (row) => JSX for action column
//   onRowClick - optional (row) => void
//   hiddenKeys - Set of field keys to hide (e.g. new Set(["id"]))

export default function WbomTable({
  rows = [],
  columns,
  loading = false,
  error = null,
  emptyMsg = "No data found",
  actions,
  onRowClick,
  hiddenKeys = new Set(),
}) {
  // ── Error state ──────────────────────────────────────────
  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700 text-sm">
        <strong>Error:</strong> {error}
      </div>
    );
  }

  // ── Loading skeleton ─────────────────────────────────────
  if (loading) {
    return (
      <div className="animate-pulse space-y-3">
        <div className="h-8 bg-gray-200 rounded w-full" />
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-6 bg-gray-100 rounded w-full" />
        ))}
      </div>
    );
  }

  // ── Empty state ──────────────────────────────────────────
  if (!rows.length) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-8 text-center text-gray-500">
        {emptyMsg}
      </div>
    );
  }

  // ── Derive columns ──────────────────────────────────────
  const cols = columns
    ? columns.filter((c) => !hiddenKeys.has(c.key))
    : Object.keys(rows[0])
        .filter((k) => !hiddenKeys.has(k))
        .map((k) => ({ key: k, label: fieldLabel(k) }));

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            {cols.map((col) => (
              <th
                key={col.key}
                className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider whitespace-nowrap"
              >
                {col.label || fieldLabel(col.key)}
              </th>
            ))}
            {actions && (
              <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Actions
              </th>
            )}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-100">
          {rows.map((row, idx) => (
            <tr
              key={row.id || idx}
              className={`${onRowClick ? "cursor-pointer hover:bg-blue-50" : "hover:bg-gray-50"} transition-colors`}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {cols.map((col) => (
                <td key={col.key} className="px-4 py-3 whitespace-nowrap text-gray-700">
                  {col.render
                    ? col.render(row[col.key], row)
                    : formatCell(row[col.key], col.key)}
                </td>
              ))}
              {actions && (
                <td className="px-4 py-3 whitespace-nowrap text-right">
                  {actions(row)}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


// ── StatusBadge: reusable status pill ────────────────────────

const STATUS_COLORS = {
  active: "bg-green-100 text-green-800",
  approved: "bg-green-100 text-green-800",
  completed: "bg-green-100 text-green-800",
  hired: "bg-green-100 text-green-800",
  pending: "bg-yellow-100 text-yellow-800",
  interview: "bg-blue-100 text-blue-800",
  shortlisted: "bg-blue-100 text-blue-800",
  rejected: "bg-red-100 text-red-800",
  inactive: "bg-gray-100 text-gray-800",
  income: "bg-emerald-100 text-emerald-800",
  expense: "bg-orange-100 text-orange-800",
};

export function StatusBadge({ status }) {
  if (!status) return "—";
  const s = String(status).toLowerCase();
  const color = STATUS_COLORS[s] || "bg-gray-100 text-gray-800";
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {status}
    </span>
  );
}


// ── MetaBar: shows total / page info ─────────────────────────

export function MetaBar({ meta, entityName = "records" }) {
  if (!meta || !meta.total) return null;
  return (
    <div className="text-sm text-gray-500 mb-2">
      Showing {meta.count} of {meta.total} {entityName}
    </div>
  );
}
