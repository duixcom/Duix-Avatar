<template>
  <div class="modal">
    <t-dialog
      v-model:visible="state.show"
      @close="action.close(false)"
      @closed="onClosed"
      :header="'Upload Character Image'"
      :closeOnEscKeydown="false"
      :closeOnOverlayClick="false"
    >
      <div class="form-item --name">
        <span class="label required">Character Name</span>
        <t-input
          class="value"
          v-model="state.form.name"
          placeholder="Enter character name"
        />
      </div>
      <ImageUpload class="modal-box" v-model="state.form.uploadInfo" />
      <template #footer>
        <t-button @click="action.submit" :loading="state.loading.submit">
          Submit
        </t-button>
      </template>
    </t-dialog>
  </div>
</template>
<script setup>
import { reactive, watchEffect } from 'vue'
import ImageUpload from './ImageUpload.vue'
import { isBoolean, isObject } from 'lodash-es'
import { addModel } from '@renderer/api' // This will need to be changed
import { MessagePlugin } from 'tdesign-vue-next'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  onClose: {
    type: Function,
    default: () => {}
  },
  onClosed: {
    type: Function,
    default: () => {}
  }
})

const state = reactive({
  show: false,
  loading: {
    submit: false
  },
  form: {
    uploadInfo: {
      imagePath: ''
    },
    name: ''
  }
})

watchEffect(() => {
  state.show = props.visible
})

const action = {
  check() {
    const { name, uploadInfo } = state.form
    if (!name) {
      MessagePlugin.error('Please enter a character name')
      return false
    }
    if (!uploadInfo.imagePath) {
      MessagePlugin.error('Please upload an image')
      return false
    }
    return true
  },
  async submit() {
    if (!action.check()) return
    state.loading.submit = true
    const { name, uploadInfo } = state.form
    try {
      const isOK = await addModel({
        name,
        videoPath: uploadInfo.imagePath,
        isImage: true
      })
      if (isOK) {
        action.close({ isSubmitOK: true })
      } else {
        throw new Error('Failed to create character')
      }
    } catch (err) {
      MessagePlugin.error(err.toString() || 'Failed to create character')
    } finally {
      state.loading.submit = false
    }
  },
  close(params = false) {
    const result = {
      isSubmitOK: false,
    }
    if (isBoolean(params)) {
      result.isSubmitOK = params
    } else if (isObject(params)) {
      Object.assign(result, params)
    }
    state.show = false
    props.onClose(result)
  }
}
</script>
<style lang="less" scoped>
/* Add your styles here */
.form-item {
  margin-bottom: 20px;
}
</style>
