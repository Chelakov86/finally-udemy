import { test, expect } from '@playwright/test';

// Setup EventSource spy in browser to control SSE connection transitions
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    const OriginalEventSource = window.EventSource;
    window.EventSource = class MockEventSource extends OriginalEventSource {
      constructor(url: string, eventSourceInitDict?: EventSourceInit) {
        super(url, eventSourceInitDict);
        (window as any).activeEventSource = this;
      }
    } as any;
  });
});

test.beforeAll(async ({ request }) => {
  const BASE_URL = process.env.BASE_URL || process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:8000';
  console.log(`Setting up database state at ${BASE_URL}...`);

  // Liquidate all holdings to restore cash to exactly $10,000.00
  try {
    const portfolioRes = await request.get(`${BASE_URL}/api/portfolio`);
    if (portfolioRes.ok()) {
      const data = await portfolioRes.json();
      const positions = data.positions || [];
      for (const pos of positions) {
        if (pos.quantity > 0) {
          await request.post(`${BASE_URL}/api/portfolio/trade`, {
            data: {
              ticker: pos.ticker,
              side: 'sell',
              quantity: pos.quantity,
              source: 'manual'
            }
          });
        }
      }
    }
  } catch (e) {
    console.error('Failed to liquidate positions in beforeAll:', e);
  }

  // Restore watchlist to exactly the 10 default tickers
  try {
    const defaultTickers = new Set(["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]);
    const watchlistRes = await request.get(`${BASE_URL}/api/watchlist`);
    if (watchlistRes.ok()) {
      const watchlist = await watchlistRes.json();
      for (const item of watchlist) {
        if (!defaultTickers.has(item.ticker)) {
          await request.delete(`${BASE_URL}/api/watchlist/${item.ticker}`);
        }
      }
      for (const ticker of defaultTickers) {
        const found = watchlist.some((item: any) => item.ticker === ticker);
        if (!found) {
          await request.post(`${BASE_URL}/api/watchlist`, {
            data: { ticker }
          });
        }
      }
    }
  } catch (e) {
    console.error('Failed to restore default watchlist in beforeAll:', e);
  }
});

test.describe('FinAlly AI Trading Workstation E2E Tests', () => {

  test('Dashboard fresh launch displays default state correctly', async ({ page }) => {
    await page.goto('/');

    // 1. Verify Cash Balance shows $10,000.00
    const cashLocator = page.locator('header').getByText('$10,000.00');
    await expect(cashLocator).toBeVisible();

    // 2. Verify all 10 default tickers are present in the watchlist
    const defaultTickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"];
    for (const ticker of defaultTickers) {
      const row = page.locator(`#watchlist-row-${ticker}`);
      await expect(row).toBeVisible();
    }

    // 3. Verify healthy SSE streaming connection dot showing CONNECTED (green)
    const sseDot = page.locator('#sse-status-dot');
    await expect(sseDot).toBeVisible();
    await expect(sseDot).toHaveClass(/bg-green-500/);

    const sseText = page.locator('header').getByText('CONNECTED');
    await expect(sseText).toBeVisible();
  });

  test('Watchlist CRUD: additions and deletions work successfully', async ({ page }) => {
    await page.goto('/');

    // Ensure initial PLTR is not there
    await expect(page.locator('#watchlist-row-PLTR')).not.toBeVisible();

    // 1. Add valid ticker PLTR
    await page.fill('#watchlist-add-input', 'PLTR');
    await page.click('#watchlist-add-submit');

    // Verify PLTR row appears in the watchlist table
    const pltrRow = page.locator('#watchlist-row-PLTR');
    await expect(pltrRow).toBeVisible();

    // 2. Delete ticker PLTR
    // Hover the PLTR row to make the trash button visible
    await pltrRow.hover();
    
    // Click the delete icon
    const deleteButton = page.locator('#watchlist-delete-PLTR');
    await expect(deleteButton).toBeVisible();
    await deleteButton.click();

    // Verify PLTR row is removed from the panel
    await expect(pltrRow).not.toBeVisible();
  });

  test('Manual trade ticket: buying, selling, and liquidating positions', async ({ page }) => {
    await page.goto('/');

    // 1. Execute a purchase: 10 shares of AAPL
    await page.fill('#trade-ticker-input', 'AAPL');
    await page.click('#trade-mode-shares');
    await page.fill('#trade-quantity-input', '10');
    
    // Click BUY
    await page.click('#trade-buy-button');

    // Verify success feedback message
    await expect(page.locator('#trade-success-message')).toBeVisible();
    await expect(page.locator('#trade-success-message')).toContainText(/Successfully executed order/i);

    // Verify positions table has AAPL
    const aaplPosRow = page.locator('#positions-row-AAPL');
    await expect(aaplPosRow).toBeVisible();
    await expect(aaplPosRow).toContainText('10.00'); // 10 shares

    // Verify cash decreased from $10,000.00
    const cashText = await page.locator('header').getByText('$').nth(1).textContent();
    const cashVal = parseFloat(cashText?.replace(/[^0-9.]/g, '') || '10000');
    expect(cashVal).toBeLessThan(10000);

    // 2. Execute a sale: sell 4 shares of AAPL
    await page.fill('#trade-quantity-input', '4');
    await page.click('#trade-sell-button');

    // Verify success feedback message
    await expect(page.locator('#trade-success-message')).toBeVisible();

    // Verify positions table shows remaining 6 shares
    await expect(aaplPosRow).toContainText('6.00');

    // 3. Liquidate All AAPL position
    const liquidateButton = page.locator('#trade-sell-all-button');
    await expect(liquidateButton).toBeVisible();
    await expect(liquidateButton).toBeEnabled();
    await liquidateButton.click();

    // Verify positions table is now empty of AAPL row
    await expect(aaplPosRow).not.toBeVisible();
  });

  test('AI Assistant: Chat, Intent Gating, and Cache Execution', async ({ page }) => {
    await page.goto('/');

    // 1. Send query asking for analysis (intent classified as analysis)
    await page.fill('#chat-input-field', 'what do you think of AAPL?');
    await page.click('#chat-send-submit');

    // Wait for the thinking indicator to disappear and the assistant response to appear
    await expect(page.locator('#chat-thinking-indicator')).not.toBeVisible({ timeout: 10000 });
    
    // Verify analysis recommendations card appears (PROPOSED AI TRADE ACTION)
    const proposedActionCard = page.locator('text=PROPOSED AI TRADE ACTION');
    await expect(proposedActionCard).toBeVisible();

    // Verify no trade executed automatically (positions table remains empty for AAPL)
    await expect(page.locator('#positions-row-AAPL')).not.toBeVisible();

    // 2. Send direct trade execution command (intent classified as execution)
    // First clear chat input
    await page.fill('#chat-input-field', 'buy AAPL');
    await page.click('#chat-send-submit');

    await expect(page.locator('#chat-thinking-indicator')).not.toBeVisible({ timeout: 10000 });

    // Verify direct execution intent applies and trade executes automatically
    const aaplPosRow = page.locator('#positions-row-AAPL');
    await expect(aaplPosRow).toBeVisible();

    // Liquidate the position manually using UI to clean up for next step
    await page.click('#positions-row-AAPL');
    await page.click('#trade-sell-all-button');
    await expect(aaplPosRow).not.toBeVisible();

    // 3. Confirm target recommended action card using confirmation button ("YES, DO IT")
    // Trigger analysis again
    await page.fill('#chat-input-field', 'what do you think of AAPL?');
    await page.click('#chat-send-submit');
    await expect(page.locator('#chat-thinking-indicator')).not.toBeVisible({ timeout: 10000 });
    await expect(proposedActionCard).toBeVisible();

    // Click on the proposed action confirmation card button
    const confirmButton = page.locator('button:has-text("CONFIRM: \\"YES, DO IT\\"")');
    await expect(confirmButton).toBeVisible();
    await confirmButton.click();

    // Verify that the trade successfully executed from PendingActionsCache
    await expect(page.locator('#chat-thinking-indicator')).not.toBeVisible({ timeout: 10000 });
    await expect(aaplPosRow).toBeVisible();
  });

  test('SSE Connection Resilience transitions status indicators gracefully', async ({ page }) => {
    await page.goto('/');

    const sseDot = page.locator('#sse-status-dot');
    const sseText = page.locator('header').getByText('CONNECTED');

    // 1. Initially green/CONNECTED
    await expect(sseDot).toHaveClass(/bg-green-500/);
    await expect(sseText).toBeVisible();

    // 2. Trigger EventSource error to mock network drop
    await page.evaluate(() => {
      const activeES = (window as any).activeEventSource;
      if (activeES) {
        const errEvent = new Event('error');
        activeES.dispatchEvent(errEvent);
      }
    });

    // Verify status changes to DISCONNECTED (red)
    await expect(sseDot).toHaveClass(/bg-red-500/);
    const disconnectedText = page.locator('header').getByText('DISCONNECTED');
    await expect(disconnectedText).toBeVisible();

    // 3. Verify transition to RECONNECTING (yellow) within 3.5 seconds
    // Reconnect timeout is 3000ms
    await expect(sseDot).toHaveClass(/bg-yellow-500/, { timeout: 4500 });
    const reconnectingText = page.locator('header').getByText('RECONNECTING');
    await expect(reconnectingText).toBeVisible();

    // 4. Verify auto-restoration back to CONNECTED (green)
    await expect(sseDot).toHaveClass(/bg-green-500/, { timeout: 5000 });
    await expect(sseText).toBeVisible();
  });

});
