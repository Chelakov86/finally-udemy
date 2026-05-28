/**
 * Cents-based monetary and data formatting utility for FinAlly Workstation.
 * Prevents client-side floating point rounding errors.
 */

/**
 * Formats a cents integer into a dollar currency string.
 * e.g., 123456 -> "$1,234.56", -500 -> "-$5.00"
 */
export function formatCents(cents: number | null | undefined): string {
  if (cents === null || cents === undefined || isNaN(cents)) return "N/A";
  const isNegative = cents < 0;
  const absCents = Math.abs(cents);
  const dollars = Math.floor(absCents / 100);
  const centsPart = absCents % 100;
  const centsString = centsPart.toString().padStart(2, "0");
  const formattedDollars = dollars.toLocaleString("en-US");
  
  return `${isNegative ? "-" : ""}$${formattedDollars}.${centsString}`;
}

/**
 * Converts a float dollar value to a cents integer cleanly.
 * e.g., 12.34 -> 1234
 */
export function dollarsToCents(dollars: number | null | undefined): number {
  if (dollars === null || dollars === undefined || isNaN(dollars)) return 0;
  return Math.round(dollars * 100);
}

/**
 * Formats standard percentages with sign and specified decimal points.
 * e.g., 2.3456 -> "+2.35%", -0.01 -> "-0.01%"
 */
export function formatPercent(percent: number | null | undefined, decimals = 2): string {
  if (percent === null || percent === undefined || isNaN(percent)) return "0.00%";
  const sign = percent > 0 ? "+" : "";
  return `${sign}${percent.toFixed(decimals)}%`;
}

/**
 * Formats trade share quantity beautifully.
 * e.g., 120.450000 -> "120.45", 10 -> "10"
 */
export function formatQuantity(qty: number | null | undefined, maxDecimals = 6): string {
  if (qty === null || qty === undefined || isNaN(qty)) return "0";
  return parseFloat(qty.toFixed(maxDecimals)).toString();
}
