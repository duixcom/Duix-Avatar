import { connect } from '../db/index.js'

export function insert({ modelName, videoPath, audioPath, voiceId, isImage, coverPath }) {
  const db = connect()
  const stmt = db.prepare(
    'INSERT INTO f2f_model (name, video_path, audio_path, voice_id, is_image, cover_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)'
  )
  const info = stmt.run(modelName, videoPath, audioPath, voiceId, isImage, coverPath, Date.now())
  return info.lastInsertRowid
}

export function selectPage({ page, pageSize, name = '' }) {
  const db = connect()
  const offset = (page - 1) * pageSize
  const rows = db
    .prepare(
      `SELECT * FROM f2f_model WHERE name like '%${name}%' ORDER BY created_at DESC LIMIT ${pageSize} OFFSET ${offset}`
    )
    .all()
  return rows
}

export function count(name = '') {
  const db = connect()
  const rows = db
    .prepare(`SELECT COUNT(*) as total FROM f2f_model WHERE name like '%${name}%'`)
    .get()
  return rows.total
}

export function selectByID(id) {
  const db = connect()
  const stmt = db.prepare('SELECT * FROM f2f_model WHERE id = ?')
  const row = stmt.get(id)
  return row
}

export function remove(id) {
  const db = connect()
  db.prepare(`DELETE FROM f2f_model WHERE id = ?`).run(id)
}
