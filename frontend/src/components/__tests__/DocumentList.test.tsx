import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DocumentList } from '../DocumentList'
import type { Document } from '../../types'

function makeDoc(overrides: Partial<Document> = {}): Document {
  return {
    id: 'doc-1',
    filename: 'saved.txt',
    original_filename: 'report.txt',
    file_size: 2048,
    mime_type: 'text/plain',
    status: 'ready',
    chunk_count: 4,
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

describe('DocumentList', () => {
  it('shows an empty state when there are no documents', () => {
    render(<DocumentList documents={[]} selectedIds={[]} onToggle={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText(/no documents uploaded yet/i)).toBeInTheDocument()
  })

  it('renders document metadata', () => {
    const doc = makeDoc()
    render(<DocumentList documents={[doc]} selectedIds={[]} onToggle={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText('report.txt')).toBeInTheDocument()
    expect(screen.getByText('2.0 KB')).toBeInTheDocument()
    expect(screen.getByText('4 chunks')).toBeInTheDocument()
    expect(screen.getByText('Ready')).toBeInTheDocument()
  })

  it('calls onToggle when a ready document is clicked, but not a processing one', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()
    const ready = makeDoc({ id: 'ready-1', original_filename: 'ready.txt', status: 'ready' })
    const processing = makeDoc({ id: 'proc-1', original_filename: 'processing.txt', status: 'processing', chunk_count: 0 })
    render(<DocumentList documents={[ready, processing]} selectedIds={[]} onToggle={onToggle} onDelete={vi.fn()} />)

    await user.click(screen.getByText('ready.txt'))
    expect(onToggle).toHaveBeenCalledWith('ready-1')

    onToggle.mockClear()
    await user.click(screen.getByText('processing.txt'))
    expect(onToggle).not.toHaveBeenCalled()
  })

  it('calls onDelete without triggering onToggle', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()
    const onDelete = vi.fn()
    const doc = makeDoc()
    render(<DocumentList documents={[doc]} selectedIds={[]} onToggle={onToggle} onDelete={onDelete} />)

    await user.click(screen.getByRole('button'))
    expect(onDelete).toHaveBeenCalledWith('doc-1')
    expect(onToggle).not.toHaveBeenCalled()
  })
})
