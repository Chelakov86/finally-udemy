"use client";

import React from "react";
import { formatCents, formatPercent, formatQuantity } from "@/utils/formatter";
import { Briefcase } from "lucide-react";

export interface PositionRow {
  ticker: string;
  quantity: number;
  avg_cost: string; // db decimal string
  avg_cost_float: number;
  current_price: number | null;
  unrealized_p_l: number | null;
  unrealized_p_l_cents: number | null; // cents-based authoritative
  unrealized_p_l_percent: number | null;
  total_value: number | null;
  total_value_cents: number | null; // cents-based authoritative
  updated_at: string;
}

interface PositionsTableProps {
  positions: PositionRow[];
  onSelectTicker: (ticker: string) => void;
  activeTicker: string;
}

export default function PositionsTable({ positions, onSelectTicker, activeTicker }: PositionsTableProps) {
  // Total valuation metrics calculated cleanly in cents
  const activePositions = positions.filter((p) => p.quantity > 0);

  const totalValueCents = activePositions.reduce((sum, pos) => sum + (pos.total_value_cents || 0), 0);
  const totalPnLCents = activePositions.reduce((sum, pos) => sum + (pos.unrealized_p_l_cents || 0), 0);
  
  // Calculate average cost cents to get total cost basis cents
  const totalCostBasisCents = totalValueCents - totalPnLCents;
  const totalPnLPercent = totalCostBasisCents > 0 ? (totalPnLCents / totalCostBasisCents) * 100 : 0;

  return (
    <div className="flex flex-col h-full bg-[#161b22] border border-border-custom rounded-lg overflow-hidden select-none">
      {/* Panel Header */}
      <div className="flex min-h-11 shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border-custom bg-[#0d1117]/80 px-3 py-2 sm:flex-nowrap sm:px-4">
        <div className="flex min-w-0 items-center space-x-2">
          <Briefcase className="w-4 h-4 text-blue-primary" />
          <h2 className="truncate text-xs font-bold tracking-wider text-gray-300 uppercase">
            HOLDINGS
          </h2>
        </div>
        <span className="hidden font-mono text-[9px] text-gray-500 tracking-wider 2xl:inline">
          CENTS-BASED AUTHORITATIVE CALCULATIONS
        </span>
      </div>

      {/* Positions Table Body */}
      <div className="flex-1 overflow-auto">
        <table className="w-full min-w-[760px] text-left border-collapse">
          <thead>
            <tr className="border-b border-border-custom bg-[#0d1117]/40 text-[9px] font-bold tracking-widest text-gray-500 uppercase">
              <th className="py-2 pl-4">SYMBOL</th>
              <th className="py-2 text-right">QUANTITY</th>
              <th className="py-2 text-right">AVG COST</th>
              <th className="py-2 text-right">CURRENT PRICE</th>
              <th className="py-2 text-right">MARKET VALUE</th>
              <th className="py-2 text-right">UNREALIZED P&L</th>
              <th className="py-2 pr-4 text-right">CHG %</th>
            </tr>
          </thead>
          <tbody>
            {activePositions.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-xs text-gray-600">
                  NO ACTIVE POSITIONS HELD
                </td>
              </tr>
            ) : (
              activePositions.map((pos) => {
                const isActive = pos.ticker === activeTicker;
                const pnlCents = pos.unrealized_p_l_cents || 0;
                const pnlColor = pnlCents > 0 ? "text-[#2ea043]" : pnlCents < 0 ? "text-[#f85149]" : "text-gray-400";
                
                const avgCostCents = Math.round(pos.avg_cost_float * 100);
                const curPriceCents = pos.current_price ? Math.round(pos.current_price * 100) : null;

                return (
                  <tr
                    key={pos.ticker}
                    id={`positions-row-${pos.ticker}`}
                    onClick={() => onSelectTicker(pos.ticker)}
                    className={`group border-b border-border-custom/50 hover:bg-[#0d1117]/40 cursor-pointer transition-colors ${
                      isActive ? "bg-blue-primary/5 border-l-2 border-l-blue-primary" : ""
                    }`}
                  >
                    {/* Ticker Symbol */}
                    <td className="py-2.5 pl-4">
                      <span className="font-mono text-[11px] font-bold text-[#f0f3f6] group-hover:text-accent-yellow">
                        {pos.ticker}
                      </span>
                    </td>

                    {/* Quantity shares formatted */}
                    <td className="py-2.5 text-right font-mono text-[11px] text-gray-300">
                      {formatQuantity(pos.quantity)}
                    </td>

                    {/* Avg Cost Cents formatted */}
                    <td className="py-2.5 text-right font-mono text-[11px] text-gray-300">
                      {formatCents(avgCostCents)}
                    </td>

                    {/* Current Price Cents formatted */}
                    <td className="py-2.5 text-right font-mono text-[11px] font-bold text-white">
                      {curPriceCents !== null ? formatCents(curPriceCents) : "STALE"}
                    </td>

                    {/* Market Value Cents formatted */}
                    <td className="py-2.5 text-right font-mono text-[11px] font-bold text-[#f0f3f6]">
                      {formatCents(pos.total_value_cents)}
                    </td>

                    {/* Unrealized P&L Cents formatted */}
                    <td className={`py-2.5 text-right font-mono text-[11px] font-bold ${pnlColor}`}>
                      {formatCents(pnlCents)}
                    </td>

                    {/* Unrealized change percent */}
                    <td className={`py-2.5 pr-4 text-right font-mono text-[10px] font-bold ${pnlColor}`}>
                      {formatPercent(pos.unrealized_p_l_percent)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Aggregate Valuation Footer (Always visible) */}
      {activePositions.length > 0 && (
        <div className="min-h-10 border-t border-border-custom bg-[#0d1117]/70 flex flex-col gap-2 px-4 py-2 text-xs select-none shrink-0 font-semibold sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <span className="text-gray-400 tracking-wider">TOTAL PORTFOLIO HOLDINGS</span>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
            <div className="flex items-center space-x-1.5">
              <span className="text-[10px] text-gray-400 font-medium">TOTAL VALUE:</span>
              <span className="font-mono text-white text-sm font-bold">{formatCents(totalValueCents)}</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="text-[10px] text-gray-400 font-medium">TOTAL P&L:</span>
              <span
                className={`font-mono text-sm font-bold ${
                  totalPnLCents > 0 ? "text-[#2ea043]" : totalPnLCents < 0 ? "text-[#f85149]" : "text-gray-400"
                }`}
              >
                {formatCents(totalPnLCents)} ({formatPercent(totalPnLPercent)})
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
