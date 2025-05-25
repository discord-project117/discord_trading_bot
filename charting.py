import yfinance as yf
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import os
import numpy as np
from ta.momentum import RSIIndicator
import matplotlib.dates as mdates

def get_chart_timeframe_params(timeframe):
    timeframe_map = {
        "1H": ("7d", "1h"),
        "4H": ("30d", "4h"),
        "1D": ("6mo", "1d"),
        "1W": ("2y", "1wk")
    }
    return timeframe_map.get(timeframe.upper(), ("6mo", "1d"))

def plot_candle_chart_with_rsi(ticker, timeframe="1D"):
    period, interval = get_chart_timeframe_params(timeframe)
    df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)

    # Flatten MultiIndex columns if needed
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Keep only OHLC columns
    df = df[["Open", "High", "Low", "Close"]].copy()
    df = df.apply(pd.to_numeric, errors="coerce")
    df.dropna(inplace=True)

    df.index.name = "Date"

    # Calculate RSI using ta library
    df["RSI"] = RSIIndicator(close=df["Close"], window=14).rsi()
    df.dropna(subset=["RSI"], inplace=True)

    # Add RSI and threshold lines
    apds = [
        mpf.make_addplot(df["RSI"], panel=1, ylabel="RSI", color="purple", secondary_y=False, width=0.75),
        mpf.make_addplot(pd.Series(70, index=df.index), panel=1, color="red", width=0.75, secondary_y=False),
        mpf.make_addplot(pd.Series(30, index=df.index), panel=1, color="green", width=0.75, secondary_y=False),
        mpf.make_addplot(pd.Series(50, index=df.index), panel=1, color="black", linestyle="--", width=0.8, secondary_y=False)
    ]

    save_path = "temp_chart.png"
    fig, axes = mpf.plot(
        df,
        type="candle",
        style="yahoo",
        title=f"{ticker.upper()} - {timeframe.upper()}",
        ylabel="Price",
        addplot=apds,
        panel_ratios=(3, 1),
        figratio=(16, 9),
        figscale=1.2,
        returnfig=True
    )

    # Remove gridlines from all panels
    for ax in axes:
        ax.grid(False)

    # This removes grids for RSI, but if other indicators are added it might reposition the index. Leaving it in commented out incase we want to implement later
    # axes[2].grid(False)
    # axes[3].grid(False)

    # Keep RSI y-axis fixed
    axes[1].set_ylim(0, 100)

    fig.savefig(save_path)
    plt.close(fig)

    return save_path
