import path from 'path'
import { fileURLToPath } from 'url'

import cors from 'cors'
import Database from 'better-sqlite3'
import dotenv from 'dotenv'
import express from 'express'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const rootDir = path.resolve(__dirname, '..')

// load env both from repo root and dashboard folder to fit local/server setups
dotenv.config({ path: path.join(rootDir, '.env') })
dotenv.config({ path: path.join(__dirname, '.env') })

const PORT = Number.parseInt(process.env.PORT || process.env.DASHBOARD_PORT || '8000', 10)
const DB_PATH = path.resolve(
  rootDir,
  process.env.DASHBOARD_DB_PATH || path.join('misc', 'db.sqlite'),
)
const API_TOKEN = (process.env.DASHBOARD_API_TOKEN || '').trim()
const EXPIRING_DAYS = Math.max(1, Number.parseInt(process.env.DASHBOARD_EXPIRING_DAYS || '7', 10) || 7)
const ALLOW_ORIGINS = (process.env.DASHBOARD_CORS_ORIGINS || '*')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean)

const db = new Database(DB_PATH, { readonly: true, fileMustExist: false })

const app = express()
app.use(cors({ origin: ALLOW_ORIGINS.includes('*') ? '*' : ALLOW_ORIGINS }))

const clamp = (value, min, max) => Math.min(Math.max(value, min), max)

const tableExists = (name) => {
  const row = db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name = ?").get(name)
  return !!row
}

