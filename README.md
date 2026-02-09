# Automatic-trading-bot by keshav-005
It is a sophisticated algorithmic trading bot designed for MetaTrader that implements a multi-strategy approach with adaptive learning capabilities.

Core Functionality
Multi-Strategy System: Combines 6 different trading strategies with weighted voting

Risk Management: Implements position sizing based on 1% risk per trade and 5% maximum daily loss

Market Coverage: Trades major forex pairs, metals, commodities, and indices



Strategy Components
EMA Crossover (25% weight): Uses 9 and 21 period exponential moving averages

RSI Bounce (20% weight): Adaptive RSI thresholds based on volatility

MACD Trend (18% weight): MACD signals with volume confirmation

Bollinger Squeeze (15% weight): Identifies breakouts from low volatility periods

Volume Spike (12% weight): Detects unusual volume activity

News Sentiment (10% weight): Analyzes market sentiment from news sources



Advanced Features
ADX Confirmation: Requires strong trend confirmation before trading

Adaptive Learning: Automatically adjusts strategy weights based on performance

Session Filtering: Only trades EUR pairs during London session hours

Volatility Filter: Avoids low-volatility conditions



Data Integration
Uses both MT5 native data and free alternative data sources

Integrates Alpha Vantage for market data and NewsAPI for sentiment analysis

Implements fallback web scraping when API access is limited

This bot represents a comprehensive approach to algorithmic trading, combining technical analysis, sentiment analysis, and robust risk management in a single system.
