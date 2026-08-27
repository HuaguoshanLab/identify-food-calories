import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

function validateProductionApiBaseUrl(value: string | undefined) {
  if (!value) {
    // No value deliberately selects the same-origin /api/v1 deployment contract.
    return
  }
  if (value.startsWith('/') && !value.startsWith('//')) {
    return
  }

  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    throw new Error('VITE_API_BASE_URL must be a same-origin path or an HTTPS URL in production.')
  }
  if (parsed.protocol !== 'https:') {
    throw new Error('Production VITE_API_BASE_URL must use HTTPS.')
  }
}

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, process.cwd(), 'VITE_')
  if (mode === 'production') {
    validateProductionApiBaseUrl(environment.VITE_API_BASE_URL)
  }
  const apiProxyTarget = environment.VITE_DEV_API_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': new URL('./src', import.meta.url).pathname,
      },
    },
    server: {
      proxy: {
        '/api': apiProxyTarget,
      },
    },
    preview: {
      proxy: {
        '/api': apiProxyTarget,
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      setupFiles: ['./src/test-setup.ts'],
    },
  }
})
