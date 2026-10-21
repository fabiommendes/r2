import { useParams } from '@solidjs/router'
import { createEffect, createMemo, createResource, For, type JSX, Show } from 'solid-js'

import { ApiError, putMarks, readReport, type WireDocument } from './api.js'
import { Nodes } from './Document.jsx'
import { ago, useProject } from './project.jsx'
import { fileHref, RefsProvider, refsFor } from './refs.jsx'

export function ReportPane(): JSX.Element {
  const params = useParams<{ id: string; path: string }>()
  const project = useProject()

  const [document] = createResource(
    () => [params.id, params.path, project.version()] as const,
    async ([id, path]) => {
      if (id === undefined || path === undefined) return undefined
      return readReport(id, path)
    },
  )

  /**
   * Opening a report marks it read. Written once per path: a rewrite by the agent
   * bumps the version and refetches, and re-marking on every refetch would fight
   * the watcher.
   */
  const marked = new Set<string>()
  createEffect(() => {
    const loaded = document()
    if (loaded === undefined) return
    const key = `${params.id}/${loaded.path}`
    if (marked.has(key)) return
    marked.add(key)
    void putMarks(params.id ?? '', loaded.path, {
      ...(loaded.marks ?? { findings: {} }),
      read: new Date().toISOString(),
    }).catch(() => marked.delete(key))
  })

  return (
    <Show
      when={document()}
      fallback={
        <Show when={document.error} fallback={<p class="empty">Loading.</p>}>
          <p class="empty">{describeError(document.error)}</p>
        </Show>
      }
    >
      {(loaded) => (
        <RefsProvider refs={refsFor(params.id ?? '', loaded().resolutions)}>
          <article class="report">
            <header class="report-header">
              <h1>{loaded().title}</h1>
              <p class="meta">
                <span class="kind">{loaded().kind}</span>
                <span class="when">{ago(loaded().modified)}</span>
                <code class="path">{loaded().path}</code>
                <For each={loaded().tags}>
                  {(tag) => <span class="tag">{tag}</span>}
                </For>
              </p>
              <Show when={loaded().rendered.open}>
                <p class="note writing">
                  A block has no closing fence. The agent is probably still writing.
                </p>
              </Show>
              <Changed project={params.id ?? ''} document={loaded()} />
              <Show when={loaded().rendered.diagnostics.length > 0}>
                <ul class="diagnostics">
                  <For each={loaded().rendered.diagnostics}>
                    {(diagnostic) => (
                      <li class={diagnostic.severity}>
                        <Show when={diagnostic.line}>
                          {(line) => <span class="line">line {line()}</span>}
                        </Show>
                        {diagnostic.message}
                      </li>
                    )}
                  </For>
                </ul>
              </Show>
            </header>
            <Nodes nodes={loaded().rendered.nodes} />
          </article>
        </RefsProvider>
      )}
    </Show>
  )
}

/**
 * Which cited files have been touched since the report was written. One note for
 * the whole report, because a report can cite the same file ten times and ten
 * warnings say nothing the first one did not.
 */
function Changed(props: { project: string; document: WireDocument }): JSX.Element {
  const stale = createMemo(() =>
    Object.values(props.document.resolutions).filter((fact) => fact.changed === true),
  )

  return (
    <Show when={stale().length > 0}>
      <p class="note stale-note">
        Changed after this report was written, so the lines may have moved:{' '}
        <For each={stale()}>
          {(fact, index) => (
            <>
              <Show when={index() > 0}>, </Show>
              <a class="ref" href={fileHref(props.project, fact.path)}>
                {fact.path}
              </a>
            </>
          )}
        </For>
      </p>
    </Show>
  )
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return 'That report is gone.'
    if (error.status === 401) return 'Run r2 web open in this project.'
    return `The daemon said: ${error.message}`
  }
  return 'The daemon is not answering.'
}