const safeJson = (raw, fallback) => {
  try {
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

const parseEnd = (raw) => {
  if (!raw) return null
  const value = String(raw).replace('T', ' ').trim()

  const parseYmd = (datePart, timePart) => {
    const [year, month, day] = datePart.split('-').map(Number)
    if (!year || !month || !day) return null
    let hour = 0
    let minute = 0
    let second = 0
    let ms = 0
    if (timePart) {
      const [hms, micros] = timePart.split('.')
      const parts = hms.split(':').map(Number)
      hour = parts[0] || 0
      minute = parts[1] || 0
      second = parts[2] || 0
      if (micros) {
        ms = Number(String(micros).padEnd(3, '0').slice(0, 3)) || 0
      }
    } else {
      // date only => end of day
      hour = 23
      minute = 59
    }
    const dt = new Date(year, month - 1, day, hour, minute, second, ms)
    return Number.isNaN(dt.getTime()) ? null : dt
  }

  const parseDmy = (datePart, timePart) => {
    const [day, month, year] = datePart.split('.').map(Number)
    if (!year || !month || !day) return null
    let hour = 0
    let minute = 0
    if (timePart) {
      const parts = timePart.split(':').map(Number)
      hour = parts[0] || 0
      minute = parts[1] || 0
    } else {
      hour = 23
      minute = 59
    }
    const dt = new Date(year, month - 1, day, hour, minute, 0, 0)
    return Number.isNaN(dt.getTime()) ? null : dt
  }

  if (/^\d{4}-\d{2}-\d{2}/.test(value)) {
    const [datePart, timePart] = value.split(' ')
    return parseYmd(datePart, timePart)
  }
  if (/^\d{2}\.\d{2}\.\d{4}/.test(value)) {
    const [datePart, timePart] = value.split(' ')
    return parseDmy(datePart, timePart)
  }

  const iso = new Date(value)
  if (!Number.isNaN(iso.getTime())) return iso
  return null
}

const statusFromSubscriptionEnd = (endDate, expiringDays, now) => {
  if (!endDate) return 'expired'
  const diffMs = endDate.getTime() - now.getTime()
  if (diffMs <= 0) return 'expired'
  if (diffMs <= expiringDays * 86400 * 1000) return 'expiring'
  return 'active'
}

const latestPaidByUser = (paymentsRaw) => {
  const map = {}
  for (const row of paymentsRaw) {
    const status = (row.status || '').toLowerCase()
    if (status !== 'paid') continue
    const ts =
      parseEnd(row.paid_at) ||
      parseEnd(row.tx_timestamp) ||
      parseEnd(row.updated_at) ||
      parseEnd(row.created_at)
    const amount = Number(row.amount || 0)
    const uid = row.telegram_id
    if (uid == null) continue
    const prev = map[uid]
    if (!prev || (ts && ts > prev.ts)) {
      map[uid] = { ts: ts || new Date(0), amount }
    }
  }
  return map
}

const buildSnapshot = ({ paymentsLimit, expiringDays, includeNonUser }) => {
  const hasUsers = tableExists('users')
  const hasPayments = tableExists('payments')
  const hasSettings = tableExists('settings')

  const usersRaw = hasUsers ? db.prepare('SELECT * FROM users').all() : []
  const paymentsRaw = hasPayments
    ? db.prepare('SELECT * FROM payments ORDER BY created_at DESC LIMIT ?').all(paymentsLimit)
    : []
  const latestPaid = latestPaidByUser(paymentsRaw)

  const now = new Date()
  const usersAll = usersRaw.map((row) => {
    const plans = safeJson(row.subscription_plan, [])
    const endDate = parseEnd(row.subscription_end)
    const status = statusFromSubscriptionEnd(endDate, expiringDays, now)
    const price = latestPaid[row.telegram_id]?.amount
    const jobTitle = row.job_title || 'user'
    return {
      telegramId: row.telegram_id,
      userName: row.user_name || '',
      firstName: row.first_name,
      plan: Array.isArray(plans) ? plans : [],
      subscriptionEnd: endDate ? endDate.toISOString().replace('T', ' ').replace('Z', '') : null,
      status,
      jobTitle,
      planPrice: price,
    }
  })

  const users = includeNonUser
    ? usersAll
    : usersAll.filter((u) => String(u.jobTitle).toLowerCase() === 'user')

  const activeUsersAll = usersAll.filter((u) => {
    const job = String(u.jobTitle || '').toLowerCase()
    if (job && job !== 'user') return true
    return u.status !== 'expired'
  })
  const stats = {
    total: usersAll.length,
    active: usersAll.filter((u) => u.status === 'active').length,
    expiring: usersAll.filter((u) => u.status === 'expiring').length,
    expired: usersAll.filter((u) => u.status === 'expired').length,
    jobTitleUser: usersAll.filter((u) => String(u.jobTitle).toLowerCase() === 'user').length,
    jobTitleNonUser: usersAll.filter((u) => String(u.jobTitle).toLowerCase() !== 'user').length,
  }

  let channels = []
  if (hasSettings) {
    const row = db.prepare("SELECT value FROM settings WHERE key = 'channel'").get()
    const list = safeJson(row?.value, [])
    channels = list.map((ch) => ({
      name: ch.name,
      members: activeUsersAll.filter((u) => Array.isArray(u.plan) && u.plan.includes(ch.name)).length,
    }))
  }

  const payments = paymentsRaw.map((row) => ({
    id: row.id,
    telegramId: row.telegram_id,
    userName: row.user_name || String(row.telegram_id || ''),
    amount: Number(row.amount || 0),
    status: row.status,
    paidAt: row.paid_at,
    plan: row.plan,
    method: row.method,
    walletAddress: row.wallet_address,
    walletFrom: row.tx_from,
  }))

  return { users, payments, channels, stats }
}

const authGuard = (req, res, next) => {
  if (!API_TOKEN) return next()
  const auth = req.headers.authorization
  const headerToken = auth?.toLowerCase().startsWith('bearer ')
    ? auth.split(' ')[1]
    : null
  const keyToken = req.headers['x-api-key']
  const queryToken = req.query.token
  const candidate = (headerToken || keyToken || queryToken || '').toString().trim()
  if (candidate !== API_TOKEN) {
    return res.status(401).json({ error: 'Unauthorized' })
  }
  return next()
}

app.get('/health', (_req, res) => res.json({ status: 'ok' }))

app.get('/api/dashboard', authGuard, (req, res) => {
  const paymentsLimit = clamp(Number.parseInt(req.query.payments_limit, 10) || 120, 1, 500)
  const expiringDays = clamp(
    Number.parseInt(req.query.expiring_days, 10) || EXPIRING_DAYS,
    1,
    90,
  )
  const includeNonUser = ['1', 'true', 'yes'].includes(
    String(req.query.include_non_user || '').toLowerCase(),
  )
  const payload = buildSnapshot({ paymentsLimit, expiringDays, includeNonUser })
  res.json(payload)
})

app.listen(PORT, () => {
  const url = `http://localhost:${PORT}/api/dashboard`
  console.log(`[dashboard-api] DB: ${DB_PATH}`)
  console.log(`[dashboard-api] listening at ${url}`)
  console.log(`[dashboard-api] Set VITE_DASHBOARD_API_URL=${url} in dashboard/.env`)
  if (API_TOKEN) {
    console.log(`[dashboard-api] Set VITE_DASHBOARD_API_TOKEN=${API_TOKEN} in dashboard/.env`)
  } else {
    console.log('[dashboard-api] No auth token set (DASHBOARD_API_TOKEN), endpoint is open')
  }
})
