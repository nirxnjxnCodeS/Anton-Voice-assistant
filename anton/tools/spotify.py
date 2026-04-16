"""
Spotify tools — playback control via Spotipy + OAuth2.

Requires Spotify Premium.
Set SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI in .env
and ensure the redirect URI is registered in your Spotify app dashboard.
"""

import asyncio
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from anton.config import config

_SCOPES = " ".join([
    "user-modify-playback-state",
    "user-read-playback-state",
    "user-read-currently-playing",
    "user-read-private",
    "playlist-read-private",
])

_CACHE_PATH = str(Path(__file__).parent.parent.parent / ".spotify_cache")


def _build_client() -> spotipy.Spotify:
    auth = SpotifyOAuth(
        client_id=config.SPOTIFY_CLIENT_ID,
        client_secret=config.SPOTIFY_CLIENT_SECRET,
        redirect_uri=config.SPOTIFY_REDIRECT_URI,
        scope=_SCOPES,
        cache_path=_CACHE_PATH,
        open_browser=True,
    )
    sp = spotipy.Spotify(auth_manager=auth)
    # Lock cache file to owner read/write only after first write
    cache = Path(_CACHE_PATH)
    if cache.exists():
        cache.chmod(0o600)
    return sp


def _not_configured() -> str | None:
    if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
        return (
            "Spotify isn't configured, sir. "
            "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your .env file."
        )
    return None


def _active_device(sp: spotipy.Spotify) -> str | None:
    """Return the ID of the currently active device, or None."""
    devices = sp.devices().get("devices", [])
    for d in devices:
        if d["is_active"]:
            return d["id"]
    # Fall back to first available device if nothing is active
    if devices:
        return devices[0]["id"]
    return None


def _is_premium(sp: spotipy.Spotify) -> bool:
    return sp.current_user().get("product") == "premium"


