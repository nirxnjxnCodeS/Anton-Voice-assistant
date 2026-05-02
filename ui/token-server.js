import { AccessToken } from 'livekit-server-sdk'
import express from 'express'
import cors from 'cors'
import dotenv from 'dotenv'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))
dotenv.config({ path: join(__dirname, '..', '.env') })

const app = express()
app.use(cors({ origin: ['http://localhost:3000', 'http://127.0.0.1:3000'] }))

const API_KEY = process.env.LIVEKIT_API_KEY
const API_SECRET = process.env.LIVEKIT_API_SECRET

if (!API_KEY || !API_SECRET) {
  console.error('[Anton] Missing LIVEKIT_API_KEY or LIVEKIT_API_SECRET in ../.env')
  process.exit(1)
}

app.get('/token', async (req, res) => {
  const room = String(req.query.room || 'anton').slice(0, 64)
  const username = String(req.query.username || 'niranjan').slice(0, 64)

  try {
    const at = new AccessToken(API_KEY, API_SECRET, {
      identity: username,
      name: 'Niranjan',
      ttl: 3600,
    })
    at.addGrant({
      roomJoin: true,
      room,
      canPublish: true,
      canSubscribe: true,
      canPublishData: true,
    })
    const token = await at.toJwt()
    res.json({ token })
  } catch (err) {
    console.error('[Anton] Token error:', err.message)
    res.status(500).json({ error: 'Token generation failed' })
  }
})

app.listen(3001, () => {
  console.log('[Anton] Token server → http://localhost:3001')
  console.log('[Anton] Using key:', API_KEY?.slice(0, 8) + '...')
})
