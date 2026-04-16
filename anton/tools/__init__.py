"""
Tool registry — imports and registers all tool modules with the MCP server.
Add new tool modules here as you build them.
"""

from anton.tools import web, system, utils, weather, sleep, calendar, gmail, spotify, system_control, obsidian, briefing


def register_all_tools(mcp):
    """Register all tool groups onto the MCP server instance."""
    web.register(mcp)
    system.register(mcp)
    utils.register(mcp)
    weather.register(mcp)
    sleep.register(mcp)
    calendar.register(mcp)
    gmail.register(mcp)
    spotify.register(mcp)
    system_control.register(mcp)
    obsidian.register(mcp)
    briefing.register(mcp)
