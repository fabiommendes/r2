import {
  A,
  Navigate,
  Route,
  Router,
  type RouteSectionProps,
  useParams,
} from '@solidjs/router'
import {
  createEffect,
  createResource,
  createSignal,
  For,
  type JSX,
  Show,
} from 'solid-js'

import { ApiError, listProjects, type WireProject } from './api.js'
import { FileView } from './file.jsx'
import { ProjectView } from './project.jsx'
import { ReportPane } from './report.jsx'

export function App(): JSX.Element {
  return (
    <Router root={Shell}>
      <Route path="/" component={Landing} />
      <Route path="/p/:id" component={ProjectView}>
        <Route path="/" component={Blank} />
        <Route path="/r/*path" component={ReportPane} />
        <Route path="/f" component={FileView} />
      </Route>
      <Route path="*" component={NotFound} />
    </Router>
  )
}

function Shell(props: RouteSectionProps): JSX.Element {
  const [projects] = createResource(listProjects)
  const [collapsed, setCollapsed] = createSignal(false)
  const [theme, setTheme] = createSignal(loadTheme())

  createEffect(() => {
    document.documentElement.dataset.theme = theme()
    localStorage.setItem('r2.theme', theme())
  })

  return (
    <div class="app-shell" classList={{ 'projects-collapsed': collapsed() }}>
      <header class="top">
        <button
          class="icon-button"
          type="button"
          aria-label="Toggle projects"
          onClick={() => setCollapsed((value) => !value)}
        >
          ☰
        </button>
        <A href="/" class="brand">
          r2 reports
        </A>
        <span class="top-spacer" />
        <span class="shortcut">Ctrl+P</span>
        <button
          class="theme-toggle"
          type="button"
          onClick={() => setTheme((value) => (value === 'dark' ? 'light' : 'dark'))}
        >
          {theme() === 'dark' ? 'light' : 'dark'}
        </button>
        <span class="daemon-status">live ●</span>
        <Show when={projects.error}>
          <span class="note">
            {projects.error instanceof ApiError && projects.error.status === 401
              ? 'Run r2 web open to open this page.'
              : 'The daemon is not answering.'}
          </span>
        </Show>
      </header>
      <ProjectRail projects={projects()} collapsed={collapsed()} />
      <div class="shell-main">{props.children}</div>
    </div>
  )
}

function ProjectRail(props: {
  projects: WireProject[] | undefined
  collapsed: boolean
}): JSX.Element {
  const params = useParams<{ id?: string }>()

  return (
    <aside class="project-rail">
      <div class="rail-title">projects</div>
      <Show when={props.projects} fallback={<p class="empty">Loading.</p>}>
        {(projects) => (
          <nav>
            <For each={projects()}>
              {(project) => (
                <A
                  href={`/p/${project.id}`}
                  class="project-link"
                  classList={{ active: params.id === project.id }}
                  title={project.root}
                >
                  <span class="project-initial">{initial(project.name)}</span>
                  <span class="project-name">{project.name}</span>
                </A>
              )}
            </For>
          </nav>
        )}
      </Show>
    </aside>
  )
}

/** With one project there is nothing to choose, so go straight in. */
function Landing(): JSX.Element {
  const [projects] = createResource(listProjects)

  return (
    <Show
      when={projects()}
      fallback={<p class="empty">{loadingError(projects.error)}</p>}
    >
      {(list) => (
        <Show
          when={list().length === 1 ? list()[0] : undefined}
          fallback={
            <p class="empty">
              <Show
                when={list().length > 0}
                fallback="No projects registered. Run r2 web init inside a repository."
              >
                Pick a project on the left.
              </Show>
            </p>
          }
        >
          {(only) => <Navigate href={`/p/${only().id}`} />}
        </Show>
      )}
    </Show>
  )
}

function Blank(): JSX.Element {
  return <p class="empty">Open a file or report.</p>
}

function NotFound(): JSX.Element {
  return <p class="empty">Nothing here.</p>
}

function loadTheme(): 'dark' | 'light' {
  return localStorage.getItem('r2.theme') === 'light' ? 'light' : 'dark'
}

function loadingError(error: unknown): string {
  if (error instanceof ApiError && error.status === 401)
    return 'Open this page through r2 web or pnpm dev.'
  if (error !== undefined) return 'The daemon is not answering.'
  return 'Loading.'
}

function initial(name: string): string {
  return name.trim().charAt(0).toUpperCase() || '?'
}
