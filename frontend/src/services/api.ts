import axios from 'axios'
import type { Document, QueryRequest, SourceChunk } from '../types'

export type QueryStreamEvent =
  | { type: 'token'; content: string }
  | { type: 'sources'; sources: SourceChunk[] }

const API_BASE = import.meta.env.VITE_API_URL || ''
const API_KEY = import.meta.env.VITE_API_KEY || ''
const api = axios.create({ baseURL: `${API_BASE}/api/v1`, headers: { 'X-API-Key': API_KEY } })

export const documentsApi = {
  list: async (): Promise<{ documents: Document[]; total: number }> => {
    const { data } = await api.get('/documents/')
    return data
  },
  upload: async (file: File, onProgress?: (pct: number) => void): Promise<Document> => {
    const form = new FormData()
    form.append('file', file)
    const { data } = await api.post('/documents/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    })
    return data
  },
  delete: async (id: string): Promise<void> => { await api.delete(`/documents/${id}`) },
  get: async (id: string): Promise<Document> => {
    const { data } = await api.get(`/documents/${id}`)
    return data
  },
}

export async function* streamQuery(request: QueryRequest): AsyncGenerator<QueryStreamEvent, void, unknown> {
  const response = await fetch(`${API_BASE}/api/v1/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
    body: JSON.stringify(request),
  })
  if (!response.ok || !response.body) throw new Error(`Query failed: ${response.statusText}`)

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const payload = line.slice(6)
        if (payload === '[DONE]') return
        if (payload.startsWith('[ERROR]')) throw new Error(payload.slice(8))
        if (payload.startsWith('[SOURCES] ')) {
          yield { type: 'sources', sources: JSON.parse(payload.slice(10)) }
          continue
        }
        yield { type: 'token', content: payload }
      }
    }
  }
}
