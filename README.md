# Anton — AI Voice Assistant

> *"Sometimes you gotta run before you can walk."*
> Your personal Tony Stark-style AI, running locally on your Mac.

Anton is a fully voice-driven AI assistant built on **OpenAI GPT-4o**, **Sarvam speech recognition**, and **LiveKit**. Two claps wake it up. You talk. It acts — controlling your calendar, email, Spotify, Mac system, memory vault, and more. No touch required.

---

## What is Anton?

Anton is inspired by J.A.R.V.I.S. / F.R.I.D.A.Y. from Iron Man. It runs as two cooperating processes on your Mac:

1. **MCP Tool Server** (`server.py`) — a [FastMCP](https://github.com/jlowin/fastmcp) server that exposes all of Anton's capabilities as tools over SSE at `http://127.0.0.1:8000`.
2. **Voice Agent** (`agent_anton.py`) — a [LiveKit Agents](https://docs.livekit.io/agents/) pipeline that listens to your voice, thinks with GPT-4o, and speaks back with OpenAI TTS.

A third process, the **Wake Listener** (`wake.py`), runs silently in the background at all times and launches the voice agent when it detects two claps followed by "wake up Anton."

---

## Architecture

```
                          ┌─────────────────────────────────┐
                          │        MCP Tool Server           │
Microphone                │  (FastMCP · SSE · port 8000)    │
    │                     │                                  │
    ▼                     │  ├─ 🌤  Weather (OpenWeatherMap) │
Sarvam STT ──────────────▶│  ├─ 📅  Google Calendar         │
(Saaras v3)               │  ├─ 📧  Gmail                   │
    │                     │  ├─ 🎵  Spotify                  │
    ▼                     │  ├─ 🎬  YouTube                  │
OpenAI GPT-4o ◀──────────▶│  ├─ 🖥  System Control (macOS)  │
(gpt-4o)                  │  ├─ 🧠  Obsidian Memory          │
    │                     │  ├─ 📰  World News (RSS)         │
    ▼                     │  ├─ 🌅  Morning Briefing         │
OpenAI TTS                │  └─ ⏰  Time & Date              │
(nova · 1.15×)            └─────────────────────────────────┘
    │
    ▼
 Speaker
```

**Boot flow:**
```
macOS login
    └─▶ LaunchAgent loads wake.py (always-on, ~0% CPU)
             └─▶ 👏👏 + "wake up Anton"
                      └─▶ uv run anton       (MCP server starts)
                      └─▶ uv run anton_voice (voice agent starts)
                               └─▶ LiveKit room joins
                                        └─▶ Anton says hello
```

---

## Full Capabilities

### 🌤️ Weather
Powered by [OpenWeatherMap API](https://openweathermap.org/api).

| Say this | Anton responds |
|----------|----------------|
| "What's the weather in Bangalore?" | "Currently 28°C in Bangalore, India — feels like 30°C. Haze, humidity at 72%, winds at 11 km/h." |
| "Weekly forecast for Mumbai" | "5-day forecast for Mumbai, IN: Mon 14 Apr: 27–31°C, Haze. Tue 15 Apr: 26–30°C, Light rain..." |

---

### 📅 Google Calendar
Full read and write access to your primary Google Calendar.

| Say this | Anton responds |
|----------|----------------|
| "What's on my calendar today?" | "You have 3 events today, sir. First up — Team Standup at 10:00 AM." |
| "What do I have this week?" | "Upcoming events over the next 7 days, sir: Today: Standup at 10 AM. Tomorrow: Gym at 7 AM..." |
| "Schedule Product Review tomorrow at 3pm" | "Done, sir. 'Product Review' has been added to your calendar at 3:00 PM on Friday, 17 Apr for 60 minutes." |
| "Add gym on Friday at 7am for 45 minutes" | "Done, sir. 'Gym' has been added to your calendar at 7:00 AM on Friday, 17 Apr for 45 minutes." |

> Natural date inputs like "tomorrow", "Friday", "next Monday" are auto-resolved. Times like "3pm" or "9:00 PM" are auto-converted to 24-hour format.

---

### 📧 Gmail
Read, search, draft, and send emails via Gmail API.

| Say this | Anton responds |
|----------|----------------|
| "Any new emails?" | "5 unread emails, sir. Top one from Sagar — subject: Project Update. Quick note about the sprint..." |
| "Search for emails from Sagar" | "Found 3 result(s) for 'from:Sagar', sir: 1. From Sagar — Project Update..." |
| "Draft an email to Sagar about the meeting" | "Draft saved, sir. To: sagar@email.com — Subject: 'Meeting'. Sitting in your Drafts folder." |
| "Send an email to Sagar saying I'll be late" | "Sent, sir. Email to sagar@email.com delivered successfully." |

> `send_email` sends immediately. Use `draft_email` if you want to review first.

---

### 🎵 Spotify
Full playback control. **Requires Spotify Premium.**

| Say this | Anton responds |
|----------|----------------|
| "Play Blinding Lights" | "Now playing Blinding Lights by The Weeknd, sir." |
| "Play my chill playlist" | "Now playing the 'Chill Vibes' playlist, sir." |
| "Pause" | "Paused. Resume anytime, sir." |
| "Next song" | "Skipped. Moving on, sir." |
| "Go back" | "Going back to the previous track, sir." |
| "What's playing?" | "Playing Blinding Lights by The Weeknd, sir. (2:14 / 3:22)" |
| "Volume to 60" | "Volume set to 60%, sir." |

---

### 🎬 YouTube
Opens the exact top result using the **YouTube Data API v3** — no search page, straight to the video.

| Say this | Anton responds |
|----------|----------------|
| "Play Interstellar OST on YouTube" | "Opening Interstellar OST on YouTube for you, sir." |
| "Put on lo-fi hip hop" | "Opening lo-fi hip hop on YouTube for you, sir." |

---

### 🖥️ System Control
Native macOS controls — no third-party apps needed.

| Say this | Anton responds |
|----------|----------------|
| "Lock my screen" | "Screen locked, sir." |
| "Battery status" | "Battery at 87%, discharging, on battery." |
| "Take a screenshot" | "Screenshot saved to your Desktop as anton_2026-04-16_14-00-00.png, sir." |
| "How's the system?" | "CPU is at 23%, sir. You're using 6.2GB of your 16GB RAM. Disk has 45GB free." |
| "What's the volume?" | "System volume is at 60%, sir." |
| "Set volume to 80" | "Volume set to 80%, sir." |
| "Open Spotify" | "Opening Spotify, sir." |
| "What Wi-Fi am I on?" | "Connected to 'HomeNetwork', sir. Signal is excellent (-38 dBm)." |

---

### 🧠 Obsidian Memory
Anton remembers things across sessions by writing to an [Obsidian](https://obsidian.md) vault. Pure markdown files — no plugins needed.

**Vault structure Anton maintains:**
```
Anton brain/
├── ANTON.md           ← vault schema / Anton's instructions
├── people/            ← notes about people
├── projects/          ← project notes and ideas
├── topics/            ← articles and general knowledge
├── preferences/       ← user preferences and settings
└── daily/             ← daily notes (YYYY-MM-DD.md)
```

| Say this | Anton responds |
|----------|----------------|
| "Remember that Sagar is my college friend from Manipal" | "Noted, sir. I've created my memory on Sagar." |
| "What do you know about Sagar?" | "Here's what I know about Sagar, sir: # Sagar — Sagar is my college friend from Manipal..." |
| "Create a note called Project Ideas" | "Note 'Project Ideas' created in topics/, sir." |
| "Add to project ideas: build a habit tracker" | "Added to 'Project Ideas', sir." |
| "Search my notes for habit tracker" | "Found 'habit tracker' in 1 note(s), sir: projects/project_ideas.md: - build a habit tracker" |
| "What's in my daily note?" | "Today's note, sir: # Daily Note — Wednesday, 16 April 2026..." |
| "Add to today's note: finished the Spotify integration" | "Added to today's note, sir." |

---

### 📰 World News
Aggregates live headlines from BBC World, CNBC, NYT, and Al Jazeera simultaneously.

| Say this | Anton responds |
|----------|----------------|
| "Brief me on the news" | Anton delivers a 3–5 sentence spoken brief of the biggest stories, then opens [World Monitor](https://worldmonitor.app) automatically. |
| "What's happening in the world?" | Same as above — news brief + world monitor. |

---

### 🌅 Morning Briefing
One command — weather, calendar, email, and news all at once, assembled concurrently.

| Say this | Anton responds |
|----------|----------------|
| "Morning briefing" | "Good morning, sir. It's Wednesday, 16th April, 8:00 AM IST. Weather: 24°C in Bangalore, partly cloudy. Calendar: 3 events today. First up — Standup at 10 AM. Emails: 5 unread. Top one from Sagar — Project Update. Top headlines: 1. [headline]... Have a productive day, sir." |

Closing line adapts by time of day: *"Have a productive day"* (morning) / *"Have a great afternoon"* (afternoon) / *"Have a good evening"* (evening) / *"Get some rest when you can"* (late night).

---

### ⏰ Time & Date
Anton always knows the exact date, time, and time-of-day context — injected dynamically into every session.

| Say this | Anton responds |
|----------|----------------|
| "What time is it?" | "It's 2:08 PM, sir." |
| "What's today's date?" | "Today is Wednesday, 16th April 2026, sir." |

---

### 😴 Sleep / Shutdown

| Say this | Anton responds |
|----------|----------------|
| "Goodnight Anton" / "Sleep" / "Bye" | "Going to sleep. I'll be standing by when you need me, boss." |
| "Sleep and shut down my Mac" | "Shutting everything down and putting the system to sleep. Goodnight, boss." |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **LLM (Brain)** | OpenAI GPT-4o |
| **Speech-to-Text** | Sarvam Saaras v3 |
| **Text-to-Speech** | OpenAI TTS — voice: `nova`, speed: 1.15× |
| **Voice Activity Detection** | Silero VAD |
| **Wake Detection** | faster-whisper `tiny.en` + RMS clap detection |
| **Voice Pipeline** | LiveKit Agents |
| **Tool Protocol** | FastMCP over SSE |
| **Calendar / Gmail** | Google API Python Client + OAuth2 |
| **Spotify** | Spotipy (Spotify Web API) |
| **YouTube** | YouTube Data API v3 |
| **System Info** | psutil |
| **Memory / Notes** | Obsidian vault (plain markdown) |
| **Package Manager** | uv |
| **Language** | Python ≥ 3.11 |

---

## Prerequisites

- **macOS** (Sonoma recommended; Apple Silicon supported)
- **Python 3.11+**
- **uv** — install with:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **LiveKit Cloud account** — [cloud.livekit.io](https://cloud.livekit.io) (free tier works)
- **OpenAI API key** — [platform.openai.com](https://platform.openai.com/api-keys)
- **Sarvam AI API key** — [dashboard.sarvam.ai](https://dashboard.sarvam.ai)

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/nirxnjxnCodeS/Anton-Voice-assistant.git
cd Anton-Voice-assistant

# 2. Install all dependencies
uv sync

# 3. Copy the env template
cp .env.example .env
# Now fill in your keys — see Environment Setup below
```

---

## Environment Setup

Copy `.env.example` to `.env` and fill in the values.

| Variable | Required | What it's for | Where to get it |
|----------|----------|---------------|-----------------|
| `LIVEKIT_URL` | ✅ | LiveKit Cloud room URL | [cloud.livekit.io](https://cloud.livekit.io) → your project |
| `LIVEKIT_API_KEY` | ✅ | LiveKit auth key | Same project settings |
| `LIVEKIT_API_SECRET` | ✅ | LiveKit auth secret | Same project settings |
| `OPENAI_API_KEY` | ✅ | GPT-4o (brain) + TTS (voice) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `SARVAM_API_KEY` | ✅ | Speech-to-text (Saaras v3) | [dashboard.sarvam.ai](https://dashboard.sarvam.ai) |
| `OPENWEATHER_API_KEY` | ⚠️ | Weather tools | [openweathermap.org/api](https://openweathermap.org/api) — free tier |
| `GOOGLE_CREDENTIALS_FILE` | ⚠️ | Path to OAuth credentials JSON | See Google Cloud Setup below |
| `TIMEZONE` | ⚠️ | Your local timezone (IANA format) | e.g. `Asia/Kolkata` |
| `SPOTIFY_CLIENT_ID` | ⚠️ | Spotify playback tools | See Spotify Setup below |
| `SPOTIFY_CLIENT_SECRET` | ⚠️ | Spotify playback tools | See Spotify Setup below |
| `SPOTIFY_REDIRECT_URI` | ⚠️ | Spotify OAuth callback | Set to `http://localhost:8888/callback` |
| `YOUTUBE_API_KEY` | ⚠️ | YouTube direct video open | See YouTube API Setup below |
| `OBSIDIAN_VAULT_PATH` | ⚠️ | Path to your Obsidian vault folder | e.g. `/Users/you/Documents/Anton brain` |
| `HOME_CITY` | ⚠️ | Default city for morning briefing weather | e.g. `Bangalore` |

✅ Required for Anton to start &nbsp;&nbsp; ⚠️ Required for that specific feature set

---

## Google Cloud Setup

Needed for **Calendar** and **Gmail** tools.

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create a project named "Anton"
2. **APIs & Services → Library** → enable:
   - **Google Calendar API**
   - **Gmail API**
   - **YouTube Data API v3** (while you're here)
3. **OAuth consent screen** → External → add your Gmail as a test user
4. **Credentials → Create Credentials → OAuth client ID** → Desktop app → download JSON
5. Rename the downloaded file to `credentials.json` and place it in the project root
6. First run opens a browser for consent → `token.json` is saved → all future runs are silent

> `credentials.json` and `token.json` are in `.gitignore` — never commit them.

---

## Spotify Setup

Requires **Spotify Premium** for playback control.

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Create an app → Settings → add `http://localhost:8888/callback` as a Redirect URI
3. Copy **Client ID** and **Client Secret** into `.env`
4. First run opens a browser for login → paste the redirect URL into the terminal → token cached to `.spotify_cache`

---

## YouTube API Setup

1. In your Google Cloud project → **APIs & Services → Library** → enable **YouTube Data API v3**
2. **Credentials → Create Credentials → API key** → copy into `.env` as `YOUTUBE_API_KEY`

---

## Obsidian Setup

1. Create a folder anywhere on your Mac — e.g. `~/Documents/Anton brain`
2. Set `OBSIDIAN_VAULT_PATH=/Users/you/Documents/Anton brain` in `.env`
3. Anton auto-creates the full folder structure on first use
4. Optionally open the folder as an Obsidian vault to browse Anton's notes visually

---

## Running Anton

Anton needs **two processes** running simultaneously:

**Terminal 1 — MCP Tool Server:**
```bash
uv run anton
```
> Starts the FastMCP server at `http://127.0.0.1:8000/sse`. Keep this running.

**Terminal 2 — Voice Agent:**
```bash
uv run anton_voice
```
> Connects to LiveKit. Open [agents-playground.livekit.io](https://agents-playground.livekit.io), connect to your project, and start talking.

---

## Wake System

The wake listener runs silently at all times — essentially zero CPU — and activates Anton on a two-clap + phrase pattern.

**How it works:**

```
Always listening (idle, <1% CPU)
        │
        ▼
  👏  Clap 1 detected  (RMS spike > 6× background noise floor)
        │
        ▼
  👏  Clap 2 within 2 seconds
        │
        ▼
  🎙️  3-second phrase window opens
        │
        ▼
  "Wake up Anton"  ──────▶  🔔 Chime plays
                                   │
                                   ▼
                            uv run anton_voice
                                   │
                                   ▼
                            Anton comes alive
```

Wake detection uses **faster-whisper** (`tiny.en`, ~75 MB, auto-downloaded on first run). Clap detection is pure RMS energy — fully local, no cloud calls.

**Run manually:**
```bash
uv run wake
```

**Run as a macOS LaunchAgent (starts automatically at login):**

```bash
# Install
cp com.niranjan.anton.wake.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.niranjan.anton.wake.plist

# Verify it's running
launchctl list | grep anton

# View logs
tail -f ~/Library/Logs/anton-wake.log

# Stop
launchctl unload ~/Library/LaunchAgents/com.niranjan.anton.wake.plist
```

---

## Project Structure

```
Anton Voice Agent/
├── agent_anton.py                  # Voice agent — STT → LLM → TTS pipeline
├── server.py                       # FastMCP tool server entry point
├── wake.py                         # Always-on clap + phrase wake listener
├── launch_wake.sh                  # Shell script to start both processes
├── com.niranjan.anton.wake.plist   # macOS LaunchAgent config
├── start.md                        # Quick-start reference
├── pyproject.toml                  # Dependencies and scripts (uv)
├── .env.example                    # Environment variable template
│
└── anton/
    ├── config.py                   # Centralised env var loading
    ├── google_auth.py              # Shared Google OAuth2 (Calendar + Gmail)
    │
    └── tools/
        ├── __init__.py             # Tool registry
        ├── weather.py              # OpenWeatherMap — current + forecast
        ├── calendar.py             # Google Calendar — schedule + create
        ├── gmail.py                # Gmail — read, search, draft, send
        ├── spotify.py              # Spotify — full playback control
        ├── system_control.py       # macOS — lock, battery, volume, apps, YouTube
        ├── obsidian.py             # Obsidian vault — persistent memory
        ├── briefing.py             # Morning briefing — concurrent fan-out
        ├── web.py                  # World news (RSS) + world monitor
        ├── system.py               # Time, date, host platform info
        ├── sleep.py                # Anton shutdown / Mac sleep
        └── utils.py                # JSON formatter, word counter
```

---

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feat/your-tool`
3. Follow the `register(mcp)` pattern used in any existing tool file
4. Register your module in `anton/tools/__init__.py`
5. Open a PR

---

*Built by [Niranjan](https://github.com/nirxnjxnCodeS). Inspired by Tony Stark's belief that the best tool is the one that works exactly when you need it.*
