import { readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import solid from 'vite-plugin-solid'

const TOKEN_COOKIE = 'r2_token'

interface DaemonState {
  pid: number
  port: number
  token: string
  started: string
}

/**
 * The daemon writes its pid, port and token here (`r2/web/paths.py`). Reading the
 * file directly keeps the front free of any Python tooling. A dead pid is the same
 * as no file, as it is for `r2 web`.
 */
function readLiveDaemonState(): DaemonState | null {
  const base = process.env.XDG_STATE_HOME || join(homedir(), '.local', 'state')
  try {
    const state = JSON.parse(
      readFileSync(join(base, 'r2', 'web', 'daemon.json'), 'utf8'),
    ) as DaemonState
    process.kill(state.pid, 0)
    return state
  } catch {
    return null
  }
}

/**
 * The dev server proxies the daemon, so the UI runs with hot reload against real
 * reports.
 *
 * `host` is pinned to `127.0.0.1` rather than left at vite's default. The default
 * is `localhost`, which on a machine with IPv6 binds `[::1]` only, and the token
 * cookie is set by `r2 web` for `127.0.0.1`. Cookies ignore the port but not the host,
 * so a dev server on `localhost` gets no cookie and every API call is a 401.
 *
 * `/auth` is proxied for the same reason: it is how a browser with no cookie, or
 * an expired one, gets a new one. Without it vite answers `/auth` with index.html
 * and there is no way to authenticate on this origin.
 */
const state = readLiveDaemonState()
const target = `http://127.0.0.1:${state?.port ?? 7717}`

function devAuthRedirect(): Plugin {
  return {
    name: 'r2-dev-auth',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (state === null || req.url === undefined) return next()
        if (hasCurrentToken(req.headers.cookie ?? '', state.token)) return next()
        if (!acceptsHtml(req.headers.accept ?? '') || ignored(req.url)) return next()

        const url = new URL(req.url, 'http://127.0.0.1:7718')
        const to = `${url.pathname}${url.search}`
        const auth = new URL('/auth', 'http://127.0.0.1:7718')
        auth.searchParams.set('token', state.token)
        auth.searchParams.set('to', to)
        res.statusCode = 302
        res.setHeader('location', `${auth.pathname}${auth.search}`)
        res.end()
      })
    },
  }
}

function hasCurrentToken(cookie: string, token: string): boolean {
  return cookie
    .split(';')
    .map((part) => part.trim().split('='))
    .some(
      ([name, value]) => name === TOKEN_COOKIE && value === encodeURIComponent(token),
    )
}

function acceptsHtml(accept: string): boolean {
  return accept.includes('text/html') || accept.includes('*/*')
}

function ignored(path: string): boolean {
  return (
    path.startsWith('/api') ||
    path.startsWith('/auth') ||
    path.startsWith('/@') ||
    path.startsWith('/node_modules') ||
    path === '/favicon.ico'
  )
}

export default defineConfig({
  plugins: [devAuthRedirect(), solid()],
  server: {
    host: '127.0.0.1',
    port: 7718,
    strictPort: true,
    proxy: {
      '/api': { target, changeOrigin: false },
      '/auth': { target, changeOrigin: false },
    },
  },
  // The Python package serves the bundle from `r2/web/static`, which is not tracked.
  build: {
    outDir: fileURLToPath(new URL('../r2/web/static', import.meta.url)),
    emptyOutDir: true,
    sourcemap: false,
  },
})
