import { protectedRoutePaths, routePaths } from '../routePaths'

/**
 * A login redirect is navigation input, not an authority decision. Accept only the
 * exact registered user routes so an attacker cannot turn authentication into an
 * open redirect or surface a future admin route in the user H5.
 */
export function parseReturnTo(candidate: string | null | undefined) {
  if (!candidate || !candidate.startsWith('/') || candidate.startsWith('//') || candidate.includes('\\')) {
    return routePaths.app
  }

  try {
    const parsed = new URL(candidate, 'http://food-agent.local')
    if (
      parsed.origin !== 'http://food-agent.local' ||
      parsed.hash ||
      !protectedRoutePaths.has(parsed.pathname)
    ) {
      return routePaths.app
    }
    return `${parsed.pathname}${parsed.search}`
  } catch {
    return routePaths.app
  }
}

export function loginHrefFor(location: { pathname: string; search: string }) {
  const returnTo = parseReturnTo(`${location.pathname}${location.search}`)
  return `/login?returnTo=${encodeURIComponent(returnTo)}`
}
