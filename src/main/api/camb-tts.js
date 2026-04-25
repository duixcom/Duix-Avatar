import axios from 'axios'
import { cambConfig } from '../config/config.js'
import log from '../logger.js'
import fs from 'fs'
import path from 'path'
import FormData from 'form-data'

const CAMB_API_BASE = 'https://client.camb.ai/apis'

function getHeaders() {
  return {
    'x-api-key': cambConfig.apiKey,
    'Content-Type': 'application/json'
  }
}

/**
 * Generate audio using CAMB AI streaming TTS
 * @param {Object} param - { text, voice_id, language, speech_model }
 * @returns {Promise<Buffer>} audio buffer
 */
export async function makeAudio(param) {
  log.debug('~ camb makeAudio ~ param:', JSON.stringify(param))

  const response = await axios.post(
    `${CAMB_API_BASE}/tts-stream`,
    {
      text: param.text,
      voice_id: param.voice_id || cambConfig.defaultVoiceId,
      language: param.language || 'en-us',
      speech_model: param.speech_model || 'mars-flash',
      output_configuration: { format: 'wav' }
    },
    {
      headers: getHeaders(),
      responseType: 'arraybuffer',
      timeout: 60000
    }
  )

  return response.data
}

/**
 * Clone a voice using CAMB AI
 * @param {Object} param - { audioFilePath, voiceName, gender, language }
 * @returns {Promise<{ voice_id: number }>}
 */
// Map BCP-47 language codes to CAMB numeric IDs for voice cloning
const LANG_ID_MAP = {
  'en-us': 1, 'es-es': 54, 'fr-fr': 76, 'de-de': 31,
  'ja-jp': 88, 'hi-in': 81, 'pt-br': 111, 'zh-cn': 139,
  'ko-kr': 93, 'it-it': 86, 'nl-nl': 48, 'ru-ru': 120,
}

export async function cloneVoice(param) {
  log.debug('~ camb cloneVoice ~ param:', JSON.stringify({ ...param, audioFilePath: '...' }))
  log.debug('~ camb cloneVoice ~ apiKey present:', !!cambConfig.apiKey)

  const langId = LANG_ID_MAP[param.language] || param.language || 1

  const form = new FormData()
  form.append('file', fs.createReadStream(param.audioFilePath))
  form.append('voice_name', param.voiceName || `voice_${Date.now()}`)
  form.append('gender', String(param.gender || 1))
  form.append('language', String(langId))
  form.append('enhance_audio', 'true')

  try {
    const response = await axios.post(`${CAMB_API_BASE}/create-custom-voice`, form, {
      headers: {
        'x-api-key': cambConfig.apiKey,
        ...form.getHeaders()
      },
      timeout: 120000
    })
    log.debug('~ camb cloneVoice ~ response:', JSON.stringify(response.data))
    return response.data
  } catch (err) {
    log.error('~ camb cloneVoice ~ error:', err.response?.status, err.response?.data || err.message)
    throw err
  }
}

/**
 * List all available voices
 * @returns {Promise<Array>}
 */
export async function listVoices() {
  const response = await axios.get(`${CAMB_API_BASE}/list-voices`, {
    headers: getHeaders()
  })

  return response.data
}