def register(mcp):

    @mcp.tool()
    async def get_current_track() -> str:
        """
        Returns the track currently playing on Spotify: title, artist, and playback state.
        Use when the user asks 'What song is this?', 'What's playing?', 'What's on?', etc.
        """
        if err := _not_configured():
            return err

        def _fetch():
            sp = _build_client()
            return sp.current_playback()

        try:
            playback = await asyncio.to_thread(_fetch)
        except Exception as e:
            return f"Couldn't reach Spotify, sir. Error: {e}"

        if not playback or not playback.get("item"):
            return "Nothing is playing on Spotify right now, sir."

        item = playback["item"]
        track = item["name"]
        artists = ", ".join(a["name"] for a in item["artists"])
        is_playing = playback["is_playing"]
        progress_ms = playback.get("progress_ms", 0)
        duration_ms = item.get("duration_ms", 1)

        progress = f"{progress_ms // 60000}:{(progress_ms % 60000) // 1000:02d}"
        duration = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"
        state = "playing" if is_playing else "paused"

        return (
            f"{'Playing' if is_playing else 'Paused'}: {track} by {artists}, sir. "
            f"({progress} / {duration})"
        )

    @mcp.tool()
    async def play_song(query: str) -> str:
        """
        Search for a song by name or artist and start playing it immediately.
        Use when the user says 'Play X', 'Put on Y by Z', 'Play something by W', etc.
        """
        if err := _not_configured():
            return err

        def _play():
            sp = _build_client()
            if not _is_premium(sp):
                return "__free_tier__"
            device_id = _active_device(sp)
            if not device_id:
                return "__no_device__"

            results = sp.search(q=query, type="track", limit=1)
            tracks = results.get("tracks", {}).get("items", [])
            if not tracks:
                return "__not_found__"

            track = tracks[0]
            sp.start_playback(device_id=device_id, uris=[track["uri"]])
            return {
                "name": track["name"],
                "artists": ", ".join(a["name"] for a in track["artists"]),
            }

        try:
            result = await asyncio.to_thread(_play)
        except Exception as e:
            return f"Playback failed, sir. Error: {e}"

        if result == "__free_tier__":
            return "Playback control requires Spotify Premium, sir. Free tier doesn't support it."
        if result == "__no_device__":
            return "No active Spotify device found, sir. Please open Spotify on any device first."
        if result == "__not_found__":
            return f"I couldn't find anything matching '{query}' on Spotify, sir."

        return f"Now playing {result['name']} by {result['artists']}, sir."

    @mcp.tool()
    async def play_playlist(name: str) -> str:
        """
        Search for a playlist by name and start playing it.
        Searches your saved playlists first, then falls back to Spotify's catalogue.
        Use when the user says 'Play my workout playlist', 'Put on chill vibes', etc.
        """
        if err := _not_configured():
            return err

        def _play():
            sp = _build_client()
            if not _is_premium(sp):
                return "__free_tier__"
            device_id = _active_device(sp)
            if not device_id:
                return "__no_device__"

            # Search user's own playlists first
            user_playlists = sp.current_user_playlists(limit=50).get("items", [])
            matched = next(
                (p for p in user_playlists if name.lower() in p["name"].lower()),
                None,
            )

            if not matched:
                # Fall back to Spotify catalogue search
                results = sp.search(q=name, type="playlist", limit=1)
                items = results.get("playlists", {}).get("items", [])
                if not items:
                    return "__not_found__"
                matched = items[0]

            sp.start_playback(device_id=device_id, context_uri=matched["uri"])
            return {"name": matched["name"]}

        try:
            result = await asyncio.to_thread(_play)
        except Exception as e:
            return f"Couldn't start the playlist, sir. Error: {e}"

        if result == "__free_tier__":
            return "Playback control requires Spotify Premium, sir. Free tier doesn't support it."
        if result == "__no_device__":
            return "No active Spotify device found, sir. Please open Spotify on any device first."
        if result == "__not_found__":
            return f"I couldn't find a playlist matching '{name}', sir."

        return f"Now playing the '{result['name']}' playlist, sir."

    @mcp.tool()
    async def pause_playback() -> str:
        """
        Pause the currently playing Spotify track.
        Use when the user says 'Pause', 'Stop the music', 'Quiet', etc.
        """
        if err := _not_configured():
            return err

        def _pause():
            sp = _build_client()
            if not _is_premium(sp):
                return "__free_tier__"
            device_id = _active_device(sp)
            if not device_id:
                return "__no_device__"
            sp.pause_playback(device_id=device_id)
            return "__ok__"

        try:
            result = await asyncio.to_thread(_pause)
        except Exception as e:
            return f"Couldn't pause, sir. Error: {e}"

        if result == "__free_tier__":
            return "Playback control requires Spotify Premium, sir."
        if result == "__no_device__":
            return "No active Spotify device found, sir. Please open Spotify on any device first."

        return "Paused. Resume anytime, sir."

    @mcp.tool()
    async def resume_playback() -> str:
        """
        Resume a paused Spotify track.
        Use when the user says 'Resume', 'Continue', 'Play', 'Unpause', etc.
        """
        if err := _not_configured():
            return err

        def _resume():
            sp = _build_client()
            if not _is_premium(sp):
                return "__free_tier__"
            device_id = _active_device(sp)
            if not device_id:
                return "__no_device__"
            sp.start_playback(device_id=device_id)
            return "__ok__"

        try:
            result = await asyncio.to_thread(_resume)
        except Exception as e:
            return f"Couldn't resume, sir. Error: {e}"

        if result == "__free_tier__":
            return "Playback control requires Spotify Premium, sir."
        if result == "__no_device__":
            return "No active Spotify device found, sir. Please open Spotify on any device first."

        return "Resuming playback, sir."

    @mcp.tool()
    async def next_track() -> str:
        """
        Skip to the next track on Spotify.
        Use when the user says 'Skip', 'Next', 'Next song', 'Skip this one', etc.
        """
        if err := _not_configured():
            return err

        def _next():
            sp = _build_client()
            if not _is_premium(sp):
                return "__free_tier__"
            device_id = _active_device(sp)
            if not device_id:
                return "__no_device__"
            sp.next_track(device_id=device_id)
            return "__ok__"

        try:
            result = await asyncio.to_thread(_next)
        except Exception as e:
            return f"Couldn't skip, sir. Error: {e}"

        if result == "__free_tier__":
            return "Playback control requires Spotify Premium, sir."
        if result == "__no_device__":
            return "No active Spotify device found, sir. Please open Spotify on any device first."

        return "Skipped. Moving on, sir."

    @mcp.tool()
    async def previous_track() -> str:
        """
        Go back to the previous track on Spotify.
        Use when the user says 'Previous', 'Go back', 'Last song', 'Play that again', etc.
        """
        if err := _not_configured():
            return err

        def _prev():
            sp = _build_client()
            if not _is_premium(sp):
                return "__free_tier__"
            device_id = _active_device(sp)
            if not device_id:
                return "__no_device__"
            sp.previous_track(device_id=device_id)
            return "__ok__"

        try:
            result = await asyncio.to_thread(_prev)
        except Exception as e:
            return f"Couldn't go back, sir. Error: {e}"

        if result == "__free_tier__":
            return "Playback control requires Spotify Premium, sir."
        if result == "__no_device__":
            return "No active Spotify device found, sir. Please open Spotify on any device first."

        return "Going back to the previous track, sir."

    @mcp.tool()
    async def set_volume(level: int) -> str:
        """
        Set Spotify playback volume. Level must be between 0 and 100.
        Use when the user says 'Volume up', 'Turn it down', 'Set volume to 50', 'Louder', etc.
        """
        if err := _not_configured():
            return err

        if not 0 <= level <= 100:
            return "Volume must be between 0 and 100, sir. Please give me a number in that range."

        def _set_vol():
            sp = _build_client()
            if not _is_premium(sp):
                return "__free_tier__"
            device_id = _active_device(sp)
            if not device_id:
                return "__no_device__"
            sp.volume(volume_percent=level, device_id=device_id)
            return "__ok__"

        try:
            result = await asyncio.to_thread(_set_vol)
        except Exception as e:
            return f"Couldn't set volume, sir. Error: {e}"

        if result == "__free_tier__":
            return "Playback control requires Spotify Premium, sir."
        if result == "__no_device__":
            return "No active Spotify device found, sir. Please open Spotify on any device first."

        return f"Volume set to {level}%, sir."
