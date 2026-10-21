import type { BundledLanguage, Highlighter, ThemedToken } from 'shiki'

/**
 * Syntax colours for a file, computed in the browser.
 *
 * Both themes are tokenized in one pass. A style is a light colour and a dark one,
 * and the stylesheet picks by theme, so switching theme repaints with no work here.
 */
export interface Style {
  color: string
  dark: string
  bold?: boolean
  italic?: boolean
}

/** `[start, end, style]`: UTF-16 offsets into the line and an index into `styles`. */
export type Span = [start: number, end: number, style: number]

export interface Highlight {
  styles: Style[]
  /** One list of spans per line, in the order of the file. */
  lines: Span[][]
}

const LIGHT = 'github-light'
const DARK = 'github-dark'

let starting: Promise<Highlighter> | null = null
const ready = new Set<string>()
const unavailable = new Set<string>()

/**
 * One highlighter for the whole page, created on first use.
 *
 * Shiki is loaded with a dynamic import so a visitor who never opens a file does
 * not download it, and languages load on demand for the same reason.
 */
function highlighter(): Promise<Highlighter> {
  starting ??= (async () => {
    const { createHighlighter } = await import('shiki')
    return createHighlighter({ themes: [LIGHT, DARK], langs: [] })
  })()
  return starting
}

/** `null` when there is no grammar for `lang`: the file shows as plain text. */
export async function highlight(
  lines: string[],
  lang: string | undefined,
): Promise<Highlight | null> {
  if (lang === undefined || unavailable.has(lang)) return null

  const shiki = await highlighter()
  if (!ready.has(lang)) {
    try {
      await shiki.loadLanguage(lang as BundledLanguage)
      ready.add(lang)
    } catch {
      unavailable.add(lang)
      return null
    }
  }

  const result = shiki.codeToTokens(lines.join('\n'), {
    lang: lang as BundledLanguage,
    themes: { light: LIGHT, dark: DARK },
  })

  // Text in the default colour carries no span: it is most of a file, and the UI
  // renders the gaps between spans with the colour it already has.
  const base = defaultStyle(result.fg ?? '')
  const styles: Style[] = []
  const indexOf = new Map<string, number>()
  const out: Span[][] = []

  for (const line of result.tokens) {
    const spans: Span[] = []
    let offset = 0
    for (const token of line) {
      const start = offset
      offset += token.content.length
      if (token.content.length === 0) continue

      const style = styleOf(token)
      if (style === null || sameStyle(style, base)) continue

      const id = intern(style, styles, indexOf)
      const last = spans.at(-1)
      if (last !== undefined && last[1] === start && last[2] === id) last[1] = offset
      else spans.push([start, offset, id])
    }
    out.push(spans)
  }

  return { styles, lines: out }
}

function intern(style: Style, styles: Style[], indexOf: Map<string, number>): number {
  const key = `${style.color}|${style.dark}|${style.bold ?? ''}|${style.italic ?? ''}`
  const known = indexOf.get(key)
  if (known !== undefined) return known
  const id = styles.length
  styles.push(style)
  indexOf.set(key, id)
  return id
}

/**
 * With two themes shiki puts both colours in `htmlStyle`, as the inline style it
 * would have written: `color` for light and `--shiki-dark` for dark.
 */
function styleOf(token: ThemedToken): Style | null {
  const raw = token.htmlStyle
  if (raw === undefined || typeof raw === 'string') return null
  const color = raw.color
  const dark = raw['--shiki-dark']
  if (color === undefined || dark === undefined) return null

  const style: Style = { color, dark }
  if (raw['font-weight'] === 'bold') style.bold = true
  if (raw['font-style'] === 'italic') style.italic = true
  return style
}

/** `fg` is the declaration shiki would have written: `#24292e;--shiki-dark:#e1e4e8`. */
function defaultStyle(fg: string): Style | null {
  const [color, ...rest] = fg.split(';')
  const dark = rest
    .map((part) => part.split(':').slice(1).join(':'))
    .find((value) => value !== '')
  if (color === undefined || dark === undefined) return null
  return { color, dark }
}

function sameStyle(style: Style, base: Style | null): boolean {
  if (base === null) return false
  return (
    style.bold === undefined &&
    style.italic === undefined &&
    style.color.toLowerCase() === base.color.toLowerCase() &&
    style.dark.toLowerCase() === base.dark.toLowerCase()
  )
}
