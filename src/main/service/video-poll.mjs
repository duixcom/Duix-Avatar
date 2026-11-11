// Call only during application startup, before starting new local submissions.
// A saved row without a code has no remote job and its old TTS Promise is gone.
export function recoverInterruptedSubmissions(pendingVideos, updateStatus) {
  for (const video of pendingVideos) {
    if (!video.code) updateStatus(video.id, 'failed', '上次提交中断，请重试')
  }
}

// Keep scheduling in one place so a transient query or local media error cannot
// leave the desktop's synthesis queue permanently stopped.
export function createPendingPoller({
  findPending, startNext, getStatus, updateStatus, complete, onError,
  schedule = setTimeout
}) {
  return async function pollPending() {
    let video
    try {
      video = findPending()
      if (!video) {
        startNext()
        return
      }
      // TTS runs before submission to the video service. There is no remote job
      // to query until synthesisVideo has stored its submission code.
      if (!video.code) return video

      let response
      try {
        response = await getStatus(video.code)
      } catch (error) {
        onError(error)
        updateStatus(video.id, 'pending', `状态查询失败，将重试：${error.message}`, video.progress || 0)
        return video
      }

      if ([9999, 10002, 10003, 10004].includes(response.code)) {
        updateStatus(video.id, 'failed', response.msg)
      } else if (response.code === 10000) {
        const result = response.data
        if (result.status === 1) {
          updateStatus(video.id, 'pending', result.msg, result.progress)
        } else if (result.status === 2) {
          try {
            await complete(video, result)
          } catch (error) {
            onError(error)
            updateStatus(video.id, 'failed', `结果视频校验失败：${error.message}`)
          }
        } else if (result.status === 3) {
          updateStatus(video.id, 'failed', result.msg)
        }
      }
      return video
    } catch (error) {
      onError(error)
    } finally {
      schedule(pollPending, 2000)
    }
  }
}
