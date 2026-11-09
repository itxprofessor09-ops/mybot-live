"""Eagle X bot logic (online-updatable). Sirf signals deta hai, guarantee nahi."""
import json
import os
import threading
import traceback

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import escape_markup

VERSION = "1.3"
BRAND = "Eagle X bot"
SOURCE = "bundled"
LOAD_ERRORS = []

CRYPTO = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE"]
FX = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "USD/CHF", "EUR/JPY", "GBP/JPY"]
TFS = {"5s": 5, "10s": 10, "15s": 15, "1m": 60, "5m": 300, "15m": 900}
GREEN, RED, GREY = "26c281", "ef4b4b", "9aa3b5"
TICKER_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "TRX", "AVAX", "LINK", "DOT", "LTC",
                "BCH", "SHIB", "XLM", "ATOM", "NEAR", "UNI", "TON", "SUI", "PEPE"]
TICKER_SPEED = 80  # pixels/second (dp), zyada = tez
TICKER_HEIGHT = 50   # banner ki unchai (bara karna ho to barhayein)
TICKER_TOP_GAP = 14  # banner ke upar khali jagah (neeche karna ho to barhayein)
TICKER_FONT = 22     # banner ke text ka size
TICKER_REFRESH = 15  # seconds
BINANCE_HOSTS = ["https://api.binance.com", "https://data-api.binance.vision"]


# ---------------- network ----------------
def http_json(url, params):
    try:
        import requests
    except ImportError:
        import urllib.parse
        import urllib.request
        q = url + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(q, timeout=15) as f:
            return json.loads(f.read().decode())
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def binance(path, params):
    last = None
    for h in BINANCE_HOSTS:
        try:
            d = http_json(h + path, params)
            if isinstance(d, list):
                return d
            last = Exception(str(d))
        except Exception as e:
            last = e
    raise Exception("Binance data nahi mila: %s" % last)


