"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";

export default function VoiceSettingsPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const [voiceMode, setVoiceMode] = useState("push-to-talk");
  const [ttsSpeed, setTtsSpeed] = useState(1.0);
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    // Persist to localStorage for now (future: save to API)
    localStorage.setItem(
      "fazle-voice-settings",
      JSON.stringify({ voiceMode, ttsSpeed })
    );
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] p-8">
      <div className="max-w-lg mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-200">Voice Settings</h1>
            <p className="text-sm text-gray-500 mt-1">
              Configure your voice experience
            </p>
          </div>
          <button
            onClick={() => router.push("/dashboard")}
            className="text-gray-400 hover:text-gray-200 px-4 py-2 rounded-lg text-sm border border-gray-700 transition-colors"
          >
            Back
          </button>
        </div>

        <div className="bg-[#12121a] border border-gray-800 rounded-2xl p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-200 mb-3">
              Voice Mode
            </label>
            <div className="space-y-2">
              {[
                { value: "push-to-talk", label: "Push to Talk", desc: "Hold mic button to speak" },
                { value: "continuous", label: "Continuous", desc: "Voice is always listening when active" },
              ].map((opt) => (
                <label
                  key={opt.value}
                  className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    voiceMode === opt.value
                      ? "border-fazle-600 bg-fazle-600/10"
                      : "border-gray-700 hover:border-gray-600"
                  }`}
                >
                  <input
                    type="radio"
                    name="voiceMode"
                    value={opt.value}
                    checked={voiceMode === opt.value}
                    onChange={(e) => setVoiceMode(e.target.value)}
                    className="mt-1 accent-fazle-500"
                  />
                  <div>
                    <p className="text-sm font-medium text-gray-200">{opt.label}</p>
                    <p className="text-xs text-gray-500">{opt.desc}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-200 mb-3">
              Speech Speed: {ttsSpeed.toFixed(1)}x
            </label>
            <input
              type="range"
              min="0.5"
              max="2.0"
              step="0.1"
              value={ttsSpeed}
              onChange={(e) => setTtsSpeed(parseFloat(e.target.value))}
              className="w-full accent-fazle-500"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>Slow (0.5x)</span>
              <span>Normal (1x)</span>
              <span>Fast (2x)</span>
            </div>
          </div>

          <button
            onClick={handleSave}
            className="w-full bg-fazle-600 hover:bg-fazle-700 text-white py-3 rounded-xl text-sm font-medium transition-colors"
          >
            {saved ? "✓ Saved" : "Save Settings"}
          </button>
        </div>
      </div>
    </div>
  );
}
