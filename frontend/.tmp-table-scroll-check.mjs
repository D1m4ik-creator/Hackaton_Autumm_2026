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
await page.fill('#login', env.ADMIN_LOGIN)
await page.fill('#password', env.ADMIN_PASSWORD)
await page.click('button[type="submit"]')
await page.waitForURL('http://127.0.0.1:5173/', { timeout: 8000 })
await page.waitForTimeout(1100)
await page.goto('http://127.0.0.1:5173/app/clients', { waitUntil: 'networkidle' })
await page.waitForTimeout(1100)

const scrollInfo = await page.locator('.client-risk-table .ant-table-content').evaluate((el) => ({
  scrollWidth: el.scrollWidth, clientWidth: el.clientWidth, overflowX: getComputedStyle(el).overflowX,
}))
console.log('table scroll container:', JSON.stringify(scrollInfo))

const cardInfo = await page.locator('.client-risk-table').evaluate((el) => ({
  overflowX: getComputedStyle(el).overflowX, clientWidth: el.clientWidth,
}))
console.log('card wrapper:', JSON.stringify(cardInfo))

// try scrolling the table horizontally
await page.locator('.client-risk-table .ant-table-content').evaluate((el) => { el.scrollLeft = 400 })
await page.waitForTimeout(300)
await page.screenshot({ path: `${shotDir}/mobile-clients-scrolled.png`, clip: { x: 0, y: 150, width: 375, height: 500 } })

await browser.close()
