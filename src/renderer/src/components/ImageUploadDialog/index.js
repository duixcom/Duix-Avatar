import { createApp } from 'vue'
import TDesign from 'tdesign-vue-next'
import ImageUploadDialog from '../ImageUploadDialog.vue'
import i18n from "@renderer/i18n/index.js";

export const createImageModel = (props = {}) => {
  const rootNode = document.createElement('div')
  document.body.appendChild(rootNode)

  return new Promise((resolve) => {
    const options = {
      ...props,
      visible: true,
      onClose(result) {
        resolve(result)
      },
      onClosed: () => {
        app.unmount()
        document.body.removeChild(rootNode)
      }
    }

    const app = createApp(ImageUploadDialog, options).use(TDesign).use(i18n)
    app.mount(rootNode)
  })
}
