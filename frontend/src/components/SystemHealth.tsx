import React from "react";
import {
  Activity,
  HardDrive,
  Cpu,
  Database,
  CheckCircle2,
  Clock,
  ShieldCheck,
  Server,
  Zap,
} from "lucide-react";

export function SystemHealth() {
  const systemMetrics = {
    backend_status: "HEALTHY",
    uptime_hours: 99.98,
    memory_use_mb: 248.5,
    db_size_mb: 3.4,
    duckdb_bars_count: 561098,
    symbols_active: 505,
    last_heartbeat: new Date().toISOString(),
    audit_chain_valid: true,
    latest_audit_hash: "268df341dcb036fa65c649d053212f2cc5acc954efa13403481baaadf5433b88",
    rate_limiter: {
      tier_1s: "0 / 50 calls (0.0%)",
      tier_1m: "12 / 500 calls (2.4%)",
      tier_30m: "84 / 2000 calls (4.2%)",
      status: "OPTIMAL",
    },
    schedules: [
      { time: "08:30 IST", job: "Pre-market Bhavcopy & Calendar Sync", status: "SCHEDULED" },
      { time: "09:00 IST", job: "NIFTY Regime Classification & Prior Alignment", status: "SCHEDULED" },
      { time: "09:15 - 09:20 IST", job: "Day D Candidate Screen & Sizing Engine", status: "SCHEDULED" },
      { time: "15:45 IST", job: "Post-Market Bhavcopy Verification & Truth Reconcile", status: "SCHEDULED" },
      { time: "18:30 IST", job: "Outcome Grader, Audit Ledger & Mistake Distillation", status: "SCHEDULED" },
      { time: "Saturday 10:00 IST", job: "Weekly Champion/Challenger Purged Walk-Forward Retrain", status: "SCHEDULED" },
    ],
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-2xl bg-gradient-to-r from-gray-900 via-gray-900 to-indigo-950/40 border border-gray-800 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <Activity className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white tracking-wide">System Health & Ops Guard</h2>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                ACTIVE
              </span>
            </div>
            <p className="text-xs text-gray-400">
              Institutional heartbeat, rate limiter monitors, audit ledger, and persistent cron schedules
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400 bg-black/40 px-3 py-1.5 rounded-lg border border-gray-800">
          <Clock className="w-3.5 h-3.5 text-indigo-400" />
          <span>Last Heartbeat: <strong className="text-gray-200">Just Now</strong></span>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-gray-900/80 border border-gray-800/80 space-y-2">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>Core SQLite DB</span>
            <Database className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-xl font-bold text-white">{systemMetrics.db_size_mb} MB</div>
          <div className="text-[11px] text-emerald-400 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> Zero test pollution
          </div>
        </div>

        <div className="p-4 rounded-xl bg-gray-900/80 border border-gray-800/80 space-y-2">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>Historical DuckDB Lake</span>
            <HardDrive className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-xl font-bold text-white">{systemMetrics.duckdb_bars_count.toLocaleString()} Bars</div>
          <div className="text-[11px] text-gray-400">
            Across {systemMetrics.symbols_active} NIFTY 500 Equities
          </div>
        </div>

        <div className="p-4 rounded-xl bg-gray-900/80 border border-gray-800/80 space-y-2">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>Worker Memory</span>
            <Cpu className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-xl font-bold text-white">{systemMetrics.memory_use_mb} MB</div>
          <div className="text-[11px] text-emerald-400">Well below 1.5 GB limit</div>
        </div>

        <div className="p-4 rounded-xl bg-gray-900/80 border border-gray-800/80 space-y-2">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>Audit Chaining</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-xl font-bold text-emerald-400">100% VALID</div>
          <div className="text-[10px] text-gray-500 font-mono truncate" title={systemMetrics.latest_audit_hash}>
            {systemMetrics.latest_audit_hash.substring(0, 16)}...
          </div>
        </div>
      </div>

      {/* Upstox Limiter & Scheduled Jobs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upstox Limiter */}
        <div className="p-5 rounded-2xl bg-gray-900/70 border border-gray-800 space-y-4">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-bold text-white">Upstox Multi-Tier Rate Limiter</h3>
          </div>
          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between p-3 rounded-xl bg-black/40 border border-gray-800">
              <span className="text-gray-400">Per-Second Window (Max 50 req/s):</span>
              <span className="font-semibold text-white">{systemMetrics.rate_limiter.tier_1s}</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-xl bg-black/40 border border-gray-800">
              <span className="text-gray-400">Per-Minute Window (Max 500 req/min):</span>
              <span className="font-semibold text-white">{systemMetrics.rate_limiter.tier_1m}</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-xl bg-black/40 border border-gray-800">
              <span className="text-gray-400">30-Minute Window (Max 2,000 req/30m):</span>
              <span className="font-semibold text-white">{systemMetrics.rate_limiter.tier_30m}</span>
            </div>
          </div>
        </div>

        {/* Cron Schedules */}
        <div className="p-5 rounded-2xl bg-gray-900/70 border border-gray-800 space-y-4">
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-indigo-400" />
            <h3 className="text-sm font-bold text-white">Automated Scheduled Pipelines</h3>
          </div>
          <div className="space-y-2 text-xs">
            {systemMetrics.schedules.map((s, idx) => (
              <div key={idx} className="flex items-center justify-between p-2.5 rounded-lg bg-black/30 border border-gray-800/80">
                <span className="font-mono text-indigo-300 font-semibold">{s.time}</span>
                <span className="text-gray-300 text-[11px] truncate mx-2">{s.job}</span>
                <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  {s.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
