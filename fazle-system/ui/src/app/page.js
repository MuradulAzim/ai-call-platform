"use client";

import { useState } from "react";
import { signIn, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function Home() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/dashboard");
    }
  }, [status, router]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });
    if (result?.error) {
      setError("Invalid email or password");
    } else {
      router.push("/dashboard");
    }
    setLoading(false);
  };

  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]">
        <div className="animate-pulse text-gray-400">Loading...</div>
      </div>
    );
  }

  if (status === "authenticated") return null;

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex flex-col">
      {/* Hero Section */}
      <div className="flex-1 flex flex-col items-center justify-center px-4">
        <div className="max-w-2xl text-center mb-12">
          <h1 className="text-5xl md:text-6xl font-bold text-white mb-4">
            <span className="text-fazle-400">Fazle</span>
          </h1>
          <p className="text-xl md:text-2xl text-gray-300 mb-2">
            Your Family&apos;s Personal AI
          </p>
          <p className="text-sm text-gray-500 max-w-md mx-auto">
            A private AI assistant that knows your family, remembers your preferences, and speaks with Azim&apos;s voice.
          </p>
        </div>

        {/* Login Card */}
        <div className="w-full max-w-sm">
          <form
            onSubmit={handleLogin}
            className="bg-[#12121a] border border-gray-800 rounded-2xl p-8 space-y-5"
          >
            <h2 className="text-lg font-semibold text-gray-200 text-center">
              Sign In
            </h2>
            <div>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email"
                className="w-full bg-[#1a1a2e] border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-fazle-500 transition-colors"
                required
              />
            </div>
            <div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                className="w-full bg-[#1a1a2e] border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-fazle-500 transition-colors"
                required
                minLength={8}
              />
            </div>
            {error && (
              <div className="text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-lg px-4 py-2">
                {error}
              </div>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-fazle-600 hover:bg-fazle-700 disabled:opacity-50 disabled:cursor-not-allowed text-white py-3 rounded-xl text-sm font-medium transition-colors"
            >
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </form>
        </div>

        {/* Feature Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-12 max-w-2xl w-full px-4">
          {[
            { icon: "💬", label: "Family Chat" },
            { icon: "🎙️", label: "Voice Calls" },
            { icon: "🧠", label: "Memories" },
            { icon: "📋", label: "Tasks" },
          ].map((f) => (
            <div
              key={f.label}
              className="bg-[#12121a] border border-gray-800 rounded-xl p-4 text-center"
            >
              <span className="text-2xl">{f.icon}</span>
              <p className="text-xs text-gray-400 mt-2">{f.label}</p>
            </div>
          ))}
        </div>
      </div>

      <footer className="text-center text-xs text-gray-600 py-6">
        Family AI System &mdash; Private &amp; Secure
      </footer>
    </div>
  );
}
