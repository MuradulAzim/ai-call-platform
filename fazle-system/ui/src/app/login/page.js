"use client";

import { useState, useEffect } from "react";
import { signIn, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [isSetup, setIsSetup] = useState(null);
  const [setupMode, setSetupMode] = useState(false);
  const [name, setName] = useState("");
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated") {
      router.push("/dashboard");
    }
  }, [status, router]);

  useEffect(() => {
    fetch("/api/setup-status")
      .then((r) => r.json())
      .then((data) => {
        setIsSetup(data.setup_completed);
        if (!data.setup_completed) setSetupMode(true);
      })
      .catch(() => setIsSetup(true));
  }, []);

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

  const handleSetup = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          name: name || "Azim",
          relationship_to_azim: "self",
          role: "admin",
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Setup failed");
        setLoading(false);
        return;
      }

      // Setup successful, now login
      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
      });

      if (!result?.error) {
        router.push("/dashboard");
      }
    } catch {
      setError("Setup failed — check connection");
    }
    setLoading(false);
  };

  if (status === "loading" || isSetup === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]">
        <div className="animate-pulse text-gray-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f] px-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-fazle-400">Fazle</h1>
          <p className="mt-2 text-gray-500 text-sm">
            {setupMode ? "Create your admin account" : "Sign in to continue"}
          </p>
        </div>

        <form
          onSubmit={setupMode ? handleSetup : handleLogin}
          className="bg-[#12121a] border border-gray-800 rounded-2xl p-8 space-y-6"
        >
          {setupMode && (
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Your Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Azim"
                className="w-full bg-[#1a1a2e] border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-fazle-500 transition-colors"
                required
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full bg-[#1a1a2e] border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-fazle-500 transition-colors"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
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
            {loading
              ? "Please wait..."
              : setupMode
                ? "Create Admin Account"
                : "Sign In"}
          </button>
        </form>

        <p className="text-center text-xs text-gray-600">
          Family AI System
        </p>
      </div>
    </div>
  );
}
