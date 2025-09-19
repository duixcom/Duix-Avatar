import path from 'path'
import os from 'os'
import fs from 'fs'
import { app } from 'electron'

const isDev = process.env.NODE_ENV === 'development'
const isWin = process.platform === 'win32'

function loadUserConfig() {
  try {
    // Electron user-specific config dir
    const userDataDir = app && app.getPath ? app.getPath('userData') : null
    let cfgPath
    if (userDataDir) {
      cfgPath = path.join(userDataDir, 'config.json')
    } else {
      // Fallback for non-Electron contexts
      const fallbackBase = isWin
        ? path.join(os.homedir(), 'AppData', 'Roaming', 'HeyGem')
        : path.join(os.homedir(), '.config', 'HeyGem')
      cfgPath = path.join(fallbackBase, 'config.json')
    }
    if (fs.existsSync(cfgPath)) {
      const raw = fs.readFileSync(cfgPath, 'utf-8')
      return JSON.parse(raw)
    }
  } catch (e) {
    // ignore parse or fs errors and fallback to env/defaults
  }
  return {}
}

const CFG = loadUserConfig()

// Allow overriding service host/ports via environment variables for LAN deployment
// HEYGEM_HOST: target host or IP (e.g., your LAN IP like 192.168.1.100)
// HEYGEM_TTS_PORT: TTS service host port (default 18180)
// HEYGEM_VIDEO_PORT: Face2Face service host port (default 8383)
const HEYGEM_HOST = CFG.HEYGEM_HOST || process.env.HEYGEM_HOST || '192.168.110.22'
const HEYGEM_TTS_PORT = CFG.HEYGEM_TTS_PORT || process.env.HEYGEM_TTS_PORT || '18180'
const HEYGEM_VIDEO_PORT = CFG.HEYGEM_VIDEO_PORT || process.env.HEYGEM_VIDEO_PORT || '8383'

export const serviceUrl = {
  face2face: `http://${HEYGEM_HOST}:${HEYGEM_VIDEO_PORT}/easy`,
  tts: `http://${HEYGEM_HOST}:${HEYGEM_TTS_PORT}`
}

export const assetPath = {
  // Allow overriding asset directories to support LAN shared folders
  model:
    CFG.HEYGEM_MODEL_DIR || process.env.HEYGEM_MODEL_DIR ||
    (isWin
      ? '\\\\192.168.110.22\\heygem_data\\face2face\\temp'
      : path.join(os.homedir(), 'heygem_data', 'face2face', 'temp')), // 模特视频
  ttsProduct:
    CFG.HEYGEM_TTS_PRODUCT_DIR || process.env.HEYGEM_TTS_PRODUCT_DIR ||
    (isWin
      ? '\\\\192.168.110.22\\heygem_data\\face2face\\temp'
      : path.join(os.homedir(), 'heygem_data', 'face2face', 'temp')), // TTS 产物
  ttsRoot:
    CFG.HEYGEM_TTS_ROOT || process.env.HEYGEM_TTS_ROOT ||
    (isWin
      ? '\\\\192.168.110.22\\heygem_data\\voice\\data'
      : path.join(os.homedir(), 'heygem_data', 'voice', 'data')), // TTS服务根目录
  ttsTrain:
    CFG.HEYGEM_TTS_TRAIN_DIR || process.env.HEYGEM_TTS_TRAIN_DIR ||
    (isWin
      ? '\\\\192.168.110.22\\heygem_data\\voice\\data\\origin_audio'
      : path.join(os.homedir(), 'heygem_data', 'voice', 'data', 'origin_audio')) // TTS 训练产物
}
