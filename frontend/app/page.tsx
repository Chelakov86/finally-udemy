"use client";

import React, { useCallback, useEffect, useState, useMemo } from "react";
import Header from "@/components/Header";
import Watchlist, { WatchlistItem } from "@/components/Watchlist";
import MainChart from "@/components/MainChart";
import PositionsTable, { PositionRow } from "@/components/PositionsTable";
import Treemap from "@/components/Treemap";
import OrderTradeBar from "@/components/OrderTradeBar";
import AiChat, { ChatMessage } from "@/components/AiChat";

// Resolve API server address based on active hosting environment
const API_BASE = typeof window !== "undefined"
  ? (window.location.port === "3000" ? "http://localhost:8000" : "")
  : "";

interface MarketHistoryTick {
  timestamp: number;
  price: number;
}

interface PriceUpdate {
  price: number;
  previous_price: number;
  change: number;
  change_percent: number;
  direction: "up" | "down" | "flat";
  timestamp: number;
}

interface ChatResponse {
  message: string;
  trades?: ChatMessage["trades"];
  watchlist_changes?: ChatMessage["watchlist_changes"];
  recommendations?: ChatMessage["recommendations"];
  actions?: {
    trades?: ChatMessage["trades"];
    watchlist_changes?: ChatMessage["watchlist_changes"];
  };
}

function getErrorMessage(err: unknown, fallback: string) {
  return err instanceof Error ? err.message : fallback;
}

// Robust fetch utility that handles APP_PASSWORD auth gates transparently
async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers = new Headers(options.headers || {});
  
  if (typeof window !== "undefined") {
    const password = localStorage.getItem("finally_app_password");
    if (password) {
      headers.set("X-App-Password", password);
      headers.set("Authorization", `Bearer ${password}`);
    }
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      const newPass = prompt("Unauthorized: Please enter FinAlly Access Password:");
      if (newPass) {
        localStorage.setItem("finally_app_password", newPass);
        headers.set("X-App-Password", newPass);
        headers.set("Authorization", `Bearer ${newPass}`);
        const retryRes = await fetch(url, { ...options, headers });
        if (retryRes.ok) return retryRes.json() as Promise<T>;
      }
    }
    throw new Error("Unauthorized: Invalid APP_PASSWORD.");
  }

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "API request failed.");
  }

  return res.json() as Promise<T>;
}

