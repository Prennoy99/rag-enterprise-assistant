export interface Document {
  id: string
  filename: string
  original_filename: string
  file_size: number
  mime_type: string
  status: 'processing' | 'ready' | 'failed'
  chunk_count: number
  created_at: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  isStreaming?: boolean
  sources?: SourceChunk[]
}

export interface QueryRequest {
  question: string
  document_ids?: string[] | null
}

export interface SourceChunk {
  document_id: string
  chunk_index: number
  content: string
}
