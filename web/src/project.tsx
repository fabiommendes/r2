import type { RouteSectionProps } from '@solidjs/router'
import {
  A,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from '@solidjs/router'
import {
  createContext,
  createEffect,
  createMemo,
  createResource,
  createSignal,
  For,
  type JSX,
  onCleanup,
  Show,
  useContext,
} from 'solid-js'

import { listReports, subscribe, type WireSummary } from './api.js'
import { FilesPanel, type TreeTarget } from './files.jsx'
import { fileHref } from './refs.jsx'

interface ProjectState {
  id: () => string
  /** Bumped by every server event, so resources can depend on it. */
  version: () => number
  reports: () => WireSummary[] | undefined
  focusTree: (path: string) => void
}

interface Tab {
  kind: 'file' | 'report'
  path: string
  title: string
}

const ProjectContext = createContext<ProjectState>()

export function useProject(): ProjectState {
  const state = useContext(ProjectContext)
  if (state === undefined) throw new Error('used outside a project route')
  return state
}

export function ProjectView(props: RouteSectionProps): JSX.Element {
  const params = useParams<{ id: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const [search] = useSearchParams<{ path?: string }>()
  const [version, setVersion] = createSignal(0)
  const [tabsByProject, setTabsByProject] = createSignal(loadTabs())
  const [treeFocus, setTreeFocus] = createSignal('')

  createEffect(() => {
    const id = params.id
    if (id === undefined) return
    const close = subscribe(id, () => setVersion((n) => n + 1))
    onCleanup(close)
  })

  const [reports] = createResource(
    () => [params.id, version()] as const,
    ([id]) => (id === undefined ? Promise.resolve([]) : listReports(id)),
  )

  const state: ProjectState = {
    id: () => params.id ?? '',
    version,
    reports: () => reports(),
    focusTree: setTreeFocus,
  }

  const tabs = createMemo(() => tabsByProject()[params.id ?? ''] ?? [])
  const active = createMemo(() => currentTab(location.pathname, search.path, reports()))

  createEffect(() => {
    const project = params.id
    const tab = active()
    if (project === undefined || tab === undefined) return
    setTabsByProject((all) => saveTabs(addTab(all, project, tab)))
  })

  createEffect(() => {
    const project = params.id ?? ''
    if (active() !== undefined) return
    const fallback = tabs().at(-1)
    if (fallback !== undefined) navigate(hrefFor(project, fallback))
  })

  const toggleTarget = (target: TreeTarget): void => {
    const project = params.id ?? ''
    const tab = targetToTab(target)
    if (!tabs().some((item) => sameTab(item, tab))) {
      navigate(hrefFor(project, tab))
      return
    }

    const before = tabsByProject()
    const next = removeTab(before, project, tab)
    setTabsByProject(saveTabs(next))
    if (!sameTab(active(), tab)) return

    const fallback = tabAfterClose(before[project] ?? [], tab)
    navigate(fallback === undefined ? `/p/${project}` : hrefFor(project, fallback))
  }

  const closeTab = (tab: Tab): void => {
    const project = params.id ?? ''
    const before = tabsByProject()
    const next = removeTab(before, project, tab)
    setTabsByProject(saveTabs(next))

    if (!sameTab(active(), tab)) return
    const fallback = tabAfterClose(before[project] ?? [], tab)
    navigate(fallback === undefined ? `/p/${project}` : hrefFor(project, fallback))
  }

  return (
    <ProjectContext.Provider value={state}>
      <div class="workspace">
        <FilesPanel
          project={params.id ?? ''}
          version={version()}
          reports={reports()}
          reportsPending={reports.loading}
          open={(target) => tabs().some((tab) => sameTab(tab, targetToTab(target)))}
          active={(target) => sameTab(active(), targetToTab(target))}
          focusedPath={treeFocus()}
          onToggle={toggleTarget}
        />
        <main class="content">
          <Tabs
            project={params.id ?? ''}
            tabs={tabs()}
            active={active()}
            onClose={closeTab}
          />
          <div class="viewer-pane">{props.children}</div>
        </main>
      </div>
    </ProjectContext.Provider>
  )
}

function Tabs(props: {
  project: string
  tabs: Tab[]
  active: Tab | undefined
  onClose: (tab: Tab) => void
}): JSX.Element {
  let scroller: HTMLDivElement | undefined
  const scroll = (by: number): void => {
    scroller?.scrollBy({ left: by, behavior: 'smooth' })
  }

  return (
    <div class="tabs-wrap">
      <button
        class="tab-scroll"
        type="button"
        aria-label="Scroll tabs left"
        onClick={() => scroll(-240)}
      >
        ‹
      </button>
      <div class="tabs" role="tablist" ref={scroller}>
        <Show
          when={props.tabs.length > 0}
          fallback={<span class="tab empty-tab">no tabs</span>}
        >
          <For each={props.tabs}>
            {(tab) => (
              <span class="tab" classList={{ active: sameTab(props.active, tab) }}>
                <A href={hrefFor(props.project, tab)} title={tab.path}>
                  {tab.title}
                </A>
                <button
                  type="button"
                  aria-label={`Close ${tab.title}`}
                  onClick={() => props.onClose(tab)}
                >
                  ×
                </button>
              </span>
            )}
          </For>
        </Show>
      </div>
      <button
        class="tab-scroll"
        type="button"
        aria-label="Scroll tabs right"
        onClick={() => scroll(240)}
      >
        ›
      </button>
    </div>
  )
}

function targetToTab(target: TreeTarget): Tab {
  return { kind: target.kind, path: target.path, title: target.title }
}

function currentTab(
  pathname: string,
  filePath: string | undefined,
  reports: WireSummary[] | undefined,
): Tab | undefined {
  if (pathname.includes('/f') && filePath !== undefined && filePath !== '') {
    return { kind: 'file', path: filePath, title: basename(filePath) }
  }

  const marker = '/r/'
  const at = pathname.indexOf(marker)
  if (at >= 0) {
    const path = decodeURIComponent(pathname.slice(at + marker.length))
    const report = reports?.find((item) => item.path === path)
    return { kind: 'report', path, title: report?.title ?? basename(path) }
  }

  return undefined
}

function hrefFor(project: string, tab: Tab): string {
  if (tab.kind === 'file') return fileHref(project, tab.path)
  return `/p/${project}/r/${tab.path}`
}

function addTab(
  all: Record<string, Tab[]>,
  project: string,
  tab: Tab,
): Record<string, Tab[]> {
  const tabs = all[project] ?? []
  const index = tabs.findIndex((item) => sameTab(item, tab))
  if (index < 0) return { ...all, [project]: [...tabs, tab] }

  const updated = [...tabs]
  updated[index] = tab
  return { ...all, [project]: updated }
}

function removeTab(
  all: Record<string, Tab[]>,
  project: string,
  tab: Tab,
): Record<string, Tab[]> {
  return {
    ...all,
    [project]: (all[project] ?? []).filter((item) => !sameTab(item, tab)),
  }
}

function tabAfterClose(tabs: Tab[], closed: Tab): Tab | undefined {
  const index = tabs.findIndex((tab) => sameTab(tab, closed))
  if (index < 0) return tabs.at(-1)
  return tabs[index + 1] ?? tabs[index - 1]
}

function sameTab(a: Tab | undefined, b: Tab | undefined): boolean {
  return a !== undefined && b !== undefined && a.kind === b.kind && a.path === b.path
}

function loadTabs(): Record<string, Tab[]> {
  try {
    const raw = localStorage.getItem('r2.tabs')
    if (raw === null) return {}
    const parsed = JSON.parse(raw) as unknown
    if (typeof parsed !== 'object' || parsed === null) return {}
    return parsed as Record<string, Tab[]>
  } catch {
    return {}
  }
}

function saveTabs(tabs: Record<string, Tab[]>): Record<string, Tab[]> {
  localStorage.setItem('r2.tabs', JSON.stringify(tabs))
  return tabs
}

function basename(path: string): string {
  return path.split('/').at(-1) ?? path
}

export function ago(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000))
  if (seconds < 45) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}
