"""
wake.py — Always-on clap + phrase wake listener for Anton.

Flow:
  1. Idle — continuously monitor mic energy (very low CPU).
  2. Two claps within 2 seconds → open a 3-second phrase window.
  3. Say "wake up Anton" → play chime → launch `uv run anton_voice`.
  4. If phrase not matched → return to idle silently.

STT: faster-whisper tiny.en model (auto-downloads ~75 MB on first run, then cached).

Run:
    uv run wake
"""

import math
import os
import signal
import struct
import subprocess
import sys
import time
import wave

import numpy as np
import pyaudio
import simpleaudio
from faster_whisper import WhisperModel


# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

RATE = 16_000           # Hz — Whisper expects 16 kHz
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK = 1024            # ~64 ms per chunk; fine time resolution for clap detection

CLAP_THRESHOLD = 6.0    # RMS must be this many × background to register as a clap
CLAP_FLOOR = 800        # absolute minimum RMS — filters out normal speech/noise
CLAP_COOLDOWN = 0.4     # seconds before a second clap can register (no double-counts)
CLAP_WINDOW = 2.0       # two claps must land within this many seconds

LISTEN_DURATION = 3.0   # seconds to record after the second clap
WAKE_WORDS = {"wake"}           # "wake up" is enough — Whisper mishears "Anton" too often

CHIME_PATH = os.path.join(os.path.dirname(__file__), "wake_chime.wav")


# ---------------------------------------------------------------------------
# Wake chime — generated on first run, no bundled file needed
# ---------------------------------------------------------------------------

def _generate_chime(path: str) -> None:
    """Write a short two-tone ascending chime to *path* if it doesn't exist."""
    if os.path.exists(path):
        return

    sample_rate = 44_100
    duration = 0.22
    tones = [880, 1_320]    # Hz — A5 → E6, quick ascending pair

    samples: list[int] = []
    for freq in tones:
        n = int(sample_rate * duration)
        for i in range(n):
            envelope = 1.0 - (i / n)
            val = 26_000 * envelope * math.sin(2 * math.pi * freq * i / sample_rate)
            samples.append(int(val))

    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def _play_chime(path: str) -> None:
    try:
        simpleaudio.WaveObject.from_wave_file(path).play().wait_done()
    except Exception:
        pass  # chime is cosmetic — don't block wake on audio failure


# ---------------------------------------------------------------------------
# faster-whisper STT — offline, no API key, auto-downloads model on first run
# ---------------------------------------------------------------------------

def _load_whisper() -> WhisperModel:
    print("[Anton] Loading speech model (downloads ~75 MB on first run)...", flush=True)
    # int8 quantisation: fast on CPU, negligible accuracy loss for phrase matching
    model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    return model


def _transcribe(model: WhisperModel, pcm_bytes: bytes) -> str:
    # Normalise raw 16-bit PCM to float32 in [-1, 1] — what Whisper expects
    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    segments, _ = model.transcribe(audio, language="en", beam_size=1, vad_filter=False)
    return " ".join(seg.text for seg in segments).lower().strip()


def _phrase_matches(transcript: str) -> bool:
    return WAKE_WORDS.issubset(set(transcript.split()))


# ---------------------------------------------------------------------------
# Energy helpers
# ---------------------------------------------------------------------------

def _rms(chunk_bytes: bytes) -> float:
    samples = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(samples ** 2))) if len(samples) else 0.0


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def _start_services(project_dir: str) -> subprocess.Popen:
    """
    Pre-warm: start only the MCP server at startup (lightweight, always needed).
    The LiveKit agent worker is intentionally NOT started here — it only launches
    on an explicit wake gesture so the LiveKit room stays closed until then.
    """
    mcp_proc = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=project_dir,
    )
    print("[Anton] MCP server starting...", flush=True)
    return mcp_proc


def _launch_agent(project_dir: str) -> subprocess.Popen:
    """
    Launch the LiveKit agent worker using the current venv Python directly —
    bypasses uv startup overhead for a noticeably faster wake response.
    """
    return subprocess.Popen(
        [sys.executable, "agent_anton.py", "dev"],
        cwd=project_dir,
    )


def main() -> None:
    project_dir = os.path.dirname(os.path.abspath(__file__))

    _generate_chime(CHIME_PATH)
    model = _load_whisper()

    # Pre-warm only the MCP server. The LiveKit agent worker starts only on wake
    # so the LiveKit room stays closed until the gesture is made.
    mcp_proc = _start_services(project_dir)
    agent_proc: subprocess.Popen | None = None

    def _shutdown(sig=None, frame=None):
        print("\n[Anton] Going to sleep.", flush=True)
        mcp_proc.terminate()
        if agent_proc and agent_proc.poll() is None:
            agent_proc.terminate()
        stream.stop_stream()
        stream.close()
        pa.terminate()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)

    pa = pyaudio.PyAudio()
    stream = pa.open(
        rate=RATE,
        channels=CHANNELS,
        format=FORMAT,
        input=True,
        frames_per_buffer=CHUNK,
    )

    print("[Anton] Listening...", flush=True)

    # Exponential moving average of background energy.
    # Small alpha → slow adaptation → stable baseline → fewer false positives.
    bg_rms: float = 300.0
    BG_ALPHA = 0.02

    clap_times: list[float] = []
    last_clap_at: float = 0.0

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            now = time.monotonic()
            rms = _rms(data)

            # --- Revive MCP server if it crashed -----------------------------
            if mcp_proc.poll() is not None:
                mcp_proc = _start_services(project_dir)

            # --- Clap detection ----------------------------------------------
            is_clap = (
                rms > CLAP_FLOOR
                and rms > CLAP_THRESHOLD * bg_rms
                and (now - last_clap_at) > CLAP_COOLDOWN
            )

            if is_clap:
                clap_times = [t for t in clap_times if now - t <= CLAP_WINDOW]
                clap_times.append(now)
                last_clap_at = now
                n = len(clap_times)
                print(f"[Anton] Clap detected ({n}/2)", end="", flush=True)

                if n >= 2:
                    print(" — say 'wake up'", flush=True)
                    clap_times.clear()

                    # --- Wake phrase window ----------------------------------
                    frames: list[bytes] = []
                    deadline = time.monotonic() + LISTEN_DURATION
                    while time.monotonic() < deadline:
                        frames.append(stream.read(CHUNK, exception_on_overflow=False))

                    transcript = _transcribe(model, b"".join(frames))

                    if _phrase_matches(transcript):
                        print("[Anton] Waking up...", flush=True)
                        _play_chime(CHIME_PATH)
                        agent_proc = _launch_agent(project_dir)
                        print("[Anton] Listening...", flush=True)
                    else:
                        heard = transcript or "(nothing)"
                        print(f"[Anton] Heard: '{heard}' — resuming...", flush=True)
                else:
                    print(flush=True)

            else:
                # Only update background on quiet / non-transient frames
                bg_rms = (1 - BG_ALPHA) * bg_rms + BG_ALPHA * rms

    except KeyboardInterrupt:
        print("\n[Anton] Standing by.")
        mcp_proc.terminate()
        if agent_proc and agent_proc.poll() is None:
            agent_proc.terminate()
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


if __name__ == "__main__":
    main()
