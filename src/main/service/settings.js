import { ipcMain, app } from 'electron'
import fs from 'fs'
import path from 'path'

const MODEL_NAME = 'settings'

function getConfigPath() {
  const userDataDir = app.getPath('userData')
  return path.join(userDataDir, 'config.json')
}

function ensureDirExists(filePath) {
  const dir = path.dirname(filePath)
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }
}

function readConfig() {
  const cfgPath = getConfigPath()
  try {
    if (fs.existsSync(cfgPath)) {
      const raw = fs.readFileSync(cfgPath, 'utf-8')
      return JSON.parse(raw)
    }
  } catch (e) {
    // ignore and return empty
  }
  return {}
}

function writeConfig(cfg) {
  const cfgPath = getConfigPath()
  ensureDirExists(cfgPath)
  fs.writeFileSync(cfgPath, JSON.stringify(cfg ?? {}, null, 2), 'utf-8')
  return true
}

function restartApp() {
  app.relaunch()
  app.exit(0)
}

export function init() {
  ipcMain.handle(MODEL_NAME + '/get', () => {
    return readConfig()
  })
  ipcMain.handle(MODEL_NAME + '/save', (event, cfg) => {
    return writeConfig(cfg)
  })
  ipcMain.handle(MODEL_NAME + '/restart', () => {
    restartApp()
  })
}
