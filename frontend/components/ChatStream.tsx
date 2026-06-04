import { useEffect, useRef, useState } from "react"
import { streamChat, type SSEEvent } from "~api/sse"

interface Message {
  role: "user" | "agent" | "tool" | "error"
  content: string
}

interface Props {
  messages: Message[]
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  onOrganizeDone?: () => void
}

export { type Message }

export function ChatStream({ messages, setMessages, onOrganizeDone }: Props) {
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const append = (msg: Message) =>
    setMessages((prev) => [...prev, msg])

  const appendToLast = (text: string) =>
    setMessages((prev) => {
      const copy = [...prev]
      const last = copy[copy.length - 1]
      if (last?.role === "agent") {
        copy[copy.length - 1] = { ...last, content: last.content + text }
        return copy
      }
      return [...copy, { role: "agent", content: text }]
    })

  const handleSend = async () => {
    const msg = input.trim()
    if (!msg || loading) return
    setInput("")
    setLoading(true)
    append({ role: "user", content: msg })

    const ctrl = new AbortController()
    abortRef.current = ctrl

    await streamChat(
      msg,
      (evt: SSEEvent) => {
        if (evt.type === "text") {
          appendToLast(evt.content)
        } else if (evt.type === "tool_call") {
          append({ role: "tool", content: `→ ${evt.name}(${JSON.stringify(evt.args)})` })
        } else if (evt.type === "tool_result") {
          append({ role: "tool", content: `← ${evt.name}: ${evt.preview}` })
        } else if (evt.type === "error") {
          append({ role: "error", content: evt.message })
        } else if (evt.type === "done") {
          if (msg.toLowerCase().includes("organiz")) {
            onOrganizeDone?.()
          }
        }
      },
      ctrl.signal
    )

    setLoading(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {messages.length === 0 && (
          <p className="text-gray-400 text-sm text-center mt-8">
            Try: "organize my inbox" or "show digest"
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`rounded-lg px-3 py-2 text-sm whitespace-pre-wrap break-words ${
              m.role === "user"
                ? "bg-blue-600 text-white ml-6"
                : m.role === "tool"
                  ? "bg-gray-100 text-gray-500 font-mono text-xs"
                  : m.role === "error"
                    ? "bg-red-50 text-red-600 border border-red-200"
                    : "bg-gray-50 text-gray-800 mr-6"
            }`}>
            {m.content}
          </div>
        ))}
        {loading && (
          <div className="flex gap-1 px-3 py-2 mr-6">
            <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce [animation-delay:0ms]" />
            <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce [animation-delay:150ms]" />
            <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce [animation-delay:300ms]" />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 p-3 flex gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a command..."
          rows={2}
          className="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-blue-700 transition-colors">
          Send
        </button>
      </div>
    </div>
  )
}
