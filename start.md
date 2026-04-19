# Anton — Start Guide

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Node.js 18+ & npm
- [Homebrew](https://brew.sh) (for PortAudio: `brew install portaudio`)
- A LiveKit Cloud account — [cloud.livekit.io](https://cloud.livekit.io)

---

## First Time Setup

```bash
# 1. Clone and enter
git clone <repo-url> "Anton Voice Agent"
cd "Anton Voice Agent"

# 2. Install Python deps
uv sync

# 3. Environment
cp .env.example .env
# Fill in all keys: LIVEKIT_*, OPENAI_API_KEY, SARVAM_API_KEY,
# SPOTIFY_*, OPENWEATHER_API_KEY, GOOGLE_API_KEY, SUPABASE_*

# 4. Google OAuth — place credentials.json in project root, then:
uv run python -c "from anton.google_auth import get_google_service; get_google_service('calendar', 'v3')"
# Browser opens → approve → token.json is written

# 5. Spotify first auth
uv run python -c "import spotipy; from spotipy.oauth2 import SpotifyOAuth; spotipy.Spotify(auth_manager=SpotifyOAuth(scope='user-modify-playback-state user-read-playback-state'))"
# Browser opens → approve → .spotify_cache is written

# 6. UI deps
cd ui && npm install && cd ..

# 7. Whisper model (auto-downloads ~75 MB on first wake run — nothing to do manually)

# 8. LaunchAgent (optional — lets wake start automatically at login)
cp ~/Library/LaunchAgents/com.niranjan.anton.wake.plist ~/Library/LaunchAgents/  # already there if you set it up
# See "Full Manual Startup" if the plist gives I/O errors
```

---

## Daily Startup (Quick)

**3 terminals:**

```bash
# Terminal 1 — MCP tool server (port 8000)
uv run anton

# Terminal 2 — Voice agent (connects to LiveKit room)
uv run anton_voice

# Terminal 3 — UI (Vite + token server, ports 3000 & 3001)
cd ui && npm start
```

Then open **http://localhost:3000**

**Wake via LaunchAgent instead of Terminal 2:**
```bash
launchctl load ~/Library/LaunchAgents/com.niranjan.anton.wake.plist
```
This auto-starts `uv run wake` and keeps it alive (restart on crash, logs to `~/Library/Logs/anton-wake.log`).

---

## Full Manual Startup

```bash
# MCP server
uv run anton

# Wake word listener (spawns + manages the voice agent via SIGSTOP/SIGCONT)
uv run wake

# UI
cd ui && npm start
```

**Wake word flow:**
```
👏  Clap once
👏  Clap twice (within 2 seconds)
🗣️  Say "wake up Anton" (within 3 seconds)
✅  Chime plays → Anton wakes
```
When the session ends, wake.py automatically suspends the agent again — ready for the next clap sequence.

**Watch wake logs (LaunchAgent mode):**
```bash
tail -f ~/Library/Logs/anton-wake.log
```

---

## Stopping Anton

```bash
# Kill wake listener
pkill -f wake.py

# Kill voice agent
pkill -f anton_voice

# Kill by port if needed
lsof -ti:8000 | xargs kill -9   # MCP server
lsof -ti:3000 | xargs kill -9   # Vite UI
lsof -ti:3001 | xargs kill -9   # Token server

# Unload LaunchAgent
launchctl unload ~/Library/LaunchAgents/com.niranjan.anton.wake.plist
```

**Restart LaunchAgent:**
```bash
launchctl unload ~/Library/LaunchAgents/com.niranjan.anton.wake.plist 2>/dev/null \
  && 
launchctl load ~/Library/LaunchAgents/com.niranjan.anton.wake.plist
```

---

## Troubleshooting

**Port 8000 already in use**
```bash
lsof -ti:8000 | xargs kill -9
```

**Port 3000 or 3001 already in use**
```bash
lsof -ti:3000 | xargs kill -9
lsof -ti:3001 | xargs kill -9
```

**LaunchAgent: `Load failed: Input/output error`**
→ Skip the plist entirely, use `uv run wake` directly in a terminal.

**Wake word not triggering**
```bash
ps aux | grep wake.py   # confirm it's running
# Check mic permissions: System Settings → Privacy → Microphone
# Clap louder — threshold requires a sharp transient, not just loud noise
```

**UI shows "connecting to room" forever**
→ Make sure `uv run anton_voice` (or `uv run wake` after clap) is running and connected to LiveKit.

**Google OAuth expired / 401 errors**
```bash
rm token.json
uv run python -c "from anton.google_auth import get_google_service; get_google_service('calendar', 'v3')"
```

**Spotify not playing**
→ Open the Spotify desktop app first (playback requires an active device).
→ If auth is stale: `rm .spotify_cache` and re-auth (step 5 above).

**Anton says meeting scheduled but it's not in Calendar**
→ Date/time format issue — always say dates explicitly ("April 20th at 3pm") rather than relative ("next Sunday").

**`Tool already exists: get_system_info` warning in logs**
→ Safe to ignore — duplicate registration warning from FastMCP, no functional impact.

**Whisper model missing / wake crashes on startup**
→ Let `uv run wake` run to completion once — it auto-downloads `tiny.en` (~75 MB) on first run.

---

## Port Reference

| Port | Service                        |
|------|--------------------------------|
| 8000 | MCP Server (FastMCP / SSE)     |
| 3000 | Anton UI (Vite dev server)     |
| 3001 | Token Server (Express / LiveKit JWT) |
