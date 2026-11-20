import requests
import pandas as pd
import time

BASE_URL = "https://api.toobit.com"
TIMEFRAME = "15m"
LIMIT = 150
MIN_OVERLAP = 0.0

def get_symbols():
    url = BASE_URL + "/api/v1/exchangeInfo"
    try:
        data = requests.get(url, timeout=15).json()
        return [
            s["symbol"] for s in data["symbols"]
            if s.get("quoteAsset") == "USDT"
            and s.get("status") == "TRADING"
        ]
    except Exception as e:
        print("Symbol error:", e)
        return []

def get_candles(symbol):
    url = BASE_URL + "/api/v1/klines"
    params = {
        "symbol": symbol,
        "interval": TIMEFRAME,
        "limit": LIMIT
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        return pd.DataFrame(data, columns=[
            "time", "open", "high", "low",
            "close", "volume", "close_time",
            "qav", "trades", "tbbav",
            "tbqav", "ignore"
        ]).astype({
            "open": float, "high": float,
            "low": float, "close": float
        })
    except Exception:
        return None

def scan(symbol):
    df = get_candles(symbol)
    if df is None or len(df) < 10:
        return None

    # Three-candle Fair Value Gap
    for i in range(len(df)-2, 3, -1):
        a = df.iloc[i-2]
        b = df.iloc[i-1]
        c = df.iloc[i]

        bullish_fvg = a["high"] < c["low"]
        bearish_fvg = a["low"] > c["high"]

        if bullish_fvg:
            zone_low = a["high"]
            zone_high = c["low"]
            direction = "BULLISH"
        elif bearish_fvg:
            zone_low = c["high"]
            zone_high = a["low"]
            direction = "BEARISH"
        else:
            continue

        # Search for opposing candle as potential OB
        for j in range(i-2, max(i-12, 0), -1):
            candle = df.iloc[j]

            if direction == "BULLISH" and candle["close"] < candle["open"]:
                ob_low = candle["low"]
                ob_high = candle["open"]
            elif direction == "BEARISH" and candle["close"] > candle["open"]:
                ob_low = candle["open"]
                ob_high = candle["high"]
            else:
                continue

            overlap_low = max(zone_low, ob_low)
            overlap_high = min(zone_high, ob_high)

            if overlap_low <= overlap_high:
                price = df.iloc[-1]["close"]
                distance = abs(price - overlap_high) / price * 100

                return {
                    "symbol": symbol,
                    "direction": direction,
                    "OB_FVG": f"{overlap_low:.8g} - {overlap_high:.8g}",
                    "price": price,
                    "distance_percent": round(distance, 2)
                }

    return None

def main():
    print("RADAR OB+FVG SCANNER STARTED")
    print("Timeframe:", TIMEFRAME)

    symbols = get_symbols()
    print("Symbols found:", len(symbols))

    results = []

    for index, symbol in enumerate(symbols):
        result = scan(symbol)
        if result:
            results.append(result)
            print("FOUND:", result)

        if index % 20 == 0:
            print("Scanning:", index, "/", len(symbols))

        time.sleep(0.15)

    results.sort(key=lambda x: x["distance_percent"])

    print("\n===== RADAR RESULTS =====")
    for item in results:
        print(item)

    if results:
        pd.DataFrame(results).to_csv(
            "radar_results.csv", index=False
        )
        print("\nSaved: radar_results.csv")
    else:
        print("No valid overlap found.")

if __name__ == "__main__":
    main()
  
