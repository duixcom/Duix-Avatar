import { selectAll, insert, insertCamb, selectByID } from '../dao/voice.js'
import { preprocessAndTran, makeAudio as makeAudioApi } from '../api/tts.js'
import { makeAudio as cambMakeAudio, cloneVoice as cambCloneVoice } from '../api/camb-tts.js'
import crypto from 'crypto'
import fs from 'fs'
import path from 'path'
import { assetPath, ttsProvider, cambConfig } from '../config/config.js'
import log from '../logger.js'
import { ipcMain } from 'electron'
import dayjs from 'dayjs'

const MODEL_NAME = 'voice'

export function getAllTimbre() {
  return selectAll()
}

export async function train(path, lang = 'zh') {
  path = path.replace(/\\/g, '/') // 将路径中的\替换为/

  if (ttsProvider === 'camb') {
    // Use CAMB AI voice cloning
    const res = await cambCloneVoice({
      audioFilePath: path,
      voiceName: `voice_${Date.now()}`,
      language: cambConfig.defaultLanguage
    })
    log.debug('~ train (camb) ~ res:', res)
    const cambVoiceId = res.voice_id
    if (!cambVoiceId) {
      return false
    }
    return insertCamb({ origin_audio_path: path, lang, camb_voice_id: cambVoiceId })
  }

  // Default: Fish Speech
  const res = await preprocessAndTran({
    format: path.split('.').pop(),
    reference_audio: path,
    lang
  })
  log.debug('~ train ~ res:', res)
  if (res.code !== 0) {
    return false
  } else {
    const { asr_format_audio_url, reference_audio_text } = res
    return insert({ origin_audio_path: path, lang, asr_format_audio_url, reference_audio_text })
  }
}

export function makeAudio4Video({voiceId, text}) {
  return makeAudio({voiceId, text, targetDir: assetPath.ttsProduct})
}

export function copyAudio4Video(filePath) {
  // 将filePath复制到ttsProduct目录下
  const targetDir = assetPath.ttsProduct
  const fileName = dayjs().format('YYYYMMDDHHmmssSSS') + path.extname(filePath)
  const targetPath = path.join(targetDir, fileName)
  fs.copyFileSync(filePath, targetPath)
  return fileName
}

export async function makeAudio({voiceId, text, targetDir}) {
  const uuid = crypto.randomUUID()
  const voice = selectByID(voiceId)

  if (ttsProvider === 'camb' && voice.camb_voice_id) {
    // Use CAMB AI TTS with cloned voice
    try {
      const audioBuffer = await cambMakeAudio({
        text,
        voice_id: voice.camb_voice_id,
        language: cambConfig.defaultLanguage,
        speech_model: cambConfig.speechModel
      })
      if (!fs.existsSync(targetDir)) {
        fs.mkdirSync(targetDir, { recursive: true })
      }
      fs.writeFileSync(path.join(targetDir, `${uuid}.wav`), Buffer.from(audioBuffer), 'binary')
      return `${uuid}.wav`
    } catch (error) {
      log.error('Error generating audio via CAMB:', error)
      throw error
    }
  }

  // Default: Fish Speech
  return makeAudioApi({
    speaker: uuid,
    text,
    format: 'wav',
    topP: 0.7,
    max_new_tokens: 1024,
    chunk_length: 100,
    repetition_penalty: 1.2,
    temperature: 0.7,
    need_asr: false,
    streaming: false,
    is_fixed_seed: 0,
    is_norm: 1,
    reference_audio: voice.asr_format_audio_url,
    reference_text: voice.reference_audio_text
  })
    .then((res) => {
      if (!fs.existsSync(targetDir)) {
        fs.mkdirSync(targetDir, {
          recursive: true
        })
      }
      fs.writeFileSync(path.join(targetDir, `${uuid}.wav`), res, 'binary')
      return `${uuid}.wav`
    })
    .catch((error) => {
      log.error('Error generating audio:', error)
      throw error
    })
}

/**
 * 试听音频
 * @param {string} voiceId
 * @param {string} text
 * @returns
 */
export async function audition(voiceId, text) {
  const tmpDir = require('os').tmpdir()
  console.log("🚀 ~ audition ~ tmpDir:", tmpDir)
  const audioPath = await makeAudio({ voiceId, text, targetDir: tmpDir })
  return path.join(tmpDir, audioPath)
}

export function init() {
  ipcMain.handle(MODEL_NAME + '/audition', (event, ...args) => {
    return audition(...args)
  })
}