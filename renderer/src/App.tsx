import { A2uiSurface } from '@a2ui/react/v0_9'
import type { A2uiMessage } from '@a2ui/web_core/v0_9'
import { useState } from 'react'
import { useA2uiProcessor } from '@/a2ui/useA2uiProcessor'

/**
 * A file-picker renderer for impactOS briefs. It reads a brief blueprint JSON
 * from the local disk (produced by `impactos brief`) and renders it through the
 * A2UI processor and the eight-component ShadCN catalogue. There is no server
 * and no `?file=`: the person picks the file, nothing is uploaded, and the
 * renderer never writes back into any record.
 */
export default function App() {
  const { surfaces, error, loadMessages, setError } = useA2uiProcessor()
  const [fileName, setFileName] = useState<string | null>(null)

  async function onPick(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setFileName(file.name)
    setError(null)
    try {
      const text = await file.text()
      const parsed = JSON.parse(text) as unknown
      const messages = Array.isArray(parsed)
        ? parsed
        : parsed && typeof parsed === 'object' && Array.isArray((parsed as { messages?: unknown }).messages)
          ? ((parsed as { messages: unknown[] }).messages)
          : null
      if (!messages) {
        setError('That file is not an A2UI brief: expected an array of messages.')
        return
      }
      loadMessages(messages as A2uiMessage[])
    } catch (caught) {
      setError(caught instanceof Error ? `Could not read the file: ${caught.message}` : 'Could not read the file.')
    }
  }

  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-border px-6 py-4">
        <div>
          <p className="font-mono text-[11px] tracking-[0.18em] text-muted-foreground uppercase">
            impactOS · brief · A2UI v0.9.1 · ShadCN catalog
          </p>
          <h1 className="mt-1 text-xl font-medium tracking-tight">Brief renderer</h1>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
          <input type="file" accept="application/json,.json" className="hidden" onChange={onPick} />
          {fileName ? 'Open another brief…' : 'Open a brief .json file…'}
        </label>
      </header>

      <main className="mx-auto max-w-3xl min-w-0 p-6">
        {error ? (
          <p className="mb-4 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        {surfaces.length === 0 && !error ? (
          <div className="mx-auto max-w-xl pt-16 text-center">
            <p className="font-mono text-[11px] tracking-[0.16em] text-muted-foreground uppercase">
              No brief loaded
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Run <code className="font-mono">impactos brief --company &lt;id&gt;</code> or
              {' '}<code className="font-mono">impactos brief --portfolio</code>, then open the
              {' '}<code className="font-mono">.json</code> it writes under
              {' '}<code className="font-mono">workspace/briefs/</code>.
            </p>
          </div>
        ) : (
          surfaces.map((surface) => <A2uiSurface key={surface.id} surface={surface} />)
        )}
      </main>
    </div>
  )
}
