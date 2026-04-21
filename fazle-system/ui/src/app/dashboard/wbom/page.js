"use client";

import { useRouter } from "next/navigation";
import { useWbomFetch } from "../../../lib/wbom-api";

function SkeletonCard() {
  return (
    <div className="bg-[#111118] rounded-lg p-5 border border-gray-800 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="space-y-2 flex-1">
          <div className="h-3 bg-gray-700 rounded w-24" />
          <div className="h-7 bg-gray-700 rounded w-16" />
          <div className="h-3 bg-gray-700 rounded w-32" />
        </div>
        <div className="h-8 w-8 bg-gray-700 rounded" />
      </div>
    </div>
  );
}

function StatCard({ label, value, icon, sub, href, alert }) {
  const router = useRouter();
  const clickable = !!href;
  return (
    <div
      onClick={clickable ? () => router.push(href) : undefined}
      className={`bg-[#111118] rounded-lg p-5 border transition-colors ${
        alert === "red"
          ? "border-red-700 bg-red-950/20"
          : alert === "green"
          ? "border-green-700 bg-green-950/20"
          : "border-gray-800 hover:border-gray-700"
      } ${clickable ? "cursor-pointer" : ""}`}
    >
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <p className="text-xs text-gray-500 uppercase tracking-wider truncate">{label}</p>
          <p className="text-2xl font-bold text-white mt-1 truncate">{value ?? "—"}</p>
          {sub && <p className="text-xs text-gray-500 mt-1 truncate">{sub}</p>}
        </div>
        <span className="text-2xl flex-shrink-0 ml-3">{icon}</span>
      </div>
    </div>
  );
}

function AlertBanner({ alerts }) {
  if (!alerts || alerts.length === 0) return null;
  return (
    <div className="space-y-2 mb-6">
      {alerts.map((a, i) => (
        <div
          key={i}
          className={`flex items-center gap-3 p-3 rounded text-sm border ${
            a.severity === "critical"
              ? "bg-red-900/30 text-red-300 border-red-700"
              : a.severity === "high"
              ? "bg-orange-900/30 text-orange-300 border-orange-700"
              : "bg-yellow-900/20 text-yellow-300 border-yellow-700"
          }`}
        >
          <span className="flex-shrink-0">
            {a.severity === "critical" ? "🔴" : a.severity === "high" ? "🟠" : "🟡"}
          </span>
          <span>{a.message}</span>
        </div>
      ))}
    </div>
  );
}

function PayrollStatusBar({ payroll_status, loading }) {
  if (loading)
    return (
      <div className="bg-[#111118] rounded-lg p-5 border border-gray-800 animate-pulse">
        <div className="h-4 bg-gray-700 rounded w-32 mb-3" />
        <div className="h-3 bg-gray-700 rounded w-full" />
      </div>
    );
  if (!payroll_status) return null;
  const { draft = 0, approved = 0, paid = 0, pending = 0 } = payroll_status;
  const total = draft + approved + paid + pending;
  return (
    <div className="bg-[#111118] rounded-lg p-5 border border-gray-800">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Payroll Status</p>
      <div className="grid grid-cols-4 gap-2 text-center text-sm">
        {[
          { label: "Draft",    count: draft,    color: "text-gray-300" },
          { label: "Approved", count: approved, color: "text-blue-400" },
          { label: "Paid",     count: paid,     color: "text-green-400" },
          { label: "Pending",  count: pending,  color: "text-yellow-400" },
        ].map(({ label, count, color }) => (
          <div key={label}>
            <p className={`text-lg font-bold ${color}`}>{count}</p>
            <p className="text-xs text-gray-500">{label}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-gray-600 mt-2 text-right">Total: {total} employees</p>
    </div>
  );
}

export default function WbomDashboard() {
  const { data: summary, loading, error, reload } = useWbomFetch("/dashboard/summary");
  const cashFlow = summary?.cash_flow ?? {};
  const lastUpdated = summary ? new Date().toLocaleTimeString("en-BD") : null;

  const openComplaints = summary?.alerts?.filter(
    (a) => a.message?.toLowerCase().includes("complaint")
  )?.length;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-white">WBOM Dashboard</h1>
          {summary?.ref_date && (
            <p className="text-xs text-gray-500 mt-0.5">{summary.ref_date}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-gray-600">Updated {lastUpdated}</span>
          )}
          <button
            onClick={reload}
            disabled={loading}
            className="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50"
          >
            {loading ? "…" : "↻ Refresh"}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/30 text-red-400 p-3 rounded mb-4 text-sm border border-red-800">
          {error}
        </div>
      )}

      <AlertBanner alerts={summary?.alerts} />

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-5">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
        ) : (
          <>
            <StatCard
              label="Active Employees"
              value={summary?.active_employees}
              icon="👥"
              href="/dashboard/wbom/employees"
            />
            <StatCard
              label="Programs Today"
              value={summary?.programs_today}
              icon="🚢"
              sub={summary?.absent_today != null ? `${summary.absent_today} absent` : undefined}
              alert={summary?.absent_today > 3 ? "red" : undefined}
            />
            <StatCard
              label="Cash Today"
              value={cashFlow.net != null ? `৳${cashFlow.net?.toLocaleString()}` : undefined}
              icon="💰"
              sub={cashFlow.inflow != null ? `In ৳${cashFlow.inflow?.toLocaleString()}` : undefined}
              alert={cashFlow.net < 0 ? "red" : cashFlow.net > 0 ? "green" : undefined}
              href="/dashboard/wbom/transactions"
            />
            <StatCard
              label="Payroll Pending"
              value={summary?.payroll_status?.draft ?? "—"}
              icon="💵"
              sub="draft runs"
              alert={summary?.payroll_status?.draft > 0 ? "red" : "green"}
              href="/dashboard/wbom/payroll"
            />
            <StatCard
              label="Open Complaints"
              value={summary?.alerts?.filter(
                (a) => a.message?.toLowerCase().includes("sla")
              )?.length ?? "—"}
              icon="🚨"
              sub="SLA alerts"
              alert={summary?.alerts?.length > 0 ? "red" : "green"}
              href="/dashboard/wbom/complaints"
            />
            <StatCard
              label="Recruitment"
              value={summary?.payroll_status != null ? "Active" : "—"}
              icon="🎯"
              sub="View funnel →"
              href="/dashboard/wbom/recruitment"
            />
          </>
        )}
      </div>

      <PayrollStatusBar payroll_status={summary?.payroll_status} loading={loading} />
    </div>
  );
}

