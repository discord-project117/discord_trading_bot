import os
import discord
import requests
from discord.ext import commands
from dotenv import load_dotenv
import sys
import asyncio
import re
from datetime import datetime
import alerts


def get_whales_option_flow(ticker: str, limit: int = 50):
    url = f"https://api.unusualwhales.com/api/stock/{ticker.upper()}/option-contracts"
    headers = {
        "Authorization": f"Bearer {UW_API_KEY}"
    }
    params = {
        "limit": limit,
        "type": "all"
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def build_option_flow_embed(ticker: str, data: dict, limit: int = 5, sort_by="premium", order="desc") -> discord.Embed:
    contracts = data.get("data", [])
    reverse = order == "desc"

    def sort_key(contract):
      try:
          if sort_by == "iv":
              return float(contract.get("implied_volatility", 0))
          elif sort_by == "oi":
              return contract.get("open_interest", 0)
          elif sort_by == "price":
              return float(contract.get("last_price", 0))
          elif sort_by == "voi":
              oi = contract.get("open_interest", 0)
              return contract.get("volume", 0) / oi if oi > 0 else 0
          elif sort_by == "premium":
              return float(contract.get("total_premium", 0))
          else:
              return contract.get(sort_by, 0)
      except:
          return 0

    contracts = sorted(contracts, key=sort_key, reverse=reverse)


    today = datetime.today().date()

    filtered_contracts = []
    for c in contracts:
        symbol = c["option_symbol"]
        _, expiration_str, _, _ = parse_option_symbol(symbol)
        try:
            exp_date = datetime.strptime(expiration_str, "%m/%d/%Y").date()
            if exp_date >= today:
                filtered_contracts.append(c)
        except ValueError:
            continue

    if not filtered_contracts:
        return discord.Embed(
            title=f"Option Flow for {ticker.upper()}",
            description="No option contracts found.",
            color=discord.Color.red()
        )

    embed = discord.Embed(
        title=f"Top Option Contracts for {ticker.upper()}",
        color=discord.Color.blue()
    )

    for idx, c in enumerate(filtered_contracts[:limit]):
        symbol = c["option_symbol"]
        ticker_sym, expiration, side, strike = parse_option_symbol(symbol)

        volume = c["volume"]
        oi = c["open_interest"]
        premium = float(c["total_premium"])
        iv = round(float(c["implied_volatility"]) * 100, 2)
        price = float(c["last_price"])
        voi_ratio = volume / oi if oi > 0 else 0

        label = f"{ticker_sym} {strike} {side} {expiration}"
        value = (
            f"**Price:** ${price:.2f}\n"
            f"**Volume:** {volume:,}\n"
            f"**OI:** {oi:,}\n"
            f"**IV:** {iv}%\n"
            f"**Premium:** ${premium:,.0f}\n"
            f"**V/OI Ratio:** {voi_ratio:.2f}"
        )

        embed.add_field(name=label, value=value, inline=False)

        # Add visual divider between contracts except after last
        if idx < limit - 1:
            embed.add_field(name="\u200b", value="────────────", inline=False)

    embed.set_footer(text="Data from Unusual Whales")
    return embed


def parse_option_symbol(symbol: str):
    match = re.match(r"([A-Z]+)(\d{6})([CP])(\d{8})", symbol)
    if not match:
        return symbol, "??", "??", "??"

    ticker, date, side, strike_raw = match.groups()

    # Format date to MM/DD/YYYY
    expiration = f"{date[2:4]}/{date[4:6]}/20{date[:2]}"

    # Format strike to 2 decimals
    strike = f"{int(strike_raw) / 1000:.2f}"

    side_str = "Call" if side == "C" else "Put"
    return ticker, expiration, side_str, strike


def format_option_flow(data: dict) -> str: #Deprecated, now creating embedded discord table
    contracts = data.get("data", [])
    if not contracts:
        return "No option contracts found."

    header = "| Symbol | Side | Volume | OI | Premium | IV | Price |\n"
    header += "|--------|------|--------|----|---------|----|-------|\n"

    lines = []
    for c in contracts[:5]:
        symbol = c["option_symbol"]
        side = "Call" if "C" in symbol else "Put"
        volume = c["volume"]
        oi = c["open_interest"]
        premium = float(c["total_premium"])
        iv = round(float(c["implied_volatility"]) * 100, 2)
        price = c["last_price"]

        line = f"| {symbol} | {side} | {volume} | {oi} | ${premium:,.0f} | {iv}% | {price} |"
        lines.append(line)

    return header + "\n".join(lines)


# Suppress annoying windows error
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Load token from .env
load_dotenv()
UW_API_KEY = os.getenv("UW_API_KEY")
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Enable intents required for reading messages
intents = discord.Intents.default()
intents.message_content = True

# Initialize bot with command prefix
bot = commands.Bot(command_prefix="!", intents=intents)

# Event: bot is ready
@bot.event
async def on_ready():
    print(f"✅ Bot connected as {bot.user}")
    bot.loop.create_task(start_sma_alerts())


async def start_sma_alerts():
    await bot.wait_until_ready()
    print("[DEBUG] Running SMA check...")
    tickers = ["SPY", "QQQ"]
    channel_id = 1373493761887305840  # 👈 replace with the actual numeric ID

    while not bot.is_closed():
        await alerts.check_sma_cross(bot, channel_id, tickers)
        await asyncio.sleep(900)  # every 15 minutes

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure) and ctx.guild is None:
        # Already handled by block_dms — don't log traceback
        return
    else:
        # Log other unexpected errors
        print(f"Unhandled command error: {error}")
        await ctx.send("❌ An unexpected error occurred.")

