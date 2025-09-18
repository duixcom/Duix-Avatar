/*
 * 通用文本
 */

import { Button } from 'tdesign-vue-next'

// 中文翻译
export const commonZh = {
  menu: {
    text: '首页'
  },
  header: {
    minimizeText: '最小化',
    maximizeText: '最大化',
    restoreText: '还原',
    closeText: '关闭'
  },
  tab: {
    myWorksText: '我的作品',
    myAvatarsText: '我的数字模特'
  },
  input: {
    enterNamePlaceholder: '请输入数字模特名称',
    enterKeywordPlaceholder: '请输入短视频名称/模特名称',
    avatarNamePlaceholder: '请输入模特名称',
    searchAvatarNamePlaceholder: '搜索模特',
    videoContentTextPlaceholder: '请在这里输入您的文本内容，支持中英文'
  },
  banner0: {
    title: '短视频制作',
    subTitle: '极速生产口播视频',
    buttonText: '创建视频'
  },
  banner1: {
    title: '快速定制模特',
    subTitle: '只需一个视频快速定制',
    buttonText: '快速定制'
  },
  videoList: {
    previewTitle: '预览视频',
    downloadTitle: '下载视频',
    makeFailedText: '制作失败',
    draftsText: '草稿',
    underProduction: '正在制作中，请耐心等待',
    queuing: '排队中，请耐心等待',
    emptyText: '您还没有视频作品',
    emptyLinkRouteText: '点击这里',
    emptyRightText: '开始制作视频'
  },
  myModelList: {
    emptyText: '您还没有专属模特',
    emptyLinkRouteText: '点击这里',
    emptyRightText: '开始制作模特',
    inProgressText: '训练中',
    createVideoText: '做视频',
    previewText: '预览'
  },
  deleteDialog: {
    buttonTextLeft: '取消',
    buttonTextRight: '确定',
    titleH1: '提示',
    titleOk: '确认删除？',
    titleText: '删除后将无法恢复哦~'
  },
  message: {
    deleteErrorText: '删除失败',
    deleteSuccessText: '删除成功',
    videoUploadError: '视频上传失败',
    videoLength: '视频时长至少8秒',
    videoContentText: '请输入文本内容',
    selectModelsTextError: '请先定制或选择模特',
    VideoTextError: '请输入视频名称',
    VideoCopywritingTextError: '请输入视频文案',
    videoSynthesisTextError: '合成视频失败，请稍后再试',
    initEditVideoPageFailed: '初始化视频编辑页面失败，请稍后再试'
  },
  modelCreateView: {
    headerTitle: '极速定制',
    submitButtonText: '提交定制',
    avatarNameText: '模特名称',
    isUploading: '正在上传中...',
    tipsText: '点击上传拍摄好的原始视频',
    uploadVideoText: '上传视频',
    guideTitle: '标准示例',
    okRulesLi1: '1.视频时长最少8秒,说话吐字清晰；',
    okRulesLi2: '2.视频前后有且只有同一个人；',
    okRulesLi3: '3.五官清晰不遮挡，头部不倾斜或侧向，手势不要出现在面部、嘴巴、脖子；',
    okRulesLi4: '4.视频分辨率最低720P；',
    okRulesLi5: '5.视频格式为MP4/MOV。',
    guideErrorTitle: '错误示例',
    faceMore: '多张人脸',
    faceBig: '面部过大',
    faceNo: '未检测到人脸',
    faceHalf: '五官遮挡',
    videoName: '视频名称'
  },
  selectView: {
    selectHeaderText: '模特列表',
    generateButtonText: '立即定制',
    modalFinishedObj: {
      text1: '请移至',
      text2: '“首页-我的作品”',
      text3: '中查看制作结果～',
      rightBtnText: '再创建一个',
      progressBtnText: '去看制作进度',
      okBtnText: '知道了',
      videoOKText: '您的视频已提交！',
      prompt: '温馨提示'
    }
  },
  preview: {
    headerText: '画面预览'
  },
  editView: {
    headerText: '视频内容',
    text: '文本合成',
    audio: '音频合成',
    addAudio: '添加音频',
    tip: '单次最多上传1个录音文件；支持mp3、wav、flac、m4a文件，单个录音时长小于30分钟，请上传纯干音文件，背景音、噪音会影响视频合成效果哦～',
    listen: '试听',
    delete: '删除',
    upload: '上传',
    uploadError: '音频上传失败',
    durationError: '音频时长不能超过30分钟',
    myVoice: '我的',
    selectSpeaker: '选择',
    speaker: '音色',
    searchSpeaker: '搜索音色'
  },
  headerView: {
    headerBackText: '返回',
    createVideoBtnText: '合成视频'
  },
  setting: {
    title: '设置',
    tab: {
      userAgreementText: '用户协议',
      languageSwitchText: '语言切换',
      openLogText: '打开日志'
    },
    languageSwitch: {
      languageEnText: '英文',
      languageZhText: '中文'
    }
  }
}

