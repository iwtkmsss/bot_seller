import type { FormEvent } from 'react'
import { memo, useEffect, useMemo, useState } from 'react'
import type { MockChannel, MockPayment, MockUser } from './data/mockData'

type UserStatus = 'active' | 'expiring' | 'expired'
type PaymentStatus = 'paid' | 'pending' | 'timeout' | 'canceled'
type TabId = 'overview' | 'stats' | 'payments'
type SortOrder = 'asc' | 'desc'
type SearchKey = 'userName' | 'telegramId' | 'plan'
type PaymentSearchKey = 'userName' | 'telegramId' | 'plan' | 'method' | 'walletAddress' | 'walletFrom'
type AuthState = {
  authed: boolean
  attemptsLeft: number
  lockedUntil: number
}

const statusChip: Record<UserStatus, string> = {
  active: 'Активен',
  expiring: 'Скоро заканчивается',
  expired: 'Просрочен',
}

const paymentChip: Record<PaymentStatus, string> = {
  paid: 'Оплачено',
  pending: 'В обработке',
  timeout: 'Тайм-аут',
  canceled: 'Отменено',
}

const ADMIN_ROLES = (import.meta.env.VITE_ADMIN_ROLES ?? 'admin')
  .split(',')
  .map((v: string) => v.trim())
  .filter(Boolean)
const PAGE_SIZE = Math.max(1, Number.parseInt(import.meta.env.VITE_PAGE_SIZE ?? '5', 10) || 5)
const AUTH_USER = import.meta.env.VITE_AUTH_USER ?? 'admin'
const AUTH_PASS = import.meta.env.VITE_AUTH_PASS ?? '1234'
const MAX_ATTEMPTS = Math.max(1, Number.parseInt(import.meta.env.VITE_MAX_ATTEMPTS ?? '5', 10) || 5)
const LOCK_MS = Math.max(1000, Number.parseInt(import.meta.env.VITE_LOCK_MS ?? '30000', 10) || 30000)

function formatDate(value?: string) {
  if (!value) return '-'
  const date = new Date(value)
  return date.toLocaleString('ru-RU', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    fractionalSecondDigits: 3,
    timeZoneName: 'short',
    hour12: false,
  })
}

function formatMoney(value: number) {
  return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
}

function toInt(value: unknown, fallback = 0) {
  const num = Number(value)
  if (Number.isFinite(num)) return Math.trunc(num)
  return fallback
}

function toPositiveInt(value: unknown, fallback = 0) {
  return Math.max(0, toInt(value, fallback))
}

function parseDateValue(value?: string) {
  if (!value) return null
  const ms = Date.parse(value.replace(' ', 'T'))
  if (Number.isNaN(ms)) return null
  return new Date(ms)
}

function SummaryCard({ title, value, sub }: { title: string; value: string; sub?: string }) {
  return (
    <div className="card summary-card">
      <div className="card-title">{title}</div>
      <div className="card-value">{value}</div>
      {sub && <div className="card-sub">{sub}</div>}
    </div>
  )
}

const UserRow = memo(function UserRow({ user }: { user: MockUser }) {
  return (
    <div className="table-row">
      <div>
        <div className="strong">@{user.userName || 'no_username'}</div>
        <div className="muted">{user.telegramId}</div>
      </div>
      <div>
        <div>{user.plan.join(', ')}</div>
        <div className="muted">{user.jobTitle}</div>
      </div>
      <div>
        <span className={`pill pill-${user.status}`}>{statusChip[user.status]}</span>
      </div>
      <div>{formatDate(user.subscriptionEnd)}</div>
    </div>
  )
})

function maskWallet(addr?: string | null) {
  if (!addr) return '—'
  const value = String(addr)
  if (value.length <= 10) return value
  return `${value.slice(0, 5)}...${value.slice(-5)}`
}

