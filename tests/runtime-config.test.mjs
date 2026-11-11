import assert from 'node:assert/strict'
import test from 'node:test'
import { createRuntimeConfig, resolveFfmpegPaths } from '../src/main/config/runtime.mjs'

test('Linux defaults share video inputs and results under the backend temp directory', () => {
  const config = createRuntimeConfig({ platform: 'linux', homedir: '/home/creator', env: {} })
  assert.deepEqual(config.assetPath, {
    model: '/home/creator/duix_avatar_data/face2face/temp',
    ttsProduct: '/home/creator/duix_avatar_data/face2face/temp',
    ttsRoot: '/home/creator/duix_avatar_data/voice/data',
    ttsTrain: '/home/creator/duix_avatar_data/voice/data/origin_audio'
  })
})

test('Windows keeps the original D drive data layout', () => {
  const config = createRuntimeConfig({ platform: 'win32', homedir: 'C:\\Users\\creator', env: {} })
  assert.deepEqual(config.assetPath, {
    model: 'D:\\duix_avatar_data\\face2face\\temp',
    ttsProduct: 'D:\\duix_avatar_data\\face2face\\temp',
    ttsRoot: 'D:\\duix_avatar_data\\voice\\data',
    ttsTrain: 'D:\\duix_avatar_data\\voice\\data\\origin_audio'
  })
})

test('a custom data root relocates all shared input and output directories together', () => {
  const config = createRuntimeConfig({
    platform: 'linux',
    homedir: '/home/creator',
    env: { DUIX_DATA_ROOT: '/srv/duix data' }
  })
  assert.deepEqual(config.assetPath, {
    model: '/srv/duix data/face2face/temp',
    ttsProduct: '/srv/duix data/face2face/temp',
    ttsRoot: '/srv/duix data/voice/data',
    ttsTrain: '/srv/duix data/voice/data/origin_audio'
  })
})

test('Windows accepts an overridden media root with spaces', () => {
  const config = createRuntimeConfig({
    platform: 'win32',
    homedir: 'C:\\Users\\creator',
    env: { DUIX_DATA_ROOT: 'E:\\Avatar Media' }
  })
  assert.equal(config.assetPath.model, 'E:\\Avatar Media\\face2face\\temp')
  assert.equal(config.assetPath.ttsRoot, 'E:\\Avatar Media\\voice\\data')
  assert.equal(config.assetPath.ttsTrain, 'E:\\Avatar Media\\voice\\data\\origin_audio')
})

test('endpoint overrides preserve the API base path and remove trailing separators', () => {
  const config = createRuntimeConfig({
    platform: 'linux',
    homedir: '/home/creator',
    env: {
      NODE_ENV: 'development',
      DUIX_F2F_URL: 'http://127.0.0.1:18383/easy/',
      DUIX_TTS_URL: 'http://127.0.0.1:18181/'
    }
  })
  assert.deepEqual(config.serviceUrl, {
    face2face: 'http://127.0.0.1:18383/easy',
    tts: 'http://127.0.0.1:18181'
  })
})

test('development uses local services when endpoint overrides are absent', () => {
  const config = createRuntimeConfig({
    platform: 'linux',
    homedir: '/home/creator',
    env: { NODE_ENV: 'development' }
  })
  assert.deepEqual(config.serviceUrl, {
    face2face: 'http://127.0.0.1:8383/easy',
    tts: 'http://127.0.0.1:18180'
  })
})

for (const mode of ['development', 'production']) {
  test(`Linux ARM64 uses native system media tools in ${mode}`, () => {
    assert.deepEqual(resolveFfmpegPaths({
      platform: 'linux', arch: 'arm64', env: { NODE_ENV: mode },
      dirname: '/project/out/main', resourcesPath: '/opt/duix/resources'
    }), { ffmpeg: '/usr/bin/ffmpeg', ffprobe: '/usr/bin/ffprobe' })
  })
}

test('Linux x64 development retains bundled media tools', () => {
  assert.deepEqual(resolveFfmpegPaths({
    platform: 'linux', arch: 'x64', env: { NODE_ENV: 'development' },
    dirname: '/project/out/main', resourcesPath: '/opt/duix/resources'
  }), {
    ffmpeg: '/project/resources/ffmpeg/linux-amd64/ffmpeg',
    ffprobe: '/project/resources/ffmpeg/linux-amd64/ffprobe'
  })
})

test('Linux x64 packaged builds retain unpacked bundled media tools', () => {
  assert.deepEqual(resolveFfmpegPaths({
    platform: 'linux', arch: 'x64', env: {},
    dirname: '/opt/duix/resources/app.asar/out/main', resourcesPath: '/opt/duix/resources'
  }), {
    ffmpeg: '/opt/duix/resources/app.asar.unpacked/resources/ffmpeg/linux-amd64/ffmpeg',
    ffprobe: '/opt/duix/resources/app.asar.unpacked/resources/ffmpeg/linux-amd64/ffprobe'
  })
})

test('Windows packaged builds retain the bundled exe layout', () => {
  assert.deepEqual(resolveFfmpegPaths({
    platform: 'win32', arch: 'x64', env: {},
    dirname: 'C:\\Duix\\resources\\app.asar\\out\\main', resourcesPath: 'C:\\Duix\\resources'
  }), {
    ffmpeg: 'C:\\Duix\\resources\\app.asar.unpacked\\resources\\ffmpeg\\win-amd64\\bin\\ffmpeg.exe',
    ffprobe: 'C:\\Duix\\resources\\app.asar.unpacked\\resources\\ffmpeg\\win-amd64\\bin\\ffprobe.exe'
  })
})

test('Windows development retains the bundled exe layout', () => {
  assert.deepEqual(resolveFfmpegPaths({
    platform: 'win32', arch: 'x64', env: { NODE_ENV: 'development' },
    dirname: 'C:\\project\\out\\main', resourcesPath: 'C:\\electron\\resources'
  }), {
    ffmpeg: 'C:\\project\\resources\\ffmpeg\\win-amd64\\bin\\ffmpeg.exe',
    ffprobe: 'C:\\project\\resources\\ffmpeg\\win-amd64\\bin\\ffprobe.exe'
  })
})

test('explicit media executable overrides take precedence independently', () => {
  assert.deepEqual(resolveFfmpegPaths({
    platform: 'linux', arch: 'arm64',
    env: { DUIX_FFMPEG_PATH: '/opt/media tools/ffmpeg' },
    dirname: '/project/out/main', resourcesPath: '/opt/duix/resources'
  }), { ffmpeg: '/opt/media tools/ffmpeg', ffprobe: '/usr/bin/ffprobe' })
  assert.deepEqual(resolveFfmpegPaths({
    platform: 'linux', arch: 'arm64',
    env: { DUIX_FFPROBE_PATH: '/opt/media tools/ffprobe' },
    dirname: '/project/out/main', resourcesPath: '/opt/duix/resources'
  }), { ffmpeg: '/usr/bin/ffmpeg', ffprobe: '/opt/media tools/ffprobe' })
})
