import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { App } from './App'
import { AdminAuthProvider } from './auth/AdminAuthProvider'
import './styles/index.css'

const queryClient = new QueryClient()
const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('React root element is missing')
}

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AdminAuthProvider>
          <App />
        </AdminAuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>,
)
