import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const timestamp = '2026-10-24T12:00:00Z'
const snapshotTimestamp = '2026-10-19T09:00:00Z'
const managerId = '11111111-1111-4111-8111-111111111111'
const modelFeatures = [
  { id: 'prolong_wait', name: 'Ожидает оплаты (prolong_wait)', weight: 0.4 },
  { id: 'autoprolong_off', name: 'Автопродление выключено', weight: 0.3 },
  { id: 'insufficient_balance', name: 'Баланс ниже стоимости продления', weight: 0.2 },
  { id: 'replenishment_drop', name: 'Падение активности пополнений', weight: 0.1 },
]

function mergeSettings(base: Record<string, unknown>, patch: Record<string, unknown>): Record<string, unknown> {
  const merged = { ...base }
  for (const [key, value] of Object.entries(patch)) {
    const previous = merged[key]
    merged[key] = value && typeof value === 'object' && !Array.isArray(value) && previous && typeof previous === 'object' && !Array.isArray(previous)
      ? mergeSettings(previous as Record<string, unknown>, value as Record<string, unknown>)
      : value
  }
  return merged
}

async function setupApi(page: Page, role: 'admin' | 'manager' = 'admin', loggedIn = true) {
  const state = {
    loggedIn, version: 1, summaryCalls: 0, customerCalls: 0, cardCalls: 0,
    refreshCalls: 0, expireMe: false, failCustomers: false, expireCustomers: false,
    refreshFailure: null as 'network' | 429 | 500 | null,
    expireSettingsPatch: false,
    loginFailure: null as 401 | 429 | null,
    customerFailure: null as 403 | 'network' | null,
    snapshotError: null as Record<string, unknown> | null,
    asOf: snapshotTimestamp as string | null,
    lossExplanation: 'Ожидаемые потери с учётом вероятности оттока и покрытия балансом',
    onSettingsSaved: null as (() => void) | null,
    settings: { asOf: null } as Record<string, unknown>,
    cardCalculatedAt: timestamp as string | null,
    cardServices: [{ id: 1, name: 'VPS Test', status: 'active', price: 1299, autoProlong: false, paymentTerm: 'week', createdAt: timestamp, expiresAt: timestamp }],
    managers: [{ id: managerId, login: 'manager1', email: 'manager1@example.com', role: 'manager', createdAt: timestamp }],
    requests: [] as { path: string; method: string; body: unknown }[],
    customers: Array.from({ length: 55 }, (_, index) => ({
      id: index + 1, email: `client${String(index + 1).padStart(3, '0')}@example.com`,
      balance: 12345 + index, totalReplenished: 54321 + index,
      riskScore: index === 0 ? null : 100 - index,
      level: index === 0 ? 'no_data' : index < 10 ? 'high' : index < 30 ? 'medium' : 'low',
      expectedLossCents: index === 0 ? 0 : 1250, reasonShort: 'Проверьте автопродление',
    })),
  }

  await page.addInitScript(() => {
    class TestEventSource extends EventTarget {
      static CLOSED = 2
      static CONNECTING = 0
      static OPEN = 1
      readyState = 1
      onerror: (() => void) | null = null
      url: string
      withCredentials: boolean
      constructor(url: string, options: EventSourceInit = {}) {
        super()
        this.url = url
        this.withCredentials = !!options.withCredentials
        const streams = (window as unknown as { streams: TestEventSource[] }).streams
        streams.push(this)
      }
      close() { this.readyState = 2 }
    }
    Object.assign(window, { streams: [], EventSource: TestEventSource, sessionExpirations: 0 })
    window.addEventListener('session-expired', () => {
      (window as unknown as { sessionExpirations: number }).sessionExpirations++
    })
  })

  await page.route('**/api/v1/**', async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const path = url.pathname.replace('/api/v1', '')
    const method = req.method()
    const body = req.postData() ? req.postDataJSON() : null
    state.requests.push({ path, method, body })
    const respond = (json: unknown, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: status === 204 ? undefined : JSON.stringify(json),
      headers: { 'access-control-allow-origin': 'http://127.0.0.1:5174', 'access-control-allow-credentials': 'true' },
    })
    if (method === 'OPTIONS') return respond(null, 204)
    if (path === '/auth/login') {
      if (state.loginFailure) return respond({ detail: state.loginFailure === 429 ? 'Rate limit exceeded' : 'Неверный логин или пароль' }, state.loginFailure)
      state.loggedIn = true; return respond({ message: 'OK' })
    }
    if (path === '/auth/logout') { state.loggedIn = false; return respond({ message: 'OK' }) }
    if (path === '/auth/refresh') {
      state.refreshCalls++
      if (state.refreshFailure === 'network') return route.abort('failed')
      if (state.refreshFailure !== null) return respond({ detail: 'Обновление сессии временно недоступно' }, state.refreshFailure)
      return respond(state.loggedIn ? { status: 'OK' } : { detail: 'Сессия истекла' }, state.loggedIn ? 200 : 401)
    }
    if (!state.loggedIn) return respond({ detail: 'Нужен вход' }, 401)
    if (path === '/auth/me') {
      if (state.expireMe) { state.expireMe = false; return respond({ detail: 'Access expired' }, 401) }
      return respond({ login: role, email: null, role })
    }
    if (path === '/analytics/summary') {
      state.summaryCalls++
      const byLevel = Object.fromEntries(['high', 'medium', 'low', 'no_data'].map((level) => {
        const items = state.customers.filter((customer) => customer.level === level)
        return [level === 'no_data' ? 'noData' : level, { customers: items.length, expectedLossCents: items.reduce((sum, customer) => sum + customer.expectedLossCents, 0) }]
      }))
      return respond({ customersTotal: state.customers.length, byLevel, expectedLossCents: state.customers.reduce((sum, customer) => sum + customer.expectedLossCents, 0), lossExplanation: state.lossExplanation, asOf: state.asOf, recalculatedAt: timestamp, version: state.version })
    }
    if (path === '/customers') {
      state.customerCalls++
      if (state.expireCustomers) return respond({ detail: 'Access expired' }, 401)
      if (state.customerFailure === 'network') return route.abort('failed')
      if (state.customerFailure === 403) return respond({ detail: 'Forbidden' }, 403)
      if (state.failCustomers) return respond({ detail: 'Временная ошибка' }, 500)
      const params = url.searchParams
      const search = params.get('search') ?? ''
      let items = state.customers.filter((customer) => (!params.get('level') || customer.level === params.get('level')) && (!search || customer.email.includes(search) || String(customer.id) === search))
      const field = (params.get('sort') ?? 'riskScore') as keyof typeof items[number]
      items = [...items].sort((a, b) => {
        const left = a[field], right = b[field]
        if (left === null) return 1
        if (right === null) return -1
        const order = params.get('order') === 'asc' ? 1 : -1
        return order * (typeof left === 'string' ? left.localeCompare(String(right)) : Number(left) - Number(right))
      })
      const pageNumber = Number(params.get('page') ?? 1), pageSize = Number(params.get('pageSize') ?? 50)
      return respond({ items: items.slice((pageNumber - 1) * pageSize, pageNumber * pageSize), total: items.length, page: pageNumber, pageSize })
    }
    if (path.startsWith('/customers/')) {
      state.cardCalls++
      const customer = state.customers.find((item) => item.id === Number(path.split('/').at(-1)))
      if (!customer) return respond({ detail: 'Клиент не найден' }, 404)
      return respond({ ...customer, withdrawBalance: 0, bonusBalance: 0, bonusState: 'unlocked',
        reasons: customer.level === 'no_data'
          ? [{ code: 'model_not_connected', text: 'Модель анализа ещё не подключена' }]
          : [{ code: 'auto_prolong', text: customer.reasonShort }], details: {},
        services: state.cardServices,
        transactions: { total: 5, performed: 3, notPerformed: 2 }, asOf: timestamp, calculatedAt: state.cardCalculatedAt,
      })
    }
    if (path === '/model/settings') {
      if (method === 'PATCH' && state.expireSettingsPatch) return respond({ detail: 'Access expired' }, 401)
      if (method === 'PATCH') { state.settings = mergeSettings(state.settings, body); state.version++; state.onSettingsSaved?.() }
      return respond({ settings: state.settings, defaults: { asOf: null }, updatedAt: timestamp, version: state.version })
    }
    if (path === '/source/snapshot') {
      if (state.snapshotError) return respond(state.snapshotError, 422)
      state.version++
      return respond({ accounts: body.accounts.length, services: body.services.length, transactions: body.transactions.length, version: state.version, recalculatedAt: timestamp })
    }
    if (path === '/users' && method === 'GET') return respond(state.managers)
    if (path === '/users' && method === 'POST') {
      const created = { id: '22222222-2222-4222-8222-222222222222', login: body.login, email: body.email, role: 'manager', createdAt: timestamp }
      state.managers.push(created)
      return respond(created, 201)
    }
    if (path.startsWith('/users/') && method === 'PATCH') {
      const manager = state.managers.find((item) => path.endsWith(item.id))!
      if (typeof body.login === 'string') manager.login = body.login
      if (typeof body.email === 'string') manager.email = body.email
      return respond(manager)
    }
    if (path.startsWith('/users/') && method === 'DELETE') {
      state.managers = state.managers.filter((item) => !path.endsWith(item.id))
      return respond(null, 204)
    }
    throw new Error(`Unexpected API request: ${method} ${path}`)
  })
  return state
}

