import { useEffect, useState, useCallback } from 'react'
import { BrainCircuit, Files, MessageSquare } from 'lucide-react'
import { DocumentUploader } from './components/DocumentUploader'
import { DocumentList } from './components/DocumentList'
import { ChatInterface } from './components/ChatInterface'
import { documentsApi } from './services/api'
import type { Document } from './types'

export default function App() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState<'docs' | 'chat'>('docs')

  const fetchDocuments = useCallback(async () => {
    try { const { documents } = await documentsApi.list(); setDocuments(documents) }
    catch (e) { console.error('Failed to load documents', e) }
  }, [])

  useEffect(() => {
    fetchDocuments()
    const interval = setInterval(() => {
      if (documents.some(d => d.status === 'processing')) fetchDocuments()
    }, 3000)
    return () => clearInterval(interval)
  }, [fetchDocuments, documents])

  const handleUploaded = (doc: Document) => {
    setDocuments(prev => [doc, ...prev])
    const poll = setInterval(async () => {
      const updated = await documentsApi.get(doc.id)
      if (updated.status !== 'processing') {
        setDocuments(prev => prev.map(d => d.id === updated.id ? updated : d))
        clearInterval(poll)
      }
    }, 2000)
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
        <BrainCircuit className="w-7 h-7 text-brand-500" />
        <div>
          <h1 className="text-lg font-bold text-gray-900 leading-none">RAG Enterprise Assistant</h1>
          <p className="text-xs text-gray-500 mt-0.5">LangChain · pgvector · FastAPI</p>
        </div>
      </header>
      <div className="flex flex-1 overflow-hidden">
        <aside className="w-80 bg-white border-r border-gray-200 flex flex-col">
          <div className="flex border-b border-gray-200">
            {[{ key: 'docs', label: 'Documents', icon: Files }, { key: 'chat', label: 'Chat', icon: MessageSquare }].map(({ key, label, icon: Icon }) => (
              <button key={key} onClick={() => setActiveTab(key as 'docs' | 'chat')}
                className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-colors
                  ${activeTab === key ? 'text-brand-600 border-b-2 border-brand-500 bg-brand-50' : 'text-gray-500 hover:text-gray-700'}`}>
                <Icon className="w-4 h-4" />{label}
                {key === 'docs' && documents.length > 0 && (
                  <span className="ml-1 bg-brand-100 text-brand-700 text-xs font-semibold px-1.5 py-0.5 rounded-full">{documents.length}</span>
                )}
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {activeTab === 'docs' ? (
              <>
                <DocumentUploader onUploaded={handleUploaded} />
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Library</h2>
                    {selectedIds.length > 0 && (
                      <button onClick={() => setSelectedIds([])} className="text-xs text-brand-500 hover:underline">Clear</button>
                    )}
                  </div>
                  <DocumentList documents={documents} selectedIds={selectedIds}
                    onToggle={id => setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])}
                    onDelete={async id => { await documentsApi.delete(id); setDocuments(prev => prev.filter(d => d.id !== id)); setSelectedIds(prev => prev.filter(x => x !== id)) }}
                  />
                </div>
              </>
            ) : (
              <div className="text-sm text-gray-500 space-y-2">
                <p className="font-medium text-gray-700">Active filter</p>
                {selectedIds.length > 0
                  ? documents.filter(d => selectedIds.includes(d.id)).map(d => (
                    <div key={d.id} className="text-xs bg-brand-50 text-brand-700 px-2 py-1 rounded">{d.original_filename}</div>
                  ))
                  : <p className="text-xs text-gray-400">Searching all {documents.length} document(s)</p>
                }
              </div>
            )}
          </div>
        </aside>
        <main className="flex-1 flex flex-col overflow-hidden">
          <ChatInterface selectedDocumentIds={selectedIds} />
        </main>
      </div>
    </div>
  )
}
