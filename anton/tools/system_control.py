"""
System control tools — macOS-specific controls via subprocess and psutil.
No external APIs required. Tested on macOS Sonoma.
"""

import re
import subprocess
from datetime import datetime


def _run(cmd: str | list, *, shell: bool = False, timeout: int = 5) -> tuple[str, str, int]:
    """Run a command and return (stdout, stderr, returncode)."""
    result = subprocess.run(
        cmd,
        shell=shell,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def register(mcp):

    @mcp.tool()
    def lock_mac() -> str:
        """
        Lock the Mac screen immediately.
        Use when the user says 'lock the screen', 'lock my Mac', 'I'm stepping away', etc.
        """
        try:
            _run(
                ["osascript", "-e",
                 'tell application "System Events" to keystroke "q" '
                 'using {control down, command down}'],
            )
            return "Screen locked, sir."
        except Exception as e:
            return f"Couldn't lock the screen, sir. Error: {e}"

    @mcp.tool()
    def get_battery_status() -> str:
        """
        Return current battery percentage and whether the MacBook is charging.
        Use when the user asks 'How's the battery?', 'Battery level?', 'Am I plugged in?', etc.
        """
        try:
            stdout, _, rc = _run(["pmset", "-g", "batt"])
            if rc != 0:
                return "Couldn't read battery status, sir."

            # Parse percentage — e.g. "87%;"
            pct_match = re.search(r"(\d+)%", stdout)
            pct = pct_match.group(1) if pct_match else "unknown"

            if "AC Power" in stdout:
                source = "on AC power"
            elif "Battery Power" in stdout:
                source = "on battery"
            else:
                source = ""

            if "charging" in stdout.lower():
                state = "currently charging"
            elif "charged" in stdout.lower():
                state = "fully charged"
            elif "discharging" in stdout.lower():
                state = "discharging"
            else:
                state = ""

            parts = [f"Battery at {pct}%"]
            if state:
                parts.append(state)
            if source:
                parts.append(source)

            return ", ".join(parts) + "."
        except Exception as e:
            return f"Couldn't read battery status, sir. Error: {e}"

    @mcp.tool()
    def take_screenshot() -> str:
        """
        Take a screenshot and save it to the Desktop with a timestamp.
        Use when the user says 'Take a screenshot', 'Capture my screen', 'Screenshot', etc.
        """
        try:
            import os
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"anton_{timestamp}.png"
            path = os.path.expanduser(f"~/Desktop/{filename}")
            # -D 1 targets the main display explicitly; required on Apple Silicon Sonoma
            # (-x alone fails with "could not create image from display" on M-series Macs)
            _, stderr, rc = _run(["screencapture", "-x", "-D", "1", path])
            if rc != 0:
                return f"Screenshot failed, sir. {stderr}"
            return f"Screenshot saved to your Desktop as {filename}, sir."
        except Exception as e:
            return f"Couldn't take the screenshot, sir. Error: {e}"

    @mcp.tool()
    def get_system_info() -> str:
        """
        Return CPU usage, RAM usage, and available disk space.
        Use when the user asks 'How's the system?', 'CPU usage?', 'How much RAM am I using?', etc.
        """
        try:
            import psutil

            cpu = psutil.cpu_percent(interval=0.5)

            mem = psutil.virtual_memory()
            ram_used_gb = mem.used / (1024 ** 3)
            ram_total_gb = mem.total / (1024 ** 3)

            disk = psutil.disk_usage("/")
            disk_free_gb = disk.free / (1024 ** 3)
            disk_total_gb = disk.total / (1024 ** 3)

            return (
                f"CPU is at {cpu:.0f}%, sir. "
                f"You're using {ram_used_gb:.1f}GB of your {ram_total_gb:.0f}GB RAM. "
                f"Disk has {disk_free_gb:.0f}GB free."
            )
        except Exception as e:
            return f"Couldn't read system info, sir. Error: {e}"

    @mcp.tool()
    def get_volume() -> str:
        """
        Return the current Mac system output volume (0–100).
        Use when the user asks 'What's the volume?', 'How loud is it?', etc.
        """
        try:
            stdout, _, rc = _run(
                ["osascript", "-e", "output volume of (get volume settings)"]
            )
            if rc != 0:
                return "Couldn't read volume, sir."
            return f"System volume is at {stdout}%, sir."
        except Exception as e:
            return f"Couldn't read volume, sir. Error: {e}"

    @mcp.tool()
    def set_system_volume(level: int) -> str:
        """
        Set the Mac system output volume. Level must be between 0 and 100.
        Use when the user says 'Set volume to 50', 'Turn it up to 80', 'Mute', etc.
        """
        if not 0 <= level <= 100:
            return "Volume must be between 0 and 100, sir."
        try:
            _, _, rc = _run(
                ["osascript", "-e", f"set volume output volume {level}"]
            )
            if rc != 0:
                return "Couldn't set volume, sir."
            if level == 0:
                return "Volume muted, sir."
            return f"Volume set to {level}%, sir."
        except Exception as e:
            return f"Couldn't set volume, sir. Error: {e}"

    @mcp.tool()
    def open_app(app_name: str) -> str:
        """
        Open any macOS application by name.
        Use when the user says 'Open Safari', 'Launch Spotify', 'Open Notes', etc.
        """
        try:
            _, stderr, rc = _run(["open", "-a", app_name])
            if rc != 0:
                return (
                    f"Couldn't open '{app_name}', sir. "
                    f"Make sure the app name is correct — e.g. 'Safari', 'Spotify', 'Notes'."
                )
            return f"Opening {app_name}, sir."
        except Exception as e:
            return f"Failed to open {app_name}, sir. Error: {e}"

    @mcp.tool()
    def get_wifi_info() -> str:
        """
        Return the current Wi-Fi network name and signal strength.
        Use when the user asks 'What Wi-Fi am I on?', 'What network?', 'Am I connected?', etc.
        """
        try:
            # `airport` binary no longer exists on Apple Silicon macOS Sonoma.
            # Use networksetup for SSID and system_profiler for signal strength.

            ssid_out, _, ssid_rc = _run(["networksetup", "-getairportnetwork", "en0"])

            if ssid_rc != 0 or "not associated" in ssid_out.lower():
                # macOS Sonoma requires Location Services for SSID in some contexts.
                # Fall back to checking if we have an IP on en0 at all.
                ip_out, _, _ = _run(["ipconfig", "getifaddr", "en0"])
                if ip_out:
                    return (
                        f"Connected to Wi-Fi, sir (IP: {ip_out}). "
                        "SSID is restricted by macOS privacy settings — "
                        "grant Location access to Terminal to see it."
                    )
                return "Not connected to any Wi-Fi network, sir."

            network = ssid_out.replace("Current Wi-Fi Network:", "").strip()

            # Signal from system_profiler — parse the first Signal/Noise entry
            # which always corresponds to the current network.
            sp_out, _, _ = _run(["system_profiler", "SPAirPortDataType"], timeout=15)
            rssi = None
            sig_match = re.search(
                r"Current Network Information:.*?Signal / Noise:\s*(-?\d+)\s*dBm",
                sp_out,
                re.DOTALL,
            )
            if sig_match:
                rssi = int(sig_match.group(1))

            if rssi is not None:
                if rssi >= -50:
                    strength = "excellent"
                elif rssi >= -65:
                    strength = "good"
                elif rssi >= -75:
                    strength = "fair"
                else:
                    strength = "weak"
                return f"Connected to '{network}', sir. Signal is {strength} ({rssi} dBm)."

            return f"Connected to '{network}', sir."
        except Exception as e:
            return f"Couldn't read Wi-Fi info, sir. Error: {e}"

    @mcp.tool()
    async def play_youtube(query: str) -> str:
        """
        Find the top YouTube video for a query via the YouTube Data API v3 and
        open it directly in the browser.
        Use when the user says 'Play X on YouTube', 'Put on Y', 'Open Z on YouTube', etc.
        Requires YOUTUBE_API_KEY in .env.
        """
        import httpx
        from anton.config import config

        if not config.YOUTUBE_API_KEY:
            return "YouTube API key not configured, sir. Add YOUTUBE_API_KEY to your .env file."

        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={
                        "q": query,
                        "part": "snippet",
                        "maxResults": 1,
                        "type": "video",
                        "key": config.YOUTUBE_API_KEY,
                    },
                )
            response.raise_for_status()
            items = response.json().get("items", [])
        except httpx.HTTPStatusError as e:
            return f"YouTube API error, sir. Status {e.response.status_code}."
        except Exception as e:
            return f"Couldn't reach YouTube, sir. Error: {e}"

        if not items:
            return "Couldn't find that on YouTube, sir."

        video_id = items[0]["id"]["videoId"]
        url = f"https://www.youtube.com/watch?v={video_id}"
        _run(["open", url])
        return f"Opening {query} on YouTube for you, sir."
