import React, { useState } from "react";
import { Send, Bot, User, Sparkles, Database, Clock } from "lucide-react";

interface ResearchConsoleProps {
  onSendMessage: (msg: string) => Promise<any>;
}

export const ResearchConsole: React.FC<ResearchConsoleProps> = ({ onSendMessage }) => {
  const [messages, setMessages] = useState<any[]>([
    {
      sender: "aura",
      text: "Hello! I am **AURA**, your quantitative AI market analyst. I can inspect live technical indicators, evaluate NIFTY regime trends, check fundamentals, or explain why any stock was approved or rejected.",
      source: "aura_knowledge_base",
      timestamp: "Live",
    },
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);

  const quickPrompts = [
    "What is the current NSE market regime?",
    "Analyze TCS technicals and swing setup",
    "Check INFY fundamentals and ROE",
    "What are today's approved trades?",
  ];

  const handleSend = async (textToSend?: string) => {
    const q = textToSend || input;
    if (!q.trim() || isSending) return;

    const userMsg = { sender: "user", text: q, timestamp: new Date().toLocaleTimeString() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsSending(true);

    try {
      const resp = await onSendMessage(q);
      const auraMsg = {
        sender: "aura",
        text: resp.reply,
        source: resp.source,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, auraMsg]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          sender: "aura",
          text: "I encountered a communication delay querying the market data layer. Please try again.",
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="aura-card border flex flex-col h-[650px] overflow-hidden">
      {/* Chat Header */}
      <div className="p-4 border-b border-gray-800 bg-gray-900/80 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center">
            <Bot className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="text-sm font-bold text-white flex items-center gap-2">
              AURA Research & Audit Console
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
            </div>
            <div className="text-[11px] text-gray-400">Function-calling over live NSE order flow and database</div>
          </div>
        </div>
      </div>

      {/* Quick Prompts Bar */}
      <div className="px-4 py-2 bg-gray-950/60 border-b border-gray-800/80 flex gap-2 overflow-x-auto text-[11px]">
        {quickPrompts.map((p, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(p)}
            className="flex-shrink-0 px-2.5 py-1 rounded-full bg-gray-900 hover:bg-gray-800 text-gray-300 border border-gray-800 hover:border-indigo-500/50 transition-all flex items-center gap-1"
          >
            <Sparkles className="w-3 h-3 text-cyan-400" /> {p}
          </button>
        ))}
      </div>

      {/* Message History */}
      <div className="flex-1 p-4 overflow-y-auto space-y-4">
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`flex gap-3 max-w-3xl ${m.sender === "user" ? "ml-auto justify-end" : ""}`}
          >
            {m.sender === "aura" && (
              <div className="w-7 h-7 rounded-full bg-indigo-600 flex-shrink-0 flex items-center justify-center mt-1">
                <Bot className="w-4 h-4 text-white" />
              </div>
            )}

            <div
              className={`p-3.5 rounded-xl text-xs leading-relaxed ${
                m.sender === "user"
                  ? "bg-indigo-600 text-white rounded-tr-none"
                  : "bg-gray-900/90 text-gray-200 border border-gray-800 rounded-tl-none whitespace-pre-line"
              }`}
            >
              {m.text}

              {m.source && (
                <div className="mt-2 pt-2 border-t border-gray-800 text-[10px] text-gray-400 flex items-center gap-2">
                  <Database className="w-3 h-3 text-cyan-400" />
                  <span>Source: {m.source}</span>
                  <Clock className="w-3 h-3 text-gray-500 ml-auto" />
                  <span>{m.timestamp}</span>
                </div>
              )}
            </div>

            {m.sender === "user" && (
              <div className="w-7 h-7 rounded-full bg-gray-700 flex-shrink-0 flex items-center justify-center mt-1">
                <User className="w-4 h-4 text-white" />
              </div>
            )}
          </div>
        ))}
        {isSending && (
          <div className="flex gap-3 items-center text-xs text-gray-400 animate-pulse">
            <Bot className="w-5 h-5 text-indigo-400" />
            <span>AURA is inspecting indicators and generating audit response...</span>
          </div>
        )}
      </div>

      {/* Input Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="p-3 bg-gray-900 border-t border-gray-800 flex gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask AURA anything (e.g. 'Analyze Reliance', 'How is India VIX looking?')..."
          className="flex-1 p-2.5 rounded-lg bg-gray-950 border border-gray-700 text-xs text-white focus:outline-none focus:border-indigo-500"
        />
        <button
          type="submit"
          disabled={!input.trim() || isSending}
          className="px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold disabled:opacity-50 transition-all flex items-center gap-1.5"
        >
          <Send className="w-3.5 h-3.5" /> Send
        </button>
      </form>
    </div>
  );
};
