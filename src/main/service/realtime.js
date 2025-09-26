import { WebSocketServer } from 'ws'
import log from '../logger.js'
import { makeAudio as makeAudioApi } from '../api/tts.js'
import { makeVideo as makeVideoApi, getVideoStatus } from '../api/f2f.js'
import { selectByID as selectF2FModelByID } from '../dao/f2f-model.js'
import { selectByID as selectVoiceByID } from '../dao/voice.js'
import crypto from 'crypto'
import fs from 'fs'
import path from 'path'
import { assetPath } from '../config/config.js'
import ffmpeg from 'fluent-ffmpeg'
import { connectToTiktok } from './tiktok.js'

const MODEL_NAME = 'realtime'
const CHUNK_DURATION = 1 // seconds

function init() {
  const wss = new WebSocketServer({ port: 8080 })

  wss.on('connection', function connection(ws) {
    let textQueue = []
    let isProcessing = false
    let model, voice
    let isRecording = false
    let recordingDir = null
    let recordedVideoPath = null

    log.info('Real-time service: client connected')

    ws.on('message', async function message(data) {
      try {
        const message = JSON.parse(data)
        log.info('Real-time service: received message:', message)

        if (message.type === 'start') {
          model = selectF2FModelByID(message.data.modelId)
          voice = selectVoiceByID(message.data.voiceId)
          textQueue.push(message.data.text)
          processTextQueue()
        } else if (message.type === 'start-tiktok-stream') {
          if (recordedVideoPath) {
            const { serverUrl, streamKey } = message.data
            startTiktokStream(serverUrl, streamKey, ws, recordedVideoPath)
          } else {
            ws.send(JSON.stringify({ type: 'error', data: 'No recorded video to stream.' }))
          }
        } else if (message.type === 'start-tiktok-comment-listener') {
          connectToTiktok(message.data.username, (comment) => {
            textQueue.push(comment)
            processTextQueue()
          })
        } else if (message.type === 'start-recording') {
          isRecording = true
          recordingDir = path.join(assetPath.model, 'recordings', crypto.randomUUID())
          fs.mkdirSync(recordingDir, { recursive: true })
        } else if (message.type === 'stop-recording') {
          isRecording = false
          recordedVideoPath = await concatenateRecordedChunks(recordingDir)
          ws.send(JSON.stringify({ type: 'recording-finished', data: { path: recordedVideoPath } }))
        }
      } catch (error) {
        log.error('Real-time service error:', error)
        ws.send(JSON.stringify({ type: 'error', data: error.message }))
      }
    })

    async function processTextQueue() {
      if (isProcessing || textQueue.length === 0) {
        return
      }
      isProcessing = true
      const text = textQueue.shift()
      const audioStream = await getAudioStream(voice, text)
      await processAudioStream(audioStream, model, ws, isRecording, recordingDir)
      isProcessing = false
      processTextQueue()
    }

    ws.send(JSON.stringify({ type: 'connected' }))
  })

  log.info('Real-time service initialized on port 8080')
}

async function getAudioStream(voice, text) {
  const uuid = crypto.randomUUID()
  const response = await makeAudioApi({
    speaker: uuid,
    text,
    format: 'wav',
    topP: 0.7,
    max_new_tokens: 1024,
    chunk_length: 100,
    repetition_penalty: 1.2,
    temperature: 0.7,
    need_asr: false,
    streaming: true,
    is_fixed_seed: 0,
    is_norm: 1,
    reference_audio: voice.asr_format_audio_url,
    reference_text: voice.reference_audio_text
  }, { responseType: 'stream' })

  return response
}

function processAudioStream(audioStream, model, ws, isRecording, recordingDir) {
  return new Promise((resolve, reject) => {
    const chunkDir = path.join(assetPath.ttsProduct, 'chunks', crypto.randomUUID())
    fs.mkdirSync(chunkDir, { recursive: true })

    const ffmpegProc = ffmpeg(audioStream)
      .toFormat('wav')
      .outputOptions([
        '-f', 'segment',
        '-segment_time', `${CHUNK_DURATION}`,
        '-c', 'copy'
      ])
      .on('end', () => {
        log.info('ffmpeg chunking finished')
        ws.send(JSON.stringify({ type: 'end-of-stream' }))
        fs.rm(chunkDir, { recursive: true, force: true }, () => {})
        resolve()
      })
      .on('error', (err) => {
        log.error('ffmpeg error:', err)
        reject(err)
      })
      .save(path.join(chunkDir, 'chunk-%03d.wav'))

    const processedChunks = new Set()
    const watcher = fs.watch(chunkDir, async (eventType, filename) => {
      if (filename && filename.endsWith('.wav') && !processedChunks.has(filename)) {
        processedChunks.add(filename)
        const audioPath = path.join(chunkDir, filename)
        generateVideoChunk(audioPath, model, ws, isRecording, recordingDir)
      }
    })
  })
}