const PaymentTableRow = memo(function PaymentTableRow({ payment }: { payment: PaymentItem }) {
  return (
    <div className="table-row">
      <div>
        <div className="strong">{payment.userName || 'unknown'}</div>
        <div className="muted">{payment.telegramId ?? '—'}</div>
      </div>
      <div>
        <div>{payment.plan || '—'}</div>
        <div className="muted">{payment.method}</div>
      </div>
      <div>
        <div className="muted">куда: {maskWallet(payment.walletAddress)}</div>
        <div className="muted">откуда: {maskWallet(payment.walletFrom)}</div>
      </div>
      <div>
        <span className="pill">{paymentChip[payment.status as PaymentStatus]}</span>
      </div>
      <div>
        <div>{formatMoney(Number(payment.amount) | 0)}</div>
        <div className="muted">{formatDate(payment.paidAt)}</div>
      </div>
    </div>
  )
})

type PaymentItem = MockPayment & {
  telegramId?: number | string
  walletAddress?: string | null
  walletFrom?: string | null
}

type DataShape = {
  users: MockUser[]
  payments: PaymentItem[]
  channels: MockChannel[]
  stats?: {
    revenueMonth?: number
  }
}

type ChannelStats = {
  name: string
  members: number
  planTotal: number
  planActive: number
  planActiveStrict: number
  planExpiring: number
  planExpired: number
  hasBreakdown: boolean
}

const fallbackData: DataShape = {
  users: [],
  payments: [],
  channels: [],
  stats: undefined,
}

