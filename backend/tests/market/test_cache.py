"""Tests for PriceCache."""

from concurrent.futures import ThreadPoolExecutor

from app.market.cache import PriceCache


class TestPriceCache:
    """Unit tests for the PriceCache."""

    def test_update_and_get(self):
        """Test updating and getting a price."""
        cache = PriceCache()
        update = cache.update("AAPL", 190.50)
        assert update.ticker == "AAPL"
        assert update.price == 190.50
        assert cache.get("AAPL") == update

    def test_first_update_is_flat(self):
        """Test that the first update has flat direction."""
        cache = PriceCache()
        update = cache.update("AAPL", 190.50)
        assert update.direction == "flat"
        assert update.previous_price == 190.50

    def test_direction_up(self):
        """Test price update with upward direction."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        update = cache.update("AAPL", 191.00)
        assert update.direction == "up"
        assert update.change == 1.00

    def test_direction_down(self):
        """Test price update with downward direction."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        update = cache.update("AAPL", 189.00)
        assert update.direction == "down"
        assert update.change == -1.00

    def test_remove(self):
        """Test removing a ticker from cache."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.remove("AAPL")
        assert cache.get("AAPL") is None
        assert cache.get_history("AAPL") == []

    def test_remove_nonexistent(self):
        """Test removing a ticker that doesn't exist."""
        cache = PriceCache()
        cache.remove("AAPL")  # Should not raise

    def test_get_all(self):
        """Test getting all prices."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.update("GOOGL", 175.00)
        all_prices = cache.get_all()
        assert set(all_prices.keys()) == {"AAPL", "GOOGL"}

    def test_get_history(self):
        """Test getting recent price history for a ticker."""
        cache = PriceCache()
        first = cache.update("AAPL", 190.00, timestamp=1.0)
        second = cache.update("AAPL", 191.00, timestamp=2.0)
        assert cache.get_history("AAPL") == [first, second]

    def test_get_history_unknown_ticker(self):
        """Test getting history for a ticker with no updates."""
        cache = PriceCache()
        assert cache.get_history("NOPE") == []

    def test_history_is_bounded(self):
        """Test that history keeps only the configured number of updates."""
        cache = PriceCache(history_size=2)
        cache.update("AAPL", 190.00)
        second = cache.update("AAPL", 191.00)
        third = cache.update("AAPL", 192.00)
        assert cache.get_history("AAPL") == [second, third]

    def test_get_all_history(self):
        """Test getting recent price history for all tickers."""
        cache = PriceCache()
        aapl = cache.update("AAPL", 190.00)
        googl = cache.update("GOOGL", 175.00)
        assert cache.get_all_history() == {"AAPL": [aapl], "GOOGL": [googl]}

    def test_invalid_history_size(self):
        """Test rejecting a non-positive history size."""
        try:
            PriceCache(history_size=0)
        except ValueError as exc:
            assert str(exc) == "history_size must be at least 1"
        else:
            raise AssertionError("Expected ValueError")

    def test_concurrent_updates_and_reads(self):
        """Test that concurrent readers and writers leave cache state consistent."""
        cache = PriceCache(history_size=10)
        tickers = [f"TICK{i}" for i in range(10)]

        def run_updates(ticker: str) -> None:
            for price in range(100):
                cache.update(ticker, float(price))
                cache.get(ticker)
                cache.get_history(ticker)

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(run_updates, tickers * 4))

        assert len(cache) == len(tickers)
        assert set(cache.get_all()) == set(tickers)
        for ticker in tickers:
            assert cache.get_price(ticker) == 99.0
            assert len(cache.get_history(ticker)) <= 10

    def test_version_increments(self):
        """Test that version counter increments."""
        cache = PriceCache()
        v0 = cache.version
        cache.update("AAPL", 190.00)
        assert cache.version == v0 + 1
        cache.update("AAPL", 191.00)
        assert cache.version == v0 + 2

    def test_get_price_convenience(self):
        """Test the convenience get_price method."""
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("NOPE") is None

    def test_len(self):
        """Test __len__ method."""
        cache = PriceCache()
        assert len(cache) == 0
        cache.update("AAPL", 190.00)
        assert len(cache) == 1
        cache.update("GOOGL", 175.00)
        assert len(cache) == 2

    def test_contains(self):
        """Test __contains__ method."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        assert "AAPL" in cache
        assert "GOOGL" not in cache

    def test_custom_timestamp(self):
        """Test updating with a custom timestamp."""
        cache = PriceCache()
        custom_ts = 1234567890.0
        update = cache.update("AAPL", 190.50, timestamp=custom_ts)
        assert update.timestamp == custom_ts

    def test_price_rounding(self):
        """Test that prices are rounded to 2 decimal places."""
        cache = PriceCache()
        update = cache.update("AAPL", 190.12345)
        assert update.price == 190.12
