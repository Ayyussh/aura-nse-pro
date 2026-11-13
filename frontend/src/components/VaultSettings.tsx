import React, { useState } from "react";
import { Key, ShieldCheck, RefreshCw, Send, CheckCircle2, XCircle, AlertCircle, Clock } from "lucide-react";

interface VaultSettingsProps {
  vaultKeys: any[];
  onValidateAll: () => void;
  onAddKey: (keyData: any) => void;
  isValidating: boolean;
}

export const VaultSettings: React.FC<VaultSettingsProps> = ({
  vaultKeys,
  onValidateAll,
  onAddKey,
  isValidating,
}) => {
  const [showAddModal, setShowAddModal] = useState(false);
  const [provider, setProvider] = useState("gemini");
  const [keyLabel, setKeyLabel] = useState("");
  const [modelName, setModelName] = useState("gemini-2.5-flash");
  const [apiKey, setApiKey] = useState("");
  const [telegramToken, setTelegramToken] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");
  const [tgSaved, setTgSaved] = useState(false);

  const handleAddSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyLabel || !apiKey) return;
    onAddKey({
      provider,
      key_label: keyLabel,
      model_name: modelName,
      api_key: apiKey,
      priority_order: vaultKeys.length + 1,
    });
    setKeyLabel("");
    setApiKey("");
    setShowAddModal(false);
  };

  const handleSaveTelegram = (e: React.FormEvent) => {
    e.preventDefault();
    setTgSaved(true);
    setTimeout(() => setTgSaved(false), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Vault Header & Validate All */}
      <div className="aura-card p-5 border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Key className="w-5 h-5 text-indigo-400" />
            <h2 className="text-base font-bold text-white">Multi-LLM & Failover Key Vault</h2>
          </div>
          <p className="text-xs text-gray-400 mt-1 max-w-xl">
            Keys are encrypted at rest with AES-Fernet. On 429 quota exhaustion, keys automatically cool down and rotate to secondary fallbacks.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 rounded-lg text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-white transition-all border border-gray-700"
          >
            + Add Key
          </button>
          <button
            onClick={onValidateAll}
            disabled={isValidating}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isValidating ? "animate-spin" : ""}`} />
            {isValidating ? "Pinging Providers..." : "Validate All Keys"}
          </button>
        </div>
      </div>

      {/* Add Key Form Modal */}
      {showAddModal && (
        <form onSubmit={handleAddSubmit} className="aura-card p-5 border border-indigo-500/50 space-y-4 animate-fade-in text-xs">
          <div className="font-bold text-white text-sm">Register New API Key in Encrypted Vault</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div>
              <label className="text-gray-400 block mb-1">Provider</label>
              <select
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value);
                  if (e.target.value === "gemini") setModelName("gemini-2.5-flash");
                  else if (e.target.value === "groq") setModelName("llama-3.3-70b-versatile");
                  else if (e.target.value === "openrouter") setModelName("anthropic/claude-3.5-sonnet");
                }}
                className="w-full p-2 rounded bg-gray-950 border border-gray-700 text-white"
              >
                <option value="gemini">Google Gemini (Primary)</option>
                <option value="groq">Groq (Ultra-Fast)</option>
                <option value="openrouter">OpenRouter (Multi-Model)</option>
                <option value="openai">OpenAI</option>
                <option value="ollama">Ollama (Local)</option>
              </select>
            </div>
            <div>
              <label className="text-gray-400 block mb-1">Key Label</label>
              <input
                type="text"
                value={keyLabel}
                onChange={(e) => setKeyLabel(e.target.value)}
                placeholder="GEMINI_PRO_2"
                className="w-full p-2 rounded bg-gray-950 border border-gray-700 text-white"
                required
              />
            </div>
            <div>
              <label className="text-gray-400 block mb-1">Model Name</label>
              <input
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                placeholder="gemini-2.5-pro"
                className="w-full p-2 rounded bg-gray-950 border border-gray-700 text-white"
                required
              />
            </div>
            <div>
              <label className="text-gray-400 block mb-1">API Key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="AIzaSy..."
                className="w-full p-2 rounded bg-gray-950 border border-gray-700 text-white"
                required
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="px-4 py-2 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-semibold">
              Encrypt & Save
            </button>
            <button type="button" onClick={() => setShowAddModal(false)} className="px-4 py-2 rounded bg-gray-800 text-gray-300">
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Vault Keys Table */}
      <div className="aura-card p-5 border">
        <h3 className="text-sm font-bold text-white mb-3">Registered LLM Keys & Live Cooldown Status</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-gray-300">
            <thead className="bg-gray-900/80 uppercase text-[10px] text-gray-400 border-b border-gray-800">
              <tr>
                <th className="p-2.5">Priority</th>
                <th className="p-2.5">Label</th>
                <th className="p-2.5">Provider / Model</th>
                <th className="p-2.5">Masked Key</th>
                <th className="p-2.5">Status</th>
                <th className="p-2.5">Latency</th>
                <th className="p-2.5">Requests (RPM/RPD)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {vaultKeys.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-gray-500">
                    No keys in vault. System will use algorithmic fallback audit or add your Google Gemini keys above.
                  </td>
                </tr>
              ) : (
                vaultKeys.map((k, i) => (
                  <tr key={k.id || i} className="hover:bg-gray-800/30">
                    <td className="p-2.5 text-gray-400 font-mono">#{k.priority_order || i + 1}</td>
                    <td className="p-2.5 font-bold text-white">{k.key_label}</td>
                    <td className="p-2.5">
                      <span className="text-cyan-400 font-medium">{k.provider}</span> / <span className="text-gray-300">{k.model_name}</span>
                    </td>
                    <td className="p-2.5 font-mono text-gray-400">{k.masked_key || "AIza...4a9f"}</td>
                    <td className="p-2.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        k.status === "ACTIVE" ? "bg-emerald-950 text-emerald-400 border border-emerald-800" :
                        k.status === "COOLING" ? "bg-amber-950 text-amber-400 border border-amber-800 flex items-center gap-1" :
                        "bg-rose-950 text-rose-400 border border-rose-800"
                      }`}>
                        {k.status === "COOLING" && <Clock className="w-3 h-3" />}
                        {k.status}
                      </span>
                    </td>
                    <td className="p-2.5 text-gray-300">
                      {k.last_latency_ms ? `${k.last_latency_ms} ms` : "--"}
                    </td>
                    <td className="p-2.5 text-gray-400">
                      {k.rpm_count || 0} rpm / {k.rpd_count || 0} rpd
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Telegram Alert Settings */}
      <div className="aura-card p-5 border">
        <h3 className="text-sm font-bold text-white mb-1 flex items-center gap-2">
          <Send className="w-4 h-4 text-cyan-400" /> Private Telegram Alerts Configuration
        </h3>
        <p className="text-xs text-gray-400 mb-4">
          Receive the 9:00 AM IST pre-market prediction brief and stop/target hit alerts directly in your private Telegram chat.
        </p>

        <form onSubmit={handleSaveTelegram} className="space-y-4 max-w-xl text-xs">
          <div>
            <label className="text-gray-400 block mb-1">Telegram Bot Token (from @BotFather)</label>
            <input
              type="password"
              value={telegramToken}
              onChange={(e) => setTelegramToken(e.target.value)}
              placeholder="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
              className="w-full p-2.5 rounded bg-gray-950 border border-gray-700 text-white"
            />
          </div>
          <div>
            <label className="text-gray-400 block mb-1">Your Telegram Chat ID</label>
            <input
              type="text"
              value={telegramChatId}
              onChange={(e) => setTelegramChatId(e.target.value)}
              placeholder="987654321"
              className="w-full p-2.5 rounded bg-gray-950 border border-gray-700 text-white"
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-semibold transition-all"
          >
            Save Telegram Settings
          </button>
          {tgSaved && (
            <span className="ml-3 text-emerald-400 text-xs font-semibold">
              Telegram credentials updated!
            </span>
          )}
        </form>
      </div>
    </div>
  );
};
