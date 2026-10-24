import { chromium } from 'playwright'
import { readFileSync } from 'node:fs'

const env = Object.fromEntries(
  readFileSync('../backend/.env', 'utf8')
    .split('\n')
    .filter((l) => l.includes('=') && !l.trim().startsWith('#'))
    .map((l) => { const i = l.indexOf('='); return [l.slice(0, i).trim(), l.slice(i + 1).trim()] }),
)

const shotDir = 'C:/Users/17F2~1/AppData/Local/Temp/claude/c--projects-hack-autumn-26/9b40eb29-7807-4c12-baa1-5c218166f3b5/scratchpad'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 375, height: 812 } })

await page.goto('http://127.0.0.1:5173/login', { waitUntil: 'networkidle' })
await page.waitForTimeout(1800)
await page.screenshot({ path: `${shotDir}/mobile-login.png`, fullPage: true })

await page.fill('#login', env.ADMIN_LOGIN)
await page.fill('#password', env.ADMIN_PASSWORD)
await page.click('button[type="submit"]')
await page.waitForURL('http://127.0.0.1:5173/', { timeout: 8000 })
await page.waitForTimeout(1100)
await page.screenshot({ path: `${shotDir}/mobile-dashboard.png`, fullPage: true })

// mobile menu drawer
await page.click('.dashboard-mobile-header button')
await page.waitForTimeout(400)
await page.screenshot({ path: `${shotDir}/mobile-drawer.png`, fullPage: false })
await page.keyboard.press('Escape')
await page.waitForTimeout(300)

await page.goto('http://127.0.0.1:5173/app/clients', { waitUntil: 'networkidle' })
await page.waitForTimeout(1100)
await page.screenshot({ path: `${shotDir}/mobile-clients.png`, fullPage: true })

await page.locator('.client-risk-table .ant-table-tbody tr.ant-table-row').first().click()
await page.waitForURL(/\/app\/clients\/\d+/, { timeout: 5000 })
await page.waitForTimeout(500)
await page.screenshot({ path: `${shotDir}/mobile-client-detail.png`, fullPage: true })

await page.goto('http://127.0.0.1:5173/app/model-settings', { waitUntil: 'networkidle' })
await page.waitForTimeout(1100)
await page.screenshot({ path: `${shotDir}/mobile-model-settings.png`, fullPage: true })

// check for horizontal overflow on each visited page
const overflowCheck = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
console.log('horizontal overflow on model-settings:', overflowCheck)

await browser.close()
