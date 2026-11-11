import { ipcMain } from 'electron'
import crypto from 'crypto'
import path from 'path'
import fs from 'fs'
import { isEmpty } from 'lodash'
import { assetPath } from '../config/config.js'
import { selectPage,selectByStatus, updateStatus, remove as deleteVideo, findFirstByStatus } from '../dao/video.js'
import { selectByID as selectF2FModelByID } from '../dao/f2f-model.js'
import { selectByID as selectVoiceByID } from '../dao/voice.js'
import {
  insert as insertVideo,
  count,
  update,
  selectByID as selectVideoByID
} from '../dao/video.js'
import { makeAudio4Video, copyAudio4Video } from './voice.js'
import { makeVideo as makeVideoApi,getVideoStatus } from '../api/f2f.js'
import log from '../logger.js'
import { getVideoDuration } from '../util/ffmpeg.js'
import { createPendingPoller, recoverInterruptedSubmissions } from './video-poll.mjs'

const MODEL_NAME = 'video'

/**
 * 分页查询合成结果
 * @param {number} page
 * @param {number} pageSize
 * @returns
 */
function page({ page, pageSize, name = '' }) {
  // 查询的有waiting状态的视频
  const waitingVideos = selectByStatus('waiting').map((v) => v.id)
  const total = count(name)
  const list = selectPage({ page, pageSize, name }).map((video) => {
    video = {
      ...video,
      file_path: video.file_path ? path.join(assetPath.model, video.file_path) : video.file_path
    }

    if(video.status === 'waiting'){
      video.progress = `${waitingVideos.indexOf(video.id) + 1} / ${waitingVideos.length}`
    }
    return video
  })

  return {
    total,
    list
  }
}

function findVideo(videoId) {
  const video = selectVideoByID(videoId)
  return {
    ...video,
    file_path: video.file_path ? path.join(assetPath.model, video.file_path) : video.file_path
  }
}

function countVideo(name = '') {
  return count(name)
}

function saveVideo({ id, model_id, name, text_content, voice_id, audio_path }) {
  const video = selectVideoByID(id)
  if(audio_path){
    audio_path = copyAudio4Video(audio_path)
  }

  if (video) {
    return update({ id, model_id, name, text_content, voice_id, audio_path })
  }
  return insertVideo({ model_id, name, status: 'draft', text_content, voice_id, audio_path })
}

/**
 * 合成视频
 * 更新视频状态为waiting
 * @param {number} videoId
 * @returns
 */
function makeVideo(videoId) {
  update({ id: videoId, status: 'waiting' })
  return videoId
}

export async function synthesisVideo(videoId) {
  try{
    update({
      id: videoId,
      file_path: null,
      code: null,
      progress: 0,
      status: 'pending',
      message: '正在提交任务',
    })

    // 查询Video
    const video = selectVideoByID(videoId)
    log.debug('~ makeVideo ~ video:', video)

    // 根据modelId获取model信息
    const model = selectF2FModelByID(video.model_id)
    log.debug('~ makeVideo ~ model:', model)

    let audioPath
    if(video.audio_path){
      // 将audio_path复制到ttsProduct目录下
      audioPath = video.audio_path
    }else{
      // 根据model信息中的voiceId获取voice信息
      const voice = selectVoiceByID(video.voice_id || model.voice_id)
      log.debug('~ makeVideo ~ voice:', voice)

      // 调用tts接口生成音频
      audioPath = await makeAudio4Video({
        voiceId: voice.id,
        text: video.text_content
      })
      log.debug('~ makeVideo ~ audioPath:', audioPath)
    }

    // 调用视频生成接口生成视频
    const { result, param } = await makeVideoByF2F(audioPath, model.video_path)

    log.debug('~ makeVideo ~ result, param:', result, param)

    // 插入视频表
    if(10000 === result.code){ // 成功
      update({
        id: videoId,
        file_path: null,
        status: 'pending',
        message: result,
        audio_path: audioPath,
        param,
        code: param.code
      })
    }else{ // 失败
      update({
        id: videoId,
        file_path: null,
        status: 'failed',
        message: result.msg,
        audio_path: audioPath,
        param,
        code: param.code
      })
    }
  } catch (error) {
    log.error('~ synthesisVideo ~ error:', error.message)
    updateStatus(videoId, 'failed', error.message)
  }

  // 6. 返回视频id
  return videoId
}

