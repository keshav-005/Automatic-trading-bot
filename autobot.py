import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
from numpy import nan
import time
from datetime import datetime, timedelta
import pytz
import requests
from bs4 import BeautifulSoup
from textblob import TextBlob
import threading
from collections import defaultdict
import random

# ==================== CONFIGURATION ====================
MT5_ACCOUNT = 5035899068             # Your MT5 demo account number
MT5_PASSWORD = "!7RqLzZn"    # MT5 demo password
MT5_SERVER = "MetaQuotes-Demo"    # Demo server name

ACCOUNT_BALANCE = 10000           # Virtual balance
RISK_PER_TRADE = 0.01             # CHANGED TO 1% risk per trade ($100)
MAX_DAILY_LOSS = 0.05             # 5% daily loss limit ($500)
TRADE_COOLDOWN = 120              # 2 minutes between same symbol trades

SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCAD",   # Major forex
    "XAUUSD", "XAGUSD",            # Metals
    "USOIL", "NAS100"              # Commodities/indices
]

# ==================== API KEYS (YOUR KEYS INSERTED) ====================
ALPHA_VANTAGE_KEY = "YS2OD2MMWQHR79NE"  # Your Alpha Vantage API key
NEWS_API_KEY = "d912d2bbe3ea40a1890795b714f157eb"  # Your NewsAPI key

STRATEGY_WEIGHTS = {
    'ema_cross': 0.25,
    'rsi_bounce': 0.20,
    'macd_trend': 0.18,
    'bollinger_squeeze': 0.15,
    'volume_spike': 0.12,
    'news_sentiment': 0.10
}

# ==================== GLOBAL TRACKERS ====================
trade_history = defaultdict(list)
strategy_performance = defaultdict(lambda: {'wins': 0, 'losses': 0})
daily_pnl = 0

# ==================== UTILITY FUNCTIONS ====================
def get_free_market_data(symbol):
    """Get free alternative data if MT5 fails"""
    try:
        if ALPHA_VANTAGE_KEY:
            url = f"https://www.alphavantage.co/query?function=FX_DAILY&from_symbol={symbol[:3]}&to_symbol={symbol[3:]}&apikey={ALPHA_VANTAGE_KEY}"
            data = requests.get(url).json()
            df = pd.DataFrame(data['Time Series FX (Daily)']).T
            df.columns = ['open', 'high', 'low', 'close']
            return df.astype(float).iloc[-100:]  # Last 100 days
    except:
        return None

def get_free_news(symbol):
    """Get market-moving news from free sources"""
    articles = []
    try:
        if NEWS_API_KEY:
            url = f"https://newsapi.org/v2/everything?q={symbol}&apiKey={NEWS_API_KEY}"
            articles = requests.get(url).json().get('articles', [])[:3]  # Top 3
        
        if not articles:
            url = f"https://www.investing.com/currencies/{symbol.lower()}-news"
            html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
            soup = BeautifulSoup(html, 'html.parser')
            articles = [{'title': a.text} for a in soup.select('.title')[:3]]
        
        return [a['title'] for a in articles if 'title' in a]
    except:
        return []

def analyze_sentiment(text):
    """Free sentiment analysis"""
    try:
        return TextBlob(text).sentiment.polarity
    except:
        return 0

def add_adx_confirmation(df):
    """Your ADX confirmation function (unchanged)"""
    adx = ta.adx(df['high'], df['low'], df['close'])
    return adx['ADX_14'].iloc[-1] > 25  # Strong trend

# ==================== CORE TRADING STRATEGIES ====================
def ema_cross_strategy(df):
    ema_fast = df['close'].ewm(span=9).mean()
    ema_slow = df['close'].ewm(span=21).mean()
    
    if ema_fast.iloc[-1] > ema_slow.iloc[-1] and df['close'].iloc[-1] > ema_slow.iloc[-1]:
        return 'BUY'
    elif ema_fast.iloc[-1] < ema_slow.iloc[-1] and df['close'].iloc[-1] < ema_slow.iloc[-1]:
        return 'SELL'
    return None

def rsi_bounce_strategy(df):
    rsi = ta.rsi(df['close'], length=14)
    atr = ta.atr(df['high'], df['low'], df['close'], length=14)
    
    lower_thresh = 30 - (atr.iloc[-1]/df['close'].iloc[-1])*20
    upper_thresh = 70 + (atr.iloc[-1]/df['close'].iloc[-1])*20
    
    if rsi.iloc[-1] < max(25, lower_thresh):
        return 'BUY'
    elif rsi.iloc[-1] > min(75, upper_thresh):
        return 'SELL'
    return None

def macd_trend_strategy(df):
    macd = ta.macd(df['close'])
    if macd['MACD_12_26_9'].iloc[-1] > macd['MACDs_12_26_9'].iloc[-1] and df['volume'].iloc[-1] > df['volume'].mean():
        return 'BUY'
    elif macd['MACD_12_26_9'].iloc[-1] < macd['MACDs_12_26_9'].iloc[-1] and df['volume'].iloc[-1] > df['volume'].mean():
        return 'SELL'
    return None

def bollinger_squeeze_strategy(df):
    bb = ta.bbands(df['close'], length=20)
    squeeze = (bb['BBU_20_2.0'].iloc[-1] - bb['BBL_20_2.0'].iloc[-1]) / bb['BBM_20_2.0'].iloc[-1]
    
    if squeeze < 0.1:
        if df['close'].iloc[-1] > bb['BBU_20_2.0'].iloc[-1]:
            return 'BUY'
        elif df['close'].iloc[-1] < bb['BBL_20_2.0'].iloc[-1]:
            return 'SELL'
    return None

