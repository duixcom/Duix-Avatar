import { WebcastPushConnection } from 'tiktok-live-connector'
import log from '../logger.js'

let connection

function connectToTiktok(username, commentCallback) {
  if (connection) {
    connection.disconnect()
  }

  connection = new WebcastPushConnection(username)

  connection.on('chat', (data) => {
    log.info(`TikTok comment from ${data.uniqueId}: ${data.comment}`)
    commentCallback(data.comment)
  })

  connection.on('connected', () => {
    log.info(`Connected to TikTok live stream for user ${username}`)
  })

  connection.on('disconnected', () => {
    log.info('Disconnected from TikTok live stream')
  })

  connection.on('error', (err) => {
    log.error('TikTok connection error:', err)
  })

  connection.connect().catch(err => {
    log.error('Failed to connect to TikTok:', err)
  })
}

export { connectToTiktok }
