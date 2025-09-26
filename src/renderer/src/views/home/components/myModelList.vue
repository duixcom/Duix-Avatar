<template>
  <div class="model-content-box">
    <div class="form-box">
      <t-input
        v-model="state.formData.name"
        class="form-input"
        :placeholder="$t('common.input.enterNamePlaceholder')"
        @change="onKeypressFun"
      >
        <template #prefix-icon>
          <img src="../../../assets/images/home/select.svg" />
        </template>
      </t-input>
      <t-button @click="handleCreateImageModel" class="upload-btn">{{ $t('common.upload.imageText') }}</t-button>
    </div>
    <div class="tab-box" style="display: none">
      <li
        v-for="(item, index) in state.tabList"
        :key="index"
        :class="item.active ? 'active' : ''"
        @click="tabClick(index)"
      >
        {{ item.name }}
      </li>
    </div>
    <div class="model-content-table">
      <div v-if="home.homeState.modelNum === 0" class="empty">
        <div class="empty-box">
          <img src="../../../assets/images/home/myModelList.svg" />
          <div class="empty-text">{{ $t('common.myModelList.emptyText') }}</div>
          <div class="empty-text">
            <span @click="handleCreateModel">{{
              $t('common.myModelList.emptyLinkRouteText')
            }}</span>
            {{ $t('common.myModelList.emptyRightText') }}
          </div>
        </div>
      </div>
      <div class="table-list" v-else>
        <div v-for="(item, index) in state.modelList" :key="index + 'modelList'" class="li">
          <!-- 视频上部分内容 -->
          <div class="img-video comme">
            <div class="img-video-content">
              <div class="duration" style="display: none">00:30</div>
              <video class="model-video" :src="localUrl.addFileProtocol(item.video_path)"></video> 
              <div class="fail" style="display: none">
                <div class="fail-line"></div>
                <span> {{ $t('common.myModelList.inProgressText') }}</span>
              </div>
            </div>
          </div>
          <!-- 下载和预览 -->
          <div class="download-preview comme">
            <div class="download-preview-content">
              <div class="download-button" @click="editVideo(item)">
                <img src="../../../assets/images/home/video.svg" />
                <span>{{ $t('common.myModelList.createVideoText') }}</span>
              </div>
              <div class="detection-failed-text" style="display: none">
                训练失败
                <img src="../../../assets/images/home/icon-delete.svg" />
              </div>
              <div class="detection-failed-title" style="display: none">未检测到人脸</div>
              <div class="delete-video" @click="delModel(item.id)">
                <DeleteIcon style="color: #fff; font-size: 12px" />
              </div>
              <div class="preview-box" @click="previewVideo(item.video_path)">
                <img src="../../../assets/images/home/play.svg" />
                <span>{{ $t('common.myModelList.previewText') }}</span>
              </div>
            </div>
          </div>
          <!-- 视频下部分内容 -->
          <div class="bottom-text">
            <div class="top">
              <div class="video-type">短视频</div>
              <div class="h1">{{ item.name }}</div>
            </div>
            <div class="text">{{ formatDate(item.created_at) }}</div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="home.homeState.modelNum > 0" class="pagination-box">
      <div class="pagination-content">
        <t-config-provider :global-config="locale === 'zh' ? globalZh : globalEn">
          <t-pagination
            v-model="state.current"
            v-model:pageSize="state.pageSize"
            :total="state.total"
            show-jumper
            class="pagination"
            @page-size-change="onPageSizeChange"
            @current-change="onCurrentChange"
          />
        </t-config-provider>
      </div>
    </div>
    <VideoDialog
      :showVideoDialog="state.showVideoDialog"
      :videoUrl="state.videoUrl"
      @cancel="cancelFun"
    />
    <DeleteDialog ref="deleteDialogRef" @ok="okDelete" />
  </div>