export default function App() {
  const [filter, setFilter] = useState<UserStatus | 'all'>('all')
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')
  const [page, setPage] = useState(1)
  const [searchKey, setSearchKey] = useState<SearchKey>('userName')
  const [searchTerm, setSearchTerm] = useState('')
  const [auth, setAuth] = useState<AuthState>(() => {
    try {
      const raw = localStorage.getItem('dashboard_auth')
      if (!raw) return { authed: false, attemptsLeft: MAX_ATTEMPTS, lockedUntil: 0 }
      const parsed = JSON.parse(raw) as Partial<AuthState>
      return {
        authed: !!parsed.authed,
        attemptsLeft: parsed.attemptsLeft ?? MAX_ATTEMPTS,
        lockedUntil: parsed.lockedUntil ?? 0,
      }
    } catch {
      return { authed: false, attemptsLeft: MAX_ATTEMPTS, lockedUntil: 0 }
    }
  })
  const [paymentFilter, setPaymentFilter] = useState<PaymentStatus | 'all'>('all')
  const [paymentSortOrder, setPaymentSortOrder] = useState<SortOrder>('desc')
  const [paymentSearchKey, setPaymentSearchKey] = useState<PaymentSearchKey>('userName')
  const [paymentSearchTerm, setPaymentSearchTerm] = useState('')
  const [paymentPage, setPaymentPage] = useState(1)
  const [data, setData] = useState<DataShape>(fallbackData)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loginInput, setLoginInput] = useState('')
  const [passInput, setPassInput] = useState('')
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    if (!auth.authed) {
      setLoadError(null)
      setLoading(false)
      setData(fallbackData)
      return
    }

    const apiUrl = import.meta.env.VITE_DASHBOARD_API_URL
    if (!apiUrl) {
      setLoadError(null)
      setLoading(false)
      setData(fallbackData)
      return
    }

    const controller = new AbortController()
    const fetchData = async () => {
      setLoading(true)
      setLoadError(null)
      try {
        const headers: Record<string, string> = { Accept: 'application/json' }
        const token = import.meta.env.VITE_DASHBOARD_API_TOKEN
        if (token) headers.Authorization = `Bearer ${token}`

        const resp = await fetch(apiUrl, { headers, signal: controller.signal })
        if (!resp.ok) {
          throw new Error(`API responded with ${resp.status}`)
        }

        const payload = (await resp.json()) as Partial<DataShape> | null
        if (
          !payload ||
          !Array.isArray(payload.users) ||
          !Array.isArray(payload.payments) ||
          !Array.isArray(payload.channels)
        ) {
          throw new Error('Unexpected payload from dashboard API')
        }

        setData({
          users: payload.users,
          payments: payload.payments,
          channels: payload.channels,
          stats: typeof payload.stats === 'object' && payload.stats !== null ? payload.stats : undefined,
        })
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        console.warn('[dashboard] API unavailable, showing zeros', err)
        setLoadError(null)
        setData(fallbackData)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    return () => controller.abort()
  }, [auth.authed])

  const visiblePool = useMemo(
    () => data.users.filter((u) => !ADMIN_ROLES.includes((u.jobTitle || '').toLowerCase())),
    [data.users],
  )

  useEffect(() => {
    setPage(1)
  }, [filter, sortOrder, searchKey, searchTerm])
  useEffect(() => {
    setPaymentPage(1)
  }, [paymentFilter, paymentSortOrder, paymentSearchKey, paymentSearchTerm])

  const visibleUsers = useMemo(() => {
    const base = filter === 'all' ? visiblePool : visiblePool.filter((u) => u.status === filter)
    const q = searchTerm.trim().toLowerCase()
    const filteredByQuery =
      q.length === 0
        ? base
        : base.filter((u) => {
            if (searchKey === 'telegramId') return `${u.telegramId}`.startsWith(q)
            if (searchKey === 'plan') return u.plan.some((p) => p.toLowerCase().startsWith(q))
            return (u.userName || '').toLowerCase().startsWith(q)
          })
    const parseDate = (val?: string) => (val ? Date.parse(val.replace(' ', 'T')) : 0)
    return [...filteredByQuery].sort((a, b) => {
      const aDate = parseDate(a.subscriptionEnd)
      const bDate = parseDate(b.subscriptionEnd)
      const aValue = aDate || (Number(a.planPrice) | 0)
      const bValue = bDate || (Number(b.planPrice) | 0)
      const diff = bValue - aValue
      return sortOrder === 'desc' ? diff : -diff
    })
  }, [filter, sortOrder, visiblePool, searchKey, searchTerm])

  const visiblePayments = useMemo(() => {
    const base =
      paymentFilter === 'all'
        ? data.payments
        : data.payments.filter((p) => p.status === paymentFilter)
    const q = paymentSearchTerm.trim().toLowerCase()
    const filteredByQuery =
      q.length === 0
        ? base
        : base.filter((p) => {
            if (paymentSearchKey === 'telegramId') return `${p.telegramId ?? ''}`.startsWith(q)
            if (paymentSearchKey === 'plan') return (p.plan || '').toLowerCase().includes(q)
            if (paymentSearchKey === 'method') return (p.method || '').toLowerCase().includes(q)
            if (paymentSearchKey === 'walletAddress') return (p.walletAddress || '').toLowerCase().includes(q)
            if (paymentSearchKey === 'walletFrom') return (p.walletFrom || '').toLowerCase().includes(q)
            return (p.userName || '').toLowerCase().includes(q)
          })
    const parseDate = (val?: string) => (val ? Date.parse(val.replace(' ', 'T')) : 0)
    return [...filteredByQuery].sort((a, b) => {
      const aDate = parseDate(a.paidAt)
      const bDate = parseDate(b.paidAt)
      const aVal = aDate || (Number(a.amount) | 0)
      const bVal = bDate || (Number(b.amount) | 0)
      const diff = bVal - aVal
      return paymentSortOrder === 'desc' ? diff : -diff
    })
  }, [data.payments, paymentFilter, paymentSearchKey, paymentSearchTerm, paymentSortOrder])

  const totals = useMemo(() => {
    // totalling по всем пользователям (включая админов), админов скрываем только в таблицах
    const pool = data.users
    const active = pool.filter((u) => u.status === 'active' || u.status === 'expiring').length
    const expiring = pool.filter((u) => u.status === 'expiring').length
    const expired = pool.filter((u) => u.status === 'expired').length
    const now = new Date()
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
    const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 1)
    const revenueMonthFallback = data.payments
      .filter((p) => p.status === 'paid')
      .reduce((acc, p) => {
        const paidAt = parseDateValue(p.paidAt)
        if (!paidAt || paidAt < monthStart || paidAt >= monthEnd) return acc
        return acc + (Number(p.amount) | 0)
      }, 0)
    const revenueFromServer = Number(data.stats?.revenueMonth)
    const hasServerRevenue = Number.isFinite(revenueFromServer)
    const revenueMonth = hasServerRevenue ? revenueFromServer : revenueMonthFallback
    return { active, expiring, expired, revenueMonth }
  }, [data.users, data.payments, data.stats])

  const totalPages = Math.max(1, Math.ceil(visibleUsers.length / PAGE_SIZE))
  const paginatedUsers = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE
    return visibleUsers.slice(start, start + PAGE_SIZE)
  }, [page, visibleUsers])

  useEffect(() => {
    setPage((p) => Math.min(p, totalPages))
  }, [totalPages])

  const paymentTotalPages = Math.max(1, Math.ceil(visiblePayments.length / PAGE_SIZE))
  const paginatedPayments = useMemo(() => {
    const start = (paymentPage - 1) * PAGE_SIZE
    return visiblePayments.slice(start, start + PAGE_SIZE)
  }, [paymentPage, visiblePayments])

  useEffect(() => {
    setPaymentPage((p) => Math.min(p, paymentTotalPages))
  }, [paymentTotalPages])

  const channelStats = useMemo<ChannelStats[]>(
    () =>
      data.channels.map((ch) => {
        const members = toPositiveInt(ch.members)
        const hasBreakdown = [
          ch.planTotal,
          ch.planActive,
          ch.planActiveStrict,
          ch.planExpiring,
          ch.planExpired,
        ].some((value) => value !== undefined && value !== null)
        const planTotal = toPositiveInt(ch.planTotal ?? members)
        const planActive = toPositiveInt(ch.planActive ?? members)
        const planActiveStrict = toPositiveInt(ch.planActiveStrict ?? planActive ?? members)
        const planExpiring = toPositiveInt(
          ch.planExpiring ??
            (hasBreakdown ? Math.max(0, planActive - planActiveStrict) : 0),
        )
        const planExpired = toPositiveInt(
          ch.planExpired ?? (hasBreakdown ? Math.max(0, planTotal - planActive) : 0),
        )
        return {
          name: ch.name,
          members,
          planTotal,
          planActive,
          planActiveStrict,
          planExpiring,
          planExpired,
          hasBreakdown,
        }
      }),
    [data.channels],
  )

  const locked = auth.lockedUntil > Date.now()

  const handleLogin = (e: FormEvent) => {
    e.preventDefault()
    if (locked) {
      setAuthError(`Слишком много попыток. Подождите ${Math.ceil((auth.lockedUntil - Date.now()) / 1000)} сек.`)
      return
    }
    if (loginInput === AUTH_USER && passInput === AUTH_PASS) {
      const next = { authed: true, attemptsLeft: MAX_ATTEMPTS, lockedUntil: 0 }
      setAuth(next)
      localStorage.setItem('dashboard_auth', JSON.stringify(next))
      setAuthError(null)
      return
    }
    const nextAttempts = auth.attemptsLeft - 1
    if (nextAttempts <= 0) {
      const next: AuthState = { authed: false, attemptsLeft: MAX_ATTEMPTS, lockedUntil: Date.now() + LOCK_MS }
      setAuth(next)
      localStorage.setItem('dashboard_auth', JSON.stringify(next))
      setAuthError(`Слишком много попыток. Вход закрыт на ${LOCK_MS / 1000} сек.`)
    } else {
      const next: AuthState = { authed: false, attemptsLeft: nextAttempts, lockedUntil: 0 }
      setAuth(next)
      localStorage.setItem('dashboard_auth', JSON.stringify(next))
      setAuthError(`Неверно. Осталось попыток: ${nextAttempts}`)
    }
  }

  const handleLogout = () => {
    const next = { authed: false, attemptsLeft: MAX_ATTEMPTS, lockedUntil: 0 }
    setAuth(next)
    localStorage.setItem('dashboard_auth', JSON.stringify(next))
    setLoginInput('')
    setPassInput('')
    setData(fallbackData)
    setLoadError(null)
    setLoading(false)
  }

  const pageButtons = useMemo(() => {
    const targets = [1, page - 10, page - 5, page, page + 5, page + 10, totalPages]
    return Array.from(
      new Map(
        targets
          .filter((p) => p >= 1 && p <= totalPages)
          .sort((a, b) => a - b)
          .map((p) => [p, p]),
      ).values(),
    )
  }, [page, totalPages])

  const paymentPageButtons = useMemo(() => {
    const targets = [
      1,
      paymentPage - 10,
      paymentPage - 5,
      paymentPage,
      paymentPage + 5,
      paymentPage + 10,
      paymentTotalPages,
    ]
    return Array.from(
      new Map(
        targets
          .filter((p) => p >= 1 && p <= paymentTotalPages)
          .sort((a, b) => a - b)
          .map((p) => [p, p]),
      ).values(),
    )
  }, [paymentPage, paymentTotalPages])

  if (!auth.authed) {
    return (
      <div className="auth-screen">
        <div className="auth-card">
          <h2>Вход</h2>
          <form className="auth-form" onSubmit={handleLogin}>
            <input
              className="input"
              placeholder="Логин"
              value={loginInput}
              onChange={(e) => setLoginInput(e.target.value)}
              autoComplete="username"
            />
            <input
              className="input"
              type="password"
              placeholder="Пароль"
              value={passInput}
              onChange={(e) => setPassInput(e.target.value)}
              autoComplete="current-password"
            />
            <button className="btn active" type="submit" disabled={locked}>
              Войти
            </button>
          </form>
          {authError && <p className="error">{authError}</p>}
          {locked && (
            <p className="muted">
              Вход временно ограничен. Подождите {Math.ceil((auth.lockedUntil - Date.now()) / 1000)} сек.
            </p>
          )}
        </div>
      </div>
    )
  }

  const tabs: { id: TabId; label: string }[] = [
    { id: 'overview', label: 'Обзор' },
    { id: 'payments', label: 'История оплат' },
    { id: 'stats', label: 'Статистика' },
  ]

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <p className="eyebrow">REFUNDER TEAM</p>
          <h1>Панель подписок и оплат</h1>
        </div>
        <div className="tabbar">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={activeTab === tab.id ? 'btn active' : 'btn ghost'}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
          <button className="btn ghost" onClick={handleLogout}>
            Выйти
          </button>
        </div>
      </header>

      {loading && <p className="muted">Обновляем данные...</p>}
      {loadError && <p className="error">Не удалось загрузить: {loadError}</p>}

      {activeTab === 'overview' && (
        <>
          <section className="grid">
            <SummaryCard title="Активные подписки" value={`${totals.active}`} sub="по текущим данным" />
            <SummaryCard title="Заканчиваются скоро" value={`${totals.expiring}`} />
            <SummaryCard title="Просрочены" value={`${totals.expired}`} />
            <SummaryCard title="Оплачено за месяц" value={formatMoney(Number(totals.revenueMonth) | 0)} />
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Каналы и аудитория</h2>
              </div>
            </div>
            <div className="channel-grid">
              {channelStats.map((ch) => (
                <div key={ch.name} className="card channel-card">
                  <div className="channel-title">{ch.name}</div>
                  <div className="channel-count">{ch.hasBreakdown ? ch.planActive : ch.members}</div>
                  <div className="channel-meta muted">
                    {ch.hasBreakdown ? 'активных' : 'участников'}
                  </div>
                  {ch.hasBreakdown && (
                    <div className="channel-breakdown muted">
                      <span>Активные: {ch.planActiveStrict}</span>
                      <span>На подходе: {ch.planExpiring}</span>
                      <span>Истекло: {ch.planExpired}</span>
                      <span>Всего: {ch.planTotal}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      {activeTab === 'payments' && (
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>История оплат</h2>
            </div>
          </div>

          <div className="controls">
            <div className="control-group">
              <span className="muted">Фильтр по статусу:</span>
              <div className="control-buttons">
                {(['all', 'paid', 'pending', 'timeout', 'canceled'] as const).map((key) => (
                  <button
                    key={key}
                    className={paymentFilter === key ? 'btn active' : 'btn ghost'}
                    onClick={() => setPaymentFilter(key as PaymentStatus | 'all')}
                  >
                    {key === 'all' ? 'Все' : paymentChip[key as PaymentStatus]}
                  </button>
                ))}
              </div>
            </div>

            <div className="control-group">
              <span className="muted">Сортировка:</span>
              <div className="control-buttons">
                <button
                  className={paymentSortOrder === 'desc' ? 'btn active' : 'btn ghost'}
                  onClick={() => setPaymentSortOrder('desc')}
                >
                  Сначала новые
                </button>
                <button
                  className={paymentSortOrder === 'asc' ? 'btn active' : 'btn ghost'}
                  onClick={() => setPaymentSortOrder('asc')}
                >
                  Сначала старые
                </button>
              </div>
            </div>

            <div className="control-group">
              <span className="muted">Поиск:</span>
              <select
                className="input"
                value={paymentSearchKey}
                onChange={(e) => setPaymentSearchKey(e.target.value as PaymentSearchKey)}
              >
                <option value="userName">Username</option>
                <option value="telegramId">Telegram ID</option>
                <option value="plan">План</option>
                <option value="method">Метод</option>
                <option value="walletAddress">Кошелек (куда)</option>
                <option value="walletFrom">Кошелек (откуда)</option>
              </select>
              <input
                className="input"
                type="text"
                placeholder="Введи значение..."
                value={paymentSearchTerm}
                onChange={(e) => setPaymentSearchTerm(e.target.value)}
              />
            </div>
          </div>

          <div className="pagination">
            <button
              className="btn ghost"
              disabled={paymentPage === 1}
              onClick={() => setPaymentPage((p) => Math.max(1, p - 1))}
            >
              Назад
            </button>
            {paymentPageButtons.map((pNum) => (
              <button
                key={pNum}
                className={paymentPage === pNum ? 'btn active' : 'btn ghost'}
                onClick={() => setPaymentPage(pNum)}
              >
                {pNum}
              </button>
            ))}
            <button
              className="btn ghost"
              disabled={paymentPage === paymentTotalPages}
              onClick={() => setPaymentPage((p) => Math.min(paymentTotalPages, p + 1))}
            >
              Вперед
            </button>
          </div>

          <div className="table">
            <div className="table-head">
              <span>Плательщик</span>
              <span>План / Метод</span>
              <span>Кошелек</span>
              <span>Статус</span>
              <span>Сумма / Дата</span>
            </div>
            {paginatedPayments.map((p) => (
              <PaymentTableRow key={p.id ?? `${p.userName}-${p.plan}`} payment={p} />
            ))}
          </div>
        </section>
      )}

      {activeTab === 'stats' && (
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Пользователи</h2>
            </div>
          </div>

          <div className="controls">
            <div className="control-group">
              <span className="muted">Фильтр статуса:</span>
              <div className="control-buttons">
                {['all', 'active', 'expiring', 'expired'].map((key) => (
                  <button
                    key={key}
                    className={filter === key ? 'btn active' : 'btn ghost'}
                    onClick={() => setFilter(key as UserStatus | 'all')}
                  >
                    {key === 'all' ? 'Все' : statusChip[key as UserStatus]}
                  </button>
                ))}
              </div>
            </div>

            <div className="control-group">
              <span className="muted">Сортировка:</span>
              <div className="control-buttons">
                <button
                  className={sortOrder === 'desc' ? 'btn active' : 'btn ghost'}
                  onClick={() => setSortOrder('desc')}
                >
                  По убыванию
                </button>
                <button
                  className={sortOrder === 'asc' ? 'btn active' : 'btn ghost'}
                  onClick={() => setSortOrder('asc')}
                >
                  По возрастанию
                </button>
              </div>
            </div>

            <div className="control-group">
              <span className="muted">Поиск:</span>
              <select className="input" value={searchKey} onChange={(e) => setSearchKey(e.target.value as SearchKey)}>
                <option value="userName">Username</option>
                <option value="telegramId">Telegram ID</option>
                <option value="plan">План</option>
              </select>
              <input
                className="input"
                type="text"
                placeholder="Введи значение..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>

          <div className="pagination">
            <button
              className="btn ghost"
              disabled={page === 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Назад
            </button>
            {pageButtons.map((pNum) => (
              <button
                key={pNum}
                className={page === pNum ? 'btn active' : 'btn ghost'}
                onClick={() => setPage(pNum)}
              >
                {pNum}
              </button>
            ))}
            <button
              className="btn ghost"
              disabled={page === totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Вперед
            </button>
          </div>

          <div className="table">
            <div className="table-head">
              <span>ID</span>
              <span>Планы</span>
              <span>Статус</span>
              <span>Окончание</span>
            </div>
            {paginatedUsers.map((u) => (
              <UserRow key={u.telegramId} user={u} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
