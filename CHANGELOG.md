# 变更日志（CHANGELOG）

## 2025-08-21
本次为次版本更新，增加局域网部署体验，新增应用内设置能力与多语言完善。

- [Added]
  - 应用内“设置”页：支持读取/保存配置并“一键保存并重启”。
    - 路由：`/settings`（`src/renderer/src/views/settings/index.vue`）
    - 预加载桥接：`window.settings.get/save/restart`（`src/preload/index.js`）
    - 主进程 IPC：`settings/get`、`settings/save`、`settings/restart`（`src/main/service/settings.js`）
  - 持久化配置：从 `app.getPath('userData')/config.json` 读取/写入；优先级：config.json > 环境变量 > 默认值（`src/main/config/config.js`）。
  - 顶部“设置”按钮整合“应用设置”入口，直达“设置”页（`src/renderer/src/components/AppHeader.vue`）。
  - i18n 补齐：`common.menu.settings`、`common.setting.appSettingsText`（`src/renderer/src/i18n/components/common.js`）。

- [Changed]
  - 默认 LAN 配置更新（Windows UNC 路径已正确转义）：
    - `HEYGEM_HOST=192.168.110.22`
    - `HEYGEM_TTS_PORT=18180`，`HEYGEM_VIDEO_PORT=8383`
    - `HEYGEM_MODEL_DIR=\\\\192.168.110.22\\heygem_data\\face2face\\temp`
    - `HEYGEM_TTS_PRODUCT_DIR=\\\\192.168.110.22\\heygem_data\\face2face\\temp`
    - `HEYGEM_TTS_ROOT=\\\\192.168.110.22\\heygem_data\\voice\\data`
    - `HEYGEM_TTS_TRAIN_DIR=\\\\192.168.110.22\\heygem_data\\voice\\data\\origin_audio`
  - 侧边栏菜单仅保留“首页”，移除“设置”入口（`src/renderer/src/components/menuLIst.vue`），避免重复入口。
  - 菜单文案改为 `t(item.key)` 渲染，语言切换即时生效（`menuLIst.vue`）。

- [Fixed]
  - 修复 UNC 默认路径字符串转义错误导致的语法/打包告警（`src/main/config/config.js`）。
  - 多语言缺失键导致显示 key 文本的问题（`common.js`）。

- [Deployment Notes]
  - 首次安装或升级后，建议进入“应用设置”保存参数并自动重启，以写入 `config.json`。
  - 局域网部署请确保 SMB 共享与读写权限：`\\192.168.110.22\heygem_data\...`。
  - 根据实际需求修改`192.168.110.22`为实际IP地址。

- [Upgrade Guide]
  1) 卸载旧版或直接覆盖安装。
  2) 打开应用 → 右上角“设置” → “应用设置” → 填写并保存 → 自动重启生效。
  3) 多人环境：确认各客户端均能访问 SMB 共享与服务端口。
