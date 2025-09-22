import path from 'path'
import os from 'os'

const isDev = process.env.NODE_ENV === 'development'
const platform = process.platform // 'win32' | 'linux' | 'darwin'

export const serviceUrl = {
  face2face: isDev ? 'http://192.168.4.204:8383/easy' : 'http://127.0.0.1:8383/easy',
  tts: isDev ? 'http://192.168.4.204:18180' : 'http://127.0.0.1:18180'
}

// 根据操作系统选择不同的路径
const getBasePath = () => {
  if (platform === 'win32') return path.join('D:', 'heygem_data')
  return path.join(os.homedir(), 'heygem_data')
}

const basePath = getBasePath()

export const assetPath = {
  model: path.join(basePath, 'face2face', 'temp'),       // 模特视频路径
  ttsProduct: path.join(basePath, 'face2face', 'temp'),  // TTS 产物路径
  ttsRoot: path.join(basePath, 'voice', 'data'),         // TTS 根目录
  ttsTrain: path.join(basePath, 'voice', 'data', 'origin_audio') // TTS 训练数据
}