export default function WorkstationDashboard() {
  // --- STATE ---
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [positions, setPositions] = useState<PositionRow[]>([]);
  const [cashBalance, setCashBalance] = useState(1000000); // in cents ($10,000)
  const [isMarketPrices, setIsMarketPrices] = useState(false);
  
  const [activeTicker, setActiveTicker] = useState("AAPL");
  const [tickHistory, setTickHistory] = useState<Record<string, Array<{ timestamp: number; price: number }>>>({});
  const [flashStates, setFlashStates] = useState<Record<string, "up" | "down" | null>>({});

  // SSE State
  const [sseStatus, setSseStatus] = useState<"connected" | "reconnecting" | "disconnected">("disconnected");

  // Chat State
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInputValue, setChatInputValue] = useState("");
  const [isThinking, setIsThinking] = useState(false);

  // --- DERIVED PORTFOLIO METRICS ---
  const { totalValueCents } = useMemo(() => {
    // Sum cash + positions values
    const cash = cashBalance;
    const activePositions = positions.filter((p) => p.quantity > 0);
    
    const positionsValue = activePositions.reduce((sum, pos) => sum + (pos.total_value_cents || 0), 0);
    const positionsPnL = activePositions.reduce((sum, pos) => sum + (pos.unrealized_p_l_cents || 0), 0);

    return {
      totalValueCents: cash + positionsValue,
      totalUnrealizedPnLCents: positionsPnL,
    };
  }, [positions, cashBalance]);

  // --- INITIAL DATA LOAD ---
  const fetchWatchlist = useCallback(async () => {
    try {
      const data = await apiRequest<WatchlistItem[]>("/api/watchlist");
      setWatchlist(data);
    } catch (err) {
      console.error("Error loading watchlist:", err);
    }
  }, []);

  const fetchPortfolio = useCallback(async () => {
    try {
      const data = await apiRequest<{ positions?: PositionRow[]; cash_balance_cents?: number }>("/api/portfolio");
      setPositions(data.positions || []);
      setCashBalance(data.cash_balance_cents || 1000000);
    } catch (err) {
      console.error("Error loading portfolio:", err);
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      const data = await apiRequest<Record<string, MarketHistoryTick[]>>("/api/market/history");
      const formattedHistory: Record<string, Array<{ timestamp: number; price: number }>> = {};
      
      Object.entries(data).forEach(([ticker, list]) => {
        formattedHistory[ticker] = list.map((tick) => ({
          timestamp: Math.floor(tick.timestamp),
          price: tick.price,
        }));
      });

      setTickHistory(formattedHistory);
    } catch (err) {
      console.error("Error loading historical prices:", err);
    }
  }, []);

  useEffect(() => {
    const loadInitialData = async () => {
      await fetchWatchlist();
      await fetchPortfolio();
      await fetchHistory();
    };

    loadInitialData();
  }, [fetchHistory, fetchPortfolio, fetchWatchlist]);

  // --- REAL-TIME SSE PRICE STREAM ---
  useEffect(() => {
    let eventSource: EventSource | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const connectSSE = () => {
      setSseStatus("reconnecting");
      
      const sseUrl = `${API_BASE}/api/stream/prices`;
      // Fetch password if cached to add to query param (EventSource doesn't support custom headers natively)
      const password = localStorage.getItem("finally_app_password") || "";
      const authUrl = password ? `${sseUrl}?app_password=${encodeURIComponent(password)}` : sseUrl;

      // Browser handles auto-reconnections natively
      eventSource = new EventSource(authUrl);

      eventSource.onopen = () => {
        setSseStatus("connected");
      };

      eventSource.onerror = () => {
        setSseStatus("disconnected");
        // Update connection visual state in UI
        reconnectTimeout = setTimeout(() => {
          connectSSE();
        }, 3000);
      };

      eventSource.onmessage = (event) => {
        try {
          const pricesMap = JSON.parse(event.data) as Record<string, PriceUpdate>;
          
          // Verify if price source is real or simulator
          const firstPrice = Object.values(pricesMap)[0];
          if (firstPrice) {
            // Massive aggregates have much higher timestamps or different mock signatures
            const isSimulator = firstPrice.previous_price > 0 && Math.abs(firstPrice.price - firstPrice.previous_price) < 5.0;
            setIsMarketPrices(!isSimulator && !!process.env.NEXT_PUBLIC_MASSIVE_API_KEY);
          }

          // 1. Update Watchlist prices & accumulated history
          setWatchlist((prevWatchlist) =>
            prevWatchlist.map((item) => {
              const update = pricesMap[item.ticker];
              if (!update) return item;

              const oldPrice = item.price;
              const newPrice = update.price;

              // Flash background check
              if (oldPrice !== null && oldPrice !== undefined && oldPrice !== newPrice) {
                const side = newPrice > oldPrice ? "up" : "down";
                setFlashStates((prev) => ({ ...prev, [item.ticker]: side }));
                
                // Clear flash state after 500ms
                setTimeout(() => {
                  setFlashStates((prev) => ({ ...prev, [item.ticker]: null }));
                }, 500);
              }

              // Append price to sparkline ticks
              const currentHistory = [...item.history, newPrice].slice(-30);

              return {
                ...item,
                price: newPrice,
                previous_price: update.previous_price,
                change: update.change,
                change_percent: update.change_percent,
                direction: update.direction,
                history: currentHistory,
              };
            })
          );

          // 2. Update Positions prices and P&L percentages
          setPositions((prevPositions) =>
            prevPositions.map((pos) => {
              const update = pricesMap[pos.ticker];
              if (!update) return pos;

              const newPrice = update.price;
              const valCents = Math.round(pos.quantity * newPrice * 100);
              const costBasisCents = Math.round(pos.quantity * pos.avg_cost_float * 100);
              const pnlCents = valCents - costBasisCents;
              
              const pnlPercent = pos.avg_cost_float > 0
                ? ((newPrice - pos.avg_cost_float) / pos.avg_cost_float) * 100
                : 0;

              return {
                ...pos,
                current_price: newPrice,
                total_value: newPrice * pos.quantity,
                total_value_cents: valCents,
                unrealized_p_l: newPrice * pos.quantity - pos.quantity * pos.avg_cost_float,
                unrealized_p_l_cents: pnlCents,
                unrealized_p_l_percent: pnlPercent,
              };
            })
          );

          // 3. Accumulate active chart ticks
          setTickHistory((prevHistory) => {
            const updated = { ...prevHistory };
            Object.entries(pricesMap).forEach(([ticker, tick]) => {
              const prevList = updated[ticker] || [];
              const timeSec = Math.floor(tick.timestamp);

              // Avoid duplicates
              if (prevList.length > 0 && prevList[prevList.length - 1].timestamp === timeSec) {
                // Update last element
                updated[ticker] = [
                  ...prevList.slice(0, -1),
                  { timestamp: timeSec, price: tick.price },
                ];
              } else {
                updated[ticker] = [
                  ...prevList,
                  { timestamp: timeSec, price: tick.price },
                ].slice(-300); // Bounded history cap to avoid layout memory issues
              }
            });
            return updated;
          });

        } catch (err) {
          console.error("Error parsing price SSE packet:", err);
        }
      };
    };

    connectSSE();

    return () => {
      if (eventSource) eventSource.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, []);

  // --- MANUAL TRADE EXECUTION HANDLER ---
  const handleExecuteTrade = async (trade: {
    ticker: string;
    side: "buy" | "sell";
    quantity?: number;
    notional_amount?: number;
  }) => {
    try {
      await apiRequest<unknown>("/api/portfolio/trade", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(trade),
      });

      // Reload portfolio, watchlist, and history aggregates on transaction complete
      await fetchPortfolio();
      await fetchWatchlist();
      await fetchHistory();
    } catch (err: unknown) {
      throw new Error(getErrorMessage(err, "Failed to execute trade transaction."));
    }
  };

  // --- WATCHLIST ADD/DELETE HANDLERS ---
  const handleAddWatchlistTicker = async (ticker: string) => {
    try {
      const data = await apiRequest<WatchlistItem[]>("/api/watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker }),
      });
      setWatchlist(data);
      setActiveTicker(ticker);
      await fetchHistory(); // Pull history for newly added ticker
    } catch (err: unknown) {
      alert(getErrorMessage(err, `Failed to add ${ticker} to watchlist.`));
    }
  };

  const handleRemoveWatchlistTicker = async (ticker: string) => {
    try {
      const data = await apiRequest<WatchlistItem[]>(`/api/watchlist/${ticker}`, {
        method: "DELETE",
      });
      setWatchlist(data);
      if (activeTicker === ticker && data.length > 0) {
        setActiveTicker(data[0].ticker);
      }
    } catch (err: unknown) {
      alert(getErrorMessage(err, `Failed to remove ${ticker} from watchlist.`));
    }
  };

  // --- AI CHAT ACTIONS ---
  const handleSendChatMessage = async (content: string) => {
    // 1. Add user message locally
    const userMsg: ChatMessage = {
      id: Math.random().toString(),
      role: "user",
      content,
    };
    setChatMessages((prev) => [...prev, userMsg]);
    setIsThinking(true);

    try {
      const res = await apiRequest<ChatResponse>("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: content }),
      });

      // 2. Add assistant response message
      const assistantMsg: ChatMessage = {
        id: Math.random().toString(),
        role: "assistant",
        content: res.message,
        trades: res.trades,
        watchlist_changes: res.watchlist_changes,
        recommendations: res.recommendations,
      };

      setChatMessages((prev) => [...prev, assistantMsg]);

      // If the AI agent automatically modified or executed transactions, reload states!
      const hasExecutedWL = res.actions?.watchlist_changes && res.actions.watchlist_changes.length > 0;
      const hasExecutedTrades = res.actions?.trades && res.actions.trades.length > 0;
      if (
        (res.trades && res.trades.length > 0) ||
        (res.watchlist_changes && res.watchlist_changes.length > 0) ||
        hasExecutedWL ||
        hasExecutedTrades
      ) {
        await fetchPortfolio();
        await fetchWatchlist();
        await fetchHistory();
      }
    } catch (err: unknown) {
      const errorMsg: ChatMessage = {
        id: Math.random().toString(),
        role: "assistant",
        content: `Error: ${getErrorMessage(err, "Failed to process chat agent.")}`,
      };
      setChatMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsThinking(false);
    }
  };

  const handleClearChatHistory = async () => {
    try {
      await apiRequest<unknown>("/api/chat", { method: "DELETE" });
      setChatMessages([]);
    } catch (err: unknown) {
      alert(getErrorMessage(err, "Failed to clear conversation history."));
    }
  };

  // Pull active ticker's ticks safely
  const activeTickerTicks = tickHistory[activeTicker] || [];

  return (
    <div className="flex min-h-screen flex-col bg-[#0d1117] text-[#f0f3f6] lg:h-screen lg:overflow-hidden">
      {/* 1. Dynamic Header */}
      <Header
        portfolioValueCents={totalValueCents}
        cashBalanceCents={cashBalance}
        sseStatus={sseStatus}
        isMarketPrices={isMarketPrices}
      />

      {/* 2. Main Workstation 3-Column Grid */}
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-3 lg:min-h-0 xl:flex-row xl:overflow-hidden">
        
        {/* Left Column: Watchlist & Order Trade Ticket */}
        <div className="flex w-full shrink-0 flex-col gap-3 xl:w-[340px] xl:min-h-0">
          <div className="min-h-[320px] xl:min-h-0 xl:flex-1">
            <Watchlist
              items={watchlist}
              activeTicker={activeTicker}
              onSelectTicker={setActiveTicker}
              onAddTicker={handleAddWatchlistTicker}
              onRemoveTicker={handleRemoveWatchlistTicker}
              flashStates={flashStates}
            />
          </div>
          <div className="min-h-[260px] shrink-0 sm:min-h-[230px] xl:h-[270px] xl:min-h-0">
            <OrderTradeBar
              key={activeTicker}
              activeTicker={activeTicker}
              positions={positions.map((p) => ({ ticker: p.ticker, quantity: p.quantity }))}
              onExecuteTrade={handleExecuteTrade}
            />
          </div>
        </div>

        {/* Center Workspace: Active Chart, Portfolio Positions, and Heatmap Heatmap */}
        <div className="flex min-w-0 flex-1 flex-col gap-3 lg:min-h-0">
          {/* Upper Section: TV High-Performance Chart */}
          <div className="min-h-[360px] lg:min-h-0 lg:flex-1">
            <MainChart ticker={activeTicker} ticks={activeTickerTicks} />
          </div>
          
          {/* Lower Section: Data Grids */}
          <div className="grid shrink-0 grid-cols-1 gap-3 lg:h-[265px] lg:min-h-0 lg:grid-cols-5">
            <div className="min-h-[260px] lg:col-span-3 lg:min-h-0">
              <PositionsTable
                positions={positions}
                activeTicker={activeTicker}
                onSelectTicker={setActiveTicker}
              />
            </div>
            <div className="min-h-[240px] lg:col-span-2 lg:min-h-0">
              <Treemap positions={positions} />
            </div>
          </div>
        </div>

        {/* Right Column: AI Co-Pilot Chat sidebar */}
        <div className="min-h-[420px] w-full shrink-0 xl:min-h-0 xl:w-[340px]">
          <AiChat
            messages={chatMessages}
            inputValue={chatInputValue}
            onInputChange={setChatInputValue}
            onSendMessage={handleSendChatMessage}
            onClearHistory={handleClearChatHistory}
            isThinking={isThinking}
          />
        </div>

      </div>
    </div>
  );
}
