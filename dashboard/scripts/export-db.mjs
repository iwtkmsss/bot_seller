import fs from 'fs'
import path from 'path'
import initSqlJs from 'sql.js'

const root = path.resolve(process.cwd(), '..')
const dbPath = path.join(root, 'misc', 'db.sqlite')
const outPath = path.join(process.cwd(), 'src', 'data', 'runtimeData.json')

export async function exportDb({ silent = false } = {}) {
  if (!fs.existsSync(dbPath)) {
    if (!silent) console.error('DB file not found:', dbPath)
    return
  }

  const fileBuffer = fs.readFileSync(dbPath)
  const SQL = await initSqlJs()
  const db = new SQL.Database(new Uint8Array(fileBuffer))

  const execRows = (sql) => {
    try {
      const res = db.exec(sql)
      if (!res[0]) return []
      const { columns, values } = res[0]
      return values.map((row) => Object.fromEntries(columns.map((c, i) => [c, row[i]])))
    } catch (e) {
      return []
    }
  }

  const parseJson = (str, fallback) => {
    try {
      return JSON.parse(str ?? 'null') ?? fallback
    } catch {
      return fallback
    }
  }

  const now = Date.now()
  const usersRaw = execRows('SELECT * FROM users')
  const users = usersRaw.map((u) => {
    const plans = parseJson(u.subscription_plan, [])
    const end = u.subscription_end
    const endDate = end ? Date.parse(end.replace(' ', 'T')) : NaN
    let status = 'expired'
    if (!Number.isNaN(endDate)) {
      const diff = endDate - now
      status = diff <= 0 ? 'expired' : diff <= 7 * 86_400_000 ? 'expiring' : 'active'
    }
    return {
      telegramId: u.telegram_id,
      userName: u.user_name,
      firstName: u.first_name,
      plan: plans,
      subscriptionEnd: end,
      status,
      jobTitle: u.job_title,
      planPrice: Array.isArray(plans) ? plans.length * 50 : 0,
    }
  })

  const paymentsRaw = execRows('SELECT * FROM payments ORDER BY created_at DESC LIMIT 120')
  const payments = paymentsRaw.map((p) => ({
    id: p.id,
    userName: p.user_name || `${p.telegram_id}`,
    amount: Number(p.amount ?? 0),
    status: p.status,
    paidAt: p.paid_at,
    plan: p.plan,
    method: p.method,
  }))

  const channelRow = execRows("SELECT value FROM settings WHERE key='channel'")[0]
  const channels = parseJson(channelRow?.value, []).map((ch) => ({
    name: ch.name,
    members: 0,
  }))

  const payload = { users, payments, channels }
  fs.writeFileSync(outPath, JSON.stringify(payload, null, 2))
  if (!silent) {
    console.log('✅ Exported to', outPath)
    console.log(`Users: ${users.length}, payments: ${payments.length}, channels: ${channels.length}`)
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  exportDb().catch((err) => {
    console.error(err)
    process.exit(1)
  })
}
