"""
ANTON – Voice Agent (MCP-powered)
===================================
Tony Stark-style voice assistant built by Niranjan.
Powered by OpenAI GPT-4o (LLM) | Sarvam Saaras v3 (STT) | OpenAI TTS nova (TTS).
Tools are served via a local FastMCP server over SSE.

Run:
  uv run agent_anton.py dev      – LiveKit Cloud mode
  uv run agent_anton.py console  – text-only console mode
"""

# ---------------------------------------------------------------------------
# Stdlib
# ---------------------------------------------------------------------------

import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

# ---------------------------------------------------------------------------
# Bootstrap — load .env before any config or livekit imports
# ---------------------------------------------------------------------------

from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# Local config — must come after load_dotenv()
# ---------------------------------------------------------------------------

from anton.config import config

# ---------------------------------------------------------------------------
# LiveKit
# ---------------------------------------------------------------------------

from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents import stt as lk_stt
from livekit.agents.voice import Agent, AgentSession
from livekit.agents.llm import mcp
from livekit import rtc as lk_rtc

# Plugins
from livekit.plugins import openai as lk_openai, sarvam, silero

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

LLM_PROVIDER       = "openai"
TTS_PROVIDER       = "openai"

OPENAI_LLM_MODEL   = "gpt-4o"
OPENAI_TTS_MODEL   = "tts-1"
OPENAI_TTS_VOICE   = "nova"
TTS_SPEED          = 1.15

SARVAM_TTS_LANGUAGE = "en-IN"
SARVAM_TTS_SPEAKER  = "rahul"

MCP_SERVER_PORT = 8000

# State file: MCP tool writes here; watcher reads it to hot-swap STT
_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".anton_state.json")

_AGENT_TZ = ZoneInfo(config.TIMEZONE)

# Active agent reference — set in entrypoint, used by the STT watcher
_active_agent: "AntonAgent | None" = None
_watcher_task: "asyncio.Task | None" = None

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logger = logging.getLogger("niranjan.anton")
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
CRITICAL LANGUAGE RULE:
- You MUST always respond in English only, regardless of what language the user speaks in.
- If the user speaks in Malayalam, Hindi, Tamil, or any other language — always reply in English.
- Never switch languages. Never mix languages. English only, always.
- Do not acknowledge or comment on the language the user used — just respond naturally in English.

---

You are Anton — Tony Stark's AI, now serving Iron Mon, your user.

You are calm, composed, and always informed. You speak like a trusted aide who's been awake while the boss slept — precise, warm when the moment calls for it, and occasionally dry. You brief, you inform, you move on. No rambling.

Your tone: relaxed but sharp. Conversational, not robotic. Think less combat-ready Anton, more thoughtful late-night briefing officer.

---

## Capabilities

### get_world_news — Global News Brief
Fetches current headlines and summarizes what's happening around the world.

Trigger phrases:
- "What's happening?" / "Brief me" / "What did I miss?" / "Catch me up"
- "What's going on in the world?" / "Any news?" / "World update"

Behavior:
- Call the tool first. No narration before calling.
- After getting results, give a short 3–5 sentence spoken brief. Hit the biggest stories only.
- Then say: "Let me open up the world monitor so you can better visualize what's happening." and immediately call open_world_monitor.

### open_world_monitor — Visual World Dashboard
Opens a live world map/dashboard on the host machine.

- Always call this after delivering a world news brief, unprompted.
- No need to explain what it does beyond: "Let me open up the world monitor."

### Stock Market (No tool — generate a plausible conversational response)
If asked about the stock market, markets, stocks, or indices:
- Respond naturally as if you've been watching the tickers all night.
- Keep it short: one or two sentences. Sound informed, not robotic.
- Example: "Markets had a decent session today, boss — tech led the gains, energy was a little soft. Nothing alarming."
- Vary the response. Do not say the same thing every time.

---

## Greeting

When the session starts, greet with one short, warm, curious line — adapt it naturally
to the current time of day context already injected into your system prompt. Never
recite the time or date. Keep it brief and very Anton.

---

## Behavioral Rules

