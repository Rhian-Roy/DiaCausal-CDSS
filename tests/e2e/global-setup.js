/**
 * Starts a real backend and a real page on spare ports, with a throwaway database, and
 * creates one admin account. Nothing here touches backend/diacausal.db.
 */

import { execFileSync, spawn } from 'node:child_process'
import crypto from 'node:crypto'
import fs from 'node:fs'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const BACKEND = path.join(REPO, 'backend')
const WINDOWS = process.platform === 'win32'
const VENV_PY = path.join(BACKEND, '.venv', WINDOWS ? 'Scripts/python.exe' : 'bin/python')

const freePort = () =>
  new Promise((resolve) => {
    const server = net.createServer()
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address()
      server.close(() => resolve(port))
    })
  })

async function waitUntilUp(url, child, seconds = 90) {
  const deadline = Date.now() + seconds * 1000
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`${url} died on start-up`)
    try {
      const response = await fetch(url)
      if (response.status < 500) return
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 300))
  }
  throw new Error(`${url} did not start within ${seconds}s`)
}

export default async function globalSetup() {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'diacausal-e2e-'))
  const dbFile = path.join(work, 'e2e.db')
  const password = `e2e ${crypto.randomBytes(8).toString('hex')}`
  const env = {
    ...process.env,
    DIACAUSAL_DATABASE_URL: `sqlite:///${dbFile.split(path.sep).join('/')}`,
    DIACAUSAL_SECRET_KEY: crypto.randomBytes(32).toString('base64url').padEnd(44, '='), // Fernet wants padding
    NO_COLOR: '1',
  }
  const apiPort = await freePort()
  const webPort = await freePort()
  const apiUrl = `http://127.0.0.1:${apiPort}`
  const webUrl = `http://localhost:${webPort}` // "localhost" so Chrome accepts the Secure cookie

  const backendLog = fs.openSync(path.join(work, 'backend.log'), 'w')
  const backend = spawn(VENV_PY, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(apiPort)],
    { cwd: BACKEND, env, stdio: ['ignore', backendLog, backendLog] })
  await waitUntilUp(`${apiUrl}/api/health`, backend)

  execFileSync(VENV_PY, ['-m', 'app.auth.cli', '--password-stdin', 'create-first-admin', 'e2e.admin', 'Dr E2E'],
    { cwd: BACKEND, env, input: `${password}\n` })

  const frontendLog = fs.openSync(path.join(work, 'frontend.log'), 'w')
  const frontend = spawn(process.execPath,
    [path.join(REPO, 'frontend', 'node_modules', 'vite', 'bin', 'vite.js'),
     '--host', '127.0.0.1', '--port', String(webPort), '--strictPort'],
    { cwd: path.join(REPO, 'frontend'), env: { ...env, DIACAUSAL_API_URL: apiUrl }, stdio: ['ignore', frontendLog, frontendLog] })
  await waitUntilUp(webUrl, frontend)

  process.env.E2E_WEB_URL = webUrl
  process.env.E2E_DB_FILE = dbFile
  process.env.E2E_PASSWORD = password
  process.env.E2E_BACKEND_LOG = path.join(work, 'backend.log')
  process.env.E2E_WORK_DIR = work
  globalThis.__diacausal = { backend, frontend, work }
}
