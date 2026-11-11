import { loopPending, recoverPendingSubmissions } from '../service/video.js'
export function init() {
  recoverPendingSubmissions()
  // 轮询正在合成的视频
  loopPending()
}
