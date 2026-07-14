import axios from 'axios'
import type { Document, QueryRequest } from '../types'

const API_BASE = import.meta.env.VITE_API_URL || ''
const api = axios.create({ baseURL: `${API_BASE}/api/v1` })

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

export async function* streamQuery(request: QueryRequest): AsyncGenerator<string, void, unknown> {
  const response = await fetch(`${API_BASE}/api/v1/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok || !response.body) throw new Error(`Query failed: ${response.statusText}`)

  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const lines = decoder.decode(value, { stream: true }).split('\n')
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const token = line.slice(6)
        if (token === '[DONE]') return
        if (token.startsWith('[ERROR]')) throw new Error(token.slice(8))
        yield token
      }
    }
  }
}
