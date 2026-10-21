import { useNavigate } from '@solidjs/router'
import {
  createEffect,
  createMemo,
  createResource,
  createSignal,
  For,
  type JSX,
  onCleanup,
  Show,
} from 'solid-js'

import { listFiles, type WireFileEntry, type WireSummary } from './api.js'
import { fileHref } from './refs.jsx'

interface Node {
  name: string
  path: string
  files: WireFileEntry[]
  dirs: Map<string, Node>
}

export type TreeTarget = { kind: 'file' | 'report'; path: string; title: string }

export function FilesPanel(props: {
  project: string
  version: number
  reports: WireSummary[] | undefined
  reportsPending: boolean
  open: (target: TreeTarget) => boolean
  active: (target: TreeTarget) => boolean
  focusedPath: string
  onToggle: (target: TreeTarget) => void
}): JSX.Element {
  const navigate = useNavigate()
  const [open, setOpen] = createSignal(false)
  const [query, setQuery] = createSignal('')
  const [selected, setSelected] = createSignal(0)
  const [reportsOpen, setReportsOpen] = createSignal(true)
  const [filesOpen, setFilesOpen] = createSignal(true)

  const [files] = createResource(
    () => [props.project, props.version] as const,
    ([project]) => (project === '' ? Promise.resolve([]) : listFiles(project)),
  )
  const tree = createMemo(() => buildTree(files() ?? []))
  const matches = createMemo(() => filterFiles(files() ?? [], query()).slice(0, 80))

  createEffect(() => {
    const down = (event: KeyboardEvent): void => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'p') {
        event.preventDefault()
        setOpen(true)
        setSelected(0)
      }
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', down)
    onCleanup(() => window.removeEventListener('keydown', down))
  })

  const choose = (path: string): void => {
    setOpen(false)
    navigate(fileHref(props.project, path))
  }

  return (
    <aside class="files-panel">
      <button class="quick-open-button" type="button" onClick={() => setOpen(true)}>
        Open file <kbd>Ctrl</kbd>
        <kbd>P</kbd>
      </button>

      <SectionHeader
        open={reportsOpen()}
        onClick={() => setReportsOpen(!reportsOpen())}
      >
        reports
      </SectionHeader>
      <Show when={reportsOpen()}>
        <Show
          when={props.reports !== undefined && props.reports.length > 0}
          fallback={
            <p class="tree-empty">
              <Show when={!props.reportsPending} fallback="Loading reports.">
                No reports yet.
              </Show>
            </p>
          }
        >
          <nav class="report-tree">
            <For each={props.reports}>
              {(report) => (
                <button
                  type="button"
                  class="report-node"
                  classList={{
                    active: props.active(reportTarget(report)),
                    open: props.open(reportTarget(report)),
                  }}
                  onClick={() => props.onToggle(reportTarget(report))}
                >
                  <span class="title">{report.title}</span>
                  <span class="meta">{report.kind}</span>
                </button>
              )}
            </For>
          </nav>
        </Show>
      </Show>

      <SectionHeader open={filesOpen()} onClick={() => setFilesOpen(!filesOpen())}>
        files
      </SectionHeader>
      <Show when={filesOpen()}>
        <Show when={!files.loading} fallback={<p class="tree-empty">Loading files.</p>}>
          <Directory
            node={tree()}
            project={props.project}
            depth={0}
            open={props.open}
            active={props.active}
            focusedPath={props.focusedPath}
            onToggle={props.onToggle}
            root
          />
        </Show>
      </Show>

      <Show when={open()}>
        <div class="quick-open" onClick={() => setOpen(false)}>
          <div class="quick-open-box" onClick={(event) => event.stopPropagation()}>
            <input
              autofocus
              value={query()}
              placeholder="Type a file name"
              onInput={(event) => {
                setQuery(event.currentTarget.value)
                setSelected(0)
              }}
              onKeyDown={(event) => {
                if (event.key === 'ArrowDown') {
                  event.preventDefault()
                  setSelected((n) => Math.min(n + 1, matches().length - 1))
                } else if (event.key === 'ArrowUp') {
                  event.preventDefault()
                  setSelected((n) => Math.max(n - 1, 0))
                } else if (event.key === 'Enter') {
                  const file = matches()[selected()]
                  if (file !== undefined) choose(file.path)
                }
              }}
            />
            <ul>
              <For each={matches()}>
                {(file, index) => (
                  <li>
                    <button
                      type="button"
                      classList={{ selected: index() === selected() }}
                      onMouseEnter={() => setSelected(index())}
                      onClick={() => choose(file.path)}
                    >
                      {file.path}
                    </button>
                  </li>
                )}
              </For>
            </ul>
          </div>
        </div>
      </Show>
    </aside>
  )
}

