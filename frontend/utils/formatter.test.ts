import { formatCents, dollarsToCents, formatPercent, formatQuantity } from "./formatter";

describe("Cents-Based Formatter Utilities", () => {
  // 1. Cents format test
  test("formatCents should format integer cents into clean currency values", () => {
    expect(formatCents(1000000)).toBe("$10,000.00");
    expect(formatCents(123456)).toBe("$1,234.56");
    expect(formatCents(5)).toBe("$0.05");
    expect(formatCents(0)).toBe("$0.00");
    expect(formatCents(-500)).toBe("-$5.00");
    expect(formatCents(null)).toBe("N/A");
    expect(formatCents(undefined)).toBe("N/A");
  });

  // 2. Dollar to Cents representation test
  test("dollarsToCents should round dollar values to closest integer cents representation", () => {
    expect(dollarsToCents(12.34)).toBe(1234);
    expect(dollarsToCents(12.345)).toBe(1235); // rounding
    expect(dollarsToCents(0.05)).toBe(5);
    expect(dollarsToCents(-10.5)).toBe(-1050);
    expect(dollarsToCents(null)).toBe(0);
  });

  // 3. Percentage formats test
  test("formatPercent should attach correct arithmetic signs and decimal cutoffs", () => {
    expect(formatPercent(2.3456)).toBe("+2.35%");
    expect(formatPercent(0.011)).toBe("+0.01%");
    expect(formatPercent(-0.0123)).toBe("-0.01%");
    expect(formatPercent(0)).toBe("0.00%");
    expect(formatPercent(null)).toBe("0.00%");
  });

  // 4. Quantities formats test
  test("formatQuantity should render fractional values up to maximum decimals cleanly", () => {
    expect(formatQuantity(120.450000)).toBe("120.45");
    expect(formatQuantity(10.0)).toBe("10");
    expect(formatQuantity(0.000123)).toBe("0.000123");
    expect(formatQuantity(null)).toBe("0");
  });
});
