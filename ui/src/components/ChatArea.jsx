import { useMemo, useEffect, useRef } from 'react'
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
}

function detectTool(text) {
  if (!text) return null
  const lower = text.toLowerCase()
  for (const [kw, tool] of Object.entries(TOOL_KEYWORDS)) {
    if (lower.includes(kw)) return tool
  }
  return null
}

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function Message({ msg, isFresh, isSpeaking }) {
  const isAnton = msg.role === 'anton'
  const tool = isAnton && msg.final ? detectTool(msg.text) : null

  return (
    <div className={`message ${isAnton ? 'anton' : 'user'}${isFresh ? ' message-new' : ''}`}>
      <div className={`avatar${isSpeaking ? ' avatar-speaking' : ''}`}>
        {isAnton ? 'A' : 'N'}
      </div>
      <div className="bubble-wrap">
        <div
          className="bubble"
          style={!msg.final ? { opacity: 0.55, borderStyle: 'dashed', minHeight: '48px', transition: 'none' } : undefined}
        >
          {msg.text}
          {!msg.final && (
            <span
              style={{
                color: 'var(--accent)',
                animation: 'blink 1s step-end infinite',
                marginLeft: 3,
              }}
            >
              ▌
            </span>
          )}
        </div>
        {tool && (
          <div className="tool-badge">
            <span className="tool-badge-dot" />
            {tool.toUpperCase()}
          </div>
        )}
        {msg.final && (
          <div className="msg-time">{formatTime(msg.firstReceivedTime)}</div>
        )}
      </div>
    </div>
  )
}

function ThinkingBubble() {
  return (
    <div className="message anton">
      <div className="avatar">A</div>
      <div className="bubble-wrap">
        <div className="bubble thinking">
          <span className="dot" />
          <span className="dot" />
          <span className="dot" />
        </div>
      </div>
    </div>
  )
}

export default function ChatArea() {
  const { state, agent } = useVoiceAssistant()
  const { localParticipant } = useLocalParticipant()
  const bottomRef = useRef(null)
  const prevCountRef = useRef(0)
  const seenFinalIds = useRef(new Set())

  const tracks = useTracks([Track.Source.Microphone])

  const agentTrack = useMemo(
    () => tracks.find(t => agent && t.participant?.identity === agent.identity),
    [tracks, agent]
  )

  const userTrack = useMemo(
    () => tracks.find(t => localParticipant && t.participant?.identity === localParticipant.identity),
    [tracks, localParticipant]
  )

  const { segments: agentSegments } = useTrackTranscription(agentTrack)
  const { segments: userSegments } = useTrackTranscription(userTrack)

  const messages = useMemo(() => {
    const all = [
      ...(agentSegments ?? []).map(s => ({
        id: `a-${s.id}`,
        role: 'anton',
        text: s.text,
        firstReceivedTime: s.firstReceivedTime,
        final: s.final,
      })),
      ...(userSegments ?? []).map(s => ({
        id: `u-${s.id}`,
        role: 'user',
        text: s.text,
        firstReceivedTime: s.firstReceivedTime,
        final: s.final,
      })),
    ]
    return all.sort((a, b) => a.firstReceivedTime - b.firstReceivedTime)
  }, [agentSegments, userSegments])

  useEffect(() => {
    const newCount = messages.length
    if (newCount > prevCountRef.current) {
      bottomRef.current?.scrollIntoView({ block: 'end' })
      prevCountRef.current = newCount
    }
  }, [messages.length])

  const showThinking = state === 'thinking'

  return (
    <main className="chat-area">
      <div className="scan-line" />
      <div className="corner corner-tl" />
      <div className="corner corner-tr" />
      <div className="corner corner-bl" />
      <div className="corner corner-br" />

      <div className="messages">
        {messages.length === 0 && !showThinking && (
          <div className="empty-state">
            <span className="empty-icon">◈</span>
            <p>ANTON ONLINE</p>
            <p className="empty-sub">Awaiting voice input or quick command</p>
          </div>
        )}

        {messages.map(msg => {
          const isFresh = msg.final && !seenFinalIds.current.has(msg.id)
          if (msg.final) seenFinalIds.current.add(msg.id)
          const isSpeaking = state === 'speaking' && msg.role === 'anton' && !msg.final
          return <Message key={msg.id} msg={msg} isFresh={isFresh} isSpeaking={isSpeaking} />
        })}

        {showThinking && <ThinkingBubble />}

        <div ref={bottomRef} style={{ height: 1, flexShrink: 0 }} />
      </div>
    </main>
  )
}
