import { useState, useEffect, useMemo } from 'react'
import {
  useVoiceAssistant,
  BarVisualizer,
  useLocalParticipant,
  useTracks,
  useTrackTranscription,
} from '@livekit/components-react'
import { Track } from 'livekit-client'

const STATE_LABELS = {
  listening:    'LISTENING',
  thinking:     'THINKING',
  speaking:     'SPEAKING',
  connecting:   'CONNECTING',
  initializing: 'INITIALIZING',
  disconnected: 'STANDBY',
}

const STATE_COLORS = {
  listening:    '#22c55e',
  thinking:     '#f59e0b',
  speaking:     '#a855f7',
  connecting:   '#60a5fa',
  initializing: '#60a5fa',
  disconnected: '#4c2d8a',
}

export default function TopBar() {
  const { state, audioTrack, agent } = useVoiceAssistant()
  const { localParticipant } = useLocalParticipant()
  const [time, setTime] = useState('')
  const [battery, setBattery] = useState(null)
  const [weather, setWeather] = useState(null)

  useEffect(() => {
    const tick = () => {
      setTime(
        new Date().toLocaleTimeString('en-IN', {
          timeZone: 'Asia/Kolkata',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        })
      )
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    if (!navigator.getBattery) return
    navigator.getBattery().then((b) => {
      const update = () => setBattery(Math.round(b.level * 100))
      update()
      b.addEventListener('levelchange', update)
    })
  }, [])

  const tracks = useTracks([Track.Source.Microphone])
  const agentTrack = useMemo(
    () => tracks.find(t => agent && t.participant?.identity === agent.identity),
    [tracks, agent]
  )
  const { segments: agentSegments } = useTrackTranscription(agentTrack)

  useEffect(() => {
    if (!agentSegments?.length) return
    for (let i = agentSegments.length - 1; i >= 0; i--) {
      const match = agentSegments[i].text.match(/(\d+)°[CF]/)
      if (match) { setWeather(match[0]); break }
    }
  }, [agentSegments])

  const label = STATE_LABELS[state] ?? 'STANDBY'
  const color = STATE_COLORS[state] ?? '#4c2d8a'

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="arc-reactor">
          <div className="arc-inner" />
          <div className="arc-ring arc-ring-1" />
          <div className="arc-ring arc-ring-2" />
        </div>
        <div className="brand">
          <span className="brand-name">ANTON</span>
          <span className="brand-sub">Niranjan Industries AI · v2.4.1</span>
        </div>
      </div>

      <div className="topbar-center">
        {audioTrack ? (
          <BarVisualizer
            trackRef={audioTrack}
            barCount={9}
            style={{ width: '120px', height: '28px' }}
            options={{ minHeight: 3 }}
            className="bar-viz"
          />
        ) : (
          <div className="bar-viz bar-viz-css">
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} className="bar-viz-bar" style={{ animationDelay: `${i * 0.12}s` }} />
            ))}
          </div>
        )}
        <div className={`agent-state agent-state-${state ?? 'disconnected'}`} style={{ color }}>
          <span className={`state-dot state-dot-${state ?? 'disconnected'}`} style={{ background: color }} />
          {label}
        </div>
      </div>

      <div className="topbar-right">
        <div className="topbar-stat">
          <span className="topbar-stat-label">TEMP</span>
          <span className="topbar-stat-value">{weather ?? '—'}</span>
        </div>
        <div className="topbar-stat">
          <span className="topbar-stat-label">BAT</span>
          <span className="topbar-stat-value">
            {battery !== null ? `${battery}%` : '—'}
          </span>
        </div>
        <div className="topbar-stat">
          <span className="topbar-stat-label">IST</span>
          <span className="topbar-stat-value time-val">{time}</span>
        </div>
        <div className="online-dot" title="Online" />
      </div>
    </header>
  )
}
