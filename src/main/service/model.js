import { ipcMain } from 'electron'
import fs from 'fs'
import path from 'path'
import dayjs from 'dayjs'
import { isEmpty } from 'lodash'
import { insert, selectPage, count, selectByID, remove as deleteModel } from '../dao/f2f-model.js'
import { train as trainVoice } from './voice.js'
import { assetPath } from '../config/config.js'
import log from '../logger.js'
import { extractAudio, toH264 } from '../util/ffmpeg.js'
const MODEL_NAME = 'model'

/**
 * 新增模特
 * @param {string} modelName 模特名称
 * @param {string} videoPath 模特视频路径
 * @returns
 */
async function addModel(modelName, videoPath) {
  if (!fs.existsSync(assetPath.model)) {
    fs.mkdirSync(assetPath.model, {
      recursive: true
    })
  }
  // copy video to model video path
  const extname = path.extname(videoPath)
  const modelFileName = dayjs().format('YYYYMMDDHHmmssSSS') + extname
  const modelPath = path.join(assetPath.model, modelFileName)

  await toH264(videoPath, modelPath)

  const relativeModelPath = path.relative(assetPath.model, modelPath)
  const id = insert({ modelName, videoPath: relativeModelPath, audioPath: '', voiceId: '' })
  return Promise.resolve(id)
}

function page({ page, pageSize, name = '' }) {
  const total = count(name)
  return {
    total,
    list: selectPage({ page, pageSize, name }).map((model) => ({
      ...model,
      video_path: path.join(assetPath.model, model.video_path),
      audio_path: path.join(assetPath.ttsRoot, model.audio_path)
    }))
  }
}

function findModel(modelId) {
  const model = selectByID(modelId)
  return {
    ...model,
    video_path: path.join(assetPath.model, model.video_path),
    audio_path: path.join(assetPath.ttsRoot, model.audio_path)
  }
}

function removeModel(modelId) {
  const model = selectByID(modelId)
  log.debug('~ removeModel ~ modelId:', modelId)

  // 删除视频
  const videoPath = path.join(assetPath.model, model.video_path ||'')
  if (!isEmpty(model.video_path) && fs.existsSync(videoPath)) {
    fs.unlinkSync(videoPath)
  }

  // 删除音频
  const audioPath = path.join(assetPath.ttsRoot, model.audio_path ||'')
  if (!isEmpty(model.audio_path) && fs.existsSync(audioPath)) {
    fs.unlinkSync(audioPath)
  }

  deleteModel(modelId)
}

function countModel(name = '') {
  return count(name)
}

export function init() {
  ipcMain.handle(MODEL_NAME + '/addModel', (event, ...args) => {
    return addModel(...args)
  })
  ipcMain.handle(MODEL_NAME + '/page', (event, ...args) => {
    return page(...args)
  })
  ipcMain.handle(MODEL_NAME + '/find', (event, ...args) => {
    return findModel(...args)
  })
  ipcMain.handle(MODEL_NAME + '/count', (event, ...args) => {
    return countModel(...args)
  })
  ipcMain.handle(MODEL_NAME + '/remove', (event, ...args) => {
    return removeModel(...args)
  })
}