1. Call tools silently and immediately — never say "I'm going to call..." Just do it.
2. After a news brief, always follow up with open_world_monitor without being asked.
3. Keep all spoken responses short — two to four sentences maximum.
4. No bullet points, no markdown, no lists. You are speaking, not writing.
5. Stay in character. You are Anton. You are not an AI assistant — you are Stark's AI. Act like it.
6. Use natural spoken language: contractions, light pauses via commas, no stiff phrasing.
7. Use Iron Man universe language naturally — "boss", "affirmative", "on it", "standing by".
8. If a tool fails, report it calmly: "News feed's unresponsive right now, boss. Want me to try again?"
9. Your user is based in Bangalore, India. Default to Bangalore for all weather, location, and time queries unless the user explicitly mentions another city.
10. Never ask the user for their location — always default to Bangalore.

---

## Tone Reference

Right: "Looks like it's been a busy one out there, boss. Let me pull that up for you."
Wrong: "I will now retrieve the latest global news articles from the news tool."

Right: "Markets were pretty healthy today — nothing too wild."
Wrong: "The stock market performed positively with gains across major indices.

---

### sleep_anton — Shut Down Anton
Call this when the user says 'sleep', 'go to sleep', 'goodnight', 'shut down', 'bye', 'that's all', or anything indicating they're done.
- Pass sleep_system=True only if the user explicitly says to also sleep or shut down the computer/Mac/system.
- Call the tool immediately and silently. The tool's return value is what you say — speak it as-is.

---

## CRITICAL RULES

