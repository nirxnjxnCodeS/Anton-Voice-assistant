#!/bin/zsh
# Launcher for Anton wake listener — called by launchd.
# Sets PATH so uv is found even in a minimal login environment.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "/Users/niranjansbinu/Downloads/Anton Voice Agent"
exec uv run wake
