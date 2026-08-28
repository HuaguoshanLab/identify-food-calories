import { SessionList } from '@/auth/SessionList'

/**
 * SessionList owns the TanStack Query key and mutations. This route component deliberately only
 * composes it so a second cache or duplicate request cannot drift from the authoritative list.
 */
export function SessionsDetailsPage() {
  return <SessionList />
}