export function recoverPendingSubmissions() {
  recoverInterruptedSubmissions(selectByStatus('pending'), updateStatus)
}

export const loopPending = createPendingPoller({
  findPending: () => findFirstByStatus('pending'),
  startNext: synthesisNext,
  getStatus: getVideoStatus,
  updateStatus,
  onError: (error) => log.error('~ loopPending ~ error:', error.message),
  complete: async (video, result) => {
    const resultPath = path.join(assetPath.model, result.result)
    const duration = Number(await getVideoDuration(resultPath))
    if (!Number.isFinite(duration) || duration <= 0) {
      throw new Error('视频时长无效')
    }
    update({
      id: video.id,
      status: 'success',
      message: result.msg,
      progress: result.progress,
      file_path: result.result,
      duration
    })
  }
})

/**
 * 合成下一个视频
 */
function synthesisNext() {
  // 查询所有未完成的视频任务
  const video = findFirstByStatus('waiting')
  if (video) {
    synthesisVideo(video.id)
  }
}

function removeVideo(videoId) {
  // 查询视频
  const video = selectVideoByID(videoId)
  log.debug('~ removeVideo ~ videoId:', videoId)

  // 删除视频
  const videoPath = path.join(assetPath.model, video.file_path ||'')
  if (!isEmpty(video.file_path) && fs.existsSync(videoPath)) {
    fs.unlinkSync(videoPath)
  }

  // 删除音频
  const audioPath = path.join(assetPath.model, video.audio_path ||'')
  if (!isEmpty(video.audio_path) && fs.existsSync(audioPath)) {
    fs.unlinkSync(audioPath)
  }

  // 删除视频表
  return deleteVideo(videoId)
}

function exportVideo(videoId, outputPath) {
  const video = selectVideoByID(videoId)
  const filePath = path.join(assetPath.model, video.file_path)
  fs.copyFileSync(filePath, outputPath)
}

/**
 * 调用face2face生成视频
 * @param {string} audioPath
 * @param {string} videoPath
 * @returns
 */
async function makeVideoByF2F(audioPath, videoPath) {
  const uuid = crypto.randomUUID()
  const param = {
    audio_url: audioPath,
    video_url: videoPath,
    code: uuid,
    chaofen: 0,
    watermark_switch: 0,
    pn: 1
  }
  const result = await makeVideoApi(param)
  return { param, result }
}

function modify(video) {
  return update(video)
}

export function init() {
  ipcMain.handle(MODEL_NAME + '/page', (event, ...args) => {
    return page(...args)
  })
  ipcMain.handle(MODEL_NAME + '/make', (event, ...args) => {
    return makeVideo(...args)
  })
  ipcMain.handle(MODEL_NAME + '/modify', (event, ...args) => {
    return modify(...args)
  })
  ipcMain.handle(MODEL_NAME + '/save', (event, ...args) => {
    return saveVideo(...args)
  })
  ipcMain.handle(MODEL_NAME + '/find', (event, ...args) => {
    return findVideo(...args)
  })
  ipcMain.handle(MODEL_NAME + '/count', (event, ...args) => {
    return countVideo(...args)
  })
  ipcMain.handle(MODEL_NAME + '/export', (event, ...args) => {
    return exportVideo(...args)
  })
  ipcMain.handle(MODEL_NAME + '/remove', (event, ...args) => {
    return removeVideo(...args)
  })
}
