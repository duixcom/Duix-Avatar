<template>
  <div class="settings">
    <h2>设置</h2>
    <div class="form">
      <div class="group">
        <label>服务主机 HEYGEM_HOST</label>
        <input v-model.trim="form.HEYGEM_HOST" placeholder="例如 192.168.110.22" />
      </div>
      <div class="group">
        <label>TTS 端口 HEYGEM_TTS_PORT</label>
        <input v-model.trim="form.HEYGEM_TTS_PORT" placeholder="18180" />
      </div>
      <div class="group">
        <label>视频端口 HEYGEM_VIDEO_PORT</label>
        <input v-model.trim="form.HEYGEM_VIDEO_PORT" placeholder="8383" />
      </div>

      <div class="group">
        <label>TTS 根目录 HEYGEM_TTS_ROOT</label>
        <input v-model.trim="form.HEYGEM_TTS_ROOT" placeholder="例如 \\192.168.110.22\\heygem_data\\voice\\data" />
      </div>
      <div class="group">
        <label>TTS 训练目录 HEYGEM_TTS_TRAIN_DIR</label>
        <input v-model.trim="form.HEYGEM_TTS_TRAIN_DIR" placeholder="例如 \\192.168.110.22\\heygem_data\\voice\\data\\origin_audio" />
      </div>
      <div class="group">
        <label>模型与产物目录 HEYGEM_MODEL_DIR</label>
        <input v-model.trim="form.HEYGEM_MODEL_DIR" placeholder="例如 \\192.168.110.22\\heygem_data\\face2face\\temp" />
      </div>
      <div class="group">
        <label>TTS 产物目录 HEYGEM_TTS_PRODUCT_DIR</label>
        <input v-model.trim="form.HEYGEM_TTS_PRODUCT_DIR" placeholder="例如 \\192.168.110.22\\heygem_data\\face2face\\temp" />
      </div>

      <div class="actions">
        <button @click="onSave" :disabled="loading">保存</button>
        <button @click="onSaveAndRestart" :disabled="loading">保存并重启</button>
        <span class="msg" :class="{ error: !!error }">{{ error || message }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { getSettings, saveSettings, restartApp } from '@renderer/api/index.js'

const form = reactive({
  HEYGEM_HOST: '',
  HEYGEM_TTS_PORT: '18180',
  HEYGEM_VIDEO_PORT: '8383',
  HEYGEM_TTS_ROOT: '',
  HEYGEM_TTS_TRAIN_DIR: '',
  HEYGEM_MODEL_DIR: '',
  HEYGEM_TTS_PRODUCT_DIR: ''
})

const loading = ref(false)
const message = ref('')
const error = ref('')

onMounted(async () => {
  try {
    const cfg = await getSettings()
    Object.assign(form, cfg || {})
  } catch (e) {
    // ignore
  }
})

function validate() {
  error.value = ''
  const portReg = /^\d+$/
  if (!form.HEYGEM_HOST) return (error.value = 'HEYGEM_HOST 不能为空'), false
  if (form.HEYGEM_TTS_PORT && !portReg.test(form.HEYGEM_TTS_PORT)) return (error.value = 'TTS 端口应为数字'), false
  if (form.HEYGEM_VIDEO_PORT && !portReg.test(form.HEYGEM_VIDEO_PORT)) return (error.value = '视频端口应为数字'), false
  return true
}

async function onSave() {
  if (!validate()) return
  loading.value = true
  message.value = ''
  try {
    await saveSettings({ ...form })
    message.value = '已保存'
  } catch (e) {
    error.value = '保存失败：' + (e?.message || e)
  } finally {
    loading.value = false
  }
}

async function onSaveAndRestart() {
  await onSave()
  if (!error.value) {
    await restartApp()
  }
}
</script>

<style scoped>
.settings {
  padding: 20px;
}
.form { max-width: 760px; }
.group { margin-bottom: 12px; display: flex; flex-direction: column; }
.group label { font-size: 12px; color: #666; margin-bottom: 6px; }
.group input { height: 34px; padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; }
.actions { margin-top: 16px; display: flex; align-items: center; gap: 12px; }
button { height: 32px; padding: 0 14px; border: 1px solid #434AF9; color: #fff; background: #434AF9; border-radius: 4px; cursor: pointer; }
button[disabled] { opacity: .6; cursor: not-allowed; }
.msg { margin-left: 8px; color: #2e7d32; font-size: 12px; }
.msg.error { color: #d32f2f; }
</style>