// 英文翻译
export const commonEn = {
  menu: {
    text: 'Home'
  },
  header: {
    minimizeText: 'Minimize',
    maximizeText: 'Maximize',
    restoreText: 'Restore',
    closeText: 'Close'
  },
  tab: {
    myWorksText: 'My Works',
    myAvatarsText: 'My Avatars'
  },
  input: {
    enterNamePlaceholder: 'Please Enter the Name',
    enterKeywordPlaceholder: 'Please Enter the keyword',
    avatarNamePlaceholder: 'Please Enter Avatar Name',
    searchAvatarNamePlaceholder: 'Search',
    videoContentTextPlaceholder: 'Please enter your text content here'
  },
  banner0: {
    title: 'Create Video',
    subTitle: 'AI Video Generator',
    buttonText: 'Create Video'
  },
  banner1: {
    title: 'Create Avatar',
    subTitle: 'Upload a video to generate your own digital avatar.',
    buttonText: 'Create Avatar'
  },
  videoList: {
    previewTitle: 'Preview',
    downloadTitle: 'Download',
    makeFailedText: 'Failed',
    draftsText: 'Drafts',
    underProduction: 'Generating, please wait for a moment.',
    queuing: 'In the queue, please wait  for a moment.',
    emptyText: "You don't have any video works yet",
    emptyLinkRouteText: 'click here',
    emptyRightText: 'to Create Video.'
  },
  myModelList: {
    emptyText: "You don't have a Avatar yet",
    emptyLinkRouteText: 'click here',
    emptyRightText: 'to start making a Avatar.',
    inProgressText: 'In Progress',
    createVideoText: 'Create Video',
    previewText: 'Preview'
  },
  deleteDialog: {
    buttonTextLeft: 'Cancel',
    buttonTextRight: 'OK',
    titleH1: 'Notice',
    titleOk: 'Confirm Delete?',
    titleText: 'It cannot be recovered after deletion~'
  },
  message: {
    deleteErrorText: 'Failed',
    deleteSuccessText: 'Successful',
    videoUploadError: 'Video Upload Failed',
    videoLength: 'Video length ≥ 8s',
    videoContentText: 'Please enter the text content',
    selectModelsTextError: 'Please customize or select a model first',
    VideoTextError: 'Please enter the video name',
    VideoCopywritingTextError: 'Please enter the video copy',
    videoSynthesisTextError: 'Video Create failed, please try again later',
    initEditVideoPageFailed: 'Failed to initialize video editing page, please try again later'
  },
  modelCreateView: {
    headerTitle: 'Rapid customization',
    submitButtonText: 'Submit',
    avatarNameText: 'Avatar Name',
    isUploading: 'Uploading...',
    tipsText: 'Click to Upload the Video',
    uploadVideoText: 'Upload Video',
    guideTitle: 'Example',
    okRulesLi1: '1.Video length ≥ 8s. ',
    okRulesLi2: '2.Only one person should appear in the video.',
    okRulesLi3: '3.Facial features should be visible.',
    okRulesLi4: '4.Resolution ≥ 720p; The video format is MP4/MOV.',
    okRulesLi5: '5.It will clone both your image and voice from the video.',
    guideErrorTitle: 'Incorrect Example',
    faceMore: 'Multiple faces',
    faceBig: 'face too close',
    faceNo: 'No face',
    faceHalf: 'Face is obscured',
    videoName: 'video name'
  },
  selectView: {
    selectHeaderText: 'My Avatars',
    generateButtonText: 'Create Avatar',
    modalFinishedObj: {
      text1: 'Please go to',
      text2: '"Home - My Avatars" ',
      text3: 'to check the results～',
      rightBtnText: 'Create again',
      progressBtnText: 'Go production progress',
      okBtnText: 'Got it',
      videoOKText: 'Your video has been submitted!',
      prompt: 'Reminder'
    }
  },
  preview: {
    headerText: 'Preview'
  },
  editView: {
    headerText: 'Content',
    text: 'Text Synthesis',
    audio: 'Audio Synthesis',
    addAudio: 'Add Audio',
    tip: 'You can upload up to 1 audio file at a time; supports mp3, wav, flac, m4a files, each recording should be less than 30 minutes. Please upload pure dry audio files, as background noise and sounds will affect the video synthesis effect.',
    listen: 'Listen',
    delete: 'Delete',
    upload: 'Upload',
    uploadError: 'Audio Upload Failed',
    durationError: 'Audio duration cannot exceed 30 minutes',
    myVoice: 'My',
    selectSpeaker: 'Select',
    speaker: 'Speaker',
    searchSpeaker: 'Search Speaker'
  },
  headerView: {
    headerBackText: 'Back',
    createVideoBtnText: 'Submit'
  },
  setting: {
    title: 'Setting',
    tab: {
      userAgreementText: 'User Agreement',
      languageSwitchText: 'Language switch',
      openLogText: 'Open Log'
    },
    languageSwitch: {
      languageEnText: 'English',
      languageZhText: 'Chinese'
    }
  }
}
