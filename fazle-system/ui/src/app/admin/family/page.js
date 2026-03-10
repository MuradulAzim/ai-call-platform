"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";

const RELATIONSHIPS = ["self", "wife", "daughter", "son", "parent", "sibling"];
const ROLES = ["admin", "member"];

export default function FamilyPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [newMember, setNewMember] = useState({
    email: "",
    password: "",
    name: "",
    relationship_to_azim: "daughter",
    role: "member",
  });

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    } else if (session?.user?.role !== "admin") {
      router.replace("/dashboard");
    }
  }, [status, session, router]);

  const authHeaders = () => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${session?.accessToken}`,
  });

  const fetchMembers = async () => {
    try {
      const res = await fetch("/api/admin/family", {
        headers: authHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setMembers(data);
      }
    } catch {
      console.error("Failed to fetch family members");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (session?.accessToken) fetchMembers();
  }, [session]);

  const addMember = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch("/api/admin/register", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(newMember),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to add member");
        return;
      }
      setNewMember({
        email: "",
        password: "",
        name: "",
        relationship_to_azim: "daughter",
        role: "member",
      });
      setShowForm(false);
      fetchMembers();
    } catch {
      setError("Failed to add member");
    }
  };

  if (status === "loading" || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]">
        <div className="animate-pulse text-gray-400">Loading...</div>
      </div>
    );
  }

  if (session?.user?.role !== "admin") return null;

  return (
    <div className="min-h-screen bg-[#0a0a0f] p-8">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-200">Family Members</h1>
            <p className="text-sm text-gray-500 mt-1">
              Manage who can access Fazle
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => router.push("/dashboard")}
              className="text-gray-400 hover:text-gray-200 px-4 py-2 rounded-lg text-sm border border-gray-700 transition-colors"
            >
              Back
            </button>
            <button
              onClick={() => setShowForm(!showForm)}
              className="bg-fazle-600 hover:bg-fazle-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              {showForm ? "Cancel" : "+ Add Member"}
            </button>
          </div>
        </div>

        {showForm && (
          <form
            onSubmit={addMember}
            className="bg-[#12121a] border border-gray-800 rounded-2xl p-6 mb-6 space-y-4"
          >
            <h3 className="text-sm font-medium text-gray-200">
              Add Family Member
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <input
                type="text"
                value={newMember.name}
                onChange={(e) =>
                  setNewMember({ ...newMember, name: e.target.value })
                }
                placeholder="Name"
                className="bg-[#1a1a2e] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-fazle-500"
                required
              />
              <input
                type="email"
                value={newMember.email}
                onChange={(e) =>
                  setNewMember({ ...newMember, email: e.target.value })
                }
                placeholder="Email"
                className="bg-[#1a1a2e] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-fazle-500"
                required
              />
              <input
                type="password"
                value={newMember.password}
                onChange={(e) =>
                  setNewMember({ ...newMember, password: e.target.value })
                }
                placeholder="Password (min 8 chars)"
                className="bg-[#1a1a2e] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-fazle-500"
                required
                minLength={8}
              />
              <select
                value={newMember.relationship_to_azim}
                onChange={(e) =>
                  setNewMember({
                    ...newMember,
                    relationship_to_azim: e.target.value,
                  })
                }
                className="bg-[#1a1a2e] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-fazle-500"
              >
                {RELATIONSHIPS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            {error && (
              <div className="text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-lg px-4 py-2">
                {error}
              </div>
            )}
            <button
              type="submit"
              className="bg-fazle-600 hover:bg-fazle-700 text-white px-6 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              Add Member
            </button>
          </form>
        )}

        <div className="space-y-3">
          {members.map((member) => (
            <div
              key={member.id}
              className="bg-[#12121a] border border-gray-800 rounded-xl p-5 flex items-center justify-between"
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-fazle-600 flex items-center justify-center text-white font-bold">
                  {member.name[0]?.toUpperCase()}
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-200">
                    {member.name}
                  </p>
                  <p className="text-xs text-gray-500">{member.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs px-2 py-1 rounded-full bg-fazle-700/20 text-fazle-300 capitalize">
                  {member.relationship_to_azim}
                </span>
                <span
                  className={`text-xs px-2 py-1 rounded-full ${
                    member.role === "admin"
                      ? "bg-yellow-500/20 text-yellow-300"
                      : "bg-gray-700/50 text-gray-400"
                  }`}
                >
                  {member.role}
                </span>
              </div>
            </div>
          ))}
          {members.length === 0 && !loading && (
            <p className="text-gray-500 text-sm text-center py-8">
              No family members yet.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
