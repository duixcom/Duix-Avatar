import test from 'node:test'
import assert from 'node:assert/strict'
import { createPendingPoller, recoverInterruptedSubmissions } from '../src/main/service/video-poll.mjs'

function harness(overrides = {}) {
  const state = {
    video: { id: 1, status: 'pending', code: 'job-1', progress: 12 },
    queries: [], timers: [], errors: [], started: 0, completed: []
  }
  const poll = createPendingPoller({
    findPending: () => state.video?.status === 'pending' ? state.video : undefined,
    startNext: () => { state.started++ },
    getStatus: async (code) => {
      state.queries.push(code)
      return { code: 10000, data: { status: 1, msg: 'processing', progress: 42 } }
    },
    updateStatus: (id, status, message, progress) => Object.assign(state.video, { status, message, progress }),
    complete: async (video, result) => {
      state.completed.push(result.result)
      video.status = 'success'
    },
    onError: (error) => state.errors.push(error.message),
    schedule: (callback, delay) => { assert.equal(delay, 2000); state.timers.push(callback) },
    ...overrides
  })
  const tick = async () => {
    assert.equal(state.timers.length, 1, 'exactly one next poll remains scheduled')
    await state.timers.shift()()
  }
  return { state, poll, tick }
}

test('slow TTS leaves a pending submission alone until its backend code is stored', async () => {
  const { state, poll, tick } = harness()
  state.video.code = null
  await poll()
  await tick()
  assert.equal(state.video.status, 'pending')
  assert.deepEqual(state.queries, [])
  assert.equal(state.started, 0)
  state.video.code = 'submitted-after-tts'
  await tick()
  assert.deepEqual(state.queries, ['submitted-after-tts'])
  assert.equal(state.video.progress, 42)
})

test('a temporary HTTP failure preserves the job and the next poll can complete it', async () => {
  let attempts = 0
  const { state, poll, tick } = harness({
    getStatus: async () => {
      if (++attempts === 1) throw new Error('ECONNRESET')
      return { code: 10000, data: { status: 2, result: 'job-1.mp4', progress: 100 } }
    }
  })
  await poll()
  assert.equal(state.video.status, 'pending')
  assert.equal(state.video.progress, 12)
  assert.match(state.video.message, /ECONNRESET/)
  await tick()
  assert.equal(state.video.status, 'success')
  assert.deepEqual(state.completed, ['job-1.mp4'])
  assert.equal(state.timers.length, 1)
})

for (const failure of ['ENOENT: result file missing', 'ffprobe exited with code 1']) {
  test(`a result verification failure releases the queue: ${failure}`, async () => {
    const { state, poll, tick } = harness({
      getStatus: async () => ({ code: 10000, data: { status: 2, result: 'broken.mp4' } }),
      complete: async () => { throw new Error(failure) }
    })
    await poll()
    assert.equal(state.video.status, 'failed')
    assert.match(state.video.message, /结果视频校验失败/)
    assert.ok(state.video.message.includes(failure))
    await tick()
    assert.equal(state.started, 1)
    assert.equal(state.timers.length, 1)
  })
}

for (const code of [10003, 10004]) {
  test(`an unavailable backend job (${code}) fails explicitly and subsequent queued work still starts`, async () => {
    const { state, poll, tick } = harness({ getStatus: async () => ({ code, msg: 'unknown job' }) })
    await poll()
    assert.equal(state.video.status, 'failed')
    assert.equal(state.video.message, 'unknown job')
    await tick()
    assert.equal(state.started, 1)
  })
}

test('a database read error cannot permanently stop the scheduler', async () => {
  const { state, poll } = harness({ findPending: () => { throw new Error('SQLITE_BUSY') } })
  await poll()
  assert.deepEqual(state.errors, ['SQLITE_BUSY'])
  assert.equal(state.timers.length, 1)
})

test('restart fails an interrupted TTS submission and releases queued work, while active TTS is left alone', async () => {
  const first = harness()
  first.state.video.code = null
  await first.poll()
  await first.tick()
  assert.equal(first.state.video.status, 'pending', 'the live TTS operation is still allowed to finish')

  // A new process sees only the persisted row; its predecessor's TTS Promise no longer exists.
  const persisted = JSON.parse(JSON.stringify(first.state.video))
  recoverInterruptedSubmissions([persisted], (id, status, message) => Object.assign(persisted, { status, message }))
  assert.equal(persisted.status, 'failed')
  assert.match(persisted.message, /提交中断.*重试/)
  const restarted = harness({ findPending: () => persisted.status === 'pending' ? persisted : undefined })
  await restarted.poll()
  assert.equal(restarted.state.started, 1)
})

test('restart preserves submitted jobs so they can resume remote status checks', async () => {
  const { state, poll } = harness()
  const changes = []
  recoverInterruptedSubmissions([state.video], (...change) => changes.push(change))
  assert.deepEqual(changes, [])
  await poll()
  assert.deepEqual(state.queries, ['job-1'])
  assert.equal(state.video.progress, 42)
})
