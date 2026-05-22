import os
import datetime
import pytz
import functools
import logging
from flask import Flask, render_template, request

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

try:
    from polygon import RESTClient
    POLYGON_AVAILABLE = True
except ImportError:
    POLYGON_AVAILABLE = False
    logger.warning("polygon-api-client not installed.")

app = Flask(__name__)

# --- Configuration ---
API_KEY = os.environ.get("POLYGON_API_KEY")
if not API_KEY:
    logger.critical("POLYGON_API_KEY environment variable is not set.")

client = RESTClient(api_key=API_KEY) if (POLYGON_AVAILABLE and API_KEY) else None
et_tz = pytz.timezone("US/Eastern")

# --- Simple in-memory cache ---
_cache = {}

def build_osi_ticker(root, expiry_date, option_type, strike):
    try:
        date_obj = datetime.datetime.strptime(expiry_date, "%Y-%m-%d")
        date_str = date_obj.strftime("%y%m%d")
        strike_int = int(float(strike) * 1000)
        strike_str = f"{strike_int:08d}"
        return f"O:{root.upper().strip()}{date_str}{option_type.upper()}{strike_str}"
    except Exception as e:
        logger.error(f"Error building OSI ticker: {e}")
        return None

def detect_fvg(bars):
    """Detects Bullish or Bearish Fair Value Gaps in the bar sequence."""
    fvgs = []
    for i in range(1, len(bars) - 1):
        if bars[i + 1].low > bars[i - 1].high:
            fvgs.append({
                "type": "Bullish",
                "time": bars[i].timestamp,
                "top": bars[i - 1].high,
                "bottom": bars[i + 1].low
            })
        elif bars[i + 1].high < bars[i - 1].low:
            fvgs.append({
                "type": "Bearish",
                "time": bars[i].timestamp,
                "top": bars[i + 1].high,
                "bottom": bars[i - 1].low
            })
    return fvgs

def get_expected_move(root, expiry_date, atm_strike, signal_dt, sig_ms):
    """
    Fetches the ATM straddle at signal time using the user-supplied strike as ATM.
    Avoids a separate spot price fetch — the strike the user entered IS the ATM.
    Returns a dict with straddle details, or None if data is unavailable.
    """
    try:
        call_ticker = build_osi_ticker(root, expiry_date, "C", atm_strike)
        put_ticker  = build_osi_ticker(root, expiry_date, "P", atm_strike)
        if not call_ticker or not put_ticker:
            return None

        def fetch_option_price(osi_ticker):
            bars = list(client.list_aggs(
                ticker=osi_ticker, multiplier=1, timespan="minute",
                from_=signal_dt - datetime.timedelta(minutes=1),
                to=signal_dt   + datetime.timedelta(minutes=2),
                limit=5
            ))
            if not bars:
                return None
            bar = min(bars, key=lambda b: abs(b.timestamp - sig_ms))
            return bar.open

        call_price = fetch_option_price(call_ticker)
        put_price  = fetch_option_price(put_ticker)

        if call_price is None or put_price is None:
            logger.warning(f"Could not fetch straddle legs: call={call_price} put={put_price}")
            return None

        straddle    = call_price + put_price
        em_dollar   = straddle
        em_pct      = (straddle / float(atm_strike)) * 100
        upper_bound = float(atm_strike) + em_dollar
        lower_bound = float(atm_strike) - em_dollar

        return {
            "atm_strike":  float(atm_strike),
            "call_ticker": call_ticker,
            "put_ticker":  put_ticker,
            "call_price":  round(call_price, 2),
            "put_price":   round(put_price, 2),
            "straddle":    round(straddle, 2),
            "em_dollar":   round(em_dollar, 2),
            "em_pct":      round(em_pct, 2),
            "upper_bound": round(upper_bound, 2),
            "lower_bound": round(lower_bound, 2),
        }

    except Exception as e:
        logger.error(f"Error fetching expected move: {e}", exc_info=True)
        return None


