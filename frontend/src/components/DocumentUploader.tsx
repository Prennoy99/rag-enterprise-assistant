import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, AlertCircle } from 'lucide-react'
import { documentsApi } from '../services/api'
import type { Document } from '../types'

interface Props { onUploaded: (doc: Document) => void }

export function DocumentUploader({ onUploaded }: Props) {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0]
    if (!file) return
    setUploading(true); setError(null); setProgress(0)
    try {
      const doc = await documentsApi.upload(file, setProgress)
      onUploaded(doc)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false); setProgress(0)
    }
  }, [onUploaded])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
    },
    maxFiles: 1,
    disabled: uploading,
  })

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
          ${isDragActive ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:border-brand-400 hover:bg-gray-50'}
          ${uploading ? 'opacity-60 cursor-not-allowed' : ''}`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-3">
          {isDragActive ? <FileText className="w-10 h-10 text-brand-500" /> : <Upload className="w-10 h-10 text-gray-400" />}
          <div>
            <p className="font-medium text-gray-700">{isDragActive ? 'Drop file here' : 'Drag & drop or click to upload'}</p>
            <p className="text-sm text-gray-500 mt-1">PDF, DOCX, or TXT · Max 50MB</p>
          </div>
        </div>
      </div>
      {uploading && (
        <div className="space-y-1">
          <div className="flex justify-between text-sm text-gray-600"><span>Uploading...</span><span>{progress}%</span></div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div className="bg-brand-500 h-2 rounded-full transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}
      {error && (
        <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 rounded-lg p-3">
          <AlertCircle className="w-4 h-4 flex-shrink-0" /><span>{error}</span>
        </div>
      )}
    </div>
  )
}
