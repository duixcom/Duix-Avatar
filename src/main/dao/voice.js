import { connect } from '../db/index.js'

export function selectAll() {
  const db = connect()
  const rows = db.prepare(`SELECT * FROM voice`).all()
  return rows
}

export function insert({ origin_audio_path, lang, asr_format_audio_url, reference_audio_text }) {
  const db = connect()
  const stmt = db.prepare(
    `insert into voice (origin_audio_path, lang, asr_format_audio_url, reference_audio_text, created_at)
      values (?,?,?,?,?);`
  )
  const info = stmt.run(
    origin_audio_path,
    lang,
    asr_format_audio_url,
    reference_audio_text,
    Date.now()
  )
  const id = info.lastInsertRowid
  return id
}

export function insertCamb({ origin_audio_path, lang, camb_voice_id }) {
  const db = connect()
  const stmt = db.prepare(
    `insert into voice (origin_audio_path, lang, camb_voice_id, created_at)
      values (?,?,?,?);`
  )
  const info = stmt.run(
    origin_audio_path,
    lang,
    camb_voice_id,
    Date.now()
  )
  const id = info.lastInsertRowid
  return id
}

export function selectByID(id) {
  const db = connect()
  const stmt = db.prepare('SELECT * FROM voice WHERE id = ?')
  const row = stmt.get(id)
  return row
}