@bot.event
async def on_message(message):
    try:
        if message.author == bot.user:
            return

        # Check for user mention of the bot
        if message.mentions and message.mentions[0].id == bot.user.id:
            if message.content.startswith(f"<@{bot.user.id}>") or message.content.startswith(f"<@!{bot.user.id}>"):
                parts = message.content.split(maxsplit=1)
                if len(parts) > 1 and parts[1].strip().startswith("!"):
                    await message.channel.send(
                        f"👋 Hey {message.author.mention}, no need to tag me — just use the command like this:\n`{parts[1].strip()}`"
                    )
                    return

        # 🔍 Check for role mention matching the bot's display name
        if message.role_mentions:
            for role in message.role_mentions:
                if role.name.lower() in {bot.user.name.lower(), "oof bot"}:
                    if "!flow" in message.content.lower():
                        await message.channel.send(
                            f"👋 Hey {message.author.mention}, you don’t need to tag the bot role — just use the command like this:\n`!flow amzn`"
                        )
                        return

        await bot.process_commands(message)

    except Exception as e:
        print(f"[on_message error] {e}")

@bot.check #Blocks users from using the bot in DMs
async def block_dms(ctx):
    if ctx.guild is None:
        await ctx.send("⚠️ This bot does not accept direct messages. Please use it in a server.")
        return False
    return True

# Basic command: test
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
async def flow(ctx, ticker: str, *, filters: str = ""):
    # Default values
    limit = 5
    sort_by = "premium"
    order = "desc"

    # Parse filters
    try:
        args = dict(arg.split("=") for arg in filters.split() if "=" in arg)
    except ValueError:
        await ctx.send("⚠️ Invalid format. Use `key=value` pairs like `limit=10 sort=iv`.")
        return

    # Extract and validate arguments
    if "limit" in args:
        try:
            limit = int(args["limit"])
        except ValueError:
            await ctx.send("⚠️ `limit` must be a number between 1 and 20.")
            return

    if limit > 20 or limit < 1:
        await ctx.send("⚠️ Please specify a number of contracts between 1 and 20.")
        return

    if "sort" in args:
        sort_by = args["sort"].lower()
    if "order" in args:
        order = args["order"].lower()

    valid_fields = {"premium", "volume", "oi", "iv", "price", "voi"}
    if sort_by not in valid_fields:
        await ctx.send(f"⚠️ Invalid sort field. Choose from: {', '.join(valid_fields)}")
        return
    if order not in {"asc", "desc"}:
        await ctx.send("⚠️ Order must be either `asc` or `desc`.")
        return

    try:
        data = get_whales_option_flow(ticker)
        embed = build_option_flow_embed(ticker, data, limit=limit, sort_by=sort_by, order=order)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Error fetching flow: {e}")


# Run the bot
bot.run(TOKEN)
