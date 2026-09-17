import type { ReactComponentImplementation } from '@a2ui/react/v0_9'
import { A2uiSurface } from '@a2ui/react/v0_9'
import { MessageProcessor } from '@a2ui/web_core/v0_9'
import type { A2uiMessage } from '@a2ui/web_core/v0_9'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { render, cleanup } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { shadcnCatalog } from '@/a2ui/catalog'

// Vitest runs with the renderer directory as cwd; the fixture lives beside it.
const companyFixture = resolve(process.cwd(), '..', 'fixtures', 'brief', 'company-ACME-1.blueprint.json')

function loadFixture(path: string): A2uiMessage[] {
  return JSON.parse(readFileSync(path, 'utf8')) as A2uiMessage[]
}

function processAndRender(messages: A2uiMessage[]) {
  // Mirrors useA2uiProcessor.loadMessages: the same catalogue the page ships.
  const processor = new MessageProcessor<ReactComponentImplementation>(
    [shadcnCatalog],
    undefined,
    { version: 'v0.9.1' },
  )
  processor.processMessages(messages)
  const surface = Array.from(processor.model.surfacesMap.values())[0]
  return render(<A2uiSurface surface={surface} />)
}

afterEach(cleanup)

describe('brief renderer smoke test', () => {
  it('renders the committed company brief fixture through the catalogue', () => {
    const { container } = processAndRender(loadFixture(companyFixture))
    const text = container.textContent ?? ''
    // Profile, track and interactions all reach the DOM.
    expect(text).toContain('Aurora Robotics')
    expect(text).toContain('Profile')
    expect(text).toContain('Track position and target')
    expect(text).toContain('First Paying Customer')
    expect(text).toContain('Q2 progress review')
    expect(text).toContain('Open flags')
  })

  it('rejects a blueprint that violates the catalogue schema', () => {
    // A known component with an out-of-enum variant fails the catalogue's own
    // validation, proving this check can actually fail.
    const broken: A2uiMessage[] = [
      { version: 'v0.9.1', createSurface: { surfaceId: 'brief', catalogId: shadcnCatalog.id } },
      {
        version: 'v0.9.1',
        updateComponents: {
          surfaceId: 'brief',
          components: [
            { id: 'root', component: 'Column', children: ['x'] },
            { id: 'x', component: 'Text', text: 'nope', variant: 'huge' },
          ],
        },
      },
    ] as unknown as A2uiMessage[]
    expect(() => processAndRender(broken)).toThrow(/Text/)
  })
})
