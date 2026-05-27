"use client";

import React, { useEffect, useRef } from "react";
import { createChart, ColorType, ISeriesApi, UTCTimestamp, AreaSeries } from "lightweight-charts";
import { AreaChart } from "lucide-react";

interface ChartTick {
  timestamp: number; // Unix timestamp
  price: number;
}

interface MainChartProps {
  ticker: string;
  ticks: ChartTick[];
}

export default function MainChart({ ticker, ticks }: MainChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create the lightweight chart instance
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#161b22" },
        textColor: "#8b949e",
        fontFamily: "var(--font-mono), monospace",
      },
      grid: {
        vertLines: { color: "#21262d" },
        horzLines: { color: "#21262d" },
      },
      crosshair: {
        mode: 1, // Magnet mode
        vertLine: {
          color: "#ecad0a",
          labelBackgroundColor: "#ecad0a",
        },
        horzLine: {
          color: "#ecad0a",
          labelBackgroundColor: "#ecad0a",
        },
      },
      rightPriceScale: {
        borderColor: "#30363d",
        visible: true,
      },
      timeScale: {
        borderColor: "#30363d",
        timeVisible: true,
        secondsVisible: true,
      },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight || 300,
    });

    // Add Area Series for premium styling
    const areaSeries = chart.addSeries(AreaSeries, {
      lineColor: "#209dd7",
      topColor: "rgba(32, 157, 215, 0.4)",
      bottomColor: "rgba(32, 157, 215, 0.0)",
      lineWidth: 2,
      priceFormat: {
        type: "price",
        precision: 2,
        minMove: 0.01,
      },
    });

    chartRef.current = chart;
    seriesRef.current = areaSeries;

    // Handle container resizing
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };

    window.addEventListener("resize", handleResize);

    // Clean up on component unmount
    return () => {
      window.removeEventListener("resize", handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
      }
    };
  }, []);

  // Update chart data whenever ticks or active ticker changes
  useEffect(() => {
    if (!seriesRef.current || !chartRef.current || ticks.length === 0) return;

    // Format and sort prices
    const chartData = ticks
      .map((tick) => ({
        time: tick.timestamp as UTCTimestamp,
        value: tick.price,
      }))
      // Ensure strictly increasing times to avoid lightweight-charts rendering exception
      .filter((value, index, self) => self.findIndex((t) => t.time === value.time) === index)
      .sort((a, b) => a.time - b.time);

    seriesRef.current.setData(chartData);

    // Fit time scale to show all points
    chartRef.current.timeScale().fitContent();
  }, [ticks, ticker]);

  return (
    <div className="flex flex-col h-full bg-[#161b22] border border-border-custom rounded-lg overflow-hidden relative">
      {/* Chart Panel Header */}
      <div className="flex h-11 items-center justify-between border-b border-border-custom bg-[#0d1117]/80 px-4 shrink-0">
        <div className="flex items-center space-x-2">
          <AreaChart className="w-4 h-4 text-blue-primary" />
          <h2 className="text-xs font-bold tracking-wider text-gray-300 uppercase">
            ACTIVE CHART: <span className="text-accent-yellow font-mono text-sm">{ticker}</span>
          </h2>
        </div>
        <span className="font-mono text-[9px] text-gray-500 tracking-wider">
          LIVE GBM SIMULATOR OR MASSIVE AGGREGATES
        </span>
      </div>

      {/* Chart DOM Container */}
      <div
        id={`main-price-chart-${ticker}`}
        ref={chartContainerRef}
        className="flex-1 w-full"
        style={{ minHeight: "150px" }}
      />
    </div>
  );
}
