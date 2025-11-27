import fs from 'fs'
import path from 'path'
import { exportDb } from './export-db.mjs'

const root = path.resolve(process.cwd(), '..')
const dbPath = path.join(root, 'misc', 'db.sqlite')

let lastMtime = 0
const intervalMs = 5000

const tick = async () => {
  try {
    const stat = fs.statSync(dbPath)
    const mtime = stat.mtimeMs
    if (mtime !== lastMtime) {
      lastMtime = mtime
      console.log(`[watch-db] change detected (${new Date(mtime).toLocaleString()}) -> exporting...`)
      await exportDb({ silent: false })
    }
  } catch (e) {
    console.error('[watch-db] error:', e.message)
  }
}

console.log('[watch-db] watching', dbPath, `every ${intervalMs / 1000}s`)
tick()
const timer = setInterval(tick, intervalMs)

process.on('SIGINT', () => {
  clearInterval(timer)
  console.log('\n[watch-db] stopped')
  process.exit(0)
})
