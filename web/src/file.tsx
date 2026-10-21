import { useLocation, useNavigate, useParams, useSearchParams } from '@solidjs/router'
import {
  createEffect,
  createMemo,
  createResource,
  createSignal,
  For,
  type JSX,
  Show,
} from 'solid-js'

import { ApiError, type LineLink, readFile, type WireFile } from './api.js'
import { Nodes } from './Document.jsx'
import { type Highlight, highlight, type Span, type Style } from './highlight.js'
import { ago, useProject } from './project.jsx'
import { parseLines, type Refs, RefsProvider, refsFor } from './refs.jsx'

/**
 * One file of the working tree, with numbered lines.
 *
 * The path is a query parameter and the line range is the fragment, so the whole
 * address is one thing a human can copy out and hand to an agent
 * (docs/conventions.md, "URLs").
 */
export function FileView(): JSX.Element {
  const params = useParams<{ id: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const [search] = useSearchParams<{ path?: string }>()
  const project = useProject()
  const [source, setSource] = createSignal(false)

  const path = (): string => search.path ?? ''
  const range = createMemo(() => parseLines(location.hash))

  const [file] = createResource(
    () => [params.id, path(), project.version()] as const,
    async ([id, at]) => {
      if (id === undefined || at === '') return undefined
      return readFile(id, at)
    },
  )

  /** Bring the cited lines into view once the file is on the page. */
  createEffect(() => {
    if (file() === undefined) return
    const lines = range()
    if (lines === undefined) return
    queueMicrotask(() => {
      document
        .getElementById(`L${lines.start}`)
        ?.scrollIntoView({ block: 'center', behavior: 'auto' })
    })
  })

  const focus = (line: number): void => {
    navigate(`${location.pathname}${location.search}#L${line}`, {
      replace: true,
      scroll: false,
    })
  }

  return (
    <Show
      when={file()}
      fallback={
        <Show when={file.error} fallback={<p class="empty">Loading.</p>}>
          <p class="empty">{describeError(file.error)}</p>
        </Show>
      }
    >
      {(loaded) => (
        <article class="file">
          <header class="file-header">
            <h1>
              <Breadcrumb path={loaded().path} onFocus={project.focusTree} />
            </h1>
            <p class="meta">
              <Show when={loaded().lang}>
                {(lang) => <span class="kind">{lang()}</span>}
              </Show>
              <span class="when">changed {ago(loaded().modified)}</span>
              <span>{loaded().lines.length} lines</span>
            </p>
            <Show when={loaded().truncated}>
              <p class="note">
                This file is too long to show in full. It stops after{' '}
                {loaded().lines.length} lines.
              </p>
            </Show>
          </header>
          <Show when={loaded().rendered}>
            <div class="view-toggle" role="group" aria-label="View mode">
              <button
                type="button"
                classList={{ active: !source() }}
                onClick={() => setSource(false)}
              >
                rendered
              </button>
              <button
                type="button"
                classList={{ active: source() }}
                onClick={() => setSource(true)}
              >
                source
              </button>
            </div>
          </Show>
          <Show
            when={!source() && loaded().rendered}
            fallback={
              <Code
                file={loaded()}
                range={range()}
                refs={refsFor(params.id ?? '', loaded().resolutions)}
                onFocus={focus}
              />
            }
          >
            {(rendered) => (
              <RefsProvider refs={refsFor(params.id ?? '', loaded().resolutions)}>
                <article class="report markdown-file">
                  <Nodes nodes={rendered().nodes} />
                </article>
              </RefsProvider>
            )}
          </Show>
        </article>
      )}
    </Show>
  )
}

function Breadcrumb(props: {
  path: string
  onFocus: (path: string) => void
}): JSX.Element {
  const parts = createMemo(() => breadcrumbParts(props.path))
  return (
    <span class="breadcrumb">
      <For each={parts()}>
        {(part, index) => (
          <>
            <Show when={index() > 0}>
              <span class="sep">/</span>
            </Show>
            <button type="button" onClick={() => props.onFocus(part.path)}>
              {part.name}
            </button>
          </>
        )}
      </For>
    </span>
  )
}

function breadcrumbParts(path: string): { name: string; path: string }[] {
  const parts = path.split('/')
  return parts.map((name, index) => ({
    name,
    path: parts.slice(0, index + 1).join('/'),
  }))
}

function Code(props: {
  file: WireFile
  range: { start: number; end: number } | undefined
  refs: Refs
  onFocus: (line: number) => void
}): JSX.Element {
  // Plain text first, colours once shiki has loaded. A highlight that belongs to
  // the previous version of the file is worth less than none: the offsets are off.
  const [colours] = createResource(
    () => props.file,
    async (file) => ({
      hash: file.hash,
      colours: await highlight(file.lines, file.lang),
    }),
  )
  const coloured = (): Highlight | null | undefined => {
    const latest = colours()
    return latest?.hash === props.file.hash ? latest.colours : undefined
  }
  const linksByLine = createMemo(() => {
    const byLine = new Map<number, LineLink[]>()
    for (const link of props.file.links) {
      byLine.set(link.line, [...(byLine.get(link.line) ?? []), link])
    }
    return byLine
  })

  return (
    <div class="code-view">
      <For each={props.file.lines}>
        {(text, index) => {
          const number = index() + 1
          const inRange = (): boolean => {
            const range = props.range
            return range !== undefined && number >= range.start && number <= range.end
          }
          return (
            <div class="code-line" classList={{ hit: inRange() }} id={`L${number}`}>
              <a
                class="line-number"
                href={`#L${number}`}
                onClick={(event) => {
                  event.preventDefault()
                  props.onFocus(number)
                }}
              >
                {number}
              </a>
              <code>
                <Line
                  text={text}
                  spans={coloured()?.lines[index()]}
                  styles={coloured()?.styles}
                  links={linksByLine().get(number) ?? []}
                  refs={props.refs}
                />
              </code>
            </div>
          )
        }}
      </For>
    </div>
  )
}

/**
 * Text not covered by a span is in the default colour, which is most of a file.
 * That is why `Highlight` carries spans and a style table instead of a token per
 * word.
 */
function Line(props: {
  text: string
  spans: Span[] | undefined
  styles: Style[] | undefined
  links: LineLink[]
  refs: Refs
}): JSX.Element {
  const parts = createMemo(() =>
    linkPieces(pieces(props.text, props.spans, props.styles), props.links, props.refs),
  )
  return (
    <For each={parts()}>
      {(piece) => {
        const content = () => (
          <Show when={piece.style} fallback={<>{piece.text}</>}>
            {(style) => (
              <span
                class="tok"
                classList={{ b: style().bold === true, i: style().italic === true }}
                style={{ '--tc': style().color, '--td': style().dark }}
              >
                {piece.text}
              </span>
            )}
          </Show>
        )
        return (
          <Show when={piece.href} fallback={content()}>
            {(href) => (
              <a class="ref code-ref" href={href()}>
                {content()}
              </a>
            )}
          </Show>
        )
      }}
    </For>
  )
}

interface Piece {
  text: string
  start: number
  end: number
  style?: Style
  href?: string
}

function pieces(
  text: string,
  spans: Span[] | undefined,
  styles: Style[] | undefined,
): Piece[] {
  if (spans === undefined || spans.length === 0 || styles === undefined) {
    return [{ text, start: 0, end: text.length }]
  }

  const out: Piece[] = []
  let at = 0
  for (const [start, end, id] of spans) {
    if (start > at) out.push({ text: text.slice(at, start), start: at, end: start })
    const style = styles[id]
    const slice = text.slice(start, end)
    out.push(
      style === undefined
        ? { text: slice, start, end }
        : { text: slice, start, end, style },
    )
    at = end
  }
  if (at < text.length) out.push({ text: text.slice(at), start: at, end: text.length })
  return out
}

/** Cut the pieces at the links the server found in this line. */
function linkPieces(source: Piece[], links: LineLink[], refs: Refs): Piece[] {
  const ranges = links.map(({ start, end, candidate }) => ({
    start,
    end,
    href: refs.href(candidate.path ?? '', candidate.startLine, candidate.endLine),
  }))

  if (ranges.length === 0) return source

  const out: Piece[] = []
  for (const piece of source) {
    let at = piece.start
    for (const range of ranges) {
      if (range.end <= piece.start || range.start >= piece.end) continue
      const start = Math.max(at, range.start)
      const end = Math.min(piece.end, range.end)
      if (start > at) out.push(slicePiece(piece, at, start))
      out.push({ ...slicePiece(piece, start, end), href: range.href })
      at = end
    }
    if (at < piece.end) out.push(slicePiece(piece, at, piece.end))
  }
  return out
}

function slicePiece(piece: Piece, start: number, end: number): Piece {
  const sliced: Piece = {
    text: piece.text.slice(start - piece.start, end - piece.start),
    start,
    end,
  }
  if (piece.style !== undefined) sliced.style = piece.style
  return sliced
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return 'That file is not in the working tree.'
    if (error.status === 415) return 'That file is not text.'
    if (error.status === 400) return 'That is not a path inside the project.'
    if (error.status === 401) return 'Run r2 web open in this project to open it.'
    return `The daemon said: ${error.message}`
  }
  return 'The daemon is not answering.'
}