def fetch(pair, tf, key):
    p = pair.replace(" OTC", "")
    if p in CRYPTO:
        sec, sym = TFS[tf], p + "USDT"
        if sec < 60:
            d = binance("/api/v3/klines", {"symbol": sym, "interval": "1s", "limit": 1000})
            m = {}
            for k in d:
                b = int(k[0] // 1000 // sec)
                o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
                if b not in m:
                    m[b] = {"o": o, "h": h, "l": l, "c": c}
                else:
                    m[b]["h"] = max(m[b]["h"], h)
                    m[b]["l"] = min(m[b]["l"], l)
                    m[b]["c"] = c
            return [m[k] for k in sorted(m)]
        d = binance("/api/v3/klines", {"symbol": sym, "interval": tf, "limit": 300})
        return [{"o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4])} for k in d]
    if not key:
        raise Exception("Forex ke liye Settings mein Twelve Data API key daalein.")
    iv = {"1m": "1min", "5m": "5min", "15m": "15min"}[tf]
    d = http_json("https://api.twelvedata.com/time_series",
                  {"symbol": p, "interval": iv, "outputsize": 300, "apikey": key})
    if "values" not in d:
        raise Exception(d.get("message", "Data nahi mila"))
    return [{"o": float(k["open"]), "h": float(k["high"]), "l": float(k["low"]), "c": float(k["close"])}
            for k in reversed(d["values"])]


# ---------------- live ticker ----------------
def pfmt(x):
    if x >= 1000:
        return "{:,.2f}".format(x)
    if x >= 1:
        return "{:.3f}".format(x)
    if x >= 0.01:
        return "{:.4f}".format(x)
    return "{:.8f}".format(x)


def fetch_ticker(symbols):
    syms = json.dumps([c + "USDT" for c in symbols], separators=(",", ":"))
    d = binance("/api/v3/ticker/24hr", {"symbols": syms})
    order = {c: i for i, c in enumerate(symbols)}
    rows = [{"name": x["symbol"][:-4], "price": float(x["lastPrice"]),
             "chg": float(x["priceChangePercent"])} for x in d]
    rows.sort(key=lambda r: order.get(r["name"], 999))
    return rows


COINGECKO_IDS = {"BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin", "SOL": "solana", "XRP": "ripple",
                 "DOGE": "dogecoin", "ADA": "cardano", "TRX": "tron", "AVAX": "avalanche-2", "LINK": "chainlink",
                 "DOT": "polkadot", "LTC": "litecoin", "BCH": "bitcoin-cash", "SHIB": "shiba-inu",
                 "XLM": "stellar", "ATOM": "cosmos", "NEAR": "near", "UNI": "uniswap",
                 "TON": "the-open-network", "SUI": "sui", "PEPE": "pepe"}


def fetch_coingecko(symbols):
    ids = ",".join(COINGECKO_IDS[c] for c in symbols if c in COINGECKO_IDS)
    d = http_json("https://api.coingecko.com/api/v3/coins/markets",
                  {"vs_currency": "usd", "ids": ids, "order": "market_cap_desc", "per_page": 50,
                   "page": 1, "price_change_percentage": "24h"})
    inv = {v: k for k, v in COINGECKO_IDS.items()}
    order = {c: i for i, c in enumerate(symbols)}
    rows = []
    for x in d:
        name = inv.get(x["id"], str(x.get("symbol", "")).upper())
        rows.append({"name": name, "price": float(x["current_price"]),
                     "chg": float(x.get("price_change_percentage_24h") or 0)})
    rows.sort(key=lambda r: order.get(r["name"], 999))
    return rows


def ticker_text(rows):
    parts = []
    for r in rows:
        ch = r["chg"]
        col = GREEN if ch >= 0 else RED
        parts.append("[b]%s[/b] %s [color=%s]%s%.2f%%[/color]"
                     % (r["name"], pfmt(r["price"]), col, "+" if ch >= 0 else "", ch))
    return "        |        ".join(parts)


# ---------------- indicators ----------------
def ema(a, n):
    k = 2 / (n + 1)
    o = [a[0]]
    for v in a[1:]:
        o.append(v * k + o[-1] * (1 - k))
    return o


def rsi(a, n=14):
    g = l = 0.0
    for i in range(1, n + 1):
        d = a[i] - a[i - 1]
        g += max(d, 0)
        l += max(-d, 0)
    g /= n
    l /= n
    for i in range(n + 1, len(a)):
        d = a[i] - a[i - 1]
        g = (g * (n - 1) + max(d, 0)) / n
        l = (l * (n - 1) + max(-d, 0)) / n
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)


def fmt(x):
    return "%.2f" % x if x > 100 else "%.5f" % x


# ---------------- analysis ----------------
def analyze(c, tf):
    n = len(c)
    if n < 60:
        raise Exception("Data kam hai (%d candles)" % n)
    cl = [x["c"] for x in c]
    p, L, P = cl[-1], c[-1], c[-2]
    A = (sum(x["h"] - x["l"] for x in c[-14:]) / 14) or 1e-9
    sc = [0]
    why = []

    def add(v, t):
        sc[0] += v
        col = GREEN if v > 0 else RED
        why.append("[color=%s]%s %s[/color]" % (col, "+" if v > 0 else "-", t))

    e9, e21, e50 = ema(cl, 9), ema(cl, 21), ema(cl, 50)
    if e9[-1] > e21[-1] > e50[-1]:
        add(1, "EMA 9>21>50 uptrend")
    elif e9[-1] < e21[-1] < e50[-1]:
        add(-1, "EMA 9<21<50 downtrend")
    else:
        why.append("* EMA: trend saaf nahi")
    m = [a - b for a, b in zip(ema(cl, 12), ema(cl, 26))]
    sg = ema(m, 9)
    h1, h0 = m[-1] - sg[-1], m[-2] - sg[-2]
    if h1 > 0 and h1 > h0:
        add(1, "MACD bullish momentum")
    elif h1 < 0 and h1 < h0:
        add(-1, "MACD bearish momentum")
    else:
        why.append("* MACD flat")
    r = rsi(cl)
    if r < 30:
        add(1, "RSI %d oversold" % r)
    elif r > 70:
        add(-1, "RSI %d overbought" % r)
    else:
        why.append("* RSI %d neutral" % r)
    w = cl[-20:]
    mu = sum(w) / 20
    sd = (sum((x - mu) ** 2 for x in w) / 20) ** 0.5
    if p <= mu - 2 * sd:
        add(1, "Bollinger lower band touch")
    elif p >= mu + 2 * sd:
        add(-1, "Bollinger upper band touch")
    res, sup = [], []
    for i in range(3, n - 3):
        win = c[i - 3:i + 4]
        if c[i]["h"] == max(x["h"] for x in win):
            res.append(c[i]["h"])
        if c[i]["l"] == min(x["l"] for x in win):
            sup.append(c[i]["l"])
    R = min([v for v in res if v > p], default=None)
    S = max([v for v in sup if v < p], default=None)
    nearS = S is not None and p - S < A * 0.8
    nearR = R is not None and R - p < A * 0.8
    if nearS:
        why.append("* Price support ke qareeb: " + fmt(S))
    if nearR:
        why.append("* Price resistance ke qareeb: " + fmt(R))
    body = abs(L["c"] - L["o"])
    rng = (L["h"] - L["l"]) or 1e-9
    lw = min(L["o"], L["c"]) - L["l"]
    uw = L["h"] - max(L["o"], L["c"])
    if lw >= 2 * body and lw >= 0.5 * rng:
        add(2 if nearS else 1, "Bullish rejection candle" + (" support par" if nearS else ""))
    if uw >= 2 * body and uw >= 0.5 * rng:
        add(-2 if nearR else -1, "Bearish rejection candle" + (" resistance par" if nearR else ""))
    ref = c[n - 12:n - 1]
    mx, mn = max(x["h"] for x in ref), min(x["l"] for x in ref)
    if L["h"] > mx and L["c"] < mx:
        add(-2, "Liquidity sweep upar, wapas andar close")
    if L["l"] < mn and L["c"] > mn:
        add(2, "Liquidity sweep neeche, wapas upar close")
    pb = abs(P["c"] - P["o"])
    if P["c"] < P["o"] and L["c"] > L["o"] and L["c"] > P["o"] and L["o"] < P["c"] and body > pb:
        add(1, "Bullish engulfing")
    if P["c"] > P["o"] and L["c"] < L["o"] and L["c"] < P["o"] and L["o"] > P["c"] and body > pb:
        add(-1, "Bearish engulfing")
    s = sc[0]
    sig = "CALL" if s >= 3 else "PUT" if s <= -3 else "NO TRADE"
    entry = "Abhi entry nahi. Confluence kam hai, agli candle ka intezar karein."
    if sig != "NO TRADE":
        against = (sig == "CALL" and nearR) or (sig == "PUT" and nearS)
        if against:
            entry = "Signal hai magar price opposite level ke qareeb hai. Skip karein ya retest ka intezar karein."
        else:
            entry = ("Entry: agli %s candle ki open par %s. Expiry: %s. "
                     "Agar open tak price signal candle ki wick se bahar chala jaye to skip karein." % (tf, sig, tf))
    return {"sig": sig, "s": s, "why": why, "entry": entry, "p": p, "S": S, "R": R}


# ---------------- UI helpers ----------------
def lbl(text, size=16, h=None, markup=True):
    l = Label(text=text, markup=markup, font_size=dp(size), size_hint_y=None, halign="left", valign="top")
    l.bind(width=lambda i, w: setattr(i, "text_size", (w - dp(10), None)))
    l.bind(texture_size=lambda i, v: setattr(i, "height", (h or v[1]) + dp(8)))
    return l


def btn(text, cb, h=56, bg=(0.14, 0.17, 0.24, 1)):
    b = Button(text=text, size_hint_y=None, height=dp(h), background_normal="",
               background_color=bg, font_size=dp(16))
    b.bind(on_release=lambda *_: cb())
    return b


class SignalApp(App):
    title = BRAND

    def build(self):
        try:
            Window.clearcolor = (0.06, 0.07, 0.09, 1)
            Window.softinput_mode = "below_target"
            Window.bind(on_keyboard=self.on_key)
            self.mode, self.pair, self.tf, self.ev = "live", None, None, None
            self.auto_btn = None
            root = BoxLayout(orientation="vertical")
            self.head = Label(text=BRAND, bold=True, size_hint_y=None, height=dp(50), font_size=dp(18))
            self.body = BoxLayout(orientation="vertical", padding=dp(10))
            nav = BoxLayout(size_hint_y=None, height=dp(54))
            nav.add_widget(btn("Live", lambda: self.set_mode("live"), h=54, bg=(0.09, 0.11, 0.15, 1)))
            nav.add_widget(btn("OTC", lambda: self.set_mode("otc"), h=54, bg=(0.09, 0.11, 0.15, 1)))
            nav.add_widget(btn("Settings", self.show_settings, h=54, bg=(0.09, 0.11, 0.15, 1)))
            root.add_widget(self.make_ticker())
            root.add_widget(self.head)
            root.add_widget(self.body)
            root.add_widget(nav)
            self.set_mode("live")
            Clock.schedule_interval(self.scroll, 1 / 30.0)
            Clock.schedule_interval(lambda dt: self.ticker_job(), TICKER_REFRESH)
            Clock.schedule_once(lambda dt: self.ticker_job(), 0.3)
            threading.Thread(target=self.warmup, daemon=True).start()
            return root
        except Exception:
            return self.err_view(traceback.format_exc())

    def make_ticker(self):
        self.ticker_ok = False
        self.ticker_busy = False
        self.ticker_syms = list(TICKER_COINS)
        wrap = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(TICKER_TOP_GAP + TICKER_HEIGHT))
        wrap.add_widget(Widget(size_hint_y=None, height=dp(TICKER_TOP_GAP)))
        box = FloatLayout(size_hint_y=None, height=dp(TICKER_HEIGHT))
        with box.canvas.before:
            Color(0.09, 0.11, 0.15, 1)
            rect = Rectangle(pos=box.pos, size=box.size)
        box.bind(pos=lambda i, v: setattr(rect, "pos", v), size=lambda i, v: setattr(rect, "size", v))
        l = Label(text="Live prices load ho rahe hain...", markup=True, size_hint=(None, 1),
                  halign="left", valign="middle", font_size=dp(TICKER_FONT), text_size=(None, dp(TICKER_HEIGHT)))
        l.bind(texture_size=lambda i, v: setattr(i, "width", v[0] + dp(30)))
        box.bind(y=lambda i, v: setattr(l, "y", v))
        l.x = Window.width
        box.add_widget(l)
        wrap.add_widget(box)
        self.ticker_lbl = l
        return wrap

    def scroll(self, dt):
        l = self.ticker_lbl
        l.x -= dp(TICKER_SPEED) * dt
        if l.x + l.width < 0:
            l.x = Window.width

    def ticker_job(self):
        if self.ticker_busy:
            return
        self.ticker_busy = True
        threading.Thread(target=self.ticker_fetch, daemon=True).start()

    def src_binance(self):
        try:
            return fetch_ticker(self.ticker_syms)
        except Exception:
            allrows = binance("/api/v3/ticker/24hr", {})
            valid = set(x["symbol"] for x in allrows)
            self.ticker_syms = [c for c in self.ticker_syms if c + "USDT" in valid] or self.ticker_syms
            return fetch_ticker(self.ticker_syms)

    def ticker_fetch(self):
        text, errs = None, []
        for name, fn in (("binance", self.src_binance),
                         ("coingecko", lambda: fetch_coingecko(self.ticker_syms))):
            try:
                rows = fn()
                if rows:
                    text = ticker_text(rows)
                    break
            except Exception as e:
                errs.append("%s: %s" % (name, str(e)[:80]))
        self.ticker_busy = False
        msg = None if text else "Live prices error - " + " | ".join(errs)
        Clock.schedule_once(lambda dt: self.set_ticker(text, msg))

    def set_ticker(self, text, msg=None):
        if text:
            self.ticker_lbl.text = text
            self.ticker_ok = True
        elif not self.ticker_ok:
            self.ticker_lbl.text = escape_markup(msg or "Live prices: internet check karein")

    def warmup(self):
        try:
            import requests  # noqa: F401
        except Exception:
            pass

    def err_view(self, text):
        sv = ScrollView()
        l = Label(text="ERROR (screenshot bhejein):\n" + text, size_hint_y=None,
                  halign="left", valign="top", font_size="12sp")
        l.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
        l.bind(texture_size=lambda i, v: setattr(i, "height", v[1]))
        sv.add_widget(l)
        return sv

    def on_key(self, window, key, *args):
        if key == 27:  # Android back button
            if self.tf:
                self.pick(self.pair)
                return True
            if self.pair:
                self.set_mode(self.mode)
                return True
        return False

    def cfg_path(self):
        return os.path.join(self.user_data_dir, "cfg.json")

    def key(self):
        try:
            with open(self.cfg_path()) as f:
                return json.load(f).get("key", "")
        except Exception:
            return ""

    def stop_auto(self):
        if self.ev:
            self.ev.cancel()
            self.ev = None

    def page(self, title, widgets, keep=False):
        if not keep:
            self.stop_auto()
        self.head.text = "%s | %s" % (BRAND, title)
        self.body.clear_widgets()
        g = GridLayout(cols=1, size_hint_y=None, spacing=dp(8))
        g.bind(minimum_height=g.setter("height"))
        for w in widgets:
            g.add_widget(w)
        sv = ScrollView()
        sv.add_widget(g)
        self.body.add_widget(sv)

    def set_mode(self, m):
        self.mode, self.pair, self.tf = m, None, None
        names = [p + (" OTC" if m == "otc" else "") for p in CRYPTO + FX]
        ws = []
        if m == "otc":
            ws.append(lbl("[color=f0b840]OTC price broker khud banata hai, uska public data nahi. "
                          "Analysis asli market ke same pair par hoti hai, sirf reference ke liye. "
                          "OTC par signal match hona zaroori nahi.[/color]", 14))
        ws.append(lbl("Pair select karein:", 16))
        grid = GridLayout(cols=2, size_hint_y=None, spacing=dp(8))
        grid.bind(minimum_height=grid.setter("height"))
        for n in names:
            grid.add_widget(btn(n, lambda n=n: self.pick(n), h=60))
        ws.append(grid)
        self.page("Live Market" if m == "live" else "OTC Market", ws)

    def pick(self, p):
        self.pair, self.tf = p, None
        opts = list(TFS) if p.replace(" OTC", "") in CRYPTO else ["1m", "5m", "15m"]
        ws = [btn("< Pairs", lambda: self.set_mode(self.mode), h=44), lbl(p, 22),
              lbl("Kis candle par trade karni hai?", 16)]
        ws += [btn(o, lambda o=o: self.analyze_now(o), h=58) for o in opts]
        self.page("Timeframe", ws)

    def show_settings(self):
        self.pair, self.tf = None, None
        ti = TextInput(text=self.key(), hint_text="Twelve Data API key", multiline=False,
                       size_hint_y=None, height=dp(48))

        def save():
            try:
                os.makedirs(self.user_data_dir, exist_ok=True)
                with open(self.cfg_path(), "w") as f:
                    json.dump({"key": ti.text.strip()}, f)
                self.head.text = "Settings (saved)"
            except Exception as e:
                self.head.text = "Save error: %s" % e

        info = "Version %s | source: %s" % (VERSION, SOURCE)
        if LOAD_ERRORS:
            info += "\n" + escape_markup("; ".join(LOAD_ERRORS))
        self.page("Settings", [lbl("Forex ke liye twelvedata.com se free API key lein aur yahan paste karein. "
                                   "Crypto ke liye key nahi chahiye.", 14), ti, btn("Save", save),
                               lbl(info, 12)])

    def run_job(self):
        threading.Thread(target=self.work, daemon=True).start()

    def analyze_now(self, tf):
        self.tf = tf
        self.page("Loading...", [lbl("Data load ho raha hai...", 16)])
        self.run_job()

    def work(self):
        pair, tf, key = self.pair, self.tf, self.key()
        try:
            c = fetch(pair, tf, key)
            r = analyze(c[:-1], tf)
            Clock.schedule_once(lambda dt: self.show(r))
        except Exception as e:
            msg = "%s: %s" % (type(e).__name__, e)
            Clock.schedule_once(lambda dt: self.show_error(msg))

    def show_error(self, msg):
        self.page("Error", [btn("< Back", lambda: self.pick(self.pair), h=44),
                            lbl("[color=%s]%s[/color]" % (RED, escape_markup(msg)), 15)])

    def show(self, r):
        col = GREEN if r["sig"] == "CALL" else RED if r["sig"] == "PUT" else GREY
        self.auto_btn = btn("Auto refresh (10s): " + ("ON" if self.ev else "OFF"), self.toggle_auto, h=48)
        ws = [btn("< Timeframe", lambda: self.pick(self.pair), h=44),
              lbl("%s | %s | price %s" % (self.pair, self.tf, fmt(r["p"])), 14),
              lbl("[b][color=%s]%s[/color][/b]" % (col, r["sig"]), 44, h=70),
              lbl("Confluence score: %d. Yeh accuracy nahi hai." % r["s"], 13),
              lbl("[b]Entry kab leni hai[/b]\n" + r["entry"], 15),
              lbl("[b]Analysis[/b]\n" + "\n".join(r["why"]), 15),
              lbl("Support: %s | Resistance: %s" % (fmt(r["S"]) if r["S"] else "-",
                                                   fmt(r["R"]) if r["R"] else "-"), 13),
              btn("Refresh", lambda: self.analyze_now(self.tf), h=52, bg=(0.23, 0.51, 0.96, 1)),
              self.auto_btn,
              lbl("[color=f0b840]Signals probability hain, guarantee nahi. Pehle demo par test karein.[/color]", 13)]
        self.page("Signal", ws, keep=True)

    def toggle_auto(self):
        if self.ev:
            self.stop_auto()
        else:
            self.ev = Clock.schedule_interval(lambda dt: self.run_job(), 10)
        if self.auto_btn:
            self.auto_btn.text = "Auto refresh (10s): " + ("ON" if self.ev else "OFF")

