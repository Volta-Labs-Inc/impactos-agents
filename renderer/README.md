# Brief renderer

A static, server-free page that displays an impactOS brief blueprint. A helper
opens the committed `dist/index.html`, picks a brief `.json` written by
`impactos brief`, and reads the card. There is no server, no `?file=`, and the
renderer never writes back into any record.

It is the A2UI POC's minimum subset: the eight-component ShadCN catalogue, the
processor hook, and the `A2uiSurface` renderer, on protocol **v0.9.1** with the
package versions pinned exactly (`@a2ui/react` 0.10.2, `@a2ui/web_core` 0.10.6).

## For helpers

Nothing to install. Open `renderer/dist/index.html` in a browser and pick a brief
file from `workspace/briefs/`. The `brief` skill does this for you.

## For maintainers

`dist/index.html` is a **committed, pre-built** single file (all JS and CSS
inlined). Rebuild it whenever `src/` or the dependencies change:

```sh
cd renderer
npm ci
npm run build        # writes dist/index.html
npm test             # Vitest smoke test: loads the fixture blueprint, renders it
npm run verify:dist  # proves the committed dist/index.html equals a fresh build
```

The build is deterministic: `npm ci && npm run build` reproduces the committed
`dist/index.html` byte-for-byte, which CI (and code review) checks. If you change
the renderer, rebuild and commit `dist/index.html` in the same change.

### Layout

- `src/a2ui/` — catalogue id, catalogue, processor hook, child list, and the
  eight components (`Text`, `Card`, `Button`, `Input`, `Select`, `Table`,
  `Column`, `Row`).
- `src/components/ui/` — the ShadCN primitives those components render.
- `src/App.tsx` — the file picker and surface renderer.
- `src/__tests__/smoke.test.tsx` — loads `fixtures/brief/company-ACME-1.blueprint.json`
  through the real processor and catalogue and asserts it renders.

The Python side (`impactos brief`) validates every blueprint against the same
v0.9.1 message schema and catalogue before writing it, so the file the renderer
loads is always well-formed.
