"use client";

import React from "react";
import { formatCents } from "@/utils/formatter";
import { Wifi, WifiOff, RefreshCw, BarChart2 } from "lucide-react";

interface HeaderProps {
  portfolioValueCents: number;
  cashBalanceCents: number;
  sseStatus: "connected" | "reconnecting" | "disconnected";
  isMarketPrices: boolean; // True if using Massive (Polygon), false if Simulated
}

export default function Header({
  portfolioValueCents,
  cashBalanceCents,
  sseStatus,
  isMarketPrices,
}: HeaderProps) {
  // Determine color and text for connection status
  const statusColor = {
    connected: "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.7)]",
    reconnecting: "bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.7)] animate-pulse",
    disconnected: "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.7)]",
  }[sseStatus];

  const statusLabel = {
    connected: "CONNECTED",
    reconnecting: "RECONNECTING",
    disconnected: "DISCONNECTED",
  }[sseStatus];

  const statusIcon = {
    connected: <Wifi className="w-4 h-4 text-green-500" />,
    reconnecting: <RefreshCw className="w-4 h-4 text-yellow-500 animate-spin" />,
    disconnected: <WifiOff className="w-4 h-4 text-red-500" />,
  }[sseStatus];

  return (
    <header className="flex h-14 items-center justify-between border-b border-border-custom bg-[#0b0e14] px-6 select-none shrink-0">
      {/* Workstation Title */}
      <div className="flex items-center space-x-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-primary text-black">
          <BarChart2 className="w-5 h-5 text-[#0d1117]" />
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-widest text-[#f0f3f6]">
            FIN<span className="text-accent-yellow">ALLY</span>
          </h1>
          <p className="text-[10px] tracking-wider text-gray-500 uppercase">
            Trading Workstation v1.0
          </p>
        </div>
      </div>

      {/* Main Portfolio Metrics */}
      <div className="flex items-center space-x-8">
        <div className="flex flex-col text-right">
          <span className="text-[10px] tracking-wider text-gray-400 font-medium">
            PORTFOLIO VALUE
          </span>
          <span className="font-mono text-lg font-bold text-accent-yellow transition-all duration-300">
            {formatCents(portfolioValueCents)}
          </span>
        </div>

        <div className="flex flex-col text-right">
          <span className="text-[10px] tracking-wider text-gray-400 font-medium">
            CASH BALANCE
          </span>
          <span className="font-mono text-base font-semibold text-[#f0f3f6]">
            {formatCents(cashBalanceCents)}
          </span>
        </div>
      </div>

      {/* Connection & Pricing Info */}
      <div className="flex items-center space-x-6">
        {/* Price Feed Mode badge */}
        <div className="flex flex-col items-end">
          <span className="text-[9px] tracking-wider text-gray-500 font-semibold uppercase">
            PRICE SOURCE
          </span>
          <span
            id="price-source-label"
            className={`mt-0.5 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
              isMarketPrices
                ? "bg-purple-secondary/20 text-purple-400 border border-purple-900/50"
                : "bg-blue-primary/10 text-blue-primary border border-blue-900/30"
            }`}
          >
            {isMarketPrices ? "Market Prices" : "Simulated Live Prices"}
          </span>
        </div>

        {/* Live SSE Status Dot */}
        <div className="flex items-center space-x-2 border-l border-border-custom pl-6">
          <div className="flex items-center space-x-2.5 rounded-full bg-[#161b22] px-3 py-1 border border-border-custom">
            {statusIcon}
            <span className="font-mono text-[10px] font-bold text-[#f0f3f6] tracking-wider">
              {statusLabel}
            </span>
            <span
              id="sse-status-dot"
              className={`h-2.5 w-2.5 rounded-full ${statusColor}`}
            />
          </div>
        </div>
      </div>
    </header>
  );
}
