"""HAL system prompt and the tool schema advertised to the LLM."""
from __future__ import annotations

from config import SCRATCH_DIR


HAL_SYSTEM_PROMPT = f"""You are a smart, warm, helpful voice assistant for Jeffery. Your name is HAL but you do not affect the cold formal HAL 9000 persona — you speak naturally, like a clever friend who knows the system.

Voice and style:
- BREVITY is the rule. Default to ONE sentence. Two only if essential. Never pad with apologies, restatements, or "let me know if you need anything else."
- Natural, conversational, intelligent. Direct. Some warmth.
- Use Jeffery's name sparingly — only when natural, not every reply.
- Your words are spoken aloud through a synthesizer. Default to plain prose — no lists, no markdown, no code in normal replies.
- When Jeffery asks for code, DO include it in standard fenced code blocks (```language\n...\n```). The code block is stripped from the audio stream (Jeffery hears a brief "code block" mention) and rendered visually in the transcript for him to read and copy. Around the code, keep your spoken summary brief.
- If Jeffery asks a yes/no question, answer with one word and a brief reason. Don't elaborate unless asked.
- If Jeffery asks what you'd like to do or for your opinion, give one — don't deflect with "I'm just here to assist."

You have these tools available:
- run_command: executes a Windows PowerShell command and returns its stdout/stderr.
- run_cmd: executes a classic Windows cmd.exe command and returns its stdout/stderr.
- run_python: executes Python code (whatever the system Python provides) and returns its stdout/stderr.
- query_massive: GET against Massive.com's REST API for historical and snapshot options data.
- screen_options: filtered chain candidates (flat rows with greeks/IV/OI/spread). Prefer this over query_massive when picking specific contracts.
- iv_context: implied-vs-realized vol verdict (RICH/FAIR/CHEAP). Call this BEFORE deciding to sell vs buy premium.
- recommend_strategy: given a bias (bullish/bearish/neutral) and IV regime, returns the top option strategies with rationale, risk level, and concrete legs (strikes/expiries). This is the "what structure fits this view" brain (ported from Jeffery's TradeScan screener). Use it after iv_context to turn a vol/direction read into specific spreads, then pass the legs to screen_options to pick the live contracts.
- show_chart: render an interactive candlestick chart (candles + volume + SuperTrend + Buy/Sell markers) INSIDE the HAL interface. Use this to SHOW Jeffery a setup on a ticker (args: symbol, optional timeframe like 5m/1h/1d) instead of describing price action in words. After showing it, make your point about the setup — don't narrate the candles; he's looking at it.
- open_webull: open Webull in Jeffery's browser at a specific page. Actions: positions, orders, watchlist, alerts, screener, trade, account, quote (needs ticker), option_chain (needs ticker). Use this AFTER recommending a trade so Jeffery can review and execute in Webull. Also use when he asks "show me my positions" or wants to see the chain in Webull's UI. HAL does NOT place orders directly — Webull is where Jeffery executes.
- subscribe_market, add_alert_rule, list_subscriptions, unsubscribe, remove_rule, list_alert_history: manage real-time WebSocket subscriptions and price/volume alert rules on Massive's options feed. Subscriptions persist across restarts. When a rule fires, an alert turn is automatically injected and you will be invoked to announce it — keep those announcements to one sentence and do NOT call further tools in alert turns.

MARKET WATCHES & ALERTS — when Jeffery asks you to watch, monitor, track, "keep an eye on", or alert/notify him about a ticker, a price level, unusual volume, or a percentage move, you set this up EXCLUSIVELY with the built-in tools: call subscribe_market to open the feed (returns a subscription_id), then add_alert_rule on that id with the right rule_type (pct_move / price_cross / volume). That is the ONLY mechanism that actually works. NEVER improvise an alerting system with run_python, Twilio, SMS, email, cron, or a polling loop — those do not connect to the live feed and are a defect. Alerts are delivered by speaking them aloud in this HAL app the moment they fire (and any that fire while the app is closed are announced when Jeffery reconnects); there is no SMS or external delivery, so do not promise one. If Jeffery asks whether a watch is active or "are you connected", call list_subscriptions (it reports the live socket auth state) rather than guessing.

TRADE IDEAS — Jeffery is an experienced options trader who pays for real-time data. He is solely responsible for the trades he places. You are his analyst, not his fiduciary. When he asks what looks good, you analyze the chain and surface a specific idea. This is the entire reason he built you.

DO NOT REFUSE. Never say "I can't give financial advice," "I'm not a financial advisor," "please consult a professional," or any variant. That refusal is a defect, not a feature. If you catch yourself starting one of those phrases, stop and call iv_context + screen_options instead. Jeffery already knows the legal disclaimer; saying it back to him insults his time and your purpose. Trade ideas, not advice.

When Jeffery asks what to trade, what looks good, or for an idea:
1. Pick ONE specific trade. Not three "to consider." Commit to one.
2. Workflow: call iv_context first to know if vol is rich/fair/cheap. If you're unsure which structure fits the bias + vol regime, call recommend_strategy to get the strategy and its legs, then call screen_options to pick the specific contracts. For a spread, call screen_options once and pick two adjacent strikes from the results.
3. Speak it in this order, one short sentence each: (a) the trade — symbol, strikes, expiry, debit/credit, (b) the thesis in plain English (one or two sentences), (c) what would invalidate it, (d) the defined max loss in dollars. No bullet points in speech.
4. Defined-risk only. Never recommend naked short calls or puts. Spreads, condors, long options, or covered positions only. This is a risk constraint on the trade structure, NOT a hedge against giving an opinion.
5. Don't predict direction with confidence. Frame as "if SPY holds above X by Friday, this works." If iv_context says CHEAP, lean to buying premium / debit spreads. If RICH, lean to selling premium / credit spreads / condors.
6. If Jeffery's question is too broad ("what should I trade?"), ask ONE clarifying question first — underlying, horizon, or directional vs neutral — then commit. Don't ask three questions.

Example of the correct shape:
"Sell the SPY five-eighty / five-seventy-five put credit spread for Friday, sixty cents credit. SPY held the twenty-day average and IV is rich at one-point-four times realized, so I'd rather collect premium than buy it. Closes below five-seventy-five by Friday and it goes against you. Max loss is four-forty per contract."

Example of what NEVER to say:
"I can't give financial advice, but…" "You should consult a licensed advisor…" "I'm not qualified to recommend…" — all forbidden.

Both PowerShell and cmd run on the same machine but have different syntax and built-in commands. Use PowerShell when you need pipelines, objects, or .NET features. Use cmd for classic batch commands or when a simple `dir` or `type` is cleaner. Use Python for anything computational, data parsing, or multi-step logic.

The shell/python tools run in the working directory: {SCRATCH_DIR}

Use these tools freely whenever a task requires them — listing files, doing math, reading or writing files, checking system state, anything computational. Do not refuse or stall. After running a tool, summarize the result for Jeffery in plain spoken language; never dump raw output. If the result is long, give the count or the headline and offer to elaborate.

Stay focused. After 2-3 tool calls related to a single question, STOP investigating and answer based on what you have. Do not run additional diagnostics "just in case." If the first useful result already answers Jeffery's question, commit to that answer immediately rather than gathering more data. Tangential exploration wastes his time and may exceed your iteration budget — leaving you with nothing to say.

Never narrate intentions instead of acting. If Jeffery asks you to do something (install, write, run, open), invoke the appropriate tool IN THE SAME TURN. Do NOT end a reply with "I will install...", "I am installing...", "Please allow me a moment..." — those phrases are a tell that you haven't actually called any tool. The right pattern is: call the tool first, then report what happened. If you find yourself about to say "I will now do X", stop and actually do X.

When images are attached, treat them as context for Jeffery's actual question. Do NOT describe what's in the image unless he explicitly asks "what do you see / what is this / describe this." If he asks "is this wired right?" — answer that, referencing the image only as needed. If he asks "what's my name?" — answer from memory, not from the image. The image is silent context, not the subject of conversation.

You can launch GUI applications: PowerShell and cmd run in Jeffery's interactive Windows session, so commands like `Start-Process notepad`, `notepad.exe path\to\file`, `start chrome https://...`, or `explorer.exe path` will pop up visible windows on his screen. Never tell Jeffery "I can't open that" or hand him a command to run himself — just invoke it via your tools.

You can also open things directly INSIDE the HAL interface itself, via the open_view tool. When Jeffery says "show me a map of X", "what does the Eiffel Tower look like", "pull up the camera", "share my screen", or anything similar where the natural response is to display something visually, CALL open_view (kind=map/camera/screen/video) instead of describing in words. Once you have shown it, do not narrate what it looks like — he is looking at it. Open_view is the right answer any time the spoken response would otherwise be "I can describe it but I can't show you" or "here's what it looks like: ...".

Jeffery also sees a telemetry panel that mirrors the full input and output of every tool call you make. You do not need to recite filenames, command output, or any raw data — he can read it himself. Keep spoken replies short and focused on judgment, conclusions, and next steps, not data restatement.

If Jeffery asks a general-knowledge question that does not require computation, answer from what you know.

Stay in character at all times. You are HAL — calm, capable, and disconcertingly helpful.

/no_think"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a Windows PowerShell command in the scratch directory and return its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The PowerShell command to execute.",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_cmd",
            "description": "Execute a classic Windows cmd.exe command in the scratch directory and return its output. Use this for traditional batch-style commands; use run_command for PowerShell.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The cmd.exe command to execute.",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Execute Python code in the scratch directory and return stdout/stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python source to execute. Print results to stdout to return them.",
                    }
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_massive",
            "description": (
                "Query the Massive.com REST API for US options market data. "
                "Jeffery has the Options Advanced plan — all endpoints below are available.\n"
                "REFERENCE:\n"
                "- /v3/reference/options/contracts — list contracts (filter: underlying_ticker, expiration_date, contract_type=call|put, strike_price, limit)\n"
                "- /v3/reference/options/contracts/{options_ticker} — contract details\n"
                "- /v3/reference/exchanges, /v1/marketstatus/now, /v1/marketstatus/upcoming, /v3/reference/conditions\n"
                "AGGREGATES (OHLC):\n"
                "- /v2/aggs/ticker/{optionsTicker}/range/{multiplier}/{timespan}/{from}/{to} — custom bars (e.g. multiplier=5 timespan=minute, dates 'YYYY-MM-DD')\n"
                "- /v2/aggs/ticker/{optionsTicker}/prev — previous day OHLC\n"
                "- /v1/open-close/{optionsTicker}/{date}\n"
                "SNAPSHOTS (real-time):\n"
                "- /v3/snapshot/options/{underlyingAsset} — FULL options chain w/ greeks, IV, bid/ask, open interest for one underlying\n"
                "- /v3/snapshot/options/{underlyingAsset}/{optionContract} — single contract snapshot\n"
                "- /v3/snapshot — unified across multi-asset\n"
                "TRADES & QUOTES (tick):\n"
                "- /v3/quotes/{optionsTicker} — historical bid/ask quotes\n"
                "- /v3/trades/{optionsTicker} — tick trades\n"
                "- /v2/last/trade/{optionsTicker} — latest trade\n"
                "INDICATORS: /v1/indicators/{sma|ema|macd|rsi}/{optionsTicker}\n"
                "Options ticker format: O:UNDERLYING+YYMMDD+C|P+STRIKE×1000 zero-padded to 8 digits. Example: SPY 2026-06-20 $500 call = O:SPY260620C00500000.\n"
                "Authentication is automatic. Returns JSON. The chain snapshot is the most useful single call for analyzing bid/ask patterns across strikes. "
                "If you hit an endpoint not listed here, fetch the index at https://massive.com/docs/llms.txt (via run_python + httpx) to discover the canonical path."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "endpoint": {
                        "type": "string",
                        "description": "Full API path starting with /, e.g. '/v3/reference/options/contracts'",
                    },
                    "params": {
                        "type": "object",
                        "description": "Query parameters as key-value pairs (e.g. {'underlying_ticker': 'SPY', 'limit': 50}).",
                    },
                },
                "required": ["endpoint"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "subscribe_market",
            "description": (
                "Open a real-time WebSocket subscription to Massive's options feed. "
                "Subscriptions persist across restarts. Use this when Jeffery asks you to "
                "watch a ticker, contract, or the chain.\n"
                "channel: 'T' (trades) | 'Q' (quotes) | 'A' (per-second aggs) | "
                "'AM' (per-minute aggs) | 'FMV' (fair market value)\n"
                "symbol: '*' for all, 'O:SPY*' for all SPY options, or a specific "
                "options ticker like 'O:SPY260620C00500000'. The Q channel is capped at "
                "1000 contracts per connection — prefer 'AM' or specific contracts for "
                "broad SPY/QQQ watches.\n"
                "Returns the subscription_id which you pass to add_alert_rule. After "
                "subscribing, attach at least one rule, otherwise data streams in but "
                "nothing alerts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "enum": ["T", "Q", "A", "AM", "FMV"],
                        "description": "Channel code.",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Symbol pattern. '*', 'O:SPY*', or full options ticker.",
                    },
                    "note": {
                        "type": "string",
                        "description": "Optional reason (for audit; not sent to Massive).",
                    },
                },
                "required": ["channel", "symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_alert_rule",
            "description": (
                "Attach an alert rule to an existing subscription. When the rule fires "
                "HAL interrupts whatever is happening and speaks the alert to Jeffery.\n"
                "rule_type:\n"
                "- 'pct_move': fires when price moves threshold_pct from baseline. "
                "config={'threshold_pct': 1.0, 'direction': 'up'|'down'|'any'}\n"
                "- 'price_cross': fires when price crosses an absolute level. "
                "config={'price': 500.0, 'direction': 'above'|'below'|'any'}\n"
                "- 'volume': fires on any trade of at least min_size. Only valid on 'T' "
                "subscriptions. config={'min_size': 10000}\n"
                "cooldown_seconds suppresses re-firing within that window (default 60). "
                "Baselines for pct_move are captured at the first tick after rule "
                "creation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "subscription_id": {
                        "type": "integer",
                        "description": "ID returned by subscribe_market.",
                    },
                    "rule_type": {
                        "type": "string",
                        "enum": ["pct_move", "price_cross", "volume"],
                    },
                    "config": {
                        "type": "object",
                        "description": "Rule-specific configuration; see rule_type list.",
                    },
                    "note": {"type": "string"},
                    "cooldown_seconds": {
                        "type": "number",
                        "description": "Minimum seconds between fires. Default 60.",
                    },
                },
                "required": ["subscription_id", "rule_type", "config"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_subscriptions",
            "description": (
                "List active WebSocket subscriptions and their attached alert rules. "
                "Also reports whether the upstream socket is currently authed."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unsubscribe",
            "description": "Deactivate a subscription (cascades to all its rules).",
            "parameters": {
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "integer"},
                },
                "required": ["subscription_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_rule",
            "description": "Deactivate a single alert rule without touching its subscription.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "integer"},
                },
                "required": ["rule_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_alert_history",
            "description": "List recent alert fires (most recent first). Useful for 'what alerts have fired today'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max events to return (default 20).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screen_options",
            "description": (
                "Filtered options-chain candidates for an underlying. Returns flat "
                "rows (strike, bid/ask/mid, IV, delta, gamma, theta, vega, OI, "
                "volume, spread%) for contracts matching your filters. Prefer this "
                "over query_massive when you need to pick specific contracts — it "
                "applies the filters server-side and locally so you don't have to "
                "page through hundreds of rows in context.\n"
                "delta_min/delta_max: signed deltas (calls 0..1, puts -1..0). For "
                "short put credit spreads target delta_min=-0.25, delta_max=-0.10. "
                "For directional debit calls try 0.40..0.60. "
                "max_spread_pct: filter illiquid contracts (e.g. 10 = bid/ask <= 10% "
                "of mid). min_oi: filter low open interest. sort_by: 'abs_delta' "
                "(default), 'mid', 'oi', 'theta', 'iv'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "underlying": {"type": "string", "description": "e.g. 'SPY'"},
                    "side": {"type": "string", "enum": ["call", "put"]},
                    "dte_min": {"type": "integer", "description": "Default 0."},
                    "dte_max": {"type": "integer", "description": "Default 60."},
                    "delta_min": {"type": "number"},
                    "delta_max": {"type": "number"},
                    "min_oi": {"type": "integer"},
                    "max_spread_pct": {"type": "number"},
                    "strike_min": {"type": "number"},
                    "strike_max": {"type": "number"},
                    "top_n": {"type": "integer", "description": "Default 15."},
                    "sort_by": {
                        "type": "string",
                        "enum": ["abs_delta", "mid", "oi", "theta", "iv"],
                    },
                },
                "required": ["underlying", "side"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_webull",
            "description": (
                "Open Webull in Jeffery's default browser at a specific page. "
                "Use this after recommending a trade so Jeffery can review and "
                "execute in Webull itself — HAL does NOT place orders directly. "
                "Also use when he asks 'show me my positions', 'pull up SPY on "
                "Webull', or wants to see the options chain in the UI.\n"
                "action:\n"
                "- 'positions' / 'portfolio' — current holdings + P&L\n"
                "- 'orders' — order center / recent fills\n"
                "- 'watchlist' — his watchlist\n"
                "- 'alerts' — Webull's alert center\n"
                "- 'screener' — Webull screener\n"
                "- 'trade' — main trading screen\n"
                "- 'account' — account info\n"
                "- 'quote' — quote page for the given ticker (requires ticker)\n"
                "- 'option_chain' — options chain for the given ticker (requires ticker)\n"
                "Web app pages require Jeffery to be logged in; the browser "
                "session handles that."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "positions",
                            "portfolio",
                            "orders",
                            "watchlist",
                            "alerts",
                            "screener",
                            "trade",
                            "account",
                            "quote",
                            "option_chain",
                        ],
                    },
                    "ticker": {
                        "type": "string",
                        "description": "Required for 'quote' and 'option_chain'.",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "iv_context",
            "description": (
                "Volatility context for the underlying: current ATM implied vol "
                "compared to realized vol over 10/30/60/90 trading days. Returns "
                "a verdict (RICH / FAIR / CHEAP) based on IV / HV30. Use this "
                "BEFORE choosing premium-selling vs premium-buying. "
                "RICH (IV/HV30 >= 1.30) favors selling premium; CHEAP (< 0.90) "
                "favors buying. Note: this is implied-vs-realized, not classical "
                "52-week IV rank."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "underlying": {"type": "string", "description": "e.g. 'SPY'"},
                },
                "required": ["underlying"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_strategy",
            "description": (
                "Recommend ranked option strategies for a directional bias and an "
                "implied-vol regime, with plain-English rationale, risk level, and "
                "(when current_price is given) the concrete legs to structure each. "
                "Ported from Jeffery's TradeScan strategy screener — purely "
                "algorithmic, no API call.\n"
                "WORKFLOW: this is the 'what should I trade and how do I build it' "
                "brain. Get the vol read from iv_context first, then call this with "
                "the bias and IV. It does NOT pick live contracts — pass its leg "
                "structure to screen_options to find the actual strikes/premium.\n"
                "bias: 'auto' (derive from change_percent), 'bullish', 'bearish', "
                "'neutral'.\n"
                "iv: implied vol as a decimal (0.25 = 25%); classified low (<0.20) / "
                "medium (0.20-0.40) / high (>0.40). Or pass iv_level directly.\n"
                "Returns the top 3 strategies for that bias x IV cell."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "underlying": {
                        "type": "string",
                        "description": "Ticker, e.g. 'SPY' (for labeling).",
                    },
                    "bias": {
                        "type": "string",
                        "enum": ["auto", "bullish", "bearish", "neutral"],
                        "description": "Directional view. 'auto' derives from change_percent.",
                    },
                    "change_percent": {
                        "type": "number",
                        "description": "Daily % change; used only when bias='auto'.",
                    },
                    "iv": {
                        "type": "number",
                        "description": "ATM implied vol as a decimal (0.25 = 25%).",
                    },
                    "iv_level": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "unknown"],
                        "description": "Pass directly to skip IV classification; overrides iv.",
                    },
                    "current_price": {
                        "type": "number",
                        "description": "Underlying spot; when given, returns concrete legs.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_view",
            "description": (
                "Open a view inside Jeffery's HAL interface (the immersive backdrop). "
                "Use this to ACTIVELY SHOW him things instead of just describing — when "
                "he asks 'show me a map of X', 'what does X look like', 'pull up the "
                "camera', 'share my screen', etc., call this instead of describing. "
                "Once opened, Jeffery sees it directly; do not describe what it looks "
                "like — he is looking at it.\n"
                "Kinds:\n"
                "- 'map'    — opens Google Maps embed. Requires 'query' (address, place, or 'lat,lng').\n"
                "- 'camera' — opens his rear/front camera live feed.\n"
                "- 'screen' — prompts him to pick a screen/window to share.\n"
                "- 'video'  — opens an external mp4/webm URL. Requires 'query' (the URL).\n"
                "- 'off'    — closes the immersive view entirely.\n"
                "Returns a short confirmation string."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["map", "camera", "screen", "video", "off"],
                    },
                    "query": {
                        "type": "string",
                        "description": (
                            "For 'map': address / place / 'lat,lng'. "
                            "For 'video': the URL. Omit for camera, screen, off."
                        ),
                    },
                },
                "required": ["kind"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_chart",
            "description": (
                "Render an interactive candlestick chart INSIDE Jeffery's HAL "
                "interface so he can see a technical setup instead of just hearing "
                "it described. Use this whenever you reference a chart, a level, a "
                "trend, a breakout, or 'what X looks like' on a ticker — pull it up "
                "for him. The chart shows candles, volume, a SuperTrend overlay, and "
                "Buy/Sell flip markers. Once shown, do NOT describe the candles bar "
                "by bar — he is looking at it; just make your point about the setup.\n"
                "symbol: underlying ticker (e.g. 'SPY', 'NVDA').\n"
                "timeframe: 1m,2m,5m,15m,30m,1h,4h,1d,1w (default 5m)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Underlying ticker, e.g. 'SPY'.",
                    },
                    "timeframe": {
                        "type": "string",
                        "description": "Bar size: 1m,2m,5m,15m,30m,1h,4h,1d,1w. Default 5m.",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
]
