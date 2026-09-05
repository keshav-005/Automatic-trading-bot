"""
Market Sentiment Analysis Module
Author: Computer Science Student Project

Financial news sentiment can provide an edge when combined with technical indicators.
Instead of requiring an expensive paid NewsAPI subscription (or scraping websites that
might block requests during an interview demo), we built a lightweight financial
lexicon analyzer that works completely offline.
"""

import re
from typing import List, Dict

class FinancialSentimentAnalyzer:
    """
    Keyword-based financial sentiment analyzer.
    Assigns positive scores to bullish financial headlines and negative scores
    to bearish ones.
    """
    
    # Financial keywords mapped to sentiment impact weights
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
        
        # Realistic sample headlines for offline demonstration across each symbol
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
            "USOIL":  [
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
        Scans a headline text and computes a normalized sentiment score between
        -1.0 (very bearish) and +1.0 (very bullish).
        """
        if not text:
            return 0.0
            
        # Clean text: lowercase and remove punctuation
        clean_text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
        
        score = 0.0
        match_count = 0
        
        # Check bullish words
        for phrase, weight in self.BULLISH_KEYWORDS.items():
            if phrase in clean_text:
                score += weight
                match_count += 1
                
        # Check bearish words
        for phrase, weight in self.BEARISH_KEYWORDS.items():
            if phrase in clean_text:
                score += weight
                match_count += 1
                
        # If no keywords matched, sentiment is neutral (0.0)
        if match_count == 0:
            return 0.0
            
        # Clamp score between -1.0 and +1.0
        normalized = max(-1.0, min(1.0, score / (match_count * 1.5)))
        return round(normalized, 3)

    def get_asset_sentiment(self, symbol: str) -> float:
        """
        Returns average sentiment for the given symbol.
        Uses cached domain headlines to ensure 100% offline reliability.
        """
        headlines = self.sample_headlines.get(symbol, ["Market demonstrating balanced liquidity conditions"])
        scores = [self.analyze_text(h) for h in headlines]
        return round(sum(scores) / max(1, len(scores)), 3)
