import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { Send, Bot, User, Loader2, FileText } from 'lucide-react'
import { streamQuery } from '../services/api'
import type { ChatMessage } from '../types'

interface Props { selectedDocumentIds: string[] }

let counter = 0
const uid = () => `msg-${++counter}`

export function ChatInterface({ selectedDocumentIds }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const handleSubmit = async () => {
    const question = input.trim()
    if (!question || isLoading) return
    setInput(''); setIsLoading(true)

    const userMsg: ChatMessage = { id: uid(), role: 'user', content: question, timestamp: new Date() }
    const assistantMsg: ChatMessage = { id: uid(), role: 'assistant', content: '', timestamp: new Date(), isStreaming: true }
    setMessages(prev => [...prev, userMsg, assistantMsg])

    try {
      let fullContent = ''
      for await (const event of streamQuery({
        question,
        document_ids: selectedDocumentIds.length > 0 ? selectedDocumentIds : null,
      })) {
        if (event.type === 'sources') {
          setMessages(prev => prev.map(m => m.id === assistantMsg.id ? { ...m, sources: event.sources } : m))
          continue
        }
        fullContent += event.content
        setMessages(prev => prev.map(m => m.id === assistantMsg.id ? { ...m, content: fullContent } : m))
      }
      setMessages(prev => prev.map(m => m.id === assistantMsg.id ? { ...m, isStreaming: false } : m))
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Something went wrong'
      setMessages(prev => prev.map(m => m.id === assistantMsg.id ? { ...m, content: `⚠️ Error: ${msg}`, isStreaming: false } : m))
    } finally {
      setIsLoading(false); inputRef.current?.focus()
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-3 py-16">
            <Bot className="w-12 h-12 text-gray-300" />
            <p className="text-gray-500 font-medium">Ask anything about your documents</p>
            <p className="text-sm text-gray-400">
              {selectedDocumentIds.length > 0 ? `Searching ${selectedDocumentIds.length} selected document(s)` : 'Searching all uploaded documents'}
            </p>
          </div>
        )}
        {messages.map(msg => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'user' ? 'bg-brand-500' : 'bg-gray-200'}`}>
              {msg.role === 'user' ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-gray-600" />}
            </div>
            <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed
              ${msg.role === 'user' ? 'bg-brand-500 text-white rounded-tr-sm' : 'bg-white border border-gray-200 text-gray-800 rounded-tl-sm shadow-sm'}`}>
              {msg.role === 'assistant' ? (
                <div className="prose prose-sm max-w-none">
                  <ReactMarkdown>{msg.content || ' '}</ReactMarkdown>
                  {msg.isStreaming && <span className="inline-block w-1.5 h-4 bg-gray-500 animate-pulse ml-0.5" />}
                  {!msg.isStreaming && msg.sources && msg.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-100 not-prose space-y-1.5">
                      <p className="text-xs font-medium text-gray-400 flex items-center gap-1">
                        <FileText className="w-3 h-3" /> Sources
                      </p>
                      {msg.sources.map((s, i) => (
                        <details key={`${s.document_id}-${s.chunk_index}-${i}`} className="text-xs text-gray-500">
                          <summary className="cursor-pointer hover:text-gray-700">
                            Chunk {s.chunk_index} · doc {s.document_id.slice(0, 8)}
                          </summary>
                          <p className="mt-1 pl-3 border-l-2 border-gray-200 text-gray-500 whitespace-pre-wrap">{s.content}</p>
                        </details>
                      ))}
                    </div>
                  )}
                </div>
              ) : <p>{msg.content}</p>}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="border-t border-gray-200 p-4 bg-white">
        <div className="flex gap-3 items-end">
          <textarea ref={inputRef} value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit() } }}
            placeholder="Ask a question… (Enter to send)"
            rows={1} disabled={isLoading}
            className="flex-1 resize-none rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            style={{ minHeight: '44px', maxHeight: '140px' }}
          />
          <button onClick={handleSubmit} disabled={!input.trim() || isLoading}
            className="h-11 w-11 rounded-xl bg-brand-500 text-white flex items-center justify-center hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0">
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  )
}
