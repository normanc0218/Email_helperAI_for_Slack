const API_BASE = process.env.PLASMO_PUBLIC_API_BASE ?? "http://localhost:8000"

// ── Token storage ─────────────────────────────────────────────────────────────

export async function getToken(): Promise<string | null> {
  return new Promise((resolve) => {
    chrome.storage.local.get("access_token", (result) => {
      resolve((result.access_token as string) ?? null)
    })
  })
}

export async function clearToken(): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.remove("access_token", resolve)
  })
}

// ── Token refresh ─────────────────────────────────────────────────────────────

/**
 * POST /auth/refresh with the current (possibly expired) session token.
 * If the Google refresh token is still valid, the backend issues a new session token.
 * Returns true on success, false if a full re-login is required.
 */
async function tryRefresh(): Promise<boolean> {
  const token = await getToken()
  if (!token) return false

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    })
    if (!res.ok) return false
    const { access_token } = await res.json() as { access_token: string }
    await new Promise<void>((resolve) =>
      chrome.storage.local.set({ access_token }, resolve)
    )
    return true
  } catch {
    return false
  }
}

// ── Fetch wrapper ─────────────────────────────────────────────────────────────

/**
 * Authenticated fetch against the backend.
 *
 * On 401:
 *   1. Attempts token refresh via /auth/refresh (Google refresh token path).
 *   2. If refresh succeeds, retries the original request once.
 *   3. If refresh fails (Google session expired), clears storage so the
 *      sidepanel's storage.onChanged listener shows the login screen.
 */
export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
  _retry = true,
): Promise<T> {
  const token = await getToken()
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  })

  if (res.status === 401 && _retry) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      // Retry once with the new token — _retry=false prevents infinite loop
      return apiFetch(path, options, false)
    }
    // Google session expired — clear storage to trigger the login screen
    await clearToken()
    throw new Error("Session expired — please sign in again")
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  return res.json() as Promise<T>
}

export function apiBase(): string {
  return API_BASE
}
