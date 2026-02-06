export type MockUser = {
  telegramId: number
  userName: string
  firstName?: string | null
  plan: string[]
  subscriptionEnd?: string
  status: 'active' | 'expiring' | 'expired'
  jobTitle: string
  planPrice?: number
}

export type MockPayment = {
  id: number
  userName: string
  amount: number
  status: 'paid' | 'pending' | 'timeout' | 'canceled'
  paidAt?: string
  plan?: string
  method: 'cryptobot' | 'usdt_trc20'
}

export type MockChannel = {
  name: string
  members?: number
  planTotal?: number
  planActive?: number
  planActiveStrict?: number
  planExpiring?: number
  planExpired?: number
}

export const users: MockUser[] = [
  {
    telegramId: 6765303097,
    userName: 'reserve_admin',
    plan: ['Резервний'],
    status: 'active',
    subscriptionEnd: '2026-03-01T14:46:27Z',
    jobTitle: 'admin',
    planPrice: 0,
  },
  {
    telegramId: 759611073,
    userName: 'quick_hustle',
    firstName: 'Ivan',
    plan: ['«REFUNDER» TEAM NEWS', 'QUICK HUSTLE', 'STRONG HUSTLE'],
    status: 'expiring',
    subscriptionEnd: '2025-12-01T23:59:00Z',
    jobTitle: 'user',
    planPrice: 120,
  },
  {
    telegramId: 982253790,
    userName: 'prime_runner',
    plan: ['«REFUNDER» TEAM NEWS', 'QUICK HUSTLE', 'STRONG HUSTLE', 'PRIME HUSTLE'],
    status: 'active',
    subscriptionEnd: '2026-03-01T23:59:00Z',
    jobTitle: 'user',
    planPrice: 250,
  },
  {
    telegramId: 6640133766,
    userName: 'dna_tp',
    plan: ['DNA TEAM TEST'],
    status: 'expired',
    subscriptionEnd: '2025-12-08T00:00:00Z',
    jobTitle: 'tp',
  },
  {
    telegramId: 645272210,
    userName: 'holiday_pack',
    plan: ['«REFUNDER» TEAM NEWS', 'QUICK HUSTLE', 'STRONG HUSTLE'],
    status: 'expiring',
    subscriptionEnd: '2026-01-01T23:59:00Z',
    jobTitle: 'user',
    planPrice: 180,
  },
  {
    telegramId: 1129717880,
    userName: 'full_stack_sub',
    plan: ['«REFUNDER» TEAM NEWS', 'QUICK HUSTLE', 'STRONG HUSTLE', 'PRIME HUSTLE'],
    status: 'active',
    subscriptionEnd: '2026-01-03T23:59:00Z',
    jobTitle: 'user',
    planPrice: 250,
  },
  {
    telegramId: 1649429208,
    userName: 'qg_member',
    plan: ['«REFUNDER» TEAM NEWS', 'QUICK HUSTLE', 'STRONG HUSTLE'],
    status: 'expired',
    subscriptionEnd: '2025-12-08T00:00:00Z',
    jobTitle: 'user',
  },
  {
    telegramId: 983498724,
    userName: 'fastlane',
    plan: ['«REFUNDER» TEAM NEWS', 'QUICK HUSTLE'],
    status: 'expiring',
    subscriptionEnd: '2025-12-08T00:00:00Z',
    jobTitle: 'user',
    planPrice: 80,
  },
  {
    telegramId: 578508295,
    userName: 'crypto_rider',
    plan: ['«REFUNDER» TEAM NEWS', 'QUICK HUSTLE'],
    status: 'active',
    subscriptionEnd: '2026-03-08T00:00:00Z',
    jobTitle: 'user',
    planPrice: 80,
  },
  {
    telegramId: 674900001,
    userName: 'manual_add',
    plan: ['QUICK HUSTLE'],
    status: 'expired',
    subscriptionEnd: '2025-11-28T15:49:52Z',
    jobTitle: 'tp',
  },
]

export const payments: MockPayment[] = [
  {
    id: 1,
    userName: 'prime_runner',
    amount: 250,
    status: 'paid',
    paidAt: '2025-11-25T08:35:00Z',
    plan: 'PRIME HUSTLE',
    method: 'cryptobot',
  },
  {
    id: 2,
    userName: 'quick_hustle',
    amount: 135,
    status: 'paid',
    paidAt: '2025-11-26T10:12:00Z',
    plan: 'THREE MONTHS',
    method: 'usdt_trc20',
  },
  {
    id: 3,
    userName: 'full_stack_sub',
    amount: 50,
    status: 'pending',
    plan: 'one_month',
    method: 'cryptobot',
  },
  {
    id: 4,
    userName: 'dna_tp',
    amount: 50,
    status: 'timeout',
    plan: 'QUICK HUSTLE',
    method: 'usdt_trc20',
  },
  {
    id: 5,
    userName: 'crypto_rider',
    amount: 80,
    status: 'paid',
    paidAt: '2025-11-27T09:40:00Z',
    plan: 'QUICK HUSTLE',
    method: 'usdt_trc20',
  },
]

export const channels: MockChannel[] = [
  {
    name: '«REFUNDER» TEAM NEWS',
    members: 42,
    planTotal: 48,
    planActive: 42,
    planActiveStrict: 30,
    planExpiring: 12,
    planExpired: 6,
  },
  {
    name: 'QUICK HUSTLE',
    members: 38,
    planTotal: 46,
    planActive: 38,
    planActiveStrict: 28,
    planExpiring: 10,
    planExpired: 8,
  },
  {
    name: 'STRONG HUSTLE',
    members: 32,
    planTotal: 38,
    planActive: 32,
    planActiveStrict: 24,
    planExpiring: 8,
    planExpired: 6,
  },
  {
    name: 'PRIME HUSTLE',
    members: 18,
    planTotal: 22,
    planActive: 18,
    planActiveStrict: 14,
    planExpiring: 4,
    planExpired: 4,
  },
  {
    name: 'DNA TEAM TEST',
    members: 6,
    planTotal: 9,
    planActive: 6,
    planActiveStrict: 4,
    planExpiring: 2,
    planExpired: 3,
  },
  {
    name: 'Резервний',
    members: 4,
    planTotal: 5,
    planActive: 4,
    planActiveStrict: 3,
    planExpiring: 1,
    planExpired: 1,
  },
]
