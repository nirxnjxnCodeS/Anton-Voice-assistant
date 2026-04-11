# Anton — Voice Agent

> *"Fully Responsive Intelligent Digital Assistant for You"*

A Tony Stark-inspired AI assistant built by **Niranjan**. This voice agent combines real-time processing with powerful AI models perfectly suited for daily use.

*(Inspired from [SAGAR-TAMANG's friday-tony-stark-demo repo](https://github.com/SAGAR-TAMANG/friday-tony-stark-demo))*

---

## 🧠 Architecture

The system is split into two cooperating pieces:

| Component | What it is |
|-----------|-----------|
| **MCP Server** (`uv run anton`) | A [FastMCP](https://github.com/jlowin/fastmcp) server that exposes tools (news, web search, system info, …) over SSE. Think of it as the Stark Industries backend — it does the actual work. |
| **Voice Agent** (`uv run anton_voice`) | A [LiveKit Agents](https://github.com/livekit/agents) voice pipeline that listens to your microphone, reasons with **OpenAI GPT-4o**, and speaks back with OpenAI TTS — all while pulling tools from the MCP server in real time. |

### The Flow
```text
Microphone ──► STT (Sarvam Saaras v3)
                    │
                    ▼
             LLM (OpenAI GPT-4o)  ◄──────► MCP Server (FastMCP / SSE)
                    │                              ├─ get_world_news
                    ▼                              ├─ open_world_monitor
             TTS (OpenAI nova)                     ├─ search_web
                    │                              └─ …more tools
                    ▼
             Speaker / LiveKit room
```

The voice agent connects to the MCP server securely at `http://127.0.0.1:8000/sse`.

---

## ⚙️ Quick Start Guide

### 1. Prerequisites

- Python ≥ 3.11
- [`uv`](https://github.com/astral-sh/uv) — fast Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- A [LiveKit Cloud](https://cloud.livekit.io) project (free tier works)

### 2. Setup

Clone the repo and sync your environment:

```bash
git clone https://github.com/nirxnjxnCodeS/Anton-Voice-assistant.git
cd Anton-Voice-assistant
uv sync  
```

Create your `.env` file from the example and fill in your keys:

```bash
cp .env.example .env
```

Ensure your `.env` file contains your real credentials:
- `OPENAI_API_KEY`
- `SARVAM_API_KEY`
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`

### 3. Run the Agent (Two Terminals Required)

**Terminal 1 — The MCP Server Backend**

```bash
uv run anton
```
*Starts the FastMCP server on `port 8000`.*

**Terminal 2 — The Voice Agent**

```bash
uv run anton_voice
```
*Starts the LiveKit voice agent which will connect to the MCP server.*

### 4. Talk to Anton

Open the [LiveKit Agents Playground](https://agents-playground.livekit.io) and connect to your room. Once connected, Anton will greet you and is ready for commands!

---

## 🛠️ Stack overview
- **Brain**: OpenAI GPT-4o
- **Ears (STT)**: Sarvam Saaras v3 
- **Mouth (TTS)**: OpenAI TTS (Nova)
- **Voice Pipeline**: LiveKit Agents
- **Tool Protocol**: FastMCP

---

## 📜 License
MIT
