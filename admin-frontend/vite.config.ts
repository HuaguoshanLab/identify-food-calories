import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

const ADMIN_API_PATH = '/api/v1/admin'

function isAdminApiPath(pathname: string) {
  return pathname === ADMIN_API_PATH || pathname.startsWith(`${ADMIN_API_PATH}/`)
}

function validateProductionAdminApiBaseUrl(value: string | undefined) {
  if (!value) {
    throw new Error('Production builds require VITE_ADMIN_API_BASE_URL for the public admin API.')
  }

  if (value.startsWith('/') && !value.startsWith('//')) {
    if (!isAdminApiPath(value)) {
      throw new Error('VITE_ADMIN_API_BASE_URL must stay within /api/v1/admin.')
    }
    return value
  }

  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    throw new Error('VITE_ADMIN_API_BASE_URL must be an admin path or an HTTPS URL.')
  }

  if (parsed.protocol !== 'https:' || !isAdminApiPath(parsed.pathname)) {
    throw new Error('VITE_ADMIN_API_BASE_URL must be an HTTPS URL within /api/v1/admin.')
  }
  return parsed.toString().replace(/\/$/, '')
}

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, process.cwd(), 'VITE_')
  const adminApiBaseUrl =
    mode === 'production'
      ? validateProductionAdminApiBaseUrl(environment.VITE_ADMIN_API_BASE_URL)
      : environment.VITE_ADMIN_API_BASE_URL || ADMIN_API_PATH
  const apiProxyTarget = environment.VITE_ADMIN_API_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react(), tailwindcss()],
    define: {
      __ADMIN_API_BASE_URL__: JSON.stringify(adminApiBaseUrl),
    },
    resolve: {
      alias: {
        '@': new URL('./src', import.meta.url).pathname,
      },
    },
    server: {
      host: '127.0.0.1',
      port: 5179,
      strictPort: true,
      proxy: {
        [ADMIN_API_PATH]: apiProxyTarget,
      },
    },
    preview: {
      host: '127.0.0.1',
      port: 5179,
      strictPort: true,
      proxy: {
        [ADMIN_API_PATH]: apiProxyTarget,
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      setupFiles: ['./src/test/setup.ts'],
    },
  }
})