</template>
<script setup>
import { reactive, onMounted, ref } from 'vue'
import { DeleteIcon } from 'tdesign-icons-vue-next'
import { modelPage, removeModel } from '@renderer/api/index.js'
import { formatDate } from '@renderer/utils/index.js'
import { useRouter } from 'vue-router'
import VideoDialog from '@renderer/views/home/components/videoDialog.vue'
import DeleteDialog from '@renderer/components/deleteDialog.vue'
import { useHomeStore } from '@renderer/stores/home.js'
import { MessagePlugin } from 'tdesign-vue-next'
import { createModel } from '@renderer/components/model-create'
import { createImageModel } from '@renderer/components/ImageUploadDialog'
import enConfig from 'tdesign-vue-next/es/locale/en_US'
import zhConfig from 'tdesign-vue-next/es/locale/zh_CN'
import { useI18n } from 'vue-i18n'
const { locale,t } = useI18n()
import { localUrl } from '@renderer/utils'

import merge from 'lodash/merge'
const globalEn = merge(enConfig, {
  pagination: {}
})
const globalZh = merge(zhConfig, {
  pagination: {}
})
const home = useHomeStore()
const router = useRouter()
const deleteDialogRef = ref(null)
const state = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  videoUrl: '',
  showVideoDialog: false,
  isTime: false,
  modelList: [], // 模型列表[],
  delModelId: '',
  formData: {
    name: ''
  },
  tabList: [
    {
      name: '最近使用',
      active: true,
      id: 'recentlyUsed'
    },
    {
      name: '极速定制',
      active: false,
      id: 'rapidCustomization'
    }
  ],
  tabValue: 'recentlyUsed'
})
onMounted(() => {
  modelPageAJax()
})
const modelPageAJax = async () => {
  try {
    const res = await modelPage({
      page: state.current,
      pageSize: state.pageSize,
      name: state.formData.name
    })
    if (res) {
      const { total, list } = res
      if (list) {
        state.total = total
        state.modelList = list
      }
    }
  } catch (error) {
    console.log(error)
  }
}
const handleCreateModel = async () => {
  const { isSubmitOK } = await createModel()
  // 提交成功
  if (isSubmitOK) {
    emit('submitOK')
  }
}
const handleCreateImageModel = async () => {
  const { isSubmitOK } = await createImageModel()
  // 提交成功
  if (isSubmitOK) {
    modelPageAJax()
  }
}
const okDelete = () => {
  removeModel(state.delModelId)
    .then(() => {
      modelPageAJax()
      MessagePlugin.success(t('common.message.deleteSuccessText'))
      home.setModelNum(home.homeState.modelNum > 0 ? home.homeState.modelNum - 1 : 0)
    })
    .catch((error) => {
      MessagePlugin.error(t('common.message.deleteErrorText'))
      console.error('Error:', error)
    })
}
const delModel = (id) => {
  if (deleteDialogRef.value && deleteDialogRef.value.showDialogFun) {
    deleteDialogRef.value.showDialogFun()
    state.delModelId = id
  }
}
defineExpose({
  modelPageAJax
})
const previewVideo = (url) => {
  state.showVideoDialog = true
  state.videoUrl = url
}
const cancelFun = () => {
  state.showVideoDialog = false
}
const onKeypressFun = () => {
  if (!state.isTime) {
    state.isTime = true
    const timeout = setTimeout(() => {
      modelPageAJax()
      state.isTime = false
      clearTimeout(timeout)
    }, 800)
  }
}
const editVideo = (item) => {
  router.push('/video/edit?modelId=' + item.id)
}
const onPageSizeChange = (size) => {
  state.pageSize = size
  modelPageAJax()
}

