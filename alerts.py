import yfinance as yf
from datetime import datetime
import asyncio
from pytz import timezone


def is_market_open():
    eastern = timezone("US/Eastern")
    now = datetime.now(eastern)

    if now.weekday() >= 5:  # Saturday (5) or Sunday (6)
        return False

    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

    return market_open <= now <= market_close


# Track last known positions to prevent duplicate alerts
last_position = {}

async def check_sma_cross(bot, channel_id, tickers):
    if not is_market_open():
        return  # Skip polling outside market hours
    channel = bot.get_channel(channel_id)

    for ticker in tickers:
        try:
            df = yf.download(ticker, period="300d", interval="1d", progress=False)
            df["SMA200"] = df["Close"].rolling(window=200).mean()

            latest = df.iloc[-1]
            previous = df.iloc[-2]

            current_price = latest["Close"]
            current_sma = latest["SMA200"]
            previous_price = previous["Close"]
            previous_sma = previous["SMA200"]

            crossed_up = previous_price < previous_sma and current_price > current_sma
            crossed_down = previous_price > previous_sma and current_price < current_sma

            key = f"{ticker}_above"
            was_above = last_position.get(key, previous_price > previous_sma)
            is_above = current_price > current_sma
            last_position[key] = is_above

            if crossed_up and not was_above:
                await channel.send(
                    f"📈 **{ticker.upper()} just crossed above its 200-day SMA!**\n"
                    f"Price: ${current_price:.2f} | SMA200: ${current_sma:.2f}"
                )
            elif crossed_down and was_above:
                await channel.send(
                    f"📉 **{ticker.upper()} just crossed below its 200-day SMA!**\n"
                    f"Price: ${current_price:.2f} | SMA200: ${current_sma:.2f}"
                )

        except Exception as e:
            print(f"Error checking {ticker}: {e}")