def get_backtest_data(ticker, target_date, start_h, end_h, sig_h, form_strike, trade_type):
    if not client:
        return {"error": "Polygon client not initialized. Check your POLYGON_API_KEY."}

    cache_key = f"{ticker}|{target_date}|{start_h}|{end_h}|{sig_h}|{form_strike}"
    if cache_key in _cache:
        logger.info(f"Cache hit for {cache_key}")
        return _cache[cache_key]

    try:
        def parse_time(time_str):
            ts = f"{time_str}:00" if len(time_str) == 5 else time_str
            dt = datetime.datetime.strptime(f"{target_date} {ts}", "%Y-%m-%d %H:%M:%S")
            return et_tz.localize(dt)

        start_dt = parse_time(start_h)
        end_dt = parse_time(end_h)
        signal_dt = parse_time(sig_h)

        # --- Validate signal time is within window ---
        if not (start_dt <= signal_dt <= end_dt):
            return {"error": f"Signal time {sig_h} must be between {start_h} and {end_h}."}

        aggs = client.list_aggs(
            ticker=ticker, multiplier=1, timespan="minute",
            from_=start_dt, to=end_dt, limit=5000
        )

        results = list(aggs)
        if not results:
            return {"error": f"No market data found for {ticker} on {target_date}. The market may have been closed or the contract didn't trade."}

        # --- Build chart data ---
        chart_labels = [
            datetime.datetime.fromtimestamp(b.timestamp / 1000, et_tz).strftime('%H:%M')
            for b in results
        ]
        chart_ohlc = [
            {"x": b.timestamp,  # raw ms timestamp for candlestick time axis
             "o": b.open, "h": b.high, "l": b.low, "c": b.close}
            for b in results
        ]
        chart_volume = [b.volume for b in results]

        # --- Stats ---
        price_start = results[0].open
        price_end = results[-1].close
        high_val = max(b.high for b in results)
        low_val = min(b.low for b in results)
        avg_volume = sum(b.volume for b in results) / len(results)

        # --- Signal bar lookup ---
        sig_ms = int(signal_dt.timestamp() * 1000)
        signal_bar = next((b for b in results if b.timestamp <= sig_ms < b.timestamp + 60000), None)
        signal_idx = next((i for i, b in enumerate(results) if b.timestamp <= sig_ms < b.timestamp + 60000), None)

        # --- Volume spike near signal ---
        volume_spike = False
        if signal_idx is not None:
            window = results[max(0, signal_idx - 2): signal_idx + 3]
            spike_vols = [b.volume for b in window]
            if spike_vols and max(spike_vols) > avg_volume * 2:
                volume_spike = True

        # --- FVG detection ---
        all_fvgs = detect_fvg(results)
        nearby_fvgs = [f for f in all_fvgs if abs(f['time'] - sig_ms) <= 180000]
        fvg_confirmed = len(nearby_fvgs) > 0

        # --- FVG zones for chart shading (convert timestamps to labels) ---
        fvg_zones = []
        for f in nearby_fvgs:
            label = datetime.datetime.fromtimestamp(f['time'] / 1000, et_tz).strftime('%H:%M')
            fvg_zones.append({
                "type": f["type"],
                "label": label,
                "top": f["top"],
                "bottom": f["bottom"]
            })

        # --- Expected move at signal time (ATM straddle using user's strike) ---
        osi_body     = ticker[2:]          # strip "O:"
        root_symbol  = osi_body[:-15]      # everything before 6-char date + 1-char type + 8-char strike
        atm_strike   = form_strike         # passed in below; user's strike IS ATM
        expected_move = get_expected_move(root_symbol, target_date, atm_strike, signal_dt, sig_ms)

        option_move = (price_end - signal_bar.open) if signal_bar else None
        potential_gain = (((price_end - signal_bar.open) / signal_bar.open) * 100) if signal_bar else 0
        total_volume = sum(b.volume for b in results)

        result = {
            "ticker": ticker,
            "date": target_date,
            "start_time": start_h,
            "end_time": end_h,
            "sig_time": sig_h,
            "trade_type": trade_type,
            "start": price_start,
            "end": price_end,
            "high": high_val,
            "low": low_val,
            "return_pct": ((price_end - price_start) / price_start) * 100,
            "signal_price": signal_bar.open if signal_bar else None,
            "signal_label": chart_labels[signal_idx] if signal_idx is not None else sig_h,
            "signal_ts_ms": signal_bar.timestamp if signal_bar else None,
            "option_move": round(option_move, 2) if option_move is not None else None,
            "potential_gain": potential_gain,
            "fvg_confirmed": fvg_confirmed,
            "fvg_zones": fvg_zones,
            "volume_spike": volume_spike,
            "volume": total_volume,
            "expected_move": expected_move,
            "chart_labels": chart_labels,
            "chart_ohlc": chart_ohlc,
            "chart_volume": chart_volume,
        }

        _cache[cache_key] = result
        return result

    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {e}", exc_info=True)
        error_msg = str(e)
        if "403" in error_msg or "Forbidden" in error_msg:
            return {"error": "API authentication failed. Check your POLYGON_API_KEY."}
        elif "404" in error_msg:
            return {"error": f"Contract {ticker} not found. Verify the strike, expiry, and type."}
        elif "429" in error_msg:
            return {"error": "Rate limit hit. Wait a moment and try again."}
        return {"error": f"Unexpected error: {error_msg}"}


@app.route("/", methods=["GET", "POST"])
def index():
    # 3-minute intervals
    time_options = []
    curr = datetime.datetime.strptime("09:30", "%H:%M")
    while curr <= datetime.datetime.strptime("16:00", "%H:%M"):
        time_options.append(curr.strftime("%H:%M"))
        curr += datetime.timedelta(minutes=5)

    form = {
        "root": "QQQ",
        "date": datetime.date.today().isoformat(),
        "type": "C",
        "strike": "",
        "start_hour": "09:30",
        "end_hour": "16:00",
        "signal_time": ""
    }
    report = None

    if request.method == "POST":
        for key in form.keys():
            form[key] = request.form.get(key, form[key])

        if not form.get("signal_time"):
            report = {"error": "Signal time is required."}
        else:
            ticker = build_osi_ticker(form['root'], form['date'], form['type'], form['strike'])
            if not ticker:
                report = {"error": "Could not build a valid OSI ticker. Check symbol, date, and strike."}
            else:
                report = get_backtest_data(
                    ticker, form['date'], form['start_hour'],
                    form['end_hour'], form['signal_time'], form['strike'], form['type']
                )

    return render_template("index.html", report=report, form=form, time_options=time_options)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
