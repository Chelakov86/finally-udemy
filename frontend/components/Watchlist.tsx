"use client";

import React, { useState } from "react";
import { formatPercent } from "@/utils/formatter";
import { Plus, Trash2, ArrowUpRight, ArrowDownRight, TrendingUp } from "lucide-react";

export interface WatchlistItem {
  ticker: string;
  price: number | null;
  previous_price: number | null;
  change: number;
  change_percent: number;
  direction: "up" | "down" | "flat";
  history: number[];
}

interface WatchlistProps {
  items: WatchlistItem[];
  activeTicker: string;
  onSelectTicker: (ticker: string) => void;
  onAddTicker: (ticker: string) => Promise<void>;
  onRemoveTicker: (ticker: string) => Promise<void>;
  flashStates: Record<string, "up" | "down" | null>;
}

// Inline pure SVG Sparkline Renderer
function Sparkline({ history, direction }: { history: number[]; direction: "up" | "down" | "flat" }) {
  if (!history || history.length < 2) {
    return (
      <div className="flex h-6 w-[80px] items-center justify-center rounded border border-gray-800/40 bg-black/10">
        <span className="font-mono text-[8px] text-gray-600">ACCUMULATING</span>
      </div>
    );
  }

  const width = 80;
  const height = 24;
  const padding = 2;

  const min = Math.min(...history);
  const max = Math.max(...history);
  const range = max - min;

  const points = history
    .map((price, index) => {
      const x = padding + (index / (history.length - 1)) * (width - padding * 2);
      const y =
        range === 0
          ? height / 2
          : height - padding - ((price - min) / range) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");

  const color = direction === "up" ? "#2ea043" : direction === "down" ? "#f85149" : "#8b949e";

  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
}

export default function Watchlist({
  items,
  activeTicker,
  onSelectTicker,
  onAddTicker,
  onRemoveTicker,
  flashStates,
}: WatchlistProps) {
  const [newTickerInput, setNewTickerInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const symbol = newTickerInput.toUpperCase().trim();
    if (!symbol) return;
    setIsSubmitting(true);
    try {
      await onAddTicker(symbol);
      setNewTickerInput("");
    } catch (err) {
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#161b22] border border-border-custom rounded-lg overflow-hidden select-none">
      {/* Panel Header */}
      <div className="flex min-h-11 flex-wrap items-center justify-between gap-2 border-b border-border-custom bg-[#0d1117]/80 px-3 py-2 sm:flex-nowrap sm:px-4">
        <div className="flex items-center space-x-2">
          <TrendingUp className="w-4 h-4 text-blue-primary" />
          <h2 className="text-xs font-bold tracking-wider text-gray-300 uppercase">
            WATCHLIST
          </h2>
        </div>
        <form onSubmit={handleSubmit} className="flex items-center space-x-1.5">
          <input
            id="watchlist-add-input"
            type="text"
            placeholder="ADD TICKER"
            value={newTickerInput}
            onChange={(e) => setNewTickerInput(e.target.value)}
            disabled={isSubmitting}
            className="h-6 w-20 rounded border border-border-custom bg-[#0d1117] px-1.5 text-[10px] font-bold text-white placeholder-gray-600 uppercase focus:border-blue-primary focus:outline-none"
          />
          <button
            id="watchlist-add-submit"
            type="submit"
            disabled={isSubmitting}
            className="flex h-6 w-6 items-center justify-center rounded bg-blue-primary text-black hover:bg-opacity-95 transition-opacity disabled:opacity-50 cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>

      {/* Watchlist Body (Scrollable Table) */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-border-custom bg-[#0d1117]/40 text-[9px] font-bold tracking-widest text-gray-500 uppercase">
              <th className="py-2 pl-4">SYMBOL</th>
              <th className="py-2 text-right">LAST</th>
              <th className="py-2 text-right">CHG</th>
              <th className="py-2 text-center">TREND</th>
              <th className="py-2 pr-3 text-right"> </th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-xs text-gray-600">
                  WATCHLIST IS EMPTY
                </td>
              </tr>
            ) : (
              items.map((item) => {
                const isActive = item.ticker === activeTicker;
                const flash = flashStates[item.ticker];
                const direction = item.direction;

                // Color coding based on daily performance
                const priceColor =
                  direction === "up"
                    ? "text-[#2ea043]"
                    : direction === "down"
                    ? "text-[#f85149]"
                    : "text-gray-400";

                const isChangePositive = item.change >= 0;
                const changeColor = isChangePositive ? "text-[#2ea043]" : "text-[#f85149]";
                const ArrowIcon = isChangePositive ? ArrowUpRight : ArrowDownRight;

                return (
                  <tr
                    key={item.ticker}
                    id={`watchlist-row-${item.ticker}`}
                    onClick={() => onSelectTicker(item.ticker)}
                    className={`group border-b border-border-custom/50 hover:bg-[#0d1117]/40 cursor-pointer transition-colors ${
                      isActive ? "bg-blue-primary/5 hover:bg-blue-primary/10 border-l-2 border-l-blue-primary" : ""
                    } ${flash === "up" ? "flash-up" : flash === "down" ? "flash-down" : ""}`}
                  >
                    {/* Ticker Name */}
                    <td className="py-2.5 pl-4">
                      <span className="font-mono text-[11px] font-bold text-[#f0f3f6] group-hover:text-accent-yellow">
                        {item.ticker}
                      </span>
                    </td>

                    {/* Live Price */}
                    <td className="py-2.5 text-right font-mono text-[11px] font-bold">
                      <span className={priceColor}>
                        {item.price !== null ? `$${item.price.toFixed(2)}` : "STALE"}
                      </span>
                    </td>

                    {/* Change % & Arrow */}
                    <td className="py-2.5 text-right font-mono text-[10px] font-semibold">
                      <div className="flex items-center justify-end space-x-0.5">
                        <span className={changeColor}>{formatPercent(item.change_percent)}</span>
                        {item.change_percent !== 0 && (
                          <ArrowIcon className={`w-3.5 h-3.5 ${changeColor}`} />
                        )}
                      </div>
                    </td>

                    {/* SVG Sparkline */}
                    <td className="py-1 text-center flex justify-center">
                      <Sparkline history={item.history} direction={direction} />
                    </td>

                    {/* Remove Action */}
                    <td className="py-2.5 pr-3 text-right">
                      <button
                        id={`watchlist-delete-${item.ticker}`}
                        onClick={async (e) => {
                          e.stopPropagation(); // Stop selection row trigger
                          await onRemoveTicker(item.ticker);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 text-gray-500 hover:text-red-500 rounded hover:bg-red-500/10 transition-all cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
