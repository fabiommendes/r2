import { createContext, type JSX, useContext } from 'solid-js'

import type { FileFact, Ref, Resolutions } from './api.js'

/**
 * How a rendered document turns a reference into a link.
 *
 * `Document.tsx` knows nothing about routes and nothing about which files exist.
 * It asks this, and with no provider the answer is always "not a link", which is
 * the right default for a component that renders untrusted input.
 */
export interface Refs {
  fact(path: string): FileFact | undefined
  href(path: string, start?: number, end?: number): string
}

const RefsContext = createContext<Refs>()

export function RefsProvider(props: {
  refs: Refs
  children: JSX.Element
}): JSX.Element {
  return (
    <RefsContext.Provider value={props.refs}>{props.children}</RefsContext.Provider>
  )
}

export function useRefs(): Refs | undefined {
  return useContext(RefsContext)
}

/**
 * Resolution backed by what the server said about one report. A link goes to
 * the file the server found, which differs from what the document says for a
 * relative path, an absolute one, or the stem of an issue.
 */
export function refsFor(project: string, resolutions: Resolutions): Refs {
  return {
    fact: (path) => resolutions[path],
    href: (path, start, end) =>
      fileHref(project, resolutions[path]?.path ?? path, start, end),
  }
}

export function fileHref(
  project: string,
  path: string,
  start?: number,
  end?: number,
): string {
  const base = `/p/${project}/f?path=${encodeURIComponent(path)}`
  if (start === undefined) return base
  if (end === undefined || end === start) return `${base}#L${start}`
  return `${base}#L${start}-${end}`
}

/** `#L10-40` to a range. Anything else is no range at all. */
export function parseLines(hash: string): { start: number; end: number } | undefined {
  const m = /^#L(\d+)(?:-L?(\d+))?$/.exec(hash)
  if (m === null) return undefined
  const start = Number(m[1])
  const end = m[2] === undefined ? start : Number(m[2])
  if (start < 1 || end < start) return undefined
  return { start, end }
}

export function refLabel(ref: Ref): string {
  if (ref.start === undefined) return ref.path
  if (ref.end !== undefined && ref.end !== ref.start) {
    return `${ref.path}:${ref.start}-${ref.end}`
  }
  if (ref.column !== undefined) return `${ref.path}:${ref.start}:${ref.column}`
  return `${ref.path}:${ref.start}`
}
