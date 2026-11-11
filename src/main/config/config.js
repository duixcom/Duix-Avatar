import os from 'os'
import { createRuntimeConfig } from './runtime.mjs'

const config = createRuntimeConfig({
  platform: process.platform,
  homedir: os.homedir(),
  env: process.env
})

export const serviceUrl = config.serviceUrl
export const assetPath = config.assetPath
