<template>
  <div class="upload-box">
    <div class="upload-content">
      <t-upload
        v-model="files"
        :abridge-name="[8, 6]"
        :auto-upload="false"
        :theme="'image'"
        :accept="'image/*'"
        :multiple="false"
        @select-change="handleSelectChange"
      >
        <template #trigger>
          <div class="upload-trigger">
            <img src="@renderer/assets/images/home/select.svg" />
            <div class="text">{{ $t('common.upload.imageText') }}</div>
            <div class="des">{{ $t('common.upload.imageDes') }}</div>
          </div>
        </template>
      </t-upload>
    </div>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'

const files = ref([])
const form = defineModel({ imagePath: '' })

const handleSelectChange = (selectedFiles) => {
  if (selectedFiles.length > 0) {
    const file = selectedFiles[0]
    if (file.type.startsWith('image/')) {
      form.value.imagePath = file.raw.path
      files.value = [file]
    } else {
      MessagePlugin.error('Please select an image file.')
      files.value = []
    }
  }
}
</script>
<style lang="less" scoped>
.upload-box {
  background: #28282b;
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  height: 100%;

  .upload-content {
    flex-grow: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px dashed #5a5a5e;
    border-radius: 6px;
  }

  .upload-trigger {
    text-align: center;
    padding: 20px;
    cursor: pointer;

    img {
      width: 48px;
      height: 48px;
    }

    .text {
      font-size: 14px;
      margin-top: 10px;
    }

    .des {
      font-size: 12px;
      color: #999;
      margin-top: 5px;
    }
  }
}
</style>
