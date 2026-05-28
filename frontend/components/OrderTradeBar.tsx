"use client";

import React, { useState } from "react";
import { CreditCard, ShoppingBag, Trash } from "lucide-react";

interface OrderTradeBarProps {
  activeTicker: string;
  positions: Array<{ ticker: string; quantity: number }>;
  onExecuteTrade: (trade: {
    ticker: string;
    side: "buy" | "sell";
    quantity?: number;
    notional_amount?: number;
  }) => Promise<void>;
}

export default function OrderTradeBar({ activeTicker, positions, onExecuteTrade }: OrderTradeBarProps) {
  const [ticker, setTicker] = useState(activeTicker);
  const [quantity, setQuantity] = useState("");
  const [mode, setMode] = useState<"shares" | "dollars">("shares");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Find held quantity for the current ticker
  const currentHolding = positions.find((p) => p.ticker === ticker.toUpperCase().trim())?.quantity || 0;

  const handleTrade = async (side: "buy" | "sell") => {
    setErrorMsg("");
    setSuccessMsg("");
    const symbol = ticker.toUpperCase().trim();
    if (!symbol) {
      setErrorMsg("Ticker is required.");
      return;
    }
    const val = parseFloat(quantity);
    if (isNaN(val) || val <= 0) {
      setErrorMsg("Quantity must be greater than zero.");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: Parameters<OrderTradeBarProps["onExecuteTrade"]>[0] = { ticker: symbol, side };
      if (mode === "shares") {
        payload.quantity = val;
      } else {
        payload.notional_amount = val;
      }

      await onExecuteTrade(payload);
      setSuccessMsg(`Successfully executed order: ${side.toUpperCase()} ${val} ${mode === "shares" ? "shares" : "$"} of ${symbol}`);
      setQuantity("");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : `Failed to execute ${side} trade.`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSellAll = async () => {
    setErrorMsg("");
    setSuccessMsg("");
    const symbol = ticker.toUpperCase().trim();
    if (!symbol) {
      setErrorMsg("Ticker is required.");
      return;
    }
    if (currentHolding <= 0) {
      setErrorMsg(`You do not hold any shares of ${symbol} to sell.`);
      return;
    }

    setIsSubmitting(true);
    try {
      await onExecuteTrade({
        ticker: symbol,
        side: "sell",
        quantity: currentHolding,
      });
      setSuccessMsg(`Successfully sold all ${currentHolding} shares of ${symbol}.`);
      setQuantity("");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to execute sell-all order.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#161b22] border border-border-custom rounded-lg overflow-hidden select-none">
      {/* Panel Header */}
      <div className="flex min-h-11 shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border-custom bg-[#0d1117]/80 px-3 py-2 sm:flex-nowrap sm:px-4">
        <div className="flex min-w-0 items-center space-x-2">
          <CreditCard className="w-4 h-4 text-blue-primary" />
          <h2 className="truncate text-xs font-bold tracking-wider text-gray-300 uppercase">
            TRADE TICKET
          </h2>
        </div>
        <span className="hidden font-mono text-[9px] text-gray-500 tracking-wider 2xl:inline">
          FAST EXECUTION BAR
        </span>
      </div>

      {/* Ticket Body */}
      <div className="flex-1 p-3 sm:p-4 flex flex-col justify-between space-y-4">
        <div className="space-y-3.5">
          {/* Ticker & Mode Row */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-2">
            <div>
              <label className="block text-[9px] font-bold text-gray-500 tracking-wider uppercase mb-1">
                TICKER SYMBOL
              </label>
              <input
                id="trade-ticker-input"
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="AAPL"
                className="h-8 w-full rounded border border-border-custom bg-[#0d1117] px-2.5 text-xs font-bold text-white uppercase focus:border-blue-primary focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-[9px] font-bold text-gray-500 tracking-wider uppercase mb-1">
                ORDER MODE
              </label>
              <div className="grid grid-cols-2 h-8 rounded border border-border-custom bg-[#0d1117] overflow-hidden p-0.5">
                <button
                  id="trade-mode-shares"
                  type="button"
                  onClick={() => setMode("shares")}
                  className={`text-[9px] font-bold tracking-wider uppercase rounded transition-colors cursor-pointer ${
                    mode === "shares" ? "bg-blue-primary text-black" : "text-gray-400 hover:text-white"
                  }`}
                >
                  SHARES
                </button>
                <button
                  id="trade-mode-dollars"
                  type="button"
                  onClick={() => setMode("dollars")}
                  className={`text-[9px] font-bold tracking-wider uppercase rounded transition-colors cursor-pointer ${
                    mode === "dollars" ? "bg-blue-primary text-black" : "text-gray-400 hover:text-white"
                  }`}
                >
                  USD ($)
                </button>
              </div>
            </div>
          </div>

          {/* Quantity & Current Holding Info */}
          <div>
            <div className="flex flex-wrap items-center justify-between gap-1 mb-1">
              <label className="text-[9px] font-bold text-gray-500 tracking-wider uppercase">
                {mode === "shares" ? "QUANTITY (SHARES)" : "TRANSACTION VALUE (USD)"}
              </label>
              {currentHolding > 0 && (
                <span className="font-mono text-[9px] text-accent-yellow">
                  HELD: {currentHolding} SHARES
                </span>
              )}
            </div>
            <input
              id="trade-quantity-input"
              type="number"
              step="any"
              min="0.000001"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder={mode === "shares" ? "10" : "1000.00"}
              className="h-8 w-full rounded border border-border-custom bg-[#0d1117] px-2.5 text-xs font-mono font-bold text-white focus:border-blue-primary focus:outline-none"
            />
          </div>

          {/* Interactive feedback messages */}
          {errorMsg && (
            <div id="trade-error-message" className="text-[10px] text-red-400 bg-red-950/20 border border-red-900/40 rounded px-2.5 py-1.5 font-semibold leading-relaxed">
              {errorMsg}
            </div>
          )}
          {successMsg && (
            <div id="trade-success-message" className="text-[10px] text-green-400 bg-green-950/20 border border-green-900/40 rounded px-2.5 py-1.5 font-semibold leading-relaxed">
              {successMsg}
            </div>
          )}
        </div>

        {/* Action Buttons Row */}
        <div className="space-y-2 shrink-0">
          <div className="grid grid-cols-2 gap-2">
            <button
              id="trade-buy-button"
              type="button"
              disabled={isSubmitting}
              onClick={() => handleTrade("buy")}
              className="h-9 w-full flex items-center justify-center space-x-1.5 rounded bg-purple-secondary text-white hover:bg-opacity-90 font-bold text-xs tracking-wider uppercase disabled:opacity-50 transition-all cursor-pointer shadow-[0_0_8px_rgba(117,57,145,0.4)]"
            >
              <ShoppingBag className="w-3.5 h-3.5" />
              <span>BUY</span>
            </button>
            <button
              id="trade-sell-button"
              type="button"
              disabled={isSubmitting}
              onClick={() => handleTrade("sell")}
              className="h-9 w-full flex items-center justify-center space-x-1.5 rounded border border-purple-secondary text-purple-300 hover:bg-purple-secondary/15 font-bold text-xs tracking-wider uppercase disabled:opacity-50 transition-all cursor-pointer"
            >
              <ShoppingBag className="w-3.5 h-3.5" />
              <span>SELL</span>
            </button>
          </div>

          {/* Sell All shortcut */}
          <button
            id="trade-sell-all-button"
            type="button"
            disabled={isSubmitting || currentHolding <= 0}
            onClick={handleSellAll}
            className="h-8 w-full flex items-center justify-center space-x-1.5 rounded border border-gray-700 bg-[#0d1117] text-gray-400 hover:text-red-400 hover:border-red-900/40 hover:bg-red-950/10 font-bold text-[10px] tracking-wider uppercase transition-all disabled:opacity-30 disabled:hover:text-gray-400 disabled:hover:border-gray-700 disabled:hover:bg-[#0d1117] cursor-pointer col-span-2"
          >
            <Trash className="w-3 h-3" />
            <span>LIQUIDATE ALL ({currentHolding} {ticker.toUpperCase()})</span>
          </button>
        </div>
      </div>
    </div>
  );
}