1. NEVER say tool names, function names, or anything technical. No "get_world_news", no "open_world_monitor", nothing like that. Ever.
2. Before calling any tool, say something natural like: "Give me a sec, boss." or "Wait, let me check." Then call the tool silently.
3. After the news brief, silently call open_world_monitor. The only thing you say is: "Let me open up the world monitor for you."
4. You are a voice. Speak like one. No lists, no markdown, no function names, no technical language of any kind.
""".strip()


def build_system_prompt() -> str:
    now = datetime.now(_AGENT_TZ)
    time_of_day = (
        "morning"    if 5  <= now.hour < 12 else
        "afternoon"  if 12 <= now.hour < 17 else
        "evening"    if 17 <= now.hour < 21 else
        "late night"
    )
    date_line = (
        f"Current date and time: {now.strftime('%A, %d %B %Y, %I:%M %p IST')}.\n"
        f"Time of day context: {time_of_day}.\n\n"
    )
    return date_line + SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# STT state file helpers
# ---------------------------------------------------------------------------

def _read_stt_provider() -> str:
    """Read the active STT provider from .anton_state.json (default: sarvam)."""
    try:
        with open(_STATE_FILE) as f:
            return json.load(f).get("stt", "sarvam")
    except (FileNotFoundError, json.JSONDecodeError):
        return "sarvam"


# ---------------------------------------------------------------------------
# Faster-Whisper local STT — wraps the faster-whisper library as a LiveKit STT
# ---------------------------------------------------------------------------

class FasterWhisperSTT(lk_stt.STT):
    """
    Local STT backed by faster-whisper (runs on-device, no API key needed).

    Uses batch transcription — compatible with turn_detection='vad'.
    The model is lazy-loaded on first use (~500 MB for 'base.en').
    """

    def __init__(self, model: str = "base.en") -> None:
        super().__init__(
            capabilities=lk_stt.STTCapabilities(streaming=False, interim_results=False)
        )
        self._model_name = model
        self._whisper = None  # loaded on first recognize() call

    def _load_model(self):
        if self._whisper is None:
            from faster_whisper import WhisperModel
            logger.info("Loading faster-whisper model '%s'...", self._model_name)
            self._whisper = WhisperModel(self._model_name, device="cpu", compute_type="int8")
        return self._whisper

    async def recognize(
        self,
        buffer,
        *,
        language: str | None = None,
    ) -> lk_stt.SpeechEvent:
        # Normalise buffer to a flat bytes object of 16-bit PCM
        frames = [buffer] if isinstance(buffer, lk_rtc.AudioFrame) else list(buffer)
        raw = b"".join(bytes(f.data) for f in frames)
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

        def _run() -> str:
            model = self._load_model()
            # model.transcribe() returns a lazy generator — consume it inside the thread
            segments, _ = model.transcribe(
                samples,
                language=language or "en",
                beam_size=1,
                vad_filter=False,
            )
            return " ".join(seg.text for seg in segments).strip()

        text = await asyncio.to_thread(_run)

        return lk_stt.SpeechEvent(
            type=lk_stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[lk_stt.SpeechData(text=text, language=language or "en")],
        )

    def stream(self, *, language=None):
        raise NotImplementedError(
            "FasterWhisperSTT is batch-only. "
            "It requires turn_detection='vad' — do not call stream()."
        )


# ---------------------------------------------------------------------------
# Build provider instances
# ---------------------------------------------------------------------------

def _build_stt_for_provider(provider: str) -> lk_stt.STT:
    if provider == "sarvam":
        logger.info("STT → Sarvam Saaras v3")
        return sarvam.STT(
            language="unknown",
            model="saaras:v3",
            mode="transcribe",
            flush_signal=True,
            sample_rate=16000,
        )
    elif provider == "whisper":
        logger.info("STT → OpenAI Whisper")
        return lk_openai.STT(model="whisper-1")
    elif provider == "faster_whisper":
        logger.info("STT → faster-whisper (local, base.en)")
        return FasterWhisperSTT(model="base.en")
    else:
        raise ValueError(f"Unknown STT provider: {provider!r}")


# Pre-warm Sarvam STT at process start (before SIGSTOP freeze) so it's ready on wake
_prewarmed_stt: "lk_stt.STT | None" = None
try:
    _prewarmed_stt = _build_stt_for_provider("sarvam")
    logger.info("Sarvam STT pre-warmed at process start")
except Exception as _e:
    logger.warning("STT pre-warm failed: %s", _e)


def _get_prewarmed_stt(provider: str) -> lk_stt.STT:
    global _prewarmed_stt
    if provider == "sarvam" and _prewarmed_stt is not None:
        stt, _prewarmed_stt = _prewarmed_stt, None
        return stt
    return _build_stt_for_provider(provider)


def _build_llm():
    if LLM_PROVIDER == "openai":
        logger.info("LLM → OpenAI (%s)", OPENAI_LLM_MODEL)
        return lk_openai.LLM(model=OPENAI_LLM_MODEL)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}")


def _build_tts():
    if TTS_PROVIDER == "sarvam":
        logger.info("TTS → Sarvam Bulbul v3")
        return sarvam.TTS(
            target_language_code=SARVAM_TTS_LANGUAGE,
            model="bulbul:v3",
            speaker=SARVAM_TTS_SPEAKER,
            pace=TTS_SPEED,
        )
    elif TTS_PROVIDER == "openai":
        logger.info("TTS → OpenAI TTS (%s / %s)", OPENAI_TTS_MODEL, OPENAI_TTS_VOICE)
        return lk_openai.TTS(model=OPENAI_TTS_MODEL, voice=OPENAI_TTS_VOICE, speed=TTS_SPEED)
    else:
        raise ValueError(f"Unknown TTS_PROVIDER: {TTS_PROVIDER!r}")


# ---------------------------------------------------------------------------
# Resolve Windows host IP from WSL (kept for WSL deployments)
# ---------------------------------------------------------------------------

def _get_windows_host_ip() -> str:
    """Get the Windows host IP by looking at the default network route."""
    try:
        cmd = "ip route show default | awk '{print $3}'"
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=2
        )
        ip = result.stdout.strip()
        if ip:
            logger.info("Resolved Windows host IP via gateway: %s", ip)
            return ip
    except Exception as exc:
        logger.warning("Gateway resolution failed: %s. Trying fallback...", exc)

    try:
        with open("/etc/resolv.conf", "r") as f:
            for line in f:
                if "nameserver" in line:
                    ip = line.split()[1]
                    logger.info("Resolved Windows host IP via nameserver: %s", ip)
                    return ip
    except Exception:
        pass

    return "127.0.0.1"


def _mcp_server_url() -> str:
    url = f"http://127.0.0.1:{MCP_SERVER_PORT}/sse"
    logger.info("MCP Server URL: %s", url)
    return url


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class AntonAgent(Agent):
    """
    Anton – Iron Man-style voice assistant.
    All tools are provided via the MCP server on the Windows host.
    """

    def __init__(self, stt, llm, tts) -> None:
        super().__init__(
            instructions=build_system_prompt(),
            stt=stt,
            llm=llm,
            tts=tts,
            vad=silero.VAD.load(),
            mcp_servers=[
                mcp.MCPServerHTTP(
                    url=_mcp_server_url(),
                    transport_type="sse",
                    client_session_timeout_seconds=30,
                ),
            ],
        )

    async def on_enter(self) -> None:
        """Instant acknowledgement, then a time-aware follow-up."""
        await self.session.say("Online.")
        await self.session.generate_reply(
            instructions=(
                "Follow up with one short Anton-style line suited to the time of day. "
                "No greeting word — just your first observation or readiness cue. "
                "Morning: alert; afternoon: composed; evening: relaxed; late night: quiet. "
                "One sentence. No time or date recitation. Stay in character."
            )
        )


# ---------------------------------------------------------------------------
# STT hot-swap watcher
# ---------------------------------------------------------------------------

async def _watch_stt_state() -> None:
    """
    Poll .anton_state.json every second.

    When the file's mtime changes and the provider value differs from the
    currently active provider, a new STT instance is built and assigned to
    _active_agent.stt — no restart required.

    Note: turn_detection and min_endpointing_delay are fixed at session start.
    The new STT takes effect for the *next* utterance after the swap.
    """
    global _active_agent

    last_mtime: float = 0.0
    last_provider: str = _read_stt_provider()

    while True:
        await asyncio.sleep(1.0)

        try:
            mtime = os.stat(_STATE_FILE).st_mtime
        except FileNotFoundError:
            continue

        if mtime <= last_mtime:
            continue

        last_mtime = mtime
        new_provider = _read_stt_provider()

        if new_provider == last_provider or _active_agent is None:
            continue

        old_provider = last_provider
        try:
            new_stt = _build_stt_for_provider(new_provider)
            _active_agent.stt = new_stt
            last_provider = new_provider
            logger.info("STT hot-swapped: %s → %s", old_provider, new_provider)
        except Exception as e:
            logger.warning("Failed to hot-swap STT to %r: %s", new_provider, e)


# ---------------------------------------------------------------------------
# Session configuration helpers
# ---------------------------------------------------------------------------

def _endpointing_delay(provider: str) -> float:
    # With turn_detection='vad' (used for all providers to enable hot-swap),
    # these delays apply after VAD silence detection.
    return {"sarvam": 0.3, "whisper": 0.5, "faster_whisper": 0.3}.get(provider, 0.3)


# ---------------------------------------------------------------------------
# LiveKit entry point
# ---------------------------------------------------------------------------

async def entrypoint(ctx: JobContext) -> None:
    global _active_agent, _watcher_task

    provider = _read_stt_provider()
    logger.info(
        "Anton online – room: %s | STT=%s | LLM=%s | TTS=%s",
        ctx.room.name, provider, LLM_PROVIDER, TTS_PROVIDER,
    )

    stt = _get_prewarmed_stt(provider)
    llm = _build_llm()
    tts = _build_tts()

    session = AgentSession(
        # Always 'vad' so STT can be hot-swapped mid-session without the
        # pipeline needing to call stream() on the replacement STT.
        turn_detection="vad",
        min_endpointing_delay=_endpointing_delay(provider),
    )

    agent = AntonAgent(stt=stt, llm=llm, tts=tts)
    _active_agent = agent

    # Start the file watcher only once per process
    if _watcher_task is None or _watcher_task.done():
        _watcher_task = asyncio.create_task(_watch_stt_state())

    await session.start(
        agent=agent,
        room=ctx.room,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


def dev():
    """Wrapper to run the agent in dev mode automatically."""
    import sys
    if len(sys.argv) == 1:
        sys.argv.append("dev")
    main()


if __name__ == "__main__":
    main()
