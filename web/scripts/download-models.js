/**
 * MediaPipe 模型下载脚本
 *
 * 在 pnpm install (postinstall) 或手动运行时，自动从 Google CDN 下载模型文件到 public/models/。
 * 已存在且大小 > 0 的文件会跳过。
 *
 * 用法: node scripts/download-models.js
 */

const { existsSync, statSync, mkdirSync, writeFileSync } = require('node:fs')
const { resolve } = require('node:path')
const https = require('node:https')

const MODELS_DIR = resolve(__dirname, '..', 'public', 'models')

const MODELS = [
  {
    name: 'face_landmarker.task',
    url: 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task',
  },
  {
    name: 'pose_landmarker_heavy.task',
    url: 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task',
  },
]

function downloadFile(url, destPath) {
  return new Promise((resolve, reject) => {
    const chunks = []
    let redirectCount = 0

    function doRequest(requestUrl) {
      if (redirectCount > 5) {
        reject(new Error('Too many redirects'))
        return
      }

      https
        .get(requestUrl, (res) => {
          if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
            redirectCount++
            doRequest(res.headers.location)
            return
          }

          if (res.statusCode !== 200) {
            reject(new Error(`HTTP ${res.statusCode} for ${requestUrl}`))
            return
          }

          const totalSize = parseInt(res.headers['content-length'], 10) || 0
          let downloaded = 0

          res.on('data', (chunk) => {
            chunks.push(chunk)
            downloaded += chunk.length
            if (totalSize > 0) {
              const pct = Math.round((downloaded / totalSize) * 100)
              const mb = (downloaded / 1024 / 1024).toFixed(1)
              const totalMb = (totalSize / 1024 / 1024).toFixed(1)
              process.stdout.write(`\r  ${pct}% (${mb}/${totalMb} MB)`)
            }
          })

          res.on('end', () => {
            process.stdout.write('\n')
            writeFileSync(destPath, Buffer.concat(chunks))
            resolve()
          })

          res.on('error', reject)
        })
        .on('error', reject)
    }

    doRequest(url)
  })
}

async function main() {
  if (!existsSync(MODELS_DIR)) {
    mkdirSync(MODELS_DIR, { recursive: true })
  }

  let allOk = true

  for (const model of MODELS) {
    const destPath = resolve(MODELS_DIR, model.name)

    if (existsSync(destPath)) {
      const stat = statSync(destPath)
      if (stat.size > 0) {
        console.log(`[skip] ${model.name} (${(stat.size / 1024 / 1024).toFixed(1)} MB)`)
        continue
      }
    }

    console.log(`[download] ${model.name} ...`)
    try {
      await downloadFile(model.url, destPath)
      const stat = statSync(destPath)
      console.log(`[done] ${model.name} (${(stat.size / 1024 / 1024).toFixed(1)} MB)`)
    } catch (err) {
      console.error(`[fail] ${model.name}: ${err.message}`)
      console.error(`  URL: ${model.url}`)
      console.error(`  Save to: ${destPath}`)
      allOk = false
    }
  }

  if (!allOk) {
    console.log('\nSome models failed. Retry: node scripts/download-models.js')
    process.exit(1)
  }
}

main()
