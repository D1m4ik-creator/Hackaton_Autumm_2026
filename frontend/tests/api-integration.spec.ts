import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const timestamp = '2026-10-24T12:00:00Z'
const managerId = '11111111-1111-4111-8111-111111111111'

async function setupApi(page: Page, role: 'admin' | 'manager' = 'admin', loggedIn = true) {
  const state = {
    loggedIn, version: 1, summaryCalls: 0, customerCalls: 0, cardCalls: 0,
    refreshCalls: 0, expireMe: false, failCustomers: false, expireCustomers: false,
    refreshFailure: null as 'network' | 429 | 500 | null,
    expireSettingsPatch: false,
    settings: { asOf: null } as Record<string, unknown>,
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
    if (path === '/auth/login') { state.loggedIn = true; return respond({ message: 'OK' }) }
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
      return respond({ customersTotal: state.customers.length, byLevel, expectedLossCents: state.customers.reduce((sum, customer) => sum + customer.expectedLossCents, 0), lossExplanation: 'Ожидаемые потери', asOf: timestamp, recalculatedAt: timestamp, version: state.version })
    }
    if (path === '/customers') {
      state.customerCalls++
      if (state.expireCustomers) return respond({ detail: 'Access expired' }, 401)
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
        reasons: [{ code: 'model_not_connected', text: 'Модель анализа ещё не подключена' }], details: {},
        services: [{ id: 1, name: 'VPS Test', status: 'active', price: 1299, autoProlong: false, paymentTerm: 'week', createdAt: timestamp, expiresAt: timestamp }],
        transactions: { total: 5, performed: 3, notPerformed: 2 }, asOf: timestamp, calculatedAt: timestamp,
      })
    }
    if (path === '/model/settings') {
      if (method === 'PATCH' && state.expireSettingsPatch) return respond({ detail: 'Access expired' }, 401)
      if (method === 'PATCH') { state.settings = { ...state.settings, ...body }; state.version++ }
      return respond({ settings: state.settings, defaults: { asOf: null }, updatedAt: timestamp, version: state.version })
    }
    if (path === '/source/snapshot') { state.version++; return respond({ accounts: 1, services: 0, transactions: 0, version: state.version, recalculatedAt: timestamp }) }
    if (path === '/users' && method === 'GET') return respond(state.managers)
    if (path === '/users' && method === 'POST') {
      const created = { id: '22222222-2222-4222-8222-222222222222', ...body, role: 'manager', createdAt: timestamp }
      state.managers.push(created)
      return respond(created, 201)
    }
    if (path.startsWith('/users/') && method === 'PATCH') {
      const manager = state.managers.find((item) => path.endsWith(item.id))!
      Object.assign(manager, body)
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
  await expect(page.getByRole('button', { name: /^Открыть клиента/ })).toHaveCount(4)
  await expect.poll(() => page.evaluate(() => (window as unknown as { streams: EventSource[] }).streams.filter((stream) => stream.readyState !== 2).map((stream) => ({ url: stream.url, withCredentials: stream.withCredentials })))).toEqual([{ url: 'http://127.0.0.1:8000/api/v1/events', withCredentials: true }])
  api.customers.pop()
  api.version++
  const calls = api.customerCalls
  await emit(page)
  await expect(page.locator('.total-value')).toHaveText('54')
  await expect.poll(() => api.customerCalls).toBeGreaterThan(calls)
  await page.setViewportSize({ width: 375, height: 812 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('customers send both sort directions for every field, page, search and no_data filter', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/app/clients')
  await expect(page.getByRole('link', { name: 'Открыть клиента client002@example.com', exact: true })).toBeVisible()
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

test('customer card renders real reasons, transactions and prices and refreshes over SSE', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/app/clients/1')
  await expect(page.getByRole('heading', { name: 'Клиент #1' })).toBeVisible()
  await expect(page.getByText('Модель анализа ещё не подключена', { exact: true })).toBeVisible()
  await expect(page.locator('.client-profile__risk')).toHaveText('нет оценки')
  await expect(page.locator('.client-profile__stats')).toContainText('€123.45')
  await expect(page.locator('.client-services__price')).toContainText('€12.99 / нед')
  const calls = api.cardCalls
  api.customers[0].balance = 999
  await emit(page)
  await expect(page.locator('.client-profile__stats')).toContainText('€9.99')
  expect(api.cardCalls).toBeGreaterThan(calls)
  await page.goto('/app/clients/999')
  await expect(page.getByRole('main').getByText('Клиент не найден', { exact: true })).toBeVisible()
})

test('settings load and PATCH actual JSON, preserving drafts across SSE', async ({ page }) => {
  const api = await setupApi(page)
  await page.goto('/app/model-settings')
  const editor = page.getByRole('textbox', { name: 'Настройки модели JSON' })
  await expect(editor).toHaveValue(JSON.stringify({ asOf: null }, null, 2))
  await editor.fill('{broken')
  await page.getByRole('button', { name: 'СОХРАНИТЬ ИЗМЕНЕНИЯ' }).click()
  await expect(page.getByText('Проверьте формат JSON.')).toBeVisible()
  const settings = { asOf: '2026-10-24T12:00:00Z', coefficients: { balance: 0.5 } }
  await editor.fill(JSON.stringify(settings))
  await emit(page)
  await expect(editor).toHaveValue(JSON.stringify(settings))
  await page.getByRole('button', { name: 'СОХРАНИТЬ ИЗМЕНЕНИЯ' }).click()
  await expect(page.getByText('Настройки сохранены, оценки пересчитаны')).toBeVisible()
  expect(api.settings).toEqual(settings)
  await page.reload()
  await expect(editor).toHaveValue(JSON.stringify(settings, null, 2))
})

test('manager cannot access administrative navigation or routes', async ({ page }) => {
  const api = await setupApi(page, 'manager')
  await page.goto('/')
  await expect(page.locator('.total-value')).toHaveText('55')
  await expect(page.getByRole('link', { name: 'Настройка модели', exact: true })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Управление менеджерами', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Загрузить снимок' })).toHaveCount(0)
  for (const path of ['/app/model-settings', '/app/users']) {
    await page.goto(path)
    await expect(page).toHaveURL('http://127.0.0.1:5174/')
  }
  expect(api.requests.some((req) => req.path === '/users' || req.path === '/model/settings' || req.path === '/source/snapshot')).toBe(false)
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
  const snapshot = { accounts: [], services: [], transactions: [] }
  await dialog.locator('input[type=file]').setInputFiles({ name: 'snapshot.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(snapshot)) })
  await expect(dialog.getByText('snapshot.json', { exact: true })).toBeVisible()
  expect(api.requests.some((req) => req.path === '/source/snapshot')).toBe(false)
  await dialog.getByRole('button', { name: 'Заменить данные' }).click()
  await expect(page.getByText('Снимок загружен, оценки пересчитаны')).toBeVisible()
  expect(api.requests.find((req) => req.path === '/source/snapshot')).toMatchObject({ method: 'PUT', body: snapshot })
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
    const editor = page.getByRole('textbox', { name: 'Настройки модели JSON' })
    await expect(editor).toHaveValue(JSON.stringify({ asOf: null }, null, 2))
    const draft = JSON.stringify({ asOf: timestamp })
    await editor.fill(draft)
    api.expireSettingsPatch = true
    api.refreshFailure = failure
    const refreshCalls = api.refreshCalls
    await page.getByRole('button', { name: 'СОХРАНИТЬ ИЗМЕНЕНИЯ' }).click()
    const reason = failure === 'network' ? 'Нет соединения с сервером' : 'Обновление сессии временно недоступно'
    await expect(page.locator('.model-settings-form').getByRole('alert')).toContainText(reason)
    await expect(editor).toHaveValue(draft)
    await expect(page).toHaveURL(/\/app\/model-settings$/)
    expect(api.refreshCalls).toBe(refreshCalls + 1)
    expect(await page.evaluate(() => (window as unknown as { sessionExpirations: number }).sessionExpirations)).toBe(0)
    expect(await page.evaluate(() => (window as unknown as { streams: EventSource[] }).streams.filter((stream) => stream.readyState !== 2).length)).toBe(1)
    api.expireSettingsPatch = false
    api.refreshFailure = null
    await page.getByRole('button', { name: 'СОХРАНИТЬ ИЗМЕНЕНИЯ' }).click()
    await expect(page.getByText('Настройки сохранены, оценки пересчитаны')).toBeVisible()
    expect(api.settings).toEqual({ asOf: timestamp })
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
