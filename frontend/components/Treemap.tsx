"use client";

import React, { useEffect, useRef, useState } from "react";
import { formatPercent } from "@/utils/formatter";
import { Layers } from "lucide-react";

export interface TreemapPosition {
  ticker: string;
  quantity: number;
  avg_cost_float: number;
  current_price: number | null;
  total_value: number | null;
  unrealized_p_l: number | null;
  unrealized_p_l_percent: number | null;
}

interface TreemapProps {
  positions: TreemapPosition[];
}

interface TreemapItem {
  ticker: string;
  value: number; // Total value of position
  unrealizedPnLPercent: number;
}

interface TreemapNode {
  ticker: string;
  x: number;
  y: number;
  width: number;
  height: number;
  value: number;
  unrealizedPnLPercent: number;
}

// Slice-and-Dice Responsive Subdivision Treemap Algorithm
function computeTreemap(
  items: TreemapItem[],
  x: number,
  y: number,
  width: number,
  height: number
): TreemapNode[] {
  if (items.length === 0) return [];
  if (items.length === 1) {
    return [
      {
        ticker: items[0].ticker,
        x,
        y,
        width,
        height,
        value: items[0].value,
        unrealizedPnLPercent: items[0].unrealizedPnLPercent,
      },
    ];
  }

  // Calculate total value of items in group
  const total = items.reduce((sum, item) => sum + item.value, 0);

  // Find partition split index to split total value near 50/50
  let accumulated = 0;
  let splitIndex = 1;

  for (let i = 0; i < items.length - 1; i++) {
    accumulated += items[i].value;
    if (accumulated >= total / 2) {
      splitIndex = i + 1;
      break;
    }
  }

  const leftItems = items.slice(0, splitIndex);
  const rightItems = items.slice(splitIndex);

  const leftValue = leftItems.reduce((sum, item) => sum + item.value, 0);
  const leftRatio = leftValue / total;

  const result: TreemapNode[] = [];

  if (width > height) {
    // Horizontal split (draw vertical boundary)
    const leftWidth = width * leftRatio;
    result.push(...computeTreemap(leftItems, x, y, leftWidth, height));
    result.push(...computeTreemap(rightItems, x + leftWidth, y, width - leftWidth, height));
  } else {
    // Vertical split (draw horizontal boundary)
    const leftHeight = height * leftRatio;
    result.push(...computeTreemap(leftItems, x, y, width, leftHeight));
    result.push(...computeTreemap(rightItems, x, y + leftHeight, width, height - leftHeight));
  }

  return result;
}

export default function Treemap({ positions }: TreemapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 400, height: 250 });

  // Update SVG dimensions on window resize or panel mount
  useEffect(() => {
    if (!containerRef.current) return;

    const measure = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight - 44, // Subtract header height
        });
      }
    };

    measure();
    window.addEventListener("resize", measure);

    // Setup a ResizeObserver for more robust containment resizing
    const observer = new ResizeObserver(measure);
    observer.observe(containerRef.current);

    return () => {
      window.removeEventListener("resize", measure);
      observer.disconnect();
    };
  }, []);

  // Filter positions to active, valued positions sorted descending
  const items: TreemapItem[] = positions
    .filter((pos) => pos.quantity > 0 && pos.total_value !== null && pos.total_value > 0)
    .map((pos) => ({
      ticker: pos.ticker,
      value: pos.total_value || 0,
      unrealizedPnLPercent: pos.unrealized_p_l_percent || 0,
    }))
    .sort((a, b) => b.value - a.value);

  const totalValue = items.reduce((sum, item) => sum + item.value, 0);

  // Compute layout blocks
  const nodes = computeTreemap(items, 0, 0, dimensions.width, dimensions.height);

  return (
    <div
      ref={containerRef}
      className="flex flex-col h-full bg-[#161b22] border border-border-custom rounded-lg overflow-hidden select-none"
    >
      {/* Panel Header */}
      <div className="flex min-h-11 shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border-custom bg-[#0d1117]/80 px-3 py-2 sm:flex-nowrap sm:px-4">
        <div className="flex min-w-0 items-center space-x-2">
          <Layers className="w-4 h-4 text-blue-primary" />
          <h2 className="truncate text-xs font-bold tracking-wider text-gray-300 uppercase">
            HEATMAP
          </h2>
        </div>
        <span className="hidden font-mono text-[9px] text-gray-500 tracking-wider 2xl:inline">
          UNREALIZED P&L COLOR SCALE
        </span>
      </div>

      {/* SVG Canvas Container */}
      <div className="flex-1 w-full relative bg-[#0d1117]/40 min-h-[120px]">
        {items.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-gray-600 uppercase tracking-wider">
            NO ACTIVE LONG POSITIONS TO RENDER
          </div>
        ) : (
          <svg
            id="portfolio-heatmap-treemap"
            width={dimensions.width}
            height={dimensions.height}
            className="overflow-hidden"
          >
            {nodes.map((node) => {
              const weight = totalValue > 0 ? (node.value / totalValue) * 100 : 0;
              const pnl = node.unrealizedPnLPercent;

              // Generate color based on profit/loss opacity
              let fill = "#21262d"; // default gray

              if (pnl > 0) {
                // Profit: Green glow scale
                const opacity = Math.min(0.9, 0.2 + pnl / 10); // Fully opaque at +7%
                fill = `rgba(46, 160, 67, ${opacity})`;
              } else if (pnl < 0) {
                // Loss: Red glow scale
                const opacity = Math.min(0.9, 0.2 + Math.abs(pnl) / 10); // Fully opaque at -7%
                fill = `rgba(248, 81, 73, ${opacity})`;
              }

              // Hide details if block is tiny to prevent text crowding
              const showText = node.width > 42 && node.height > 28;
              const showSubText = node.width > 56 && node.height > 44;

              return (
                <g key={node.ticker} className="cursor-pointer group">
                  {/* Heatmap Rect */}
                  <rect
                    x={node.x}
                    y={node.y}
                    width={node.width}
                    height={node.height}
                    fill={fill}
                    stroke="#0d1117"
                    strokeWidth="1.5"
                    className="transition-all duration-300 group-hover:stroke-accent-yellow"
                  />

                  {/* Node content labels */}
                  {showText && (
                    <text
                      x={node.x + node.width / 2}
                      y={node.y + node.height / 2 + (showSubText ? -5 : 4)}
                      textAnchor="middle"
                      className="font-sans text-[11px] font-bold fill-white select-none pointer-events-none uppercase tracking-wider"
                    >
                      {node.ticker}
                    </text>
                  )}

                  {showSubText && (
                    <text
                      x={node.x + node.width / 2}
                      y={node.y + node.height / 2 + 10}
                      textAnchor="middle"
                      className="font-mono text-[9px] font-semibold fill-gray-100 select-none pointer-events-none"
                    >
                      {formatPercent(pnl, 1)}
                    </text>
                  )}

                  {/* Standard SVG title hover tooltip fallback */}
                  <title>
                    {`${node.ticker}\nValue: $${node.value.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}\nWeight: ${weight.toFixed(1)}%\nP&L: ${formatPercent(pnl)}`}
                  </title>
                </g>
              );
            })}
          </svg>
        )}
      </div>
    </div>
  );
}
