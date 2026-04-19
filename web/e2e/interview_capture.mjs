import fs from 'node:fs/promises'
import path from 'node:path'
import { chromium } from 'playwright'

const manifestPath = process.argv[2]

if (!manifestPath) {
  console.error('Missing screenshot manifest path')
  process.exit(1)
}

const chromeCandidates = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
]

async function resolveBrowserExecutable() {
  for (const candidate of chromeCandidates) {
    try {
      await fs.access(candidate)
      return candidate
    } catch {
      // ignore
    }
  }
  return null
}

async function waitForSelectors(page, selectors) {
  const parts = String(selectors || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

  if (!parts.length) {
    await page.waitForLoadState('networkidle')
    return
  }

  const timeout = 45000
  const start = Date.now()
  while (Date.now() - start < timeout) {
    for (const selector of parts) {
      const locator = page.locator(selector).first()
      if ((await locator.count()) > 0) {
        return
      }
    }
    await page.waitForTimeout(500)
  }

  throw new Error(`Timed out waiting for selectors: ${parts.join(', ')}`)
}

async function main() {
  const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf-8'))
  const executablePath = await resolveBrowserExecutable()

  const browser = await chromium.launch({
    headless: true,
    ...(executablePath ? { executablePath } : {})
  })

  try {
    const context = await browser.newContext({
      viewport: { width: 1600, height: 1200 }
    })

    if (manifest.token) {
      await context.addInitScript((token) => {
        try {
          window.localStorage.setItem('user_token', token)
        } catch {
          // ignore local file pages
        }
      }, manifest.token)
    }

    for (const item of manifest.screenshots) {
      const page = await context.newPage()
      await page.goto(item.url, { waitUntil: 'domcontentloaded', timeout: 60000 })
      await waitForSelectors(page, item.wait_selector)
      await page.waitForTimeout(1500)

      const targetPath = path.resolve(item.path)
      await fs.mkdir(path.dirname(targetPath), { recursive: true })
      await page.screenshot({ path: targetPath, fullPage: true })
      console.log(`[capture] ${item.name} -> ${targetPath}`)
      await page.close()
    }
  } finally {
    await browser.close()
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
