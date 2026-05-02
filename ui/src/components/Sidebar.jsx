import { useState, useEffect, useMemo } from 'react'
import {
  useVoiceAssistant,
  useLocalParticipant,
  useTracks,
  useTrackTranscription,
} from '@livekit/components-react'
import { Track } from 'livekit-client'

const TOOL_KEYWORDS = {
  weather: 'Weather', temperature: 'Weather', forecast: 'Weather',
  calendar: 'Calendar', event: 'Calendar', schedule: 'Calendar', meeting: 'Calendar',
  email: 'Gmail', gmail: 'Gmail', inbox: 'Gmail',
  spotify: 'Spotify', music: 'Spotify', song: 'Spotify', playing: 'Spotify',
  note: 'Memory', obsidian: 'Memory', saved: 'Memory',
  screenshot: 'System', battery: 'System', wifi: 'System', system: 'System',
  youtube: 'YouTube', video: 'YouTube',
  news: 'News', headline: 'News', article: 'News',
}

const TOOLS = [
  { name: 'Weather'  },
  { name: 'Calendar' },
  { name: 'Gmail'    },
  { name: 'Spotify'  },
  { name: 'YouTube'  },
  { name: 'Memory'   },
  { name: 'System'   },
  { name: 'News'     },
]

const PIPELINE = [
  { label: 'STT', value: 'Sarvam v3', activeState: 'listening' },
  { label: 'LLM', value: 'GPT-4o',    activeState: 'thinking'  },
  { label: 'TTS', value: 'Nova',       activeState: 'speaking'  },
]

const INITIAL_STATS = [
  { label: 'NOTES',   value: '47' },
  { label: 'UNREAD',  value: '12' },
  { label: 'EVENTS',  value: '3'  },
  { label: 'SPOTIFY', value: 'ON' },
]

function detectToolInText(text) {
  if (!text) return null
  const lower = text.toLowerCase()
  for (const [kw, tool] of Object.entries(TOOL_KEYWORDS)) {
    if (lower.includes(kw)) return tool
  }
  return null
}

export default function Sidebar() {
  const { state, agent } = useVoiceAssistant()
  const { localParticipant } = useLocalParticipant()
  const [recentTool, setRecentTool] = useState(null)
  const [speakingTool, setSpeakingTool] = useState(null)

  const tracks = useTracks([Track.Source.Microphone])
  const agentTrack = useMemo(
    () => tracks.find(t => agent && t.participant?.identity === agent.identity),
    [tracks, agent]
  )
  const { segments } = useTrackTranscription(agentTrack)

  // Detect tool from most recent final segment
  useEffect(() => {
    const finals = segments?.filter(s => s.final) ?? []
    const last = finals[finals.length - 1]
    if (!last) return
    const tool = detectToolInText(last.text)
    if (!tool) return
    setRecentTool(tool)
    const timer = setTimeout(() => setRecentTool(null), 3000)
    return () => clearTimeout(timer)
  }, [segments])

  // Detect tool from live streaming segment
  useEffect(() => {
    if (state !== 'speaking') { setSpeakingTool(null); return }
    const streaming = segments?.find(s => !s.final)
    setSpeakingTool(streaming ? detectToolInText(streaming.text) : null)
  }, [segments, state])

  function getDotColor(name) {
    if (speakingTool === name) return '#22c55e'
    if (recentTool === name) return '#a855f7'
    return '#166534'
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <div className="section-label">SYS STATUS</div>
        <div className="stats-grid">
          {INITIAL_STATS.map((s) => (
            <div key={s.label} className="stat-card">
              <div className="stat-val">{s.value}</div>
              <div className="stat-key">{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="sidebar-section">
        <div className="section-label">TOOLS</div>
        <div className="tool-list">
          {TOOLS.map((t) => {
            const isActive = speakingTool === t.name || recentTool === t.name
            const isPulsing = recentTool === t.name && speakingTool !== t.name
            return (
              <div
                key={t.name}
                className={`tool-item${isActive ? ' tool-active' : ''}`}
              >
                <span
                  className={`tool-dot${isPulsing ? ' tool-dot-pulse' : ''}`}
                  style={{ background: getDotColor(t.name) }}
                />
                <span className="tool-name">{t.name}</span>
                {speakingTool === t.name && <span className="tool-busy">▶</span>}
                {isPulsing && <span className="tool-busy" style={{ color: '#a855f7' }}>✓</span>}
              </div>
            )
          })}
        </div>
      </div>

      <div className="sidebar-section">
        <div className="section-label">PIPELINE</div>
        <div className="pipeline">
          {PIPELINE.map((p, i) => {
            const isActive = state === p.activeState
            return (
              <div key={p.label}>
                <div className={`pipe-item${isActive ? ' pipe-active' : ''}`}>
                  <span className="pipe-label">{p.label}</span>
                  <span className="pipe-value">{p.value}</span>
                  {isActive && <span className="pipe-activity-dot" />}
                </div>
                {i < PIPELINE.length - 1 && (
                  <div className="pipe-arrow">↓</div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </aside>
  )
}