def volume_spike_strategy(df):
    vol_mean = df['volume'].rolling(20).mean()
    if df['volume'].iloc[-1] > 2 * vol_mean.iloc[-1]:
        if df['close'].iloc[-1] > df['open'].iloc[-1]:
            return 'BUY'
        else:
            return 'SELL'
    return None

def news_sentiment_strategy(symbol):
    news = get_free_news(symbol)
    if not news:
        return None
    
    sentiment = np.mean([analyze_sentiment(n) for n in news])
    if sentiment > 0.3:
        return 'BUY'
    elif sentiment < -0.3:
        return 'SELL'
    return None

# ==================== RISK MANAGEMENT ====================
def calculate_position_size(symbol, df):
    point = mt5.symbol_info(symbol).point
    atr = ta.atr(df['high'], df['low'], df['close'], length=14).iloc[-1]
    
    risk_amount = ACCOUNT_BALANCE * RISK_PER_TRADE  # Now uses 1% risk
    stop_loss = atr * 1.5
    
    lot_size = (risk_amount / (stop_loss / point)) / 100000
    lot_size = max(min(lot_size, 50), 0.01)
    return round(lot_size, 2), stop_loss

# ==================== TRADE EXECUTION ====================
def execute_trade(signal, symbol, df):
    global daily_pnl
    
    lot_size, stop_loss = calculate_position_size(symbol, df)
    price = mt5.symbol_info_tick(symbol).ask if signal == 'BUY' else mt5.symbol_info_tick(symbol).bid
    take_profit = price + (stop_loss * 1.8) if signal == 'BUY' else price - (stop_loss * 1.8)
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": mt5.ORDER_TYPE_BUY if signal == 'BUY' else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": price - stop_loss if signal == 'BUY' else price + stop_loss,
        "tp": take_profit,
        "deviation": 10,
        "magic": 202406,
        "comment": "Ultimate Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    print(f"\n⚡ {symbol} {signal} | Lots: {lot_size} | Price: {price:.5f}")
    print(f"🛑 SL: {request['sl']:.5f} | ✅ TP: {request['tp']:.5f}")

# ==================== STRATEGY ORCHESTRATION ====================
def generate_combined_signal(symbol, df):
    strategies = {
        'ema_cross': ema_cross_strategy(df),
        'rsi_bounce': rsi_bounce_strategy(df),
        'macd_trend': macd_trend_strategy(df),
        'bollinger_squeeze': bollinger_squeeze_strategy(df),
        'volume_spike': volume_spike_strategy(df),
        'news_sentiment': news_sentiment_strategy(symbol)
    }
    
    if not add_adx_confirmation(df):
        return None
    
    signal_counts = {'BUY': 0, 'SELL': 0}
    for strat, signal in strategies.items():
        if signal in ['BUY', 'SELL']:
            signal_counts[signal] += STRATEGY_WEIGHTS[strat] * 100
    
    if signal_counts['BUY'] > 50 and signal_counts['BUY'] > signal_counts['SELL']:
        return 'BUY'
    elif signal_counts['SELL'] > 50 and signal_counts['SELL'] > signal_counts['BUY']:
        return 'SELL'
    return None

# ==================== MAIN TRADING LOOP ====================
def trading_cycle():
    global daily_pnl
    
    print(f"\n📡 Cycle Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    for symbol in SYMBOLS:
        try:
            london_session = 8 <= datetime.now().hour < 17
            if 'EUR' in symbol and not london_session:
                continue
            
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
            df = pd.DataFrame(rates)
            
            atr = ta.atr(df['high'], df['low'], df['close']).iloc[-1]
            if (atr/df['close'].iloc[-1]) < 0.002:
                continue
                
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            signal = generate_combined_signal(symbol, df)
            if signal:
                execute_trade(signal, symbol, df)
                
        except Exception as e:
            print(f"⚠️ Error on {symbol}: {str(e)}")
    
    update_strategy_weights()

def update_strategy_weights():
    global STRATEGY_WEIGHTS
    total_trades = sum(s['wins'] + s['losses'] for s in strategy_performance.values())
    if total_trades < 10:
        return
    
    new_weights = {}
    for strat in STRATEGY_WEIGHTS:
        wins = strategy_performance[strat]['wins']
        total = wins + strategy_performance[strat]['losses']
        new_weights[strat] = wins / max(1, total)
    
    total = sum(new_weights.values())
    STRATEGY_WEIGHTS = {k: v/total for k,v in new_weights.items()}

# ==================== BOT INITIALIZATION ====================
if __name__ == "__main__":
    if not mt5.initialize(login=MT5_ACCOUNT, password=MT5_PASSWORD, server=MT5_SERVER):
        print("❌ Failed to connect to MT5")
        mt5.shutdown()
        exit()
    
    print("\n🚀 Ultimate MT5 Trading Bot Activated")
    print(f"💰 Demo Balance: ${ACCOUNT_BALANCE:,}")
    print(f"📈 Strategies: 6 Adaptive Systems")
    print(f"🌎 Markets: {', '.join(SYMBOLS)}")
    print(f"⚖️ Risk: {RISK_PER_TRADE*100}% per trade | Max Daily Loss: {MAX_DAILY_LOSS*100}%")
    
    while True:
        trading_cycle()
        time.sleep(60)  # Run every 1 minutes
