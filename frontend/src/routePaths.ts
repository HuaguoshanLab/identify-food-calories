/**
 * The user H5 route contract intentionally has no React dependency. Authentication
 * redirects and route declarations must share these exact values so a future route
 * cannot accidentally become a valid post-login destination through prefix matching.
 */
export const routePaths = {
  app: '/app',
  analyze: '/app/analyze',
  records: '/app/records',
  plans: '/app/plans',
  me: '/app/me',
  account: '/app/me/account',
  sessions: '/app/me/sessions',
} as const

export const protectedRoutePaths = new Set<string>(Object.values(routePaths))
