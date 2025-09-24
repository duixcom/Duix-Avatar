<template>
  <div class="realtime-view">
    <h1>Real-time Interaction</h1>
    <div class="controls">
      <t-select v-model="selectedModel" placeholder="Select Character">
        <t-option v-for="model in models" :key="model.id" :value="model.id" :label="model.name"></t-option>
      </t-select>
      <t-select v-model="selectedVoice" placeholder="Select Voice">
        <t-option v-for="voice in voices" :key="voice.id" :value="voice.id" :label="voice.name"></t-option>
      </t-select>
      <t-textarea v-model="text" placeholder="Enter text to speak"></t-textarea>
      <t-button @click="startInteraction">Start</t-button>
    </div>
    <div class="video-container">
      <video ref="videoPlayer" autoplay></video>
    </div>
    <div class="tiktok-streaming">
      <h2>TikTok Live Streaming</h2>
      <t-input v-model="tiktokServerUrl" placeholder="TikTok Server URL"></t-input>
      <t-input v-model="tiktokStreamKey" placeholder="TikTok Stream Key"></t-input>
      <t-button @click="startTiktokStream">Start Streaming</t-button>
      <t-input v-model="tiktokUsername" placeholder="TikTok Username"></t-input>
      <t-button @click="startTiktokCommentListener">Listen for Comments</t-button>
      <t-button @click="toggleRecording">{{ isRecording ? 'Stop Recording' : 'Start Recording' }}</t-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { modelPage, getAllTimbre } from '@renderer/api'

const selectedModel = ref(null)
const selectedVoice = ref(null)
const text = ref('')
const models = ref([])
const voices = ref([])
const videoPlayer = ref(null)
const socket = ref(null)
const tiktokServerUrl = ref('')
const tiktokStreamKey = ref('')
const tiktokUsername = ref('')
const isRecording = ref(false)
const mediaSource = new MediaSource()
let sourceBuffer
const queue = []

onMounted(async () => {
  const modelRes = await modelPage({ page: 1, pageSize: 100 })
  models.value = modelRes.list

  const voiceRes = await getAllTimbre()
  voices.value = voiceRes

  socket.value = new WebSocket('ws://localhost:8080')

  socket.value.onopen = () => {
    console.log('WebSocket connected')
  }

  socket.value.onmessage = (event) => {
    if (event.data instanceof Blob) {
      handleVideoChunk(event.data)
      return
    }
    const message = JSON.parse(event.data)
    console.log('WebSocket message received:', message)
    if (message.type === 'end-of-stream') {
      if (mediaSource.readyState === 'open') {
        mediaSource.endOfStream()
      }
    }
  }

  socket.value.onerror = (error) => {
    console.error('WebSocket error:', error)
  }

  videoPlayer.value.src = URL.createObjectURL(mediaSource)
  mediaSource.addEventListener('sourceopen', () => {
    sourceBuffer = mediaSource.addSourceBuffer('video/webm; codecs="vp8, opus"')
    sourceBuffer.addEventListener('updateend', () => {
      if (queue.length > 0) {
        sourceBuffer.appendBuffer(queue.shift())
      }
    })
  })
})

function handleVideoChunk(chunk) {
  chunk.arrayBuffer().then(buffer => {
    if (sourceBuffer.updating || queue.length > 0) {
      queue.push(buffer)
    } else {
      sourceBuffer.appendBuffer(buffer)
    }
  })
}

onUnmounted(() => {
  if (socket.value) {
    socket.value.close()
  }
})

const startInteraction = () => {
  if (socket.value && socket.value.readyState === WebSocket.OPEN) {
    const message = {
      type: 'start',
      data: {
        modelId: selectedModel.value,
        voiceId: selectedVoice.value,
        text: text.value
      }
    }
    socket.value.send(JSON.stringify(message))
  }
}

const startTiktokCommentListener = () => {
  if (socket.value && socket.value.readyState === WebSocket.OPEN) {
    const message = {
      type: 'start-tiktok-comment-listener',
      data: {
        username: tiktokUsername.value
      }
    }
    socket.value.send(JSON.stringify(message))
  }
}

const startTiktokStream = () => {
  if (socket.value && socket.value.readyState === WebSocket.OPEN) {
    const message = {
      type: 'start-tiktok-stream',
      data: {
        serverUrl: tiktokServerUrl.value,
        streamKey: tiktokStreamKey.value
      }
    }
    socket.value.send(JSON.stringify(message))
  }
}

const toggleRecording = () => {
  if (socket.value && socket.value.readyState === WebSocket.OPEN) {
    const message = {
      type: isRecording.value ? 'stop-recording' : 'start-recording'
    }
    socket.value.send(JSON.stringify(message))
    isRecording.value = !isRecording.value
  }
}
</script>

<style scoped>
.realtime-view {
  padding: 20px;
}
.controls {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}
.video-container {
  width: 640px;
  height: 480px;
  border: 1px solid #ccc;
}
video {
  width: 100%;
  height: 100%;
}
</style>