function StatCard({ label, value, icon, loading, sub }) {
  return (
    <div className="bg-[#111118] rounded-lg p-5 border border-gray-800">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-bold text-white mt-1">
            {loading
              ? <span className="animate-pulse bg-gray-700 rounded w-12 h-7 inline-block" />
              : (value ?? "—")}
          </p>
          {sub && !loading && (
            <p className="text-xs text-gray-500 mt-1">{sub}</p>
          )}
        </div>
        <span className="text-2xl">{icon}</span>
      </div>
    </div>
  );
}

function AlertBanner({ alerts }) {
  if (!alerts || alerts.length === 0) return null;
  return (
    <div className="space-y-2 mb-6">
      {alerts.map((a, i) => (
        <div
          key={i}
          className={`flex items-center gap-3 p-3 rounded text-sm border ${
            a.severity === "critical"
              ? "bg-red-900/30 text-red-300 border-red-700"
              : a.severity === "high"
              ? "bg-orange-900/30 text-orange-300 border-orange-700"
              : "bg-yellow-900/20 text-yellow-300 border-yellow-700"
          }`}
        >
          <span>{a.severity === "critical" ? "🔴" : a.severity === "high" ? "🟠" : "🟡"}</span>
          <span>{a.message}</span>
        </div>
      ))}
    </div>
  );
}

function PayrollStatusBar({ payroll_status, loading }) {
  if (loading) return (
    <div className="bg-[#111118] rounded-lg p-5 border border-gray-800 animate-pulse">
      <div className="h-4 bg-gray-700 rounded w-32 mb-3" />
      <div className="h-3 bg-gray-700 rounded w-full" />
    </div>
  );
  if (!payroll_status) return null;
  const { draft = 0, approved = 0, paid = 0, pending = 0 } = payroll_status;
  const total = draft + approved + paid + pending;
  return (
    <div className="bg-[#111118] rounded-lg p-5 border border-gray-800">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Payroll Status</p>
      <div className="grid grid-cols-4 gap-2 text-center text-sm">
        {[
          { label: "Draft",    count: draft,    color: "text-gray-300" },
          { label: "Approved", count: approved, color: "text-blue-400" },
          { label: "Paid",     count: paid,     color: "text-green-400" },
          { label: "Pending",  count: pending,  color: "text-yellow-400" },
        ].map(({ label, count, color }) => (
          <div key={label}>
            <p className={`text-lg font-bold ${color}`}>{count}</p>
            <p className="text-xs text-gray-500">{label}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-gray-600 mt-2 text-right">Total: {total} employees</p>
    </div>
  );
}

export default function WbomDashboard() {
  const { data: summary, loading, error } = useWbomFetch("/dashboard/summary");

  const cashFlow = summary?.cash_flow ?? {};

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">WBOM Dashboard</h1>
        {summary?.ref_date && (
          <span className="text-xs text-gray-500">{summary.ref_date}</span>
        )}
      </div>

      {error && (
        <div className="bg-red-900/30 text-red-400 p-3 rounded mb-4 text-sm">{error}</div>
      )}

      <AlertBanner alerts={summary?.alerts} />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <StatCard
          label="Active Employees"
          value={summary?.active_employees}
          icon="👥"
          loading={loading}
        />
        <StatCard
          label="Programs Today"
          value={summary?.programs_today}
          icon="🚢"
          loading={loading}
          sub={summary?.absent_today != null ? `${summary.absent_today} absent` : undefined}
        />
        <StatCard
          label="Cash Flow"
          value={cashFlow.net != null ? `৳${cashFlow.net?.toLocaleString()}` : undefined}
          icon="💰"
          loading={loading}
          sub={cashFlow.inflow != null ? `In: ৳${cashFlow.inflow?.toLocaleString()}` : undefined}
        />
      </div>

      <PayrollStatusBar payroll_status={summary?.payroll_status} loading={loading} />
    </div>
  );
}
