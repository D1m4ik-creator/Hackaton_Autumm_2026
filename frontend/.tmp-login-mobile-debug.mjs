import { chromium } from 'playwright'

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 375, height: 812 } })
await page.goto('http://127.0.0.1:5173/login', { waitUntil: 'networkidle' })
await page.waitForTimeout(1800)

for (const sel of ['.auth-layout', '.auth-visual', '.auth-panel', '.auth-card', '.auth-card__title']) {
  const info = await page.locator(sel).evaluate((el) => {
    const r = el.getBoundingClientRect()
    const s = getComputedStyle(el)
    return { rect: { x: r.x, y: r.y, w: r.width, h: r.height }, display: s.display, visibility: s.visibility, opacity: s.opacity, gridTemplateRows: s.gridTemplateRows, gridTemplateColumns: s.gridTemplateColumns }
  }).catch((e) => 'ERROR: ' + e.message)
  console.log(sel, JSON.stringify(info))
}

await browser.close()
