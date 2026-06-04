import { apiBase, clearToken, getToken } from "./client"

export type SSEEvent =
  | { type: "text"; content: string }
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; name: string; preview: string }
  | { type: "done" }
  | { type: "error"; message: string }

/**
 * Stream chat events from POST /api/chat via SSE.
 * Calls onEvent for each parsed SSE message; resolves when the stream closes.
 *
 * On 401: clears the stored token (triggers storage.onChanged → login screen)
 * and emits an error event so the UI can show a message immediately.
 */
export async function streamChat(
  message: string,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const token = await getToken()
  const res = await fetch(`${apiBase()}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message }),
    signal,
  })

  if (res.status === 401) {
    await clearToken()
    onEvent({ type: "error", message: "Session expired — please sign in again" })
    return
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "")
    onEvent({ type: "error", message: `${res.status}: ${text}` })
    return
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split("\n")
    buffer = lines.pop() ?? ""

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue
      const raw = line.slice(6).trim()
      if (!raw || raw === "[DONE]") continue
      try {
        const evt = JSON.parse(raw) as SSEEvent
        onEvent(evt)
      } catch {
        // skip malformed lines
      }
    }
  }
}
