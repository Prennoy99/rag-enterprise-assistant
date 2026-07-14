import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ChatInterface } from '../ChatInterface'
import { streamQuery } from '../../services/api'
import type { QueryStreamEvent } from '../../services/api'

vi.mock('../../services/api', () => ({
  streamQuery: vi.fn(),
}))

async function* eventsOf(events: QueryStreamEvent[]) {
  for (const e of events) yield e
}

describe('ChatInterface', () => {
  it('streams an answer and renders its sources', async () => {
    const user = userEvent.setup()
    vi.mocked(streamQuery).mockReturnValue(
      eventsOf([
        { type: 'sources', sources: [{ document_id: 'doc-1', chunk_index: 2, content: 'excerpt text' }] },
        { type: 'token', content: 'The answer ' },
        { type: 'token', content: 'is 42.' },
      ])
    )

    render(<ChatInterface selectedDocumentIds={[]} />)
    await user.type(screen.getByPlaceholderText(/ask a question/i), 'What is the answer?')
    await user.click(screen.getByRole('button', { name: /send message/i }))

    expect(await screen.findByText('The answer is 42.')).toBeInTheDocument()
    expect(screen.getByText(/chunk 2/i)).toBeInTheDocument()
  })

  it('shows an error message when the stream throws', async () => {
    const user = userEvent.setup()
    vi.mocked(streamQuery).mockImplementation(async function* () {
      throw new Error('Query failed: 500')
    })

    render(<ChatInterface selectedDocumentIds={[]} />)
    await user.type(screen.getByPlaceholderText(/ask a question/i), 'Hello')
    await user.click(screen.getByRole('button', { name: /send message/i }))

    expect(await screen.findByText(/Query failed: 500/)).toBeInTheDocument()
  })
})
