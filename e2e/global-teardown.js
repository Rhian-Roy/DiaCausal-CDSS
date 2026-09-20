/** Stops the two servers started for the tests. */

export default async function globalTeardown() {
  for (const child of [globalThis.__diacausal?.backend, globalThis.__diacausal?.frontend]) {
    if (child && child.exitCode === null) child.kill('SIGTERM')
  }
}
