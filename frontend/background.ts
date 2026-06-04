// Open the side panel when the extension icon is clicked
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch(console.error)

// Intercept the OAuth success redirect and exchange the short-lived URL token
// for a full session token before storing.
//
// Flow:
//   1. backend redirects to /auth/success?token=<5-min exchange token>
//   2. we POST that token to /auth/exchange
//   3. backend validates it and returns a 7-day session token
//   4. we store the session token in chrome.storage.local and close the tab
//
// Why not store the URL token directly?
//   The exchange token has a 5-min expiry and is type-locked ("exchange"),
//   so it cannot be replayed as a session token even if the URL leaks from
//   browser history.
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete" || !tab.url) return

  let url: URL
  try { url = new URL(tab.url) } catch { return }

  const apiBase = process.env.PLASMO_PUBLIC_API_BASE ?? "http://localhost:8000"
  if (!tab.url.startsWith(`${apiBase}/auth/success`)) return

  const exchangeCode = url.searchParams.get("token")
  if (!exchangeCode) return

  try {
    const res = await fetch(`${apiBase}/auth/exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: exchangeCode }),
    })

    if (res.ok) {
      const { access_token } = await res.json() as { access_token: string }
      await chrome.storage.local.set({ access_token })
    } else {
      console.error("Token exchange failed:", res.status)
    }
  } catch (err) {
    console.error("Token exchange error:", err)
  }

  chrome.tabs.remove(tabId)
})
