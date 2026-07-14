import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DocumentUploader } from '../DocumentUploader'
import { documentsApi } from '../../services/api'
import type { Document } from '../../types'

vi.mock('../../services/api', () => ({
  documentsApi: { upload: vi.fn() },
}))

describe('DocumentUploader', () => {
  beforeEach(() => {
    vi.mocked(documentsApi.upload).mockReset()
  })

  it('uploads a dropped file and reports it via onUploaded', async () => {
    const user = userEvent.setup()
    const uploaded: Document = {
      id: 'doc-1',
      filename: 'saved.txt',
      original_filename: 'notes.txt',
      file_size: 10,
      mime_type: 'text/plain',
      status: 'processing',
      chunk_count: 0,
      created_at: new Date().toISOString(),
    }
    vi.mocked(documentsApi.upload).mockResolvedValue(uploaded)
    const onUploaded = vi.fn()

    render(<DocumentUploader onUploaded={onUploaded} />)
    const file = new File(['hello world'], 'notes.txt', { type: 'text/plain' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, file)

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith(uploaded))
  })

  it('shows an error message when the upload fails', async () => {
    const user = userEvent.setup()
    vi.mocked(documentsApi.upload).mockRejectedValue(new Error('Upload failed: 400'))
    render(<DocumentUploader onUploaded={vi.fn()} />)

    const file = new File(['hello world'], 'notes.txt', { type: 'text/plain' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, file)

    expect(await screen.findByText('Upload failed: 400')).toBeInTheDocument()
  })
})
