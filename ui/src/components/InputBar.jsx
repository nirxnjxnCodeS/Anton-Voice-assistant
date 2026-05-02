import { useCallback } from 'react'
import { useLocalParticipant, useChat, useVoiceAssistant } from '@livekit/components-react'

const STATE_PROMPTS = {
  listening:    '[ LISTENING FOR COMMAND... ]',
  thinking:     '[ PROCESSING QUERY...      ]',
  speaking:     '[ ANTON RESPONDING...      ]',
  connecting:   '[ CONNECTING TO ROOM...    ]',
  initializing: '[ INITIALIZING AGENT...    ]',
  disconnected: '[ SYSTEM READY             ]',
}

const CHIPS = ['briefing', 'weather', 'emails']

export default function InputBar() {
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant()
  const { send } = useChat()
  const { state } = useVoiceAssistant()

  const toggleMic = useCallback(async () => {
    if (!localParticipant) return
    try {
      await localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled)
    } catch (err) {
      console.error('[Anton] Mic toggle error:', err)
    }
  }, [localParticipant, isMicrophoneEnabled])

  const sendChip = useCallback(async (text) => {
    if (!send) return
    try {
      await send(text)
    } catch (err) {
      console.error('[Anton] Send error:', err)
    }
  }, [send])

  const prompt = STATE_PROMPTS[state] ?? '[ SYSTEM READY ]'

  return (
    <footer className="inputbar">
      <button
        className={`mic-btn ${isMicrophoneEnabled ? 'mic-active' : 'mic-muted'}`}
        onClick={toggleMic}
        title={isMicrophoneEnabled ? 'Mute microphone' : 'Unmute microphone'}
        aria-label={isMicrophoneEnabled ? 'Mute microphone' : 'Unmute microphone'}
      >
        {isMicrophoneEnabled && <span className="mic-ring mic-ring-1" />}
        {isMicrophoneEnabled && <span className="mic-ring mic-ring-2" />}
        <span className="mic-icon">
          {isMicrophoneEnabled ? '🎙' : '🔇'}
        </span>
      </button>

      <div className="input-display">
        <span className="cursor">▌</span>
        <span className="input-prompt">{prompt}</span>
      </div>

      <div className="chips">
        {CHIPS.map((chip) => (
          <button
            key={chip}
            className="chip"
            onClick={() => sendChip(chip)}
          >
            {chip}
          </button>
        ))}
      </div>
    </footer>
  )
}
