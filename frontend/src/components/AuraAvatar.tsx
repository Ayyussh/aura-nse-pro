import React, { useState, useEffect } from "react";
import { Volume2, VolumeX, Play, Pause, Activity, ShieldAlert, Sparkles, Brain, Radio } from "lucide-react";

export type AuraState = "Idle" | "Scanning" | "Analyzing" | "Bullish Signal" | "Risk Warning" | "Auditing Mistakes" | "Offline";

interface AuraAvatarProps {
  state: AuraState;
  briefingScript?: string;
  regime: string;
}

export const AuraAvatar: React.FC<AuraAvatarProps> = ({ state, briefingScript, regime }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [caption, setCaption] = useState<string>("");
  const [speechRate, setSpeechRate] = useState<number>(1.0);
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    const updateVoices = () => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        const voices = window.speechSynthesis.getVoices();
        setAvailableVoices(voices);
      }
    };
    updateVoices();
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.onvoiceschanged = updateVoices;
    }
  }, []);

  const handlePlayBriefing = () => {
    if (!("speechSynthesis" in window) || !briefingScript) return;

    if (isPlaying) {
      window.speechSynthesis.cancel();
      setIsPlaying(false);
      setCaption("");
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(briefingScript);

    // Prefer Indian English voice
    const inVoice = availableVoices.find(
      (v) => v.lang.includes("en-IN") || v.name.includes("India") || v.lang.includes("hi-IN")
    ) || availableVoices.find((v) => v.lang.startsWith("en"));

    if (inVoice) {
      utterance.voice = inVoice;
    }
    utterance.rate = speechRate;
    utterance.pitch = 1.0;

    utterance.onstart = () => {
      setIsPlaying(true);
      setCaption(briefingScript);
    };

    utterance.onend = () => {
      setIsPlaying(false);
      setCaption("");
    };

    utterance.onerror = () => {
      setIsPlaying(false);
      setCaption("");
    };

    window.speechSynthesis.speak(utterance);
  };

  // Dynamic visual styling based on AURA state
  const getStateColor = () => {
    switch (state) {
      case "Bullish Signal":
        return { ring: "border-emerald-500", glow: "aura-glow-green", text: "text-emerald-400", badge: "bg-emerald-950/80 border-emerald-500/50" };
      case "Risk Warning":
        return { ring: "border-amber-500", glow: "aura-glow-amber", text: "text-amber-400", badge: "bg-amber-950/80 border-amber-500/50" };
      case "Auditing Mistakes":
        return { ring: "border-purple-500", glow: "aura-glow-cyan", text: "text-purple-400", badge: "bg-purple-950/80 border-purple-500/50" };
      case "Scanning":
      case "Analyzing":
        return { ring: "border-cyan-500", glow: "aura-glow-cyan", text: "text-cyan-400", badge: "bg-cyan-950/80 border-cyan-500/50" };
      default:
        return { ring: "border-indigo-500", glow: "aura-glow-cyan", text: "text-indigo-400", badge: "bg-indigo-950/80 border-indigo-500/50" };
    }
  };

  const style = getStateColor();

  return (
    <div className={`aura-card p-5 border relative overflow-hidden transition-all duration-300 ${style.glow}`}>
      {/* Background ambient gradient */}
      <div className="absolute -top-12 -right-12 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="flex flex-col md:flex-row items-center gap-6">
        {/* Humanoid Holographic Avatar Orb */}
        <div className="relative flex-shrink-0">
          <div className={`w-32 h-32 rounded-full border-2 ${style.ring} flex items-center justify-center relative p-2 transition-all duration-500`}>
            {/* Outer radar pulse */}
            <div className={`absolute inset-0 rounded-full border border-dashed ${style.ring} opacity-50 animate-spin`} style={{ animationDuration: "12s" }} />
            <div className={`absolute -inset-2 rounded-full border ${style.ring} opacity-20 animate-radar`} />

            {/* Core Humanoid Avatar SVG */}
            <div className="w-24 h-24 rounded-full bg-gray-900/90 flex flex-col items-center justify-center relative z-10 shadow-inner">
              {state === "Scanning" && <Radio className="w-10 h-10 text-cyan-400 animate-pulse" />}
              {state === "Analyzing" && <Brain className="w-10 h-10 text-indigo-400 animate-bounce" />}
              {state === "Bullish Signal" && <Sparkles className="w-10 h-10 text-emerald-400 animate-spin" style={{ animationDuration: "6s" }} />}
              {state === "Risk Warning" && <ShieldAlert className="w-10 h-10 text-amber-400 animate-pulse" />}
              {state === "Auditing Mistakes" && <Activity className="w-10 h-10 text-purple-400 animate-pulse" />}
              {state === "Idle" && (
                <div className="flex flex-col items-center">
                  <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-cyan-500 to-indigo-500 shadow-lg shadow-cyan-500/50 mb-1" />
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Persona Tag */}
          <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase bg-gray-900 border border-white/10 text-gray-300">
            AURA v2.0
          </div>
        </div>

        {/* Narrative & Voice Controls */}
        <div className="flex-1 text-center md:text-left">
          <div className="flex flex-wrap items-center justify-center md:justify-start gap-2 mb-2">
            <span className={`px-2.5 py-1 rounded-md text-xs font-semibold border ${style.badge} ${style.text}`}>
              ● {state.toUpperCase()}
            </span>
            <span className="px-2.5 py-1 rounded-md text-xs font-medium bg-gray-800 text-gray-300 border border-gray-700">
              Macro Regime: <strong className="text-white">{regime}</strong>
            </span>
          </div>

          <h2 className="text-xl font-bold tracking-tight text-white mb-1">
            Humanoid AI Chief Quantitative Analyst
          </h2>
          <p className="text-xs text-gray-400 mb-3 max-w-xl">
            Real-time multi-LLM consensus engine monitoring NSE 500 order flow, India VIX volatility regime, and pre-market 9:00 AM signals.
          </p>

          {/* Voice Briefing Controls */}
          <div className="flex flex-wrap items-center justify-center md:justify-start gap-3">
            <button
              onClick={handlePlayBriefing}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-xs transition-all shadow-md ${
                isPlaying
                  ? "bg-amber-600 hover:bg-amber-500 text-white"
                  : "bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/30"
              }`}
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              {isPlaying ? "Pause Spoken Briefing" : "Play 9:00 AM Voice Briefing (en-IN)"}
            </button>

            <div className="flex items-center gap-1.5 bg-gray-800/80 px-2.5 py-1.5 rounded-lg border border-gray-700 text-xs text-gray-300">
              <span className="text-[11px] text-gray-400">Rate:</span>
              <button
                onClick={() => setSpeechRate(1.0)}
                className={`px-1.5 py-0.5 rounded text-[10px] ${speechRate === 1.0 ? "bg-indigo-500 text-white font-bold" : "text-gray-400 hover:text-white"}`}
              >
                1.0x
              </button>
              <button
                onClick={() => setSpeechRate(1.25)}
                className={`px-1.5 py-0.5 rounded text-[10px] ${speechRate === 1.25 ? "bg-indigo-500 text-white font-bold" : "text-gray-400 hover:text-white"}`}
              >
                1.25x
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Voice Captions Display */}
      {caption && (
        <div className="mt-4 p-3 rounded-lg bg-gray-900/90 border border-indigo-500/30 text-xs text-gray-200 leading-relaxed animate-fade-in flex items-start gap-2">
          <Volume2 className="w-4 h-4 text-indigo-400 flex-shrink-0 mt-0.5 animate-pulse" />
          <div>
            <span className="font-semibold text-indigo-300">AURA Spoken Audio: </span>
            {caption}
          </div>
        </div>
      )}
    </div>
  );
};