function SectionHeader(props: {
  open: boolean
  onClick: () => void
  children: JSX.Element
}): JSX.Element {
  return (
    <button class="tree-section" type="button" onClick={props.onClick}>
      <span>{props.open ? '▾' : '▸'}</span> {props.children}
    </button>
  )
}

function Directory(props: {
  node: Node
  project: string
  depth: number
  open: (target: TreeTarget) => boolean
  active: (target: TreeTarget) => boolean
  focusedPath: string
  onToggle: (target: TreeTarget) => void
  root?: boolean
}): JSX.Element {
  const [open, setOpen] = createSignal(props.root === true || props.depth < 1)
  const dirs = createMemo(() =>
    [...props.node.dirs.values()].sort((a, b) => a.name.localeCompare(b.name)),
  )

  createEffect(() => {
    if (props.root === true) return
    if (
      props.focusedPath === props.node.path ||
      props.focusedPath.startsWith(`${props.node.path}/`)
    ) {
      setOpen(true)
      queueMicrotask(() =>
        document.getElementById(treeId(props.node.path))?.scrollIntoView({
          block: 'nearest',
        }),
      )
    }
  })

  return (
    <div class="tree" style={{ '--depth': props.depth }}>
      <Show when={!props.root}>
        <button
          class="tree-dir"
          classList={{ focused: props.focusedPath === props.node.path }}
          id={treeId(props.node.path)}
          type="button"
          onClick={() => setOpen(!open())}
        >
          <span>{open() ? '▾' : '▸'}</span> {props.node.name}
        </button>
      </Show>
      <Show when={open()}>
        <For each={dirs()}>
          {(dir) => (
            <Directory
              node={dir}
              project={props.project}
              depth={props.depth + 1}
              open={props.open}
              active={props.active}
              focusedPath={props.focusedPath}
              onToggle={props.onToggle}
            />
          )}
        </For>
        <For each={props.node.files}>
          {(file) => (
            <button
              class="tree-file"
              classList={{
                active: props.active(fileTarget(file.path)),
                focused: props.focusedPath === file.path,
                open: props.open(fileTarget(file.path)),
              }}
              id={treeId(file.path)}
              type="button"
              title={file.path}
              onClick={() => props.onToggle(fileTarget(file.path))}
            >
              {file.path.split('/').at(-1)}
            </button>
          )}
        </For>
      </Show>
    </div>
  )
}

function treeId(path: string): string {
  return `tree-${encodeURIComponent(path)}`
}

function fileTarget(path: string): TreeTarget {
  return { kind: 'file', path, title: path.split('/').at(-1) ?? path }
}

function reportTarget(report: WireSummary): TreeTarget {
  return { kind: 'report', path: report.path, title: report.title }
}

function buildTree(files: WireFileEntry[]): Node {
  const root: Node = { name: '', path: '', files: [], dirs: new Map() }
  for (const file of files) {
    const parts = file.path.split('/')
    let node = root
    for (const part of parts.slice(0, -1)) {
      let child = node.dirs.get(part)
      if (child === undefined) {
        child = {
          name: part,
          path: node.path === '' ? part : `${node.path}/${part}`,
          files: [],
          dirs: new Map(),
        }
        node.dirs.set(part, child)
      }
      node = child
    }
    node.files.push(file)
  }
  for (const node of walkNodes(root))
    node.files.sort((a, b) => a.path.localeCompare(b.path))
  return root
}

function* walkNodes(node: Node): Generator<Node> {
  yield node
  for (const child of node.dirs.values()) yield* walkNodes(child)
}

function filterFiles(files: WireFileEntry[], query: string): WireFileEntry[] {
  const q = query.trim().toLowerCase()
  if (q === '') return files
  return files.filter((file) => file.path.toLowerCase().includes(q))
}