async function generateVideoChunk(audioPath, model, ws, isRecording, recordingDir) {
  const videoResult = await submitVideoTask(audioPath, model)
  if (videoResult && videoResult.code === 10000) {
    const videoPath = await pollForVideo(videoResult.data.code)
    if (videoPath) {
      const fullVideoPath = path.join(assetPath.model, videoPath)
      const videoData = fs.readFileSync(fullVideoPath)
      ws.send(videoData)

      if (isRecording) {
        fs.copyFileSync(fullVideoPath, path.join(recordingDir, path.basename(videoPath)))
      }

      fs.unlinkSync(fullVideoPath)
      fs.unlinkSync(audioPath)
    }
  }
}

async function concatenateRecordedChunks(recordingDir) {
  return new Promise((resolve, reject) => {
    const chunkPaths = fs.readdirSync(recordingDir).map(p => path.join(recordingDir, p))
    const fullVideoPath = path.join(assetPath.model, `recorded-video-${crypto.randomUUID()}.mp4`)
    const ffmpegCmd = ffmpeg()

    chunkPaths.forEach(p => {
      ffmpegCmd.input(p)
    })

    ffmpegCmd
      .on('end', () => {
        log.info('Concatenation finished')
        fs.rm(recordingDir, { recursive: true, force: true }, () => {})
        resolve(fullVideoPath)
      })
      .on('error', (err) => {
        log.error('Concatenation error:', err)
        reject(err)
      })
      .mergeToFile(fullVideoPath, assetPath.model)
  })
}


async function submitVideoTask(audioPath, model) {
  const uuid = crypto.randomUUID()
  const relativeAudioPath = path.relative(assetPath.ttsRoot, audioPath)

  const param = {
    audio_url: relativeAudioPath.replace(/\\/g, '/'),
    video_url: model.video_path,
    code: uuid,
    chaofen: 0,
    watermark_switch: 0,
    pn: 1
  }

  const f2fAudioDir = path.dirname(path.join(assetPath.ttsRoot, relativeAudioPath))
  if (!fs.existsSync(f2fAudioDir)) {
    fs.mkdirSync(f2fAudioDir, { recursive: true })
  }
  fs.copyFileSync(audioPath, path.join(assetPath.ttsRoot, relativeAudioPath))

  const result = await makeVideoApi(param)
  log.info('Real-time service: video chunk synthesis result:', result)
  return result
}


async function pollForVideo(taskCode) {
  let attempts = 0
  while (attempts < 60) { // Poll for 30 seconds
    const statusRes = await getVideoStatus(taskCode)
    if (statusRes.code === 10000 && statusRes.data.status === 2) {
      return statusRes.data.result
    }
    await new Promise(resolve => setTimeout(resolve, 500))
    attempts++
  }
  return null
}

function startTiktokStream(serverUrl, streamKey, ws, videoPath) {
  const rtmpUrl = `${serverUrl}/${streamKey}`

  ffmpeg(videoPath)
    .inputOptions('-re')
    .videoCodec('libx264')
    .audioCodec('aac')
    .toFormat('flv')
    .save(rtmpUrl)
    .on('start', (commandLine) => {
      log.info('ffmpeg started with command:', commandLine)
      ws.send(JSON.stringify({ type: 'tiktok-stream-started' }))
    })
    .on('error', (err) => {
      log.error('ffmpeg error:', err)
      ws.send(JSON.stringify({ type: 'tiktok-stream-error', data: err.message }))
    })
    .on('end', () => {
      log.info('ffmpeg finished streaming')
      ws.send(JSON.stringify({ type: 'tiktok-stream-finished' }))
    })
}


export { init }