const onCurrentChange = (index) => {
  state.page = index
  modelPageAJax()
}
const tabClick = (index) => {
  state.tabList.forEach((yItem, yIndex) => {
    if (index === yIndex) {
      yItem.active = true
      state.tabValue = yItem.id
    } else {
      yItem.active = false
    }
  })
}
</script>
<style lang="less" scoped>
.model-content-box {
  .form-box {
    display: flex;
    margin-bottom: 24px;
    position: absolute;
    top: -50px;
    right: 0;
    .form-input {
      width: 216px;
      margin-left: auto;
    }
  }
  .tab-box {
    display: flex;
    margin-bottom: 17px;
    li {
      cursor: pointer;
      list-style: none;
      font-family: HarmonyOS Sans SC, HarmonyOS Sans SC;
      font-weight: 500;
      font-size: 13px;
      color: #696f7a;
      line-height: 14px;
      margin-right: 14px;
      position: relative;
      padding-bottom: 10px;
    }
    .active {
      color: #000000 !important;
      font-weight: bold !important;
      .total {
        font-weight: bold !important;
        font-size: 12px !important;
        color: #000000 !important;
      }
      .line {
        display: block !important;
      }
    }
  }
  .model-content-table {
    min-height: calc(100vh - 404px);
    .empty {
      display: flex;
      justify-content: center;
      align-items: center;
      height: calc(100vh - 384px);
      .empty-box {
        img {
          width: 160px;
          margin: 0 auto;
          display: block;
        }
        .empty-text {
          font-family: PingFang SC, PingFang SC;
          font-weight: 400;
          font-size: 12px;
          text-align: center;
          color: #999999;
          line-height: 16px;
          span {
            color: #434af9;
            border-bottom: 1xp solid #434af9;
            cursor: pointer;
          }
        }
      }
    }
    .table-list {
      display: grid;
      grid-template-columns: repeat(4, 1fr); /* 每行 5 列 */
      gap: 20px; /* 项目之间的间距 */
      padding-bottom: 40px;
      color: #ccc;
      .li:hover {
        transform: scale(1.01);
        box-shadow: 0px 0px 12px rgba(0, 0, 0, 0.12);
        .download-preview {
          z-index: 2;
          background: rgba(0, 0, 0, 0.6);
          display: flex;
          justify-content: center;
          align-items: center;
          position: relative;
          .download-preview-content {
            .download-button {
              padding:0 5px;
              height: 30px;
              cursor: pointer;
              background: #434af9;
              border-radius: 4px;
              display: flex;
              align-items: center;
              justify-content: center;
              border: 1px solid #434af9;
              font-family: PingFang SC, PingFang SC;
              font-weight: 500;
              font-size: 12px;
              color: #ffffff;

              line-height: 18px;

              img {
                margin-right: 4px;
              }
            }
            .preview-box {
              padding: 0 5px;
              height: 18px;
              background: rgba(0, 0, 0, 0.6);
              border-radius: 100px;
              position: absolute;
              right: 6px;
              display: flex;
              align-items: center;
              justify-content: center;
              cursor: pointer;
              bottom: 6px;
              z-index: 1;
              font-family: HarmonyOS Sans SC, HarmonyOS Sans SC;
              font-weight: 400;
              font-size: 10px;
              color: #ffffff;
              line-height: 12px;
              img {
                margin-right: 4px;
              }
            }
            .delete-video {
              width: 20px;
              height: 20px;
              background: rgba(255, 255, 255, 0.2);
              border-radius: 6px;
              position: absolute;
              left: 10px;
              display: flex;
              align-items: center;
              justify-content: center;
              cursor: pointer;
              top: 10px;
              z-index: 1;
            }
            .detection-failed-text {
              font-family: PingFang SC, PingFang SC;
              font-weight: 500;
              font-size: 12px;
              width: 80px;
              display: flex;
              justify-content: center;
              color: #ffffff;
              line-height: 18px;
              margin-bottom: 12px;
            }
            .detection-failed-title {
              font-family: PingFang SC, PingFang SC;
              font-weight: 400;
              width: 80px;
              font-size: 12px;
              display: flex;
              justify-content: center;
              color: #ffffff;
              line-height: 18px;
            }
            .preview-button {
              width: 80px;
              height: 30px;
              cursor: pointer;
              display: flex;
              align-items: center;
              justify-content: center;
              margin-bottom: 8px;
              border-radius: 4px;
              font-family: PingFang SC, PingFang SC;
              font-weight: 500;
              font-size: 12px;
              color: #ffffff;
              line-height: 18px;
              border: 1px solid rgba(255, 255, 255, 0.6);
              img {
                margin-right: 4px;
              }
            }
          }
        }
      }

      .li {
        transition: all 0.3s ease;
        aspect-ratio: 1 / 0.83;
        border-radius: 8px;
        position: relative;
        cursor: pointer;
        border: 1px solid #f2f2f4;

        .download-preview {
          display: none;
        }
        .comme {
          position: absolute;
          top: 0;
          width: 100%;
          left: 0;
          border-radius: 8px 8px 0 0;
          height: calc(100% - 65px);
        }
        .img-video {
          z-index: 1;
          background: linear-gradient(180deg, #b8c2ce 0%, #e2e6f0 100%);
          .img-video-content {
            position: relative;
            height: 100%;
            .model-video {
              width: 100%;
              height: 100%;
              object-fit: contain;
            }
            .duration {
              width: 35px;
              position: absolute;
              bottom: 8px;
              right: 8px;
              height: 18px;
              background: rgba(0, 0, 0, 0.63);
              border-radius: 4px;
              font-family: PingFang SC, PingFang SC;
              font-weight: 400;
              display: flex;
              justify-content: center;
              align-items: center;
              font-size: 10px;
              color: #ffffff;
              line-height: 12px;
              font-style: normal;
            }
            .fail {
              padding: 0 6px;
              height: 22px;
              background: rgba(255, 255, 255, 0.9);
              border-radius: 0px 8px 0px 8px;
              position: absolute;
              display: flex;
              justify-content: center;
              align-items: center;
              top: 0;
              right: 0;
              .fail-line {
                width: 4px;
                height: 4px;
                border-radius: 8px;
                background-color: red;
                margin-right: 5px;
              }
              span {
                font-family: HarmonyOS Sans SC, HarmonyOS Sans SC;
                font-weight: 400;
                font-size: 12px;
                color: #253858;
                line-height: 14px;
              }
            }
          }
        }
        .bottom-text {
          position: absolute;
          bottom: 0;
          padding: 4px 8px 8px 8px;
          left: 0;
          width: 100%;
          height: 65px;
          background: #ffffff;
          .top {
            display: flex;
            margin-top: 5px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 4px;
            .video-type {
              padding: 6px 7px;
              display: none;
              justify-content: center;
              align-items: center;
              background: rgba(6, 96, 255, 0.1);
              border-radius: 4px;
              font-family: PingFang SC, PingFang SC;
              font-weight: 500;
              font-size: 10px;
              color: #434af9;
              font-size: 14px;
              line-height: 12px;
            }
            .h1 {
              font-family: HarmonyOS Sans SC, HarmonyOS Sans SC;
              font-weight: 600;
              font-size: 14px;
              color: #252525;
              line-height: 23px;
              margin-left: 4px;
            }
          }
          .text {
            font-family: HarmonyOS Sans SC, HarmonyOS Sans SC;
            font-weight: 400;
            font-size: 12px;
            color: rgba(37, 37, 37, 0.5);
            white-space: nowrap;
            overflow: hidden;
            margin-top: 6px;
            text-overflow: ellipsis;
          }
        }
      }
    }
  }

  .pagination-box {
    position: sticky;
    z-index: 99;
    height: 46px;
    width: 100%;
    bottom: -20px;
    left: 0;
    background-color: #fff;
    .pagination-content {
      justify-content: center;
      display: flex;
      height: 46px;
    }
  }
}
</style>
