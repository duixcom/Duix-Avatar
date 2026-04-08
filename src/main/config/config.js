import path from 'path'
import os from 'os'
import fs from 'fs'

// Load .env from parent camb-ai-work directory as fallback
const parentEnvPath = path.resolve(process.cwd(), '..', '.env')
try {
  if (fs.existsSync(parentEnvPath)) {
    const content = fs.readFileSync(parentEnvPath, 'utf-8')
    for (const line of content.split('\n')) {
      const match = line.match(/^([^#=]+)=(.*)$/)
      if (match && !process.env[match[1].trim()]) {
        process.env[match[1].trim()] = match[2].trim()
      }
    }
  }
} catch { /* ignore */ }

const isDev = process.env.NODE_ENV === 'development'
const isWin = process.platform === 'win32'

export const serviceUrl = {
  face2face: isDev ? 'http://192.168.4.204:8383/easy' : 'http://127.0.0.1:8383/easy',
  tts: isDev ? 'http://192.168.4.204:18180' : 'http://127.0.0.1:18180'
}

// TTS provider: 'fish' (default, local Fish Speech) or 'camb' (CAMB AI cloud)
export const ttsProvider = process.env.TTS_PROVIDER || 'fish'

export const cambConfig = {
  apiKey: process.env.CAMB_API_KEY || '',
  defaultVoiceId: parseInt(process.env.CAMB_VOICE_ID || '147320', 10),
  defaultLanguage: process.env.CAMB_LANGUAGE || 'en-us',
  speechModel: process.env.CAMB_SPEECH_MODEL || 'mars-flash'
}

export const assetPath = {
  model: isWin
    ? path.join('D:', 'duix_avatar_data', 'face2face', 'temp')
    : path.join(os.homedir(), 'duix_avatar_data', 'face2face', 'temp'), // 模特视频
  ttsProduct: isWin
    ? path.join('D:', 'duix_avatar_data', 'face2face', 'temp')
    : path.join(os.homedir(), 'duix_avatar_data', 'face2face', 'temp'), // TTS 产物
  ttsRoot: isWin
    ? path.join('D:', 'duix_avatar_data', 'voice', 'data')
    : path.join(os.homedir(), 'duix_avatar_data', 'voice', 'data'), // TTS服务根目录
  ttsTrain: isWin
    ? path.join('D:', 'duix_avatar_data', 'voice', 'data', 'origin_audio')
    : path.join(os.homedir(), 'duix_avatar_data', 'voice', 'data', 'origin_audio') // TTS 训练产物
}
