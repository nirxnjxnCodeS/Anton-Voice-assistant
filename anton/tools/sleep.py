"""
Sleep tools — gracefully shut down Anton and optionally put the system to sleep.
"""

import os
import subprocess

PLIST = os.path.expanduser(
    "~/Library/LaunchAgents/com.niranjan.anton.wake.plist"
)


def register(mcp):

    @mcp.tool()
    def sleep_anton(sleep_system: bool = False) -> str:
        """
        Gracefully shut down Anton — stops the wake listener, MCP server, and LiveKit agent.
        Pass sleep_system=True to also put the Mac to sleep after shutting down.
        Trigger when the user says 'sleep', 'go to sleep', 'goodnight', 'shut down',
        'bye', 'that's all', 'I'm done', etc.
        """
        # Run as a single independent shell process so it survives launchd killing
        # the MCP server. All steps happen inside the shell after the TTS delay.
        cmd = f"sleep 8 && launchctl unload {PLIST}"
        if sleep_system:
            cmd += " && sleep 2 && /usr/bin/pmset sleepnow"

        subprocess.Popen(["bash", "-c", cmd])

        if sleep_system:
            return "Shutting everything down and putting the system to sleep. Goodnight, boss."
        return "Going to sleep. I'll be standing by when you need me, boss."
