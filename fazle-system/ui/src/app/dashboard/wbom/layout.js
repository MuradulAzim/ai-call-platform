"use client";

import { useSession, signOut } from "next-auth/react";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";

const WBOM_VERSION = "v1.6";

const NAV_ITEMS = [
  { href: "/dashboard/wbom",               label: "Dashboard",    icon: "📊" },
  { href: "/dashboard/wbom/employees",     label: "Employees",    icon: "👥" },
  { href: "/dashboard/wbom/transactions",  label: "Transactions", icon: "💰" },
  { href: "/dashboard/wbom/payments",      label: "Payments",     icon: "📤" },
  { href: "/dashboard/wbom/clients",       label: "Clients",      icon: "🏢" },
  { href: "/dashboard/wbom/payroll",       label: "Payroll",      icon: "💵" },
  { href: "/dashboard/wbom/complaints",    label: "Complaints",   icon: "🚨" },
  { href: "/dashboard/wbom/recruitment",   label: "Recruitment",  icon: "🎯" },
  { href: "/dashboard/wbom/audit",         label: "Audit Log",    icon: "📜" },
];

function WbomSidebar({ pathname, collapsed, onToggle }) {
  return (
    <aside
      className={`${collapsed ? "w-14" : "w-56"} bg-[#111118] border-r border-gray-800 flex flex-col transition-all duration-200`}
    >
      {/* Header */}
      <div className="p-3 border-b border-gray-800 flex items-center justify-between min-h-[56px]">
        {!collapsed && (
          <div>
            <h2 className="text-base font-bold text-white leading-none">WBOM</h2>
            <p className="text-[10px] text-gray-500 mt-0.5">Business Operations</p>
          </div>
        )}
        <button
          onClick={onToggle}
          className="text-gray-500 hover:text-white p-1 rounded ml-auto"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const active =
            pathname === item.href ||
            (item.href !== "/dashboard/wbom" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? item.label : undefined}
              className={`flex items-center gap-3 px-3 py-2.5 text-sm transition-colors ${
                active
                  ? "bg-blue-900/30 text-blue-400 border-r-2 border-blue-400"
                  : "text-gray-400 hover:text-white hover:bg-gray-800/50"
              }`}
            >
              <span className="text-base flex-shrink-0">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-gray-800 space-y-1">
        {!collapsed && (
          <Link
            href="/dashboard"
            className="block text-xs text-gray-500 hover:text-gray-300 py-1"
          >
            ← Main Dashboard
          </Link>
        )}
        <button
          onClick={() => signOut({ callbackUrl: "/login" })}
          title="Logout"
          className="flex items-center gap-2 text-xs text-red-500 hover:text-red-400 w-full py-1"
        >
          <span>🚪</span>
          {!collapsed && <span>Logout</span>}
        </button>
        {!collapsed && (
          <p className="text-[10px] text-gray-700 pt-1">WBOM {WBOM_VERSION}</p>
        )}
      </div>
    </aside>
  );
}

export default function WbomLayout({ children }) {
  const { data: session, status } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Collapse sidebar automatically on small viewports
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 640px)");
    setSidebarCollapsed(mq.matches);
    const handler = (e) => setSidebarCollapsed(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]">
        <div className="animate-pulse text-gray-400">Loading...</div>
      </div>
    );
  }

  if (!session) return null;

  return (
    <div className="flex h-screen bg-[#0a0a0f]">
      <WbomSidebar
        pathname={pathname}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((c) => !c)}
      />
      <main className="flex-1 overflow-auto p-4 md:p-6">{children}</main>
    </div>
  );
}

function WbomSidebar({ pathname }) {
  return (
    <aside className="w-56 bg-[#111118] border-r border-gray-800 flex flex-col">
      <div className="p-4 border-b border-gray-800">
        <h2 className="text-lg font-bold text-white">WBOM</h2>
        <p className="text-xs text-gray-500">Business Operations</p>
      </div>
      <nav className="flex-1 py-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href ||
            (item.href !== "/dashboard/wbom" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                active
                  ? "bg-blue-900/30 text-blue-400 border-r-2 border-blue-400"
                  : "text-gray-400 hover:text-white hover:bg-gray-800/50"
              }`}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-gray-800">
        <Link href="/dashboard" className="text-xs text-gray-500 hover:text-gray-300">
          ← Back to Dashboard
        </Link>
      </div>
    </aside>
  );
}

export default function WbomLayout({ children }) {
  const { data: session, status } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]">
        <div className="animate-pulse text-gray-400">Loading...</div>
      </div>
    );
  }

  if (!session) return null;

  return (
    <div className="flex h-screen bg-[#0a0a0f]">
      <WbomSidebar pathname={pathname} />
      <main className="flex-1 overflow-auto p-6">
        {children}
      </main>
    </div>
  );
}
