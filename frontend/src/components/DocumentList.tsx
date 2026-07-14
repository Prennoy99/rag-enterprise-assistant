import { FileText, Trash2, CheckCircle, Clock, XCircle, Hash } from 'lucide-react'
import type { Document } from '../types'

interface Props {
  documents: Document[]
  selectedIds: string[]
  onToggle: (id: string) => void
  onDelete: (id: string) => void
}

const statusConfig = {
  ready: { icon: CheckCircle, color: 'text-green-500', label: 'Ready' },
  processing: { icon: Clock, color: 'text-amber-500', label: 'Processing' },
  failed: { icon: XCircle, color: 'text-red-500', label: 'Failed' },
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentList({ documents, selectedIds, onToggle, onDelete }: Props) {
  if (documents.length === 0) return <p className="text-sm text-gray-500 text-center py-6">No documents uploaded yet.</p>

  return (
    <ul className="space-y-2">
      {documents.map((doc) => {
        const isSelected = selectedIds.includes(doc.id)
        const { icon: StatusIcon, color, label } = statusConfig[doc.status]
        return (
          <li key={doc.id}
            onClick={() => doc.status === 'ready' && onToggle(doc.id)}
            className={`rounded-lg border p-3 transition-all cursor-pointer select-none
              ${isSelected ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:border-gray-300 bg-white'}
              ${doc.status !== 'ready' ? 'opacity-70 cursor-default' : ''}`}
          >
            <div className="flex items-start gap-3">
              <FileText className="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{doc.original_filename}</p>
                <div className="flex items-center gap-3 mt-1">
                  <span className={`flex items-center gap-1 text-xs ${color}`}>
                    <StatusIcon className="w-3 h-3" />{label}
                  </span>
                  <span className="text-xs text-gray-400">{formatSize(doc.file_size)}</span>
                  {doc.chunk_count > 0 && (
                    <span className="flex items-center gap-1 text-xs text-gray-400">
                      <Hash className="w-3 h-3" />{doc.chunk_count} chunks
                    </span>
                  )}
                </div>
              </div>
              <button onClick={(e) => { e.stopPropagation(); onDelete(doc.id) }}
                className="text-gray-400 hover:text-red-500 transition-colors p-1 rounded">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
