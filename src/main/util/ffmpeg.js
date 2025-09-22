import ffmpeg from 'fluent-ffmpeg'
import path from 'path'
import log from '../logger.js'

function initFFmpeg() {
  if (!process.env.NODE_ENV) {
    process.env.NODE_ENV = 'production'
  }

  const key = `${process.env.NODE_ENV}-${process.platform}`

  const ffmpegPath = {
    'development-win32': path.join(__dirname, '../../resources/ffmpeg/win-amd64/bin/ffmpeg.exe'),
    'development-linux': path.join(__dirname, '../../resources/ffmpeg/linux-amd64/ffmpeg'),
    'development-darwin': path.join(__dirname, '../../resources/ffmpeg/mac-x64/ffmpeg'),

    'production-win32': path.join(
      process.resourcesPath,
      'app.asar.unpacked',
      'resources',
      'ffmpeg',
      'win-amd64',
      'bin',
      'ffmpeg.exe'
    ),
    'production-linux': path.join(
      process.resourcesPath,
      'app.asar.unpacked',
      'resources',
      'ffmpeg',
      'linux-amd64',
      'ffmpeg'
    ),
    'production-darwin': path.join(
      process.resourcesPath,
      'app.asar.unpacked',
      'resources',
      'ffmpeg',
      'mac-x64',
      'ffmpeg'
    )
  }

  const ffprobePath = {
    'development-win32': path.join(__dirname, '../../resources/ffmpeg/win-amd64/bin/ffprobe.exe'),
    'development-linux': path.join(__dirname, '../../resources/ffmpeg/linux-amd64/ffprobe'),
    'development-darwin': path.join(__dirname, '../../resources/ffmpeg/mac-x64/ffprobe'),

    'production-win32': path.join(
      process.resourcesPath,
      'app.asar.unpacked',
      'resources',
      'ffmpeg',
      'win-amd64',
      'bin',
      'ffprobe.exe'
    ),
    'production-linux': path.join(
      process.resourcesPath,
      'app.asar.unpacked',
      'resources',
      'ffmpeg',
      'linux-amd64',
      'ffprobe'
    ),
    'production-darwin': path.join(
      process.resourcesPath,
      'app.asar.unpacked',
      'resources',
      'ffmpeg',
      'mac-x64',
      'ffprobe'
    )
  }

  const ffmpegPathValue = ffmpegPath[key]
  const ffprobePathValue = ffprobePath[key]

  log.debug('ENV:', key)
  log.info('FFmpeg path:', ffmpegPathValue)
  ffmpeg.setFfmpegPath(ffmpegPathValue)

  log.info('FFprobe path:', ffprobePathValue)
  ffmpeg.setFfprobePath(ffprobePathValue)
}

initFFmpeg()

export function extractAudio(videoPath, audioPath) {
  return new Promise((resolve, reject) => {
    ffmpeg(videoPath)
      .noVideo()
      .save(audioPath)
      .on('end', () => {
        log.info('Audio extraction completed.')
        resolve(true)
      })
      .on('error', (err) => {
        log.error('Audio extraction failed:', err)
        reject(err)
      })
  })
}

export async function toH264(videoPath, outputPath) {
  const hasNvidia = await detectNvidia()
  log.debug('hasNvidia:', hasNvidia)
  return new Promise((resolve, reject) => {
    ffmpeg(videoPath)
      .videoCodec(hasNvidia ? 'h264_nvenc' : 'libx264')
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
        log.error('FFprobe error:', err)
        reject(err)
      } else if (data?.streams?.length > 0) {
        resolve(data.streams[0].duration) // 单位秒
      } else {
        log.error('No video streams found.')
        reject(new Error('No video streams found.'))
      }
    })
  })
}
