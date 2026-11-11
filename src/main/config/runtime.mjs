import path from 'node:path'

export function createRuntimeConfig({ platform, homedir, env = {} }) {
  const paths = platform === 'win32' ? path.win32 : path.posix
  const dataRoot = env.DUIX_DATA_ROOT || (platform === 'win32'
    ? paths.join('D:', 'duix_avatar_data')
    : paths.join(homedir, 'duix_avatar_data'))

  return {
    serviceUrl: {
      // The video API base includes /easy; both overrides may include a trailing slash.
      face2face: (env.DUIX_F2F_URL || 'http://127.0.0.1:8383/easy').replace(/\/+$/, ''),
      tts: (env.DUIX_TTS_URL || 'http://127.0.0.1:18180').replace(/\/+$/, '')
    },
    assetPath: {
      model: paths.join(dataRoot, 'face2face', 'temp'),
      ttsProduct: paths.join(dataRoot, 'face2face', 'temp'),
      ttsRoot: paths.join(dataRoot, 'voice', 'data'),
      ttsTrain: paths.join(dataRoot, 'voice', 'data', 'origin_audio')
    }
  }
}

export function resolveFfmpegPaths({ platform, arch, env = {}, dirname, resourcesPath }) {
  let ffmpeg
  let ffprobe

  if (platform === 'linux' && arch === 'arm64') {
    // The repository bundles x86 executables. Ubuntu's native package supports GB10.
    ffmpeg = '/usr/bin/ffmpeg'
    ffprobe = '/usr/bin/ffprobe'
  } else if (platform === 'win32' || platform === 'linux') {
    const paths = platform === 'win32' ? path.win32 : path.posix
    const root = env.NODE_ENV === 'development'
      ? paths.join(dirname, '../../resources/ffmpeg')
      : paths.join(resourcesPath, 'app.asar.unpacked', 'resources', 'ffmpeg')
    const binaryDir = platform === 'win32'
      ? paths.join(root, 'win-amd64', 'bin')
      : paths.join(root, 'linux-amd64')
    const extension = platform === 'win32' ? '.exe' : ''
    ffmpeg = paths.join(binaryDir, `ffmpeg${extension}`)
    ffprobe = paths.join(binaryDir, `ffprobe${extension}`)
  }

  return {
    ffmpeg: env.DUIX_FFMPEG_PATH || ffmpeg,
    ffprobe: env.DUIX_FFPROBE_PATH || ffprobe
  }
}
