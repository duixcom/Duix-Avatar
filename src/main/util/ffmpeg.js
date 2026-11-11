import ffmpeg from 'fluent-ffmpeg'
import log from '../logger.js'
import { resolveFfmpegPaths } from '../config/runtime.mjs'

function initFFmpeg() {
  const paths = resolveFfmpegPaths({
    platform: process.platform,
    arch: process.arch,
    env: process.env,
    dirname: __dirname,
    resourcesPath: process.resourcesPath
  })
  log.debug('ENV:', `${process.env.NODE_ENV || 'production'}-${process.platform}-${process.arch}`)
  log.info('FFmpeg path:', paths.ffmpeg)
  log.info('FFprobe path:', paths.ffprobe)
  if (paths.ffmpeg) ffmpeg.setFfmpegPath(paths.ffmpeg)
  if (paths.ffprobe) ffmpeg.setFfprobePath(paths.ffprobe)
}

initFFmpeg()

export function extractAudio(videoPath, audioPath) {
  return new Promise((resolve, reject) => {
    ffmpeg(videoPath)
      .noVideo()
      .save(audioPath)
      .on('end', () => {
        log.info('audio split done')
        resolve(true)
      })
      .on('error', (err) => {
        reject(err)
      })
  })
}

export async function toH264(videoPath, outputPath) {
  // const hasNvidia = await detectNvidia()
  return new Promise((resolve, reject) => {
    ffmpeg(videoPath)
      .videoCodec('libx264')
      .outputOptions('-pix_fmt yuv420p')
      .save(outputPath)
      .on('end', () => {
        log.info('video convert to h264 done')
        resolve(true)
      })
      .on('error', (err) => {
        reject(err)
      })
  })
}

function detectNvidia() {
  return new Promise((resolve) => {
    const exec = require('child_process').exec;
    exec('nvidia-smi', (error, stdout, stderr) => {
      if (error || stderr) {
        resolve(false);
      } else {
        resolve(true);
      }
    });
  });
}

export function getVideoDuration(videoPath) {
  return new Promise((resolve, reject) => {
    ffmpeg(videoPath).ffprobe((err, data) => {
      if (err) {
        log.error("🚀 ~ ffmpeg ~ err:", err)
        reject(err)
      } else if (data && data.streams && data.streams.length > 0) {
        resolve(data.streams[0].duration) // 单位秒
      } else {
        log.error('No streams found')
        reject(new Error('No streams found'))
      }
    })
  })
}
