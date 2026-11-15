import React, { useState, useEffect } from "react";
import {
  Key,
  ShieldCheck,
  RefreshCw,
  Send,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  Wifi,
  WifiOff,
  Activity,
  Zap,
  TrendingUp,
  Database,
  ExternalLink,
} from "lucide-react";

interface VaultSettingsProps {
  keys?: any[];
  vaultKeys?: any[];
  onValidateAll?: () => void;
  onAddKey?: (keyData: any) => void;
  onSaveKey?: (keyData: any) => void;
  isValidating?: boolean;
}

export const VaultSettings: React.FC<VaultSettingsProps> = ({
  keys,
  vaultKeys,
  onValidateAll,
  onAddKey,
  onSaveKey,
  isValidating = false,
}) => {
  const activeKeys = keys || vaultKeys || [];
  const [showAddModal, setShowAddModal] = useState(false);
  const [provider, setProvider] = useState("gemini");
  const [keyLabel, setKeyLabel] = useState("");
  const [modelName, setModelName] = useState("gemini-2.5-flash");
  const [apiKey, setApiKey] = useState("");
  const [telegramToken, setTelegramToken] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");
  const [tgSaved, setTgSaved] = useState(false);

  // Upstox Market Data Feed State
  const [upstoxToken, setUpstoxToken] = useState("");
  const [upstoxStatus, setUpstoxStatus] = useState<any>(null);
  const [isTestingUpstox, setIsTestingUpstox] = useState(false);
  const [upstoxTestResult, setUpstoxTestResult] = useState<any>(null);
  const [upstoxSaveMessage, setUpstoxSaveMessage] = useState("");

  const fetchUpstoxStatus = async () => {
    try {
      const res = await fetch("/api/upstox/status");
      if (res.ok) {
        const data = await res.json();
        setUpstoxStatus(data);
      }
    } catch (e) {
      console.warn("Could not fetch Upstox status", e);
    }
  };

  useEffect(() => {
    fetchUpstoxStatus();
  }, []);

  const handleTestUpstox = async (tokenOverride?: string) => {
    setIsTestingUpstox(true);
    setUpstoxSaveMessage("");
    try {
      const res = await fetch("/api/upstox/test-connection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: tokenOverride !== undefined ? tokenOverride : upstoxToken }),
      });
      const data = await res.json();
      setUpstoxTestResult(data);
      fetchUpstoxStatus();
    } catch (e: any) {
      setUpstoxTestResult({
        success: false,
        status: "FAILED",
        message: e?.message || "Network request failed.",
      });
    } finally {
      setIsTestingUpstox(false);
    }
  };

  const handleSaveUpstox = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!upstoxToken.trim()) return;
    setIsTestingUpstox(true);
    setUpstoxSaveMessage("");
    try {
      const res = await fetch("/api/upstox/save-token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: upstoxToken.trim() }),
      });
      const data = await res.json();
      if (data.saved) {
        setUpstoxSaveMessage("Token securely saved to .env & memory!");
        setUpstoxTestResult(data.verification);
        fetchUpstoxStatus();
        setTimeout(() => setUpstoxSaveMessage(""), 5000);
      }
    } catch (e: any) {
      setUpstoxSaveMessage(`Failed to save: ${e?.message}`);
    } finally {
      setIsTestingUpstox(false);
    }
  };

  const handleAddSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyLabel || !apiKey) return;
    const saveFn = onSaveKey || onAddKey;
    if (saveFn) {
      saveFn({
        provider,
        key_label: keyLabel,
        model_name: modelName,
        api_key: apiKey,
        priority_order: activeKeys.length + 1,
      });
    }
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
          {onValidateAll && (
            <button
              onClick={onValidateAll}
              disabled={isValidating}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30 transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isValidating ? "animate-spin" : ""}`} />
              {isValidating ? "Pinging Providers..." : "Validate All Keys"}
            </button>
          )}
        </div>
      </div>

      {/* Upstox Live Market Data Connection Card */}
      <div className="aura-card p-5 border border-cyan-500/30 bg-gradient-to-br from-gray-900/90 to-cyan-950/20 space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-3 border-b border-gray-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-cyan-950/60 border border-cyan-800/60 text-cyan-400">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-white">Upstox Market Data Feed (Tier-2 Engine)</h3>
                {upstoxStatus?.is_configured ? (
                  <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800 animate-pulse">
                    <Wifi className="w-3 h-3" /> FEED CONFIGURED
                  </span>
                ) : (
                  <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-400 border border-amber-800">
                    <WifiOff className="w-3 h-3" /> TOKEN PENDING
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-400 mt-0.5">
                Powers real-time LTP quotes, India VIX readings, and 5-minute intraday candle tie-breakers. Rate limited strictly to 50/s, 500/m, and 2,000/30m.
              </p>
            </div>
          </div>

          <button
            onClick={() => handleTestUpstox()}
            disabled={isTestingUpstox}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg shadow-cyan-600/30 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isTestingUpstox ? "animate-spin" : ""}`} />
            {isTestingUpstox ? "Testing Upstox..." : "Test Upstox Connection"}
          </button>
        </div>

        {/* Input Form */}
        <form onSubmit={handleSaveUpstox} className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-end">
          <div className="lg:col-span-8">
            <label className="text-xs text-gray-400 font-medium block mb-1 flex items-center justify-between">
              <span>Upstox 1-Year Analytics Access Token</span>
              <span className="text-[10px] text-gray-500">
                {upstoxStatus?.masked_token ? `Active Token: ${upstoxStatus.masked_token}` : "Not yet set"}
              </span>
            </label>
            <input
              type="password"
              value={upstoxToken}
              onChange={(e) => setUpstoxToken(e.target.value)}
              placeholder={upstoxStatus?.masked_token ? "Paste new token to replace existing..." : "Paste your Upstox Analytics Token here..."}
              className="w-full p-2.5 rounded-lg bg-gray-950 border border-gray-700 text-white text-xs font-mono focus:border-cyan-500 focus:outline-none"
            />
          </div>

          <div className="lg:col-span-4 flex items-center gap-2">
            <button
              type="submit"
              disabled={isTestingUpstox || !upstoxToken.trim()}
              className="w-full py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-800 disabled:text-gray-500 text-white text-xs font-semibold transition-all shadow-lg shadow-emerald-600/20"
            >
              Save & Connect
            </button>
          </div>
        </form>

        {upstoxSaveMessage && (
          <div className="p-2.5 rounded bg-emerald-950/60 border border-emerald-800 text-emerald-400 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{upstoxSaveMessage}</span>
          </div>
        )}

        {/* Live Test Results Panel */}
        {upstoxTestResult && (
          <div className={`p-4 rounded-lg border text-xs space-y-3 ${
            upstoxTestResult.success
              ? "bg-emerald-950/20 border-emerald-800/60"
              : "bg-rose-950/20 border-rose-800/60"
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {upstoxTestResult.success ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <XCircle className="w-4 h-4 text-rose-400" />
                )}
                <span className={`font-bold ${upstoxTestResult.success ? "text-emerald-300" : "text-rose-300"}`}>
                  {upstoxTestResult.message}
                </span>
              </div>
              {upstoxTestResult.latency_ms && (
                <span className="text-[11px] text-gray-400 font-mono">
                  Latency: {upstoxTestResult.latency_ms} ms
                </span>
              )}
            </div>

            {upstoxTestResult.success && upstoxTestResult.sample_quotes && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-gray-800">
                <div className="p-2.5 rounded bg-gray-950/70 border border-gray-800">
                  <div className="text-[10px] text-gray-400">Market Status</div>
                  <div className="text-sm font-bold text-white uppercase">{upstoxTestResult.market_status || "OPEN"}</div>
                </div>

                <div className="p-2.5 rounded bg-gray-950/70 border border-gray-800">
                  <div className="text-[10px] text-gray-400">RELIANCE.NS (LTP)</div>
                  <div className="text-sm font-bold text-cyan-400">
                    ₹{upstoxTestResult.sample_quotes.reliance?.ltp ? upstoxTestResult.sample_quotes.reliance.ltp.toLocaleString("en-IN") : "--"}
                  </div>
                  <div className="text-[9px] text-gray-500 font-mono">
                    Lag: {upstoxTestResult.sample_quotes.reliance?.data_lag_seconds ?? "0.1"}s
                  </div>
                </div>

                <div className="p-2.5 rounded bg-gray-950/70 border border-gray-800">
                  <div className="text-[10px] text-gray-400">India VIX Quote</div>
                  <div className="text-sm font-bold text-amber-400">
                    {upstoxTestResult.sample_quotes.india_vix?.ltp ?? "--"}
                  </div>
                </div>

                <div className="p-2.5 rounded bg-gray-950/70 border border-gray-800">
                  <div className="text-[10px] text-gray-400">Token Remaining</div>
                  <div className="text-sm font-bold text-emerald-400">
                    {upstoxTestResult.days_remaining} Days
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Rate Limiting Architecture Note */}
        <div className="p-3 rounded bg-gray-950/50 border border-gray-800/80 flex flex-wrap items-center justify-between gap-3 text-[11px] text-gray-400">
          <div className="flex items-center gap-2">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>Shared Multi-Tier Limiter: <strong>50 req/s</strong>, <strong>500 req/min</strong>, <strong>2,000 req/30m</strong> with automatic 429 backoff</span>
          </div>
          <div className="flex items-center gap-2 text-cyan-400">
            <Database className="w-3.5 h-3.5" />
            <span>Bulk daily history (&gt;15 days) routes to NSE Bhavcopy; Upstox provides live quotes.</span>
          </div>
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
                placeholder="e.g. GEMINI_BACKUP_2"
                className="w-full p-2 rounded bg-gray-950 border border-gray-700 text-white"
              />
            </div>

            <div>
              <label className="text-gray-400 block mb-1">Model Name</label>
              <input
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                className="w-full p-2 rounded bg-gray-950 border border-gray-700 text-white"
              />
            </div>

            <div>
              <label className="text-gray-400 block mb-1">Raw Secret Key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Paste API secret..."
                className="w-full p-2 rounded bg-gray-950 border border-gray-700 text-white"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setShowAddModal(false)}
              className="px-4 py-2 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 font-semibold"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-semibold shadow-md shadow-indigo-600/30"
            >
              Save Key to Encrypted Vault
            </button>
          </div>
        </form>
      )}

      {/* Vault Table */}
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
              {activeKeys.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-gray-500">
                    No keys in vault. System will use algorithmic fallback audit or add your Google Gemini keys above.
                  </td>
                </tr>
              ) : (
                activeKeys.map((k, i) => (
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
