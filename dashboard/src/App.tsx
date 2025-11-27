import { useMemo, useState } from 'react'
import { channels as mockChannels, payments as mockPayments, users as mockUsers, type MockChannel, type MockPayment, type MockUser } from './data/mockData'
import runtimeData from './data/runtimeData.json'

type UserStatus = 'active' | 'expiring' | 'expired'

const statusChip: Record<UserStatus, string> = {
  active: 'Активна',
  expiring: 'Скоро закінчиться',
  expired: 'Неактивна',
}

function formatDate(value?: string) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function formatMoney(value: number) {
  return new Intl.NumberFormat('uk-UA', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
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

function ProgressBar({ label, value, total }: { label: string; value: number; total: number }) {
  const pct = total === 0 ? 0 : Math.round((value / total) * 100)
  return (
    <div className="bar-row">
      <div className="bar-label">
        <span>{label}</span>
        <span className="muted">{value} корист.</span>
      </div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${pct}%` }}>
          <span>{pct}%</span>
        </div>
      </div>
    </div>
  )
}

function PaymentRow({
  amount,
  status,
  paidAt,
  plan,
  method,
  userName,
}: {
  amount: number
  status: string
  paidAt?: string
  plan?: string
  method: string
  userName: string
}) {
  const label =
    status === 'paid'
      ? 'Оплачено'
      : status === 'pending'
        ? 'Очікує'
        : status === 'timeout'
          ? 'Не знайдено'
          : 'Скасовано'
  return (
    <div className="timeline-item">
      <div>
        <div className="timeline-title">
          {userName} — {plan || 'Без плану'}
        </div>
        <div className="timeline-meta">
          <span className="pill">{label}</span>
          <span className="muted">{method}</span>
          <span className="muted">{paidAt ? new Date(paidAt).toLocaleString('uk-UA') : '—'}</span>
        </div>
      </div>
      <div className="timeline-amount">{formatMoney(amount)}</div>
    </div>
  )
}

type DataShape = {
  users: MockUser[]
  payments: MockPayment[]
  channels: MockChannel[]
}

const runtime = runtimeData as DataShape
const hasRuntime = Array.isArray(runtime?.users) && runtime.users.length > 0
const dataSource: DataShape = hasRuntime
  ? runtime
  : {
      users: mockUsers,
      payments: mockPayments,
      channels: mockChannels,
    }

export default function App() {
  const [filter, setFilter] = useState<UserStatus | 'all'>('all')

  const filteredUsers = useMemo(() => {
    if (filter === 'all') return dataSource.users
    return dataSource.users.filter((u) => u.status === filter)
  }, [filter])

  const totals = useMemo(() => {
    const active = dataSource.users.filter((u) => u.status === 'active').length
    const expiring = dataSource.users.filter((u) => u.status === 'expiring').length
    const expired = dataSource.users.filter((u) => u.status === 'expired').length
    const mrr = dataSource.users
      .filter((u) => u.status !== 'expired')
      .reduce((acc, u) => acc + (u.planPrice ?? 0), 0)
    const revenue30d = dataSource.payments
      .filter((p) => p.status === 'paid')
      .reduce((acc, p) => acc + p.amount, 0)
    return { active, expiring, expired, mrr, revenue30d }
  }, [])

  const totalUsers = dataSource.users.length

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <p className="eyebrow">REFUNDER TEAM</p>
          <h1>Аналітика доступів та оплат</h1>
          <p className="muted">Мок-дані з поточної SQLite. API підключимо окремо.</p>
        </div>
        <div className="filter">
          {['all', 'active', 'expiring', 'expired'].map((key) => (
            <button
              key={key}
              className={filter === key ? 'btn active' : 'btn ghost'}
              onClick={() => setFilter(key as UserStatus | 'all')}
            >
              {key === 'all' ? 'Всі' : statusChip[key as UserStatus]}
            </button>
          ))}
        </div>
      </header>

      <section className="grid">
        <SummaryCard title="Активні зараз" value={`${totals.active}`} sub="користувачів" />
        <SummaryCard title="Закінчуються ≤7 днів" value={`${totals.expiring}`} />
        <SummaryCard title="Вимкнено" value={`${totals.expired}`} />
        <SummaryCard title="Очікуваний MRR" value={formatMoney(totals.mrr)} sub="без урахування скидок" />
        <SummaryCard title="Оплати за 30 днів" value={formatMoney(totals.revenue30d)} />
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Розподіл по каналах</h2>
            <p className="muted">Маємо {dataSource.channels.length} каналів, сумарно {totalUsers} користувачів</p>
          </div>
        </div>
        <div className="bars">
          {dataSource.channels.map((ch) => (
            <ProgressBar key={ch.name} label={ch.name} value={ch.members} total={totalUsers} />
          ))}
        </div>
      </section>

      <section className="panel two-columns">
        <div className="panel-block">
          <div className="panel-head">
            <div>
              <h2>Останні оплати</h2>
              <p className="muted">CryptoBot та USDT TRC-20</p>
            </div>
          </div>
          <div className="timeline">
            {dataSource.payments.map((p) => (
              <PaymentRow
                key={p.id}
                amount={p.amount}
                status={p.status}
                paidAt={p.paidAt}
                plan={p.plan}
                method={p.method}
                userName={p.userName}
              />
            ))}
          </div>
        </div>

        <div className="panel-block">
          <div className="panel-head">
            <div>
              <h2>Користувачі</h2>
              <p className="muted">Фільтр: {filter === 'all' ? 'всі' : statusChip[filter]}</p>
            </div>
          </div>
          <div className="table">
            <div className="table-head">
              <span>ID</span>
              <span>План</span>
              <span>Статус</span>
              <span>До</span>
            </div>
            {filteredUsers.map((u) => (
              <div className="table-row" key={u.telegramId}>
                <div>
                  <div className="strong">@{u.userName || 'no_username'}</div>
                  <div className="muted">{u.telegramId}</div>
                </div>
                <div>
                  <div>{u.plan.join(', ')}</div>
                  <div className="muted">{u.jobTitle}</div>
                </div>
                <div>
                  <span className={`pill pill-${u.status}`}>{statusChip[u.status]}</span>
                </div>
                <div>{formatDate(u.subscriptionEnd)}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