async function emit(page: Page, type = 'recalculated', id = '2') {
  await page.evaluate(({ type, id }) => {
    const streams = (window as unknown as { streams: EventSource[] }).streams
    const active = streams.filter((stream) => stream.readyState !== 2).at(-1)!
    active.dispatchEvent(new MessageEvent(type, { lastEventId: id, data: JSON.stringify({ version: Number(id) }) }))
  }, { type, id })
}

test('login uses login payload, restores an expired access token, and logs out', async ({ page }) => {
  const api = await setupApi(page, 'admin', false)
  await page.goto('/login')
  await page.getByLabel('Логин', { exact: true }).fill('admin')
  await page.getByLabel('Пароль', { exact: true }).fill('password123')
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Обзор рисков оттока' })).toBeVisible()
  expect(api.requests.find((req) => req.path === '/auth/login')?.body).toEqual({ login: 'admin', password: 'password123' })
  api.expireMe = true
  const previousRefresh = api.refreshCalls
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Обзор рисков оттока' })).toBeVisible()
  expect(api.refreshCalls).toBe(previousRefresh + 1)
  await page.getByRole('button', { name: 'Выйти', exact: true }).click()
  await expect(page).toHaveURL(/\/login$/)
  expect(api.requests.some((req) => req.path === '/auth/logout' && req.method === 'POST')).toBe(true)
  expect(await page.evaluate(() => (window as unknown as { streams: EventSource[] }).streams.filter((stream) => stream.readyState !== 2).length)).toBe(0)
})

