import createClient from 'openapi-fetch'

import type { components, paths } from './api.gen.js'

/**
 * The wire types come from the OpenAPI schema of the Python models
 * (`pnpm run gen`), never written by hand. These aliases only give the generated
 * names a short form. An optional field is absent on the wire, never `null`.
 */
type Schemas = components['schemas']

export type Candidate = Schemas['Candidate']
export type DocNode = Schemas['DocNode']
export type FileFact = Schemas['FileFact']
export type Finding = Schemas['Finding']
export type Inline = Schemas['Inline']
export type LineLink = Schemas['LineLink']
export type Ref = Schemas['Ref']
export type RenderedReport = Schemas['RenderedReport']
export type Resolutions = Schemas['Resolutions']
export type ReviewMarks = Schemas['ReviewMarks']
export type WireDocument = Schemas['WireDocument']
export type WireEvent = Schemas['WireEvent']
export type WireFile = Schemas['WireFile']
export type WireFileEntry = Schemas['WireFileEntry']
export type WireProject = Schemas['WireProject']
export type WireSummary = Schemas['WireSummary']

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
  }
}

/**
 * The cookie carries the token, so nothing here handles credentials. A 401 means
 * the browser arrived without going through `/auth`, which `r2 web` does for you.
 */
const client = createClient<paths>({ baseUrl: '' })

interface Reply<T> {
  data?: T
  error?: unknown
  response: Response
}

/**
 * Failures from the daemon are plain text (`plain_errors` in `r2/web/app.py`), so
 * the status and the body are all there is to report.
 */
function unwrap<T>({ data, error, response }: Reply<T>): T {
  if (data !== undefined) return data
  const text = typeof error === 'string' ? error.trim() : ''
  throw new ApiError(response.status, text || response.statusText)
}

export const listProjects = async (): Promise<WireProject[]> =>
  unwrap(await client.GET('/api/projects'))

export const listReports = async (project: string): Promise<WireSummary[]> =>
  unwrap(
    await client.GET('/api/p/{project}/reports', { params: { path: { project } } }),
  )

/**
 * Paths travel as a query parameter rather than as path segments. A report path
 * and a file path both contain slashes, and one parameter is one decoding step
 * (dev/adr/0013-paths-as-query-parameters.md).
 */
export const readReport = async (
  project: string,
  path: string,
): Promise<WireDocument> =>
  unwrap(
    await client.GET('/api/p/{project}/report', {
      params: { path: { project }, query: { path } },
    }),
  )

export const listFiles = async (project: string): Promise<WireFileEntry[]> =>
  unwrap(await client.GET('/api/p/{project}/files', { params: { path: { project } } }))

export const readFile = async (project: string, path: string): Promise<WireFile> =>
  unwrap(
    await client.GET('/api/p/{project}/file', {
      params: { path: { project }, query: { path } },
    }),
  )

export const putMarks = async (
  project: string,
  path: string,
  marks: ReviewMarks,
): Promise<ReviewMarks> =>
  unwrap(
    await client.PUT('/api/p/{project}/marks', {
      params: { path: { project }, query: { path } },
      body: marks,
    }),
  )

/** The SSE event name is the event's `type`, so these are the names to listen to. */
const EVENT_TYPES = [
  'report',
  'report-removed',
  'marks',
  'projects',
] as const satisfies readonly WireEvent['type'][]

/**
 * Subscribe to a project's events. Returns a function that closes the stream.
 * The browser reconnects on its own, which is why nothing here retries.
 */
export function subscribe(
  project: string,
  onEvent: (event: WireEvent) => void,
): () => void {
  const source = new EventSource(`/api/p/${encodeURIComponent(project)}/stream`)
  const handler = (message: MessageEvent<string>): void => {
    try {
      onEvent(JSON.parse(message.data) as WireEvent)
    } catch {
      // A frame we do not understand is not worth breaking the page over.
    }
  }
  for (const type of EVENT_TYPES) {
    source.addEventListener(type, handler as EventListener)
  }
  return () => source.close()
}
