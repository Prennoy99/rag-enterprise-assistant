import { beforeEach, describe, expect, it, vi } from 'vitest'
import { streamQuery } from '../api'

function sseResponse(chunks: string[]) {
  const encoder = new TextEncoder()
  let i = 0
  return {
    ok: true,
    statusText: 'OK',
    body: {
      getReader() {
        return {
          async read() {
            if (i < chunks.length) {
              const value = encoder.encode(chunks[i])
              i += 1
              return { done: false, value }
            }
            return { done: true, value: undefined }
          },
        }
      },
    },
  }
}

async function drain(request: { question: string; document_ids: string[] | null }) {
  const events = []
  for await (const event of streamQuery(request)) {
    events.push(event)
  }
  return events
}

describe('streamQuery', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  it('parses tokens and a SOURCES sentinel, stopping at DONE', async () => {
    const sources = [{ document_id: 'doc-1', chunk_index: 0, content: 'hi' }]
    const body = [
      `data: [SOURCES] ${JSON.stringify(sources)}\n\n`,
      'data: Hello\n\n',
      'data:  world\n\n',
      'data: [DONE]\n\n',
    ].join('')
    vi.mocked(fetch).mockResolvedValue(sseResponse([body]) as unknown as Response)

    const events = await drain({ question: 'q', document_ids: null })

    expect(events).toEqual([
      { type: 'sources', sources },
      { type: 'token', content: 'Hello' },
      { type: 'token', content: ' world' },
    ])
  })

  it('handles a data line split across two stream reads', async () => {
    vi.mocked(fetch).mockResolvedValue(
      sseResponse(['data: Hel', 'lo\n\n', 'data: [DONE]\n\n']) as unknown as Response
    )

    const events = await drain({ question: 'q', document_ids: null })

    expect(events).toEqual([{ type: 'token', content: 'Hello' }])
  })

  it('throws on an [ERROR] sentinel', async () => {
    vi.mocked(fetch).mockResolvedValue(
      sseResponse(['data: [ERROR] boom\n\n']) as unknown as Response
    )

    await expect(drain({ question: 'q', document_ids: null })).rejects.toThrow('boom')
  })

  it('throws when the response is not ok', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      statusText: 'Bad Request',
      body: null,
    } as unknown as Response)

    await expect(drain({ question: 'q', document_ids: null })).rejects.toThrow('Query failed')
  })
})