test('dashboard uses the API summary, converts cents and updates over SSE', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/')
  await expect(page.locator('.total-value')).toHaveText('55')
  await expect(page.locator('.revenue-value')).toHaveText('€675,00')
  await expect(page.locator('.account-summary').getByText('нет оценки: 1', { exact: true })).toBeVisible()
  await expect(page.locator('.dashboard-loss-explanation')).toHaveText(api.lossExplanation)
  const asOf = await page.evaluate((value) => new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)), snapshotTimestamp)
  await expect(page.locator('.dashboard-as-of')).toHaveText(`Данные на: ${asOf}`)
  await expect(page.getByRole('button', { name: /^Открыть клиента/ })).toHaveCount(4)
  await expect.poll(() => page.evaluate(() => (window as unknown as { streams: EventSource[] }).streams.filter((stream) => stream.readyState !== 2).map((stream) => ({ url: stream.url, withCredentials: stream.withCredentials })))).toEqual([{ url: 'http://127.0.0.1:8000/api/v1/events', withCredentials: true }])
  api.customers.pop()
  api.version++
  api.asOf = null
  api.lossExplanation = 'Обновлённая оценка потерь'
  const calls = api.customerCalls
  await emit(page)
  await expect(page.locator('.total-value')).toHaveText('54')
  await expect(page.locator('.dashboard-as-of')).toHaveText('Данные на: —')
  await expect(page.locator('.dashboard-loss-explanation')).toHaveText(api.lossExplanation)
  await expect.poll(() => api.customerCalls).toBeGreaterThan(calls)
  await page.setViewportSize({ width: 375, height: 812 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('customers send both sort directions for every field, page, search and no_data filter', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/app/clients')
  await expect(page.getByRole('link', { name: 'Открыть клиента client002@example.com', exact: true })).toBeVisible()
  const scoredRow = page.getByRole('row').filter({ has: page.getByRole('link', { name: 'Открыть клиента client002@example.com', exact: true }) })
  await expect(scoredRow.locator('.client-table-reason')).toHaveText('Проверьте автопродление')
  await expect(scoredRow.locator('.client-risk-indicator__level')).toHaveText('Высокий')
  await expect(scoredRow.getByRole('img', { name: 'Высокий риск · 99%' })).toBeVisible()
  for (const [title, field] of [['ID', 'id'], ['EMAIL', 'email'], ['БАЛАНС', 'balance'], ['ПОПОЛНЕНИЯ', 'totalReplenished'], ['RISK', 'riskScore']]) {
    for (const order of ['asc', 'desc']) {
      const request = page.waitForRequest((req) => {
        const url = new URL(req.url())
        return url.pathname.endsWith('/customers') && url.searchParams.get('sort') === field && url.searchParams.get('order') === order
      })
      await page.getByRole('columnheader', { name: new RegExp(`^${title}`) }).click()
      await request
      await expect(page.locator('.ant-spin-spinning')).toHaveCount(0)
    }
  }
  const paged = page.waitForRequest((req) => new URL(req.url()).searchParams.get('page') === '2')
  await page.locator('.ant-pagination-item-2').click()
  await paged
  const before = api.customerCalls
  await page.getByRole('button', { name: 'нет оценки', exact: true }).click()
  await expect(page.getByRole('link', { name: 'Открыть клиента client001@example.com', exact: true })).toBeVisible()
  await expect.poll(() => api.customerCalls).toBeGreaterThan(before)
  await expect(page.locator('.client-risk-indicator')).toHaveText('нет оценки')
  await expect(page.getByRole('cell', { name: '€123.45', exact: true })).toBeVisible()
  await page.getByRole('textbox', { name: 'Поиск клиентов' }).fill('absent')
  await expect(page.getByText('Нет клиентов с выбранным уровнем риска')).toBeVisible()
})

test('client filters survive navigation between dashboard, settings and client details', async ({ page }) => {
  await setupApi(page)
  const queries: URLSearchParams[] = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (url.pathname === '/api/v1/customers') queries.push(url.searchParams)
  })
  await page.goto('/app/clients')
  await page.getByRole('button', { name: 'Высокий', exact: true }).click()
  await expect(page.locator('.client-table-link')).toHaveCount(9)
  await page.getByRole('textbox', { name: 'Поиск клиентов' }).fill('client002')
  await expect(page.locator('.client-table-link')).toHaveCount(1)
  await page.getByRole('columnheader', { name: /^EMAIL/ }).click()
  await expect(page.getByRole('columnheader', { name: /^EMAIL/ })).toHaveAttribute('aria-sort', 'ascending')

  async function expectPreserved() {
    await expect(page.getByRole('button', { name: 'Высокий', exact: true })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('textbox', { name: 'Поиск клиентов' })).toHaveValue('client002')
    await expect(page.locator('.client-table-link')).toHaveCount(1)
    await expect(page.getByRole('columnheader', { name: /^EMAIL/ })).toHaveAttribute('aria-sort', 'ascending')
    const query = queries.at(-1)!
    expect(Object.fromEntries(query)).toMatchObject({ level: 'high', search: 'client002', sort: 'email', order: 'asc' })
  }

  await page.getByRole('link', { name: 'Дашборд', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Обзор рисков оттока' })).toBeVisible()
  await page.getByRole('link', { name: 'Клиенты под риском', exact: true }).click()
  await expectPreserved()
  await page.getByRole('link', { name: 'Настройка модели', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Настройка модели', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Клиенты под риском', exact: true }).click()
  await expectPreserved()
  await page.getByRole('link', { name: 'Открыть клиента client002@example.com', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Клиент #2', exact: true })).toBeVisible()
  await page.getByRole('link', { name: '← Все клиенты под риском', exact: true }).click()
  await expectPreserved()
})

test('dashboard risk card opens a filtered list without a StrictMode reset', async ({ page }) => {
  await setupApi(page)
  const levels: (string | null)[] = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (url.pathname === '/api/v1/customers') levels.push(url.searchParams.get('level'))
  })
  await page.goto('/')
  await expect(page.getByRole('button', { name: /^Открыть клиента/ })).toHaveCount(4)
  const start = levels.length
  await page.getByRole('button', { name: /^ВЫСОКИЙ РИСК:/ }).click()
  await expect(page).toHaveURL(/\/app\/clients$/)
  await expect(page.getByRole('button', { name: 'Высокий', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.client-table-link')).toHaveCount(9)
  expect(levels.slice(start).length).toBeGreaterThan(0)
  expect(levels.slice(start).every((level) => level === 'high')).toBe(true)
})

test('customer card restores the activity timeline and refreshes real data over SSE', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/app/clients/1')
  await expect(page.getByRole('heading', { name: 'Клиент #1' })).toBeVisible()
  await expect(page.getByText('Модель анализа ещё не подключена', { exact: true })).toBeVisible()
  await expect(page.locator('.client-profile__risk')).toHaveText('нет оценки')
  await expect(page.locator('.client-profile__stats')).toContainText('€123.45')
  await expect(page.locator('.client-services__price')).toContainText('€12.99 / нед')
  const activity = page.getByRole('region', { name: 'Активность', exact: true })
  await expect(activity.getByRole('listitem')).toHaveCount(2)
  await expect(activity.locator('.client-activity__description')).toHaveText([
    'Обновлена оценка риска клиента', 'Создана услуга «VPS Test»',
  ])
  await expect(activity.locator('.client-activity__item--highlighted')).toHaveCount(1)
  const calls = api.cardCalls
  api.customers[0].balance = 999
  api.cardServices[0].name = 'VPS Updated'
  await emit(page)
  await expect(page.locator('.client-profile__stats')).toContainText('€9.99')
  await expect(activity).toContainText('Создана услуга «VPS Updated»')
  expect(api.cardCalls).toBeGreaterThan(calls)
  await page.goto('/app/clients/999')
  await expect(page.getByRole('main').getByText('Клиент не найден', { exact: true })).toBeVisible()
})

test('activity shows the four latest dated events in the original timeline', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-10-24T18:00:00Z'))
  const api = await setupApi(page)
  const service = api.cardServices[0]
  api.cardServices = [19, 22, 20, 21].map((day) => ({
    ...service, id: day, name: `VPS ${day}`, createdAt: `2026-10-${day}T12:00:00Z`,
  }))
  await page.goto('/app/clients/1')
  const activity = page.getByRole('region', { name: 'Активность', exact: true })
  await expect(activity.locator('.client-activity__description')).toHaveText([
    'Обновлена оценка риска клиента', 'Создана услуга «VPS 22»',
    'Создана услуга «VPS 21»', 'Создана услуга «VPS 20»',
  ])
  await expect(activity.locator('.client-activity__time').first()).toContainText('Сегодня,')
  await expect(activity.locator('.client-activity__time').nth(1)).toHaveText('2 дня назад')
})

test('activity does not invent events when the customer has no activity data', async ({ page }) => {
  const api = await setupApi(page)
  api.cardCalculatedAt = null
  api.cardServices = []
  await page.goto('/app/clients/1')
  const activity = page.getByRole('region', { name: 'Активность', exact: true })
  await expect(activity.getByRole('listitem')).toHaveCount(0)
  await expect(activity).toContainText('Нет событий активности')
})

test('settings sliders load from API, save edits and preserve drafts across SSE', async ({ page }) => {
  const api = await setupApi(page)
  api.settings = { asOf: timestamp, features: structuredClone(modelFeatures), thresholds: { high: 80, medium: 40 }, coefficients: { balance: 0.5 } }
  await page.goto('/app/model-settings')
  const slider = page.getByRole('slider', { name: 'Ожидает оплаты (prolong_wait)', exact: true })
  const weight = page.getByRole('spinbutton', { name: 'Вес: Ожидает оплаты (prolong_wait)', exact: true })
  await expect(slider).toHaveAttribute('aria-valuenow', '0.4')
  await slider.focus()
  await slider.press('ArrowRight')
  await expect(weight).toHaveValue('0.41')
  await weight.fill('0.50')
  await page.getByRole('spinbutton', { name: 'Вес: Автопродление выключено', exact: true }).fill('0.20')
  await page.getByRole('spinbutton', { name: 'Высокий риск, от', exact: true }).fill('85')
  api.settings.asOf = snapshotTimestamp
  await emit(page)
  await expect(slider).toHaveAttribute('aria-valuenow', '0.5')
  await page.getByRole('button', { name: 'СОХРАНИТЬ ИЗМЕНЕНИЯ' }).click()
  await expect(page.getByText('Настройки сохранены, оценки пересчитаны')).toBeVisible()
  expect(api.settings).toEqual({
    asOf: snapshotTimestamp, coefficients: { balance: 0.5 }, thresholds: { high: 85, medium: 40 },
    features: modelFeatures.map((feature, index) => ({ ...feature, weight: [0.5, 0.2, 0.2, 0.1][index] })),
  })
  const patch = api.requests.find((request) => request.path === '/model/settings' && request.method === 'PATCH')!
  expect(patch.body).toEqual({ features: api.settings.features, thresholds: { high: 85 } })
  await page.reload()
  await expect(slider).toHaveAttribute('aria-valuenow', '0.5')
  await expect(page.getByRole('spinbutton', { name: 'Высокий риск, от', exact: true })).toHaveValue('85 баллов')
})

test('settings restore the original slider layout when the API only provides asOf', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/app/model-settings')
  await expect(page.getByRole('slider')).toHaveCount(4)
  await expect(page.getByRole('heading', { name: 'Веса признаков', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Пороги уровней риска', exact: true })).toBeVisible()
  await expect(page.getByRole('slider', { name: 'Ожидает оплаты (prolong_wait)', exact: true })).toHaveAttribute('aria-valuenow', '0.42')
  await expect(page.getByText('Модель расчёта пока не подключена.', { exact: false })).toBeVisible()
  await expect(page.locator('textarea')).toHaveCount(0)
  await page.screenshot({ path: 'test-results/model-settings-sliders.png', fullPage: true })
  const date = page.getByLabel('Дата расчёта', { exact: true })
  await date.fill('2026-10-19T12:30')
  const expected = await page.evaluate(() => new Date('2026-10-19T12:30').toISOString())
  await page.getByRole('button', { name: 'СОХРАНИТЬ ИЗМЕНЕНИЯ' }).click()
  await expect(page.getByText('Настройки сохранены, оценки пересчитаны')).toBeVisible()
  expect(api.settings).toEqual({ asOf: expected })
})

test('settings validate weight sums and risk thresholds before saving', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/app/model-settings')
  const weight = page.getByRole('spinbutton', { name: 'Вес: Ожидает оплаты (prolong_wait)', exact: true })
  await expect(weight).toHaveValue('0.42')
  await weight.fill('0.50')
  await page.getByRole('button', { name: 'СОХРАНИТЬ ИЗМЕНЕНИЯ' }).click()
  await expect(page.getByText('Сумма весов должна быть равна 1.00.', { exact: true })).toBeVisible()
  await weight.fill('0.42')
  await page.getByRole('spinbutton', { name: 'Средний риск, от', exact: true }).fill('90')
  await page.getByRole('button', { name: 'СОХРАНИТЬ ИЗМЕНЕНИЯ' }).click()
  await expect(page.getByText('Порог высокого риска должен быть больше порога среднего риска.', { exact: true })).toBeVisible()
  expect(api.requests.filter((request) => request.path === '/model/settings' && request.method === 'PATCH')).toHaveLength(0)
})

test('settings add a feature with a slider and persist it through the API', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/app/model-settings')
  await page.getByRole('button', { name: '+ Добавить признак', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Добавить признак', exact: true })
  await dialog.getByLabel('Название признака', { exact: true }).fill('Неоплаченные транзакции')
  await dialog.getByRole('button', { name: 'Добавить', exact: true }).click()
  await expect(page.getByRole('slider')).toHaveCount(5)
  await expect(page.getByRole('slider', { name: 'Неоплаченные транзакции', exact: true })).toHaveAttribute('aria-valuenow', '0')
  await page.getByRole('button', { name: 'СОХРАНИТЬ ИЗМЕНЕНИЯ' }).click()
  await expect(page.getByText('Настройки сохранены, оценки пересчитаны')).toBeVisible()
  expect(api.settings.features).toEqual(expect.arrayContaining([expect.objectContaining({ name: 'Неоплаченные транзакции', weight: 0 })]))
  await page.reload()
  await expect(page.getByRole('slider', { name: 'Неоплаченные транзакции', exact: true })).toBeVisible()
})

test('manager views settings without mutation controls and cannot access user management', async ({ page }) => {
  const api = await setupApi(page, 'manager')
  await page.goto('/')
  await expect(page.locator('.total-value')).toHaveText('55')
  await expect(page.getByRole('link', { name: 'Настройка модели', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Управление менеджерами', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Загрузить снимок' })).toHaveCount(0)
  await page.getByRole('link', { name: 'Настройка модели', exact: true }).click()
  await expect(page.getByRole('slider')).toHaveCount(4)
  for (const field of await page.getByRole('spinbutton').all()) await expect(field).toBeDisabled()
  for (const slider of await page.getByRole('slider').all()) await expect(slider).toBeDisabled()
  await expect(page.getByLabel('Дата расчёта', { exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'СОХРАНИТЬ ИЗМЕНЕНИЯ' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '+ Добавить признак', exact: true })).toHaveCount(0)
  await expect(page.getByText('Режим просмотра.', { exact: false })).toBeVisible()
  await page.locator('.model-settings-form').evaluate((form) => form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })))
  await page.goto('/app/users')
  await expect(page).toHaveURL('http://127.0.0.1:5174/')
  expect(api.requests.some((req) => req.path === '/users' || req.path === '/source/snapshot' || (req.path === '/model/settings' && req.method === 'PATCH'))).toBe(false)
  expect(api.requests.some((req) => req.path === '/model/settings' && req.method === 'GET')).toBe(true)
})

test('administrator creates, edits and deletes managers', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/app/users')
  await expect(page.getByRole('cell', { name: 'manager1', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Добавить менеджера' }).click()
  let dialog = page.getByRole('dialog')
  await dialog.getByLabel('Логин', { exact: true }).fill('manager2')
  await dialog.getByLabel('Email', { exact: true }).fill('manager2@example.com')
  await dialog.getByLabel('Пароль', { exact: true }).fill('Passw0rd-2')
  await dialog.getByRole('button', { name: 'Сохранить' }).click()
  await expect(page.getByRole('cell', { name: 'manager2', exact: true })).toBeVisible()
  let row = page.getByRole('row').filter({ has: page.getByRole('cell', { name: 'manager2', exact: true }) })
  await row.getByRole('button', { name: 'Изменить' }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Email', { exact: true }).fill('updated@example.com')
  await dialog.getByRole('button', { name: 'Сохранить' }).click()
  await expect(page.getByRole('cell', { name: 'updated@example.com', exact: true })).toBeVisible()
  const update = api.requests.find((req) => req.method === 'PATCH' && req.path.startsWith('/users/'))!
  expect(update.body).toEqual({ email: 'updated@example.com' })
  await row.getByRole('button', { name: 'Удалить' }).click()
  await page.getByRole('button', { name: 'Удалить', exact: true }).last().click()
  await expect(page.getByRole('cell', { name: 'manager2', exact: true })).toHaveCount(0)
  expect(api.managers).toHaveLength(1)
})

test('SSE renews the session on CLOSED and catches changes missed during reconnect', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/')
  await expect(page.locator('.total-value')).toHaveText('55')
  await emit(page, 'ready', '1')
  const previous = api.refreshCalls
  await page.evaluate(() => {
    const stream = (window as unknown as { streams: (EventSource & { readyState: number; onerror: () => void })[] }).streams.filter((item) => item.readyState !== 2).at(-1)!
    stream.close()
    stream.onerror()
  })
  await expect.poll(() => api.refreshCalls).toBe(previous + 1)
  api.customers.pop()
  await emit(page, 'ready', '2')
  await expect(page.locator('.total-value')).toHaveText('54')
})

test('customer errors can be retried without showing fixture data', async ({ page }) => {
  const api = await setupApi(page)
  api.failCustomers = true
  await page.goto('/app/clients')
  await expect(page.getByText('Не удалось загрузить клиентов', { exact: true })).toBeVisible()
  await expect(page.locator('.client-table-link')).toHaveCount(0)
  api.failCustomers = false
  await page.getByRole('button', { name: 'Повторить', exact: true }).click()
  await expect(page.locator('.client-table-link')).toHaveCount(50)
})

test('SSE reloads the current customer page and recovers when that page disappears', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/app/clients')
  await expect(page.locator('.client-table-link')).toHaveCount(50)
  await page.getByRole('columnheader', { name: /^ID/ }).click()
  await expect(page.locator('.client-table-link').first()).toHaveText('client001@example.com')
  await page.locator('.ant-pagination-item-2').click()
  await expect(page.locator('.client-table-link')).toHaveCount(5)
  api.customers[50].balance = 999
  await emit(page)
  await expect(page.getByRole('cell', { name: '€9.99', exact: true })).toBeVisible()
  await expect(page.locator('.ant-pagination-item-active')).toHaveText('2')
  api.customers = api.customers.slice(0, 10)
  await emit(page, 'recalculated', '3')
  await expect(page.locator('.client-table-link')).toHaveCount(10)
  await expect(page.locator('.ant-pagination-item-active')).toHaveText('1')
})

test('administrator uploads a snapshot after choosing and confirming a JSON file', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Загрузить снимок', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('button', { name: 'Заменить данные' })).toBeDisabled()
  const snapshot = { accounts: [{ id: 1, email: 'snapshot@example.com', balance: 100, withdrawBalance: 0, totalReplenished: 100, bonusBalance: 0, bonusState: 'unlocked' }], services: [], transactions: [] }
  await dialog.locator('input[type=file]').setInputFiles({ name: 'snapshot.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(snapshot)) })
  await expect(dialog.getByText('snapshot.json', { exact: true })).toBeVisible()
  expect(api.requests.some((req) => req.path === '/source/snapshot')).toBe(false)
  await dialog.getByRole('button', { name: 'Заменить данные' }).click()
  await expect(page.getByText('Снимок загружен, оценки пересчитаны')).toBeVisible()
  await expect(dialog.getByText('Аккаунтов: 1', { exact: true })).toBeVisible()
  await expect(dialog.getByText('Услуг: 0', { exact: true })).toBeVisible()
  await expect(dialog.getByText('Транзакций: 0', { exact: true })).toBeVisible()
  expect(api.requests.find((req) => req.path === '/source/snapshot')).toMatchObject({ method: 'PUT', body: snapshot })
  await dialog.getByRole('button', { name: /Готово/ }).click()
  await expect(dialog).toHaveCount(0)
})

test('expired SSE session returns to login and closes the stream', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/')
  await expect(page.locator('.total-value')).toHaveText('55')
  api.loggedIn = false
  await page.evaluate(() => {
    const stream = (window as unknown as { streams: (EventSource & { onerror: () => void })[] }).streams.filter((item) => item.readyState !== 2).at(-1)!
    stream.close()
    stream.onerror()
  })
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('button', { name: 'Войти', exact: true })).toBeVisible()
})

test('summary accepts the backend noData bucket when every customer has no score', async ({ page }) => {
  const api = await setupApi(page)
  api.customers = api.customers.map((customer) => ({ ...customer, level: 'no_data', riskScore: null, expectedLossCents: 0 }))
  await page.goto('/')
  await expect(page.locator('.total-value')).toHaveText('55')
  await expect(page.locator('.account-summary').getByText('нет оценки: 55', { exact: true })).toBeVisible()
  await expect(page.locator('.revenue-value')).toHaveText('€0,00')
  await expect(page.getByText('Не удалось загрузить сводку', { exact: true })).toHaveCount(0)
})

for (const failure of [500, 429, 'network'] as const) {
  test(`temporary refresh failure ${failure} preserves the session and settings draft`, async ({ page }) => {
    const api = await setupApi(page)
    await page.goto('/app/model-settings')
    const threshold = page.getByRole('spinbutton', { name: 'Высокий риск, от', exact: true })
    await expect(threshold).toHaveValue('70 баллов')
    await threshold.fill('75')
    api.expireSettingsPatch = true
    api.refreshFailure = failure
    const refreshCalls = api.refreshCalls
    await page.getByRole('button', { name: 'СОХРАНИТЬ ИЗМЕНЕНИЯ' }).click()
    const reason = failure === 'network' ? 'Нет соединения с сервером' : failure === 429 ? 'Слишком много запросов. Попробуйте позже.' : 'Обновление сессии временно недоступно'
    await expect(page.locator('.model-settings-form').getByRole('alert')).toContainText(reason)
    await expect(threshold).toHaveValue('75 баллов')
    await expect(page).toHaveURL(/\/app\/model-settings$/)
    expect(api.refreshCalls).toBe(refreshCalls + 1)
    expect(await page.evaluate(() => (window as unknown as { sessionExpirations: number }).sessionExpirations)).toBe(0)
    expect(await page.evaluate(() => (window as unknown as { streams: EventSource[] }).streams.filter((stream) => stream.readyState !== 2).length)).toBe(1)
    api.expireSettingsPatch = false
    api.refreshFailure = null
    await page.getByRole('button', { name: 'СОХРАНИТЬ ИЗМЕНЕНИЯ' }).click()
    await expect(page.getByText('Настройки сохранены, оценки пересчитаны')).toBeVisible()
    expect(api.settings).toEqual({ asOf: null, thresholds: { high: 75 } })
  })
}

for (const rejection of ['refresh', 'retried request'] as const) {
  test(`HTTP authentication failure in ${rejection} still expires the session`, async ({ page }) => {
    const api = await setupApi(page)
    await page.goto('/app/clients')
    await expect(page.locator('.client-table-link')).toHaveCount(50)
    if (rejection === 'refresh') api.loggedIn = false
    else api.expireCustomers = true
    const refreshCalls = api.refreshCalls
    await page.getByRole('button', { name: 'Высокий', exact: true }).click()
    await expect(page).toHaveURL(/\/login$/)
    expect(api.refreshCalls).toBe(refreshCalls + 1)
    expect(await page.evaluate(() => (window as unknown as { streams: EventSource[] }).streams.filter((stream) => stream.readyState !== 2).length)).toBe(0)
  })
}

for (const screen of ['dashboard', 'customers', 'card'] as const) {
  test(`first SSE ready refreshes ${screen} after a recalculation during connection setup`, async ({ page }) => {
    const api = await setupApi(page)
    const path = screen === 'dashboard' ? '/' : screen === 'customers' ? '/app/clients' : '/app/clients/1'
    await page.goto(path)
    if (screen === 'dashboard') await expect(page.locator('.total-value')).toHaveText('55')
    else if (screen === 'customers') await expect(page.locator('.client-table-link')).toHaveCount(50)
    else await expect(page.locator('.client-profile__stats')).toContainText('€123.45')
    await expect.poll(() => api.summaryCalls).toBeGreaterThan(0)
    const summaryCalls = api.summaryCalls, customerCalls = api.customerCalls, cardCalls = api.cardCalls
    api.customers[0].balance = 999
    api.customers[1].email = 'changed@example.com'
    api.customers.pop()
    api.version = 2
    await emit(page, 'ready', '2')
    await expect.poll(() => api.summaryCalls).toBeGreaterThan(summaryCalls)
    if (screen === 'dashboard') {
      await expect(page.locator('.total-value')).toHaveText('54')
      await expect(page.locator('.priority-clients')).toContainText('changed@example.com')
      expect(api.customerCalls).toBeGreaterThan(customerCalls)
    } else if (screen === 'customers') {
      await expect(page.getByRole('link', { name: 'Открыть клиента changed@example.com', exact: true })).toBeVisible()
      expect(api.customerCalls).toBeGreaterThan(customerCalls)
    } else {
      await expect(page.locator('.client-profile__stats')).toContainText('€9.99')
      expect(api.cardCalls).toBeGreaterThan(cardCalls)
    }
  })
}

test('metrics navigation opens the backend Prometheus endpoint in a new tab', async ({ page }) => {
  await setupApi(page)
  await page.context().route('http://127.0.0.1:8000/metrics', (route) => route.fulfill({
    contentType: 'text/plain; version=0.0.4; charset=utf-8',
    body: 'churn_customers_total 55\nchurn_expected_loss_eurocents 67500\n',
  }))
  await page.goto('/')
  const link = page.getByRole('link', { name: 'Метрики /metrics', exact: true })
  await expect(link).toHaveAttribute('href', 'http://127.0.0.1:8000/metrics')
  const popupOpened = page.waitForEvent('popup')
  await link.click()
  const metricsPage = await popupOpened
  await expect(metricsPage).toHaveURL('http://127.0.0.1:8000/metrics')
  await expect(metricsPage.locator('body')).toContainText('churn_customers_total 55')
  await expect(metricsPage.locator('body')).toContainText('churn_expected_loss_eurocents 67500')
  await expect(page).toHaveURL('http://127.0.0.1:5174/')
  await metricsPage.close()
})

test('saving settings refreshes the summary and the customer data shown afterwards', async ({ page }) => {
  const api = await setupApi(page)
  api.onSettingsSaved = () => {
    Object.assign(api.customers[1], { riskScore: 12, level: 'low', expectedLossCents: 123, reasonShort: 'Автопродление восстановлено' })
  }
  await page.goto('/app/model-settings')
  const threshold = page.getByRole('spinbutton', { name: 'Высокий риск, от', exact: true })
  await expect(threshold).toHaveValue('70 баллов')
  await expect.poll(() => api.summaryCalls).toBeGreaterThan(0)
  const summaryCalls = api.summaryCalls
  await threshold.fill('75')
  await page.getByRole('button', { name: 'СОХРАНИТЬ ИЗМЕНЕНИЯ' }).click()
  await expect(page.getByText('Настройки сохранены, оценки пересчитаны')).toBeVisible()
  await expect.poll(() => api.summaryCalls).toBeGreaterThan(summaryCalls)
  expect(api.settings).toEqual({ asOf: null, thresholds: { high: 75 } })
  await page.getByRole('link', { name: 'Дашборд', exact: true }).click()
  await expect(page.locator('.revenue-value')).toHaveText('€663,73')
  await page.getByRole('link', { name: 'Клиенты под риском', exact: true }).click()
  await page.getByRole('textbox', { name: 'Поиск клиентов' }).fill('client002@example.com')
  const client = page.getByRole('link', { name: 'Открыть клиента client002@example.com', exact: true })
  const row = page.getByRole('row').filter({ has: client })
  await expect(row.locator('.client-risk-indicator__level')).toHaveText('Низкий')
  await expect(row.locator('.client-table-reason')).toHaveText('Автопродление восстановлено')
  await expect(row.getByRole('img', { name: 'Низкий риск · 12%' })).toBeVisible()
  await client.click()
  await expect(page.getByRole('heading', { name: 'Клиент #2' })).toBeVisible()
  await expect(page.locator('.client-profile__stats').getByText('12', { exact: true })).toBeVisible()
  await expect(page.locator('.client-profile__risk')).toHaveText('НИЗКИЙ РИСК')
  await expect(page.locator('.client-risk-reasons__list')).toContainText('Автопродление восстановлено')
  await expect(page.locator('.client-profile__loss')).toHaveText('€1,23')
})

test('snapshot validation errors identify the record and field in Russian', async ({ page }) => {
  const api = await setupApi(page)
  api.snapshotError = { detail: [{ loc: ['body', 'accounts', 0, 'balance'], msg: 'Input should be greater than or equal to 0', type: 'greater_than_equal', ctx: { ge: 0 } }] }
  await page.goto('/')
  await page.getByRole('button', { name: 'Загрузить снимок', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Загрузка снимка', exact: true })
  const picker = dialog.locator('input[type=file]')
  await picker.setInputFiles({ name: 'broken.json', mimeType: 'application/json', buffer: Buffer.from('{broken') })
  await expect(dialog.getByRole('alert')).toContainText('Проверьте формат файла')
  await expect(dialog.getByRole('button', { name: 'Заменить данные' })).toBeDisabled()
  expect(api.requests.some((req) => req.path === '/source/snapshot')).toBe(false)
  await picker.setInputFiles({ name: 'data.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify({ accounts: [{ balance: -1 }], services: [], transactions: [] })) })
  await dialog.getByRole('button', { name: 'Заменить данные' }).click()
  await expect(dialog.getByRole('alert')).toContainText('Аккаунты → запись 1 → Баланс')
  await expect(dialog.getByRole('alert')).toContainText('Значение должно быть не меньше 0.')
  await expect(dialog.getByRole('button', { name: 'Заменить данные' })).toBeEnabled()
})

for (const failure of [403, 'network'] as const) {
  test(`customer failure ${failure} shows an understandable error and can be retried`, async ({ page }) => {
    const api = await setupApi(page)
    api.customerFailure = failure
    await page.goto('/app/clients')
    const alert = page.locator('.client-risk-table').getByRole('alert')
    await expect(alert).toContainText(failure === 403 ? 'Недостаточно прав' : 'Нет соединения с сервером')
    await expect(page).toHaveURL(/\/app\/clients$/)
    api.customerFailure = null
    await alert.getByRole('button', { name: 'Повторить', exact: true }).click()
    await expect(page.locator('.client-table-link')).toHaveCount(50)
  })
}

test('login rate limit displays a Russian explanation without a refresh loop', async ({ page }) => {
  const api = await setupApi(page, 'admin', false)
  api.loginFailure = 429
  await page.goto('/login')
  await page.getByLabel('Логин', { exact: true }).fill('admin')
  await page.getByLabel('Пароль', { exact: true }).fill('password123')
  const refreshCalls = api.refreshCalls
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page.getByRole('alert')).toHaveText('Слишком много попыток входа. Попробуйте позже.')
  await expect(page).toHaveURL(/\/login$/)
  expect(api.refreshCalls).toBe(refreshCalls)
  await expect(page.getByRole('button', { name: 'Войти', exact: true })).toBeEnabled()
})

test('administrator can change a manager login and password without sending unchanged fields', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/app/users')
  await page.getByRole('row').filter({ has: page.getByRole('cell', { name: 'manager1', exact: true }) }).getByRole('button', { name: 'Изменить', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Логин', { exact: true }).fill('renamed_manager')
  await dialog.getByLabel('Новый пароль (необязательно)', { exact: true }).fill('NewPassw0rd-2')
  await dialog.getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(page.getByRole('cell', { name: 'renamed_manager', exact: true })).toBeVisible()
  expect(api.requests.find((req) => req.method === 'PATCH' && req.path === `/users/${managerId}`)?.body).toEqual({ login: 'renamed_manager', password: 'NewPassw0rd-2' })
})

test('empty customer and manager lists have explicit empty states', async ({ page }) => {
  const api = await setupApi(page)
  api.customers = []
  api.managers = []
  await page.goto('/')
  await expect(page.locator('.total-value')).toHaveText('0')
  await expect(page.getByText('Клиентов пока нет', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Клиенты под риском', exact: true }).click()
  await expect(page.getByText('Нет клиентов с выбранным уровнем риска', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Управление менеджерами', exact: true }).click()
  await expect(page.getByText('Менеджеров пока нет', { exact: true })).toBeVisible()
})

test('live update text reflects a connected or interrupted event stream', async ({ page }) => {
  await setupApi(page)
  await page.goto('/')
  const status = page.locator('.dashboard-updates')
  await expect(status).toHaveText('Подключаем обновления…')
  await emit(page, 'ready', '1')
  await expect(status).toContainText('Обновляется в реальном времени')
  await page.evaluate(() => {
    const stream = (window as unknown as { streams: { readyState: number; onerror: () => void }[] }).streams.filter((item) => item.readyState !== 2).at(-1)!
    stream.readyState = 0
    stream.onerror()
  })
  await expect(status).toHaveText('Восстанавливаем соединение для обновлений…')
  await emit(page, 'ready', '1')
  await expect(status).toContainText('Обновляется в реальном времени')
})
