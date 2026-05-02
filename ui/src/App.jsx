import { useState, useEffect, useCallback, useRef } from 'react'
import { LiveKitRoom, RoomAudioRenderer } from '@livekit/components-react'
import TopBar from './components/TopBar'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'
import InputBar from './components/InputBar'

const BOOT_LINES = [
  '> Initializing Anton v2.4.1...',
  '> Loading MCP tools... [OK]',
  '> Connecting to LiveKit... [OK]',
  '> STT pipeline ready... [OK]',
  '> All systems nominal.',
]

function BootScreen({ error, onRetry }) {
  const [phase, setPhase] = useState(0)
  const [greeting, setGreeting] = useState('')

  useEffect(() => {
    const h = new Date().getHours()
    setGreeting(
      h < 12 ? 'GOOD MORNING, SIR'
      : h < 17 ? 'GOOD AFTERNOON, SIR'
      : 'GOOD EVENING, SIR'
    )
    const timers = [
      setTimeout(() => setPhase(1), 400),
      setTimeout(() => setPhase(2), 1200),
      setTimeout(() => setPhase(3), 2200),
      setTimeout(() => setPhase(4), 3400),
      setTimeout(() => setPhase(5), 3800),
    ]
    return () => timers.forEach(clearTimeout)
  }, [])

  if (error) {
    return (
      <div className="boot-screen">
        <div className="boot-logo error">⚠</div>
        <div className="boot-text">CONNECTION FAILED</div>
        <div className="boot-error">{error}</div>
        <button className="boot-retry" onClick={onRetry}>RETRY</button>
      </div>
    )
  }

  return (
    <div className="boot-screen boot-dramatic">
      {phase >= 1 && <div className="boot-company">NIRANJAN INDUSTRIES</div>}
      {phase >= 2 && (
        <div className="arc-reactor boot-arc">
          <div className="arc-inner" />
          <div className="arc-ring arc-ring-1" />
          <div className="arc-ring arc-ring-2" />
        </div>
      )}
      {phase >= 3 && (
        <div className="boot-lines">
          {BOOT_LINES.map((line, i) => (
            <div
              key={i}
              className="boot-line"
              style={{ animationDelay: `${i * 0.18}s` }}
            >
              {line}
            </div>
          ))}
        </div>
      )}
      {phase >= 4 && <div className="boot-greeting">{greeting}</div>}
      {phase >= 5 && (
        <div className="boot-bar" style={{ marginTop: 12 }}>
          <div className="boot-fill" />
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [token, setToken] = useState(null)
  const [error, setError] = useState(null)
  const [fetchState, setFetchState] = useState('fetching')
  const [minBootDone, setMinBootDone] = useState(false)
  const hasBootedRef = useRef(false)

  useEffect(() => {
    const t1 = setTimeout(() => setMinBootDone(true), 2000)
    const t2 = setTimeout(() => setMinBootDone(true), 4000)
    return () => { clearTimeout(t1); clearTimeout(t2) }
  }, [])

  const fetchToken = useCallback(async () => {
    setFetchState('fetching')
    setError(null)
    setToken(null)
    try {
      const res = await fetch('/token?room=anton&username=niranjan')
      if (!res.ok) throw new Error(`Server responded ${res.status}`)
      const data = await res.json()
      if (!data.token) throw new Error('No token received')
      setToken(data.token)
      setFetchState('ready')
    } catch (err) {
      setError(err.message)
      setFetchState('error')
    }
  }, [])

  useEffect(() => {
    fetchToken()
  }, [fetchToken])

  if (!token || (!minBootDone && !hasBootedRef.current)) {
    return (
      <BootScreen
        state={fetchState}
        error={error}
        onRetry={fetchToken}
      />
    )
  }

  hasBootedRef.current = true

  return (
    <LiveKitRoom
      token={token}
      serverUrl={import.meta.env.VITE_LIVEKIT_URL}
      audio={true}
      video={false}
      connect={true}
      onDisconnected={() => {
        setToken(null)
        setFetchState('fetching')
        setTimeout(fetchToken, 3000)
      }}
      onError={(err) => {
        console.error('[Anton] Room error:', err)
      }}
    >
      <RoomAudioRenderer />
      <div className="app">
        <TopBar />
        <div className="body">
          <Sidebar />
          <ChatArea />
        </div>
        <InputBar />
      </div>
    </LiveKitRoom>
  )
}
