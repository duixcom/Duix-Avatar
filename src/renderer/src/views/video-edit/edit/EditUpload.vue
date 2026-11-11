<template>
  <div class="upload">
    <div class="upload-uploaded" v-if="select.uploaded">
      <div class="info">
        <div class="tag">{{ $t('common.editView.upload') }}</div>
        <div class="name">{{ select.uploaded.name }}</div>
      </div>
      <div class="control">
        <div class="duration">{{ select.uploaded.duration }}</div>
        <t-button class="start" size="small" @click="action.listen">{{ $t('common.editView.listen') }}</t-button>
        <img class="delete" src="@renderer/assets/images/icons/icon-del.png" @click="action.deleteAudio"
          :title="$t('common.editView.delete')" />
      </div>
    </div>
    <div class="upload-box" v-else>
      <t-button class="btn" theme="default" @click="action.uploadAudio" :loading="state.uploading">
        <template #icon>
          <AddIcon />
        </template>
        {{ $t('common.editView.addAudio') }}</t-button>
      <div class="tip">
        <img class="icon" src="@renderer/assets/images/icons/icon-alert.png" />
        <span>{{ $t('common.editView.tip') }}</span>
      </div>
    </div>

  </div>
</template>
<script setup>
import { reactive } from 'vue'
import { AddIcon } from 'tdesign-icons-vue-next'
import { millisecondsToTime } from '@renderer/utils'
import { MessagePlugin } from 'tdesign-vue-next'
import { Client } from '@renderer/client'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  listener: {
    type: Object,
    default: () => ({})
  }
})


const state = reactive({
  uploading: false,
})

const select = defineModel({})

const action = {
  async uploadAudio() {
    const filePath = await Client.file.selectAudio()
    if (filePath) {
      state.uploading = true
      try {
        const info = await Client.file.getAudioInfo(filePath)
        if (action.check(info)) {
          select.value.uploaded = {
            name: info.name,
            audioUrl: filePath,
            duration: millisecondsToTime(info.duration * 1000)
          }
        }
      } catch (err) {
        console.error(err)
      } finally {
        state.uploading = false
      }
    }
  },
  check(audioInfo) {
    if (!audioInfo.isOK) {
      MessagePlugin.error(audioInfo.msg || t('common.editView.uploadError'))
      return false
    }
    if (audioInfo.duration > 60 * 30) {
      MessagePlugin.error(t('common.editView.durationError'))
      return false
    }
    return true
  },
  deleteAudio() {
    const { audioUrl } = props.listener.current()
    if (audioUrl === select.value.uploaded?.audioUrl) {
      props.listener.close()
    }
    select.value.uploaded = null
  },
  listen() {
    if (!select.value.uploaded) return
    const { name, audioUrl, duration } = select.value.uploaded

    props.listener.listen({ name, audioUrl, duration })
  }
}


</script>
<style lang="less" scoped>
.upload {

  &-box {
    display: flex;
    align-items: center;
    gap: 16px;
    --td-bg-color-secondarycontainer: transparent;
    --td-bg-color-specialcomponent: #1d1e20;
    --td-text-color-primary: #ffffff;
    --td-text-color-placeholder: rgba(255, 255, 255, 0.6);

    .btn {
      flex: none;
      height: 28px;
      background: #3D4045;
      border-radius: 4px 4px 4px 4px;
      border: none;
      font-weight: 500;
      font-size: 12px;
      padding: 0 10px;
    }

    .tip {
      flex: 1;
      padding: 4px 8px;
      background: rgba(255, 147, 47, 0.12);
      border-radius: 4px 4px 4px 4px;
      font-weight: 400;
      font-size: 10px;
      color: #FF932F;
      line-height: 16px;
      display: flex;

      .icon {
        width: 12px;
        height: 12px;
        margin: 4px 8px 0 0;
      }
    }
  }

  &-uploaded {
    color: #ffffff;
    padding: 12px;
    width: 100%;
    height: 90px;
    background: #191A1B;
    border-radius: 4px 4px 4px 4px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;

    .info {
      display: flex;
      align-items: center;
      gap: 6px;
      font-weight: 400;
      font-size: 12px;
      color: #FFFFFF;
      line-height: 20px;

      .tag {
        width: 32px;
        height: 16px;
        background: rgba(48, 156, 255, 0.1);
        border-radius: 2px 2px 2px 2px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #309CFF;
      }
    }

    .control {
      display: flex;
      align-items: center;
      gap: 12px;

      .duration {
        margin-left: 6px;
        font-weight: 400;
        font-size: 12px;
        color: rgba(255, 255, 255, 0.3);
        line-height: 14px;
      }

      .start {
        margin-left: auto;
        width: 44px;
        height: 22px;
        border-radius: 3px;
        font-size: 12px;
      }

      .delete {
        width: 14px;
        height: 14px;
        cursor: pointer;
      }
    }

  }

}
</style>
