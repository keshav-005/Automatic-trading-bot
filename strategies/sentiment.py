"""
Financial sentiment scoring via financial domain keyword matching.

Works completely offline — no API keys required. The bundled headlines give each
symbol a stable baseline sentiment that feeds into the ensemble as a light bias
signal. Replace with a live news feed by overriding get_asset_sentiment().
"""

import re
from typing import List, Dict


class FinancialSentimentAnalyzer:
    """Scores text against a curated financial keyword lexicon."""

    BULLISH_KEYWORDS = {
        'surge': 1.5, 'rally': 1.6, 'breakout': 1.4, 'gains': 1.2, 'bullish': 1.8,
        'outperform': 1.5, 'record high': 2.0, 'growth': 1.1, 'uptrend': 1.4,
        'profit': 1.2, 'boost': 1.2, 'upgrade': 1.5, 'recovery': 1.3, 'strong': 1.1,
        'positive': 1.0, 'expansion': 1.2, 'dovish': 1.2, 'rate cut': 1.4
    }

    BEARISH_KEYWORDS = {
        'plunge': -1.6, 'crash': -2.0, 'slump': -1.4, 'selloff': -1.6, 'bearish': -1.8,
        'underperform': -1.5, 'record low': -2.0, 'recession': -1.8, 'downtrend': -1.4,
        'loss': -1.2, 'drop': -1.2, 'downgrade': -1.5, 'inflation': -1.0, 'weak': -1.1,
        'negative': -1.0, 'contraction': -1.3, 'hawkish': -1.1, 'rate hike': -1.2
    }

    def __init__(self, news_api_key: str = ""):
        self.news_api_key = news_api_key

        # Bundled sample headlines used when no live feed is connected
        self.sample_headlines = {
            "EURUSD": [
                "ECB signals steady monetary policy amid gradual eurozone economic recovery",
                "Euro edges higher against dollar on resilient European trade data"
            ],
            "GBPUSD": [
                "Bank of England maintains cautious stance following inflation report",
                "Sterling consolidates near technical resistance against US dollar"
            ],
            "USDJPY": [
                "Bank of Japan reaffirms accommodative framework as sovereign yields stabilize",
                "Yen steady against dollar amid balanced currency market sentiment"
            ],
            "USDCAD": [
                "Oil market firmness lends strong support to Canadian Dollar",
                "US Dollar index cools slightly as Treasury yields moderate"
            ],
            "XAUUSD": [
                "Gold maintains strong safe-haven demand near key technical resistance",
                "Precious metals see continuous institutional accumulation on inflation hedges"
            ],
            "XAGUSD": [
                "Silver follows gold higher with industrial demand providing support",
                "Metals complex shows solid foundation above recent swing lows"
            ],
            "USOIL": [
                "Crude oil prices find support from global supply discipline and tight inventories",
                "Energy futures steady ahead of weekly crude stockpiles release"
            ],
            "NAS100": [
                "Tech sector rallies as enterprise software earnings exceed expectations",
                "Nasdaq index extends weekly gains driven by strong semiconductor performance"
            ]
        }

    def analyze_text(self, text: str) -> float:
        """
        Scan headline text and return a normalized sentiment score in [-1.0, 1.0].
        Returns 0.0 if no financial keywords are found.
        """
        if not text:
            return 0.0

        clean_text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())

        score = 0.0
        match_count = 0

        for phrase, weight in self.BULLISH_KEYWORDS.items():
            if phrase in clean_text:
                score += weight
                match_count += 1

        for phrase, weight in self.BEARISH_KEYWORDS.items():
            if phrase in clean_text:
                score += weight
                match_count += 1

        if match_count == 0:
            return 0.0

        normalized = max(-1.0, min(1.0, score / (match_count * 1.5)))
        return round(normalized, 3)

    def get_asset_sentiment(self, symbol: str) -> float:
        """Average sentiment across all headlines for the given symbol."""
        headlines = self.sample_headlines.get(symbol, ["Market demonstrating balanced liquidity conditions"])
        scores = [self.analyze_text(h) for h in headlines]
        return round(sum(scores) / max(1, len(scores)), 3)
