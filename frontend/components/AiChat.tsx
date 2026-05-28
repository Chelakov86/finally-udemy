"use client";

import React, { useRef, useEffect } from "react";
import { Send, Trash2, Bot, User, CheckCircle2, TrendingUp } from "lucide-react";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  // Recommendations parsed from response
  trades?: Array<{
    ticker: string;
    side: "buy" | "sell";
    quantity?: number;
    notional_amount?: number;
  }>;
  watchlist_changes?: Array<{
    ticker: string;
    action: "add" | "remove";
  }>;
  recommendations?: Array<{
    type: "trade" | "watchlist";
    ticker: string;
    side?: "buy" | "sell";
    rationale: string;
  }>;
}

interface AiChatProps {
  messages: ChatMessage[];
  inputValue: string;
  onInputChange: (val: string) => void;
  onSendMessage: (msg: string) => Promise<void>;
  onClearHistory: () => Promise<void>;
  isThinking: boolean;
}

export default function AiChat({
  messages,
  inputValue,
  onInputChange,
  onSendMessage,
  onClearHistory,
  isThinking,
}: AiChatProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Auto scroll to bottom on new messages or thinking status
  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [messages, isThinking]);

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const msg = inputValue.trim();
    if (!msg) return;
    onInputChange("");
    await onSendMessage(msg);
  };

  const handleConfirmationAction = async (text: string) => {
    await onSendMessage(text);
  };

  return (
    <div className="flex flex-col h-full bg-[#161b22] border border-border-custom rounded-lg overflow-hidden select-none">
      {/* Panel Header */}
      <div className="flex min-h-11 shrink-0 items-center justify-between gap-2 border-b border-border-custom bg-[#0d1117]/80 px-3 py-2 sm:px-4">
        <div className="flex min-w-0 items-center space-x-2">
          <Bot className="w-4 h-4 text-blue-primary" />
          <h2 className="truncate text-xs font-bold tracking-wider text-gray-300 uppercase">
            AI FINANCIAL ALLY
          </h2>
        </div>
        <button
          id="chat-clear-history-button"
          onClick={onClearHistory}
          title="CLEAR CONVERSATION"
          className="p-1 text-gray-500 hover:text-red-400 rounded hover:bg-[#0d1117] transition-colors cursor-pointer"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Message Feed Feed Container */}
      <div
        ref={scrollContainerRef}
        className="flex-1 p-4 overflow-y-auto space-y-4 bg-[#0d1117]/25"
      >
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-3">
            <Bot className="w-10 h-10 text-gray-600 animate-pulse" />
            <div className="space-y-1">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">
                FINALLY CHAT IS ACTIVE
              </h3>
              <p className="text-[10px] text-gray-600 max-w-[200px] leading-relaxed">
                Ask me to analyze positions, add tickers, or recommend trading strategies.
              </p>
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.role === "user";
            
            return (
              <div
                key={msg.id}
                id={`chat-message-${msg.id}`}
                className={`flex space-x-2.5 max-w-[90%] ${isUser ? "ml-auto flex-row-reverse space-x-reverse" : "mr-auto"}`}
              >
                {/* Avatar Icon */}
                <div
                  className={`flex h-7 w-7 items-center justify-center rounded-full shrink-0 border select-none ${
                    isUser
                      ? "bg-[#21262d] border-gray-700 text-gray-300"
                      : "bg-blue-primary/10 border-blue-primary/30 text-blue-primary"
                  }`}
                >
                  {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>

                {/* Message Body Content */}
                <div className="space-y-2 flex-1">
                  <div
                    className={`rounded-lg px-3 py-2 text-xs leading-relaxed font-sans shadow-sm break-words ${
                      isUser
                        ? "bg-[#21262d] text-gray-100 border border-gray-700/50"
                        : "bg-[#161b22] text-[#f0f3f6] border border-border-custom"
                    }`}
                  >
                    {msg.content}
                  </div>

                  {/* Render interactive trade recommendation confirmation card */}
                  {!isUser && msg.trades && msg.trades.length > 0 && (
                    <div className="rounded-lg border border-purple-secondary/40 bg-purple-secondary/5 p-3 space-y-2.5 animate-fadeIn">
                      <div className="flex items-center space-x-1.5 text-purple-400 font-bold uppercase text-[9px] tracking-wider">
                        <TrendingUp className="w-3.5 h-3.5" />
                        <span>PROPOSED AI TRADE ACTION</span>
                      </div>
                      
                      {msg.trades.map((trade, idx) => (
                        <div key={idx} className="font-mono text-[10px] text-gray-300 bg-[#0d1117] p-2 rounded border border-gray-800">
                          <span className={`font-bold ${trade.side === "buy" ? "text-purple-400" : "text-red-400"}`}>
                            {trade.side.toUpperCase()}
                          </span>{" "}
                          {trade.quantity ? `${trade.quantity} shares` : `$${trade.notional_amount}`}{" "}
                          of <span className="text-accent-yellow font-bold">{trade.ticker}</span>
                        </div>
                      ))}

                      {/* Yes, do it confirmation trigger button */}
                      <button
                        onClick={() => {
                          const primaryTrade = msg.trades?.[0];
                          if (primaryTrade) {
                            handleConfirmationAction(`yes, do it: buy ${primaryTrade.quantity || primaryTrade.notional_amount} ${primaryTrade.ticker}`);
                          }
                        }}
                        className="w-full h-7 bg-purple-secondary text-white hover:bg-opacity-95 text-[10px] font-bold tracking-wider uppercase rounded flex items-center justify-center space-x-1.5 transition-colors cursor-pointer"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>CONFIRM: &quot;YES, DO IT&quot;</span>
                      </button>
                    </div>
                  )}

                  {/* Render watchlist recommendation confirmation card */}
                  {!isUser && msg.watchlist_changes && msg.watchlist_changes.length > 0 && (
                    <div className="rounded-lg border border-blue-900/30 bg-blue-900/10 p-3 space-y-2.5 animate-fadeIn">
                      <div className="flex items-center space-x-1.5 text-blue-400 font-bold uppercase text-[9px] tracking-wider">
                        <TrendingUp className="w-3.5 h-3.5" />
                        <span>WATCHLIST MODIFICATION</span>
                      </div>
                      
                      {msg.watchlist_changes.map((wc, idx) => (
                        <div key={idx} className="font-mono text-[10px] text-gray-300 bg-[#0d1117] p-2 rounded border border-gray-800">
                          <span className={`font-bold ${wc.action === "add" ? "text-green-400" : "text-red-400"}`}>
                            {wc.action.toUpperCase() === "ADD" ? "ADD TO" : "REMOVE FROM"}
                          </span>{" "}
                          Watchlist: <span className="text-accent-yellow font-bold">{wc.ticker}</span>
                        </div>
                      ))}

                      <button
                        onClick={() => {
                          const change = msg.watchlist_changes?.[0];
                          if (change) {
                            handleConfirmationAction(`yes, do it: ${change.action} ${change.ticker}`);
                          }
                        }}
                        className="w-full h-7 bg-blue-primary text-black hover:bg-opacity-95 text-[10px] font-bold tracking-wider uppercase rounded flex items-center justify-center space-x-1.5 transition-colors cursor-pointer font-semibold"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>CONFIRM ACTION</span>
                      </button>
                    </div>
                  )}

                  {/* Render standard reasoning/recommendations cards */}
                  {!isUser && msg.recommendations && msg.recommendations.length > 0 && (
                    <div className="space-y-2 animate-fadeIn">
                      {msg.recommendations.map((rec, idx) => (
                        <div key={idx} className="rounded-lg border border-border-custom bg-[#161b22] p-2.5 space-y-1 text-[10px]">
                          <div className="flex items-center justify-between text-[9px] tracking-wider uppercase">
                            <span className="font-bold text-accent-yellow">{rec.ticker}</span>
                            <span className={`px-1 rounded font-bold ${rec.side === "buy" ? "bg-purple-900/30 text-purple-400" : "bg-red-950/30 text-red-400"}`}>
                              {rec.side?.toUpperCase()} RECOMMENDATION
                            </span>
                          </div>
                          <p className="text-gray-400 leading-normal">{rec.rationale}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}

        {/* Thinking pulsing status bubble */}
        {isThinking && (
          <div id="chat-thinking-indicator" className="flex space-x-2.5 max-w-[90%] mr-auto items-center">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-primary/10 border border-blue-primary/30 text-blue-primary shrink-0 select-none animate-pulse">
              <Bot className="w-4 h-4" />
            </div>
            <div className="rounded-lg px-3 py-2 text-[10px] bg-[#161b22] border border-border-custom text-gray-500 font-semibold tracking-wider flex items-center space-x-2 select-none">
              <span className="flex h-1.5 w-1.5 rounded-full bg-blue-primary animate-ping" />
              <span>ALLY IS VALUING PORTFOLIO & INTENT AGENTS...</span>
            </div>
          </div>
        )}
      </div>

      {/* Input Message Form */}
      <form
        onSubmit={handleFormSubmit}
        className="min-h-14 border-t border-border-custom bg-[#0d1117]/80 px-3 py-3 sm:px-4 flex items-center space-x-2 shrink-0"
      >
        <input
          id="chat-input-field"
          type="text"
          value={inputValue}
          onChange={(e) => onInputChange(e.target.value)}
          placeholder="Ask AI Ally (e.g. 'Should I buy AAPL?')"
          disabled={isThinking}
          className="flex-1 h-8 rounded border border-border-custom bg-[#0d1117] px-3 text-xs font-medium text-white placeholder-gray-600 focus:border-blue-primary focus:outline-none"
        />
        <button
          id="chat-send-submit"
          type="submit"
          disabled={isThinking || !inputValue.trim()}
          className="flex h-8 w-8 items-center justify-center rounded bg-blue-primary text-black hover:bg-opacity-95 transition-opacity disabled:opacity-30 cursor-pointer"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}
