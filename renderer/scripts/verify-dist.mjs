// Proves the committed dist/index.html equals a fresh production build.
// Builds into a throwaway directory and byte-compares. Run after `npm ci`:
//   npm run verify:dist
// Exits non-zero (and prints how to fix) if the committed build is stale.
import { execFileSync } from 'node:child_process'
import { readFileSync, rmSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const committed = fileURLToPath(new URL('../dist/index.html', import.meta.url))
const verifyDir = fileURLToPath(new URL('../.dist-verify', import.meta.url))
const verifyFile = fileURLToPath(new URL('../.dist-verify/index.html', import.meta.url))

rmSync(verifyDir, { recursive: true, force: true })
execFileSync('npx', ['vite', 'build', '--outDir', '.dist-verify', '--emptyOutDir'], {
  cwd: root,
  stdio: 'inherit',
})

const committedBytes = readFileSync(committed)
const freshBytes = readFileSync(verifyFile)
rmSync(verifyDir, { recursive: true, force: true })

if (Buffer.compare(committedBytes, freshBytes) !== 0) {
  console.error(
    '\nrenderer/dist/index.html is STALE: it does not match a fresh build.\n' +
      'Rebuild and commit it:  cd renderer && npm ci && npm run build\n',
  )
  process.exit(1)
}
console.log('renderer/dist/index.html matches a fresh build.')
