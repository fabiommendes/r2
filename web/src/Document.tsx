import { For, type JSX, Show } from 'solid-js'

import type { Candidate, DocNode, Finding, Inline, Ref } from './api.js'
import { refLabel, useRefs } from './refs.jsx'

/**
 * Render the typed document AST.
 *
 * Every branch is explicit and nothing is ever written as HTML: a report is
 * untrusted input, and the AST carries no markup to begin with
 * (dev/adr/0006-markdown-with-typed-blocks.md).
 */
export function Nodes(props: { nodes: DocNode[] }): JSX.Element {
  return <For each={props.nodes}>{(node) => <Node node={node} />}</For>
}

function Node(props: { node: DocNode }): JSX.Element {
  const node = props.node
  switch (node.type) {
    case 'heading':
      return <Heading depth={node.depth} children={<Inlines parts={node.children} />} />
    case 'paragraph':
      return (
        <p>
          <Inlines parts={node.children} />
        </p>
      )
    case 'list':
      return (
        <Show when={node.ordered} fallback={<ul>{listItems(node.items)}</ul>}>
          <ol>{listItems(node.items)}</ol>
        </Show>
      )
    case 'blockquote':
      return (
        <blockquote>
          <Nodes nodes={node.children} />
        </blockquote>
      )
    case 'code':
      return (
        <pre class="code" classList={{ open: node.open === true }}>
          <code>{node.value}</code>
        </pre>
      )
    case 'table':
      return (
        <div class="scroller">
          <table>
            <Show when={node.head.length > 0}>
              <thead>
                <tr>
                  <For each={node.head}>
                    {(cell) => (
                      <th>
                        <Inlines parts={cell} />
                      </th>
                    )}
                  </For>
                </tr>
              </thead>
            </Show>
            <tbody>
              <For each={node.rows}>
                {(row) => (
                  <tr>
                    <For each={row}>
                      {(cell) => (
                        <td>
                          <Inlines parts={cell} />
                        </td>
                      )}
                    </For>
                  </tr>
                )}
              </For>
            </tbody>
          </table>
        </div>
      )
    case 'thematicBreak':
      return <hr />
    case 'finding':
      return <FindingCard finding={node} />
    case 'dataTable':
      return (
        <figure class="data-table">
          <div class="scroller">
            <table>
              <thead>
                <tr>
                  <For each={node.columns}>{(column) => <th>{column}</th>}</For>
                </tr>
              </thead>
              <tbody>
                <For each={node.rows}>
                  {(row) => (
                    <tr>
                      <For each={row}>
                        {(value) => (
                          <td classList={{ numeric: typeof value === 'number' }}>
                            {value === null ? '' : String(value)}
                          </td>
                        )}
                      </For>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>
          <Show when={node.caption}>
            {(caption) => <figcaption>{caption()}</figcaption>}
          </Show>
        </figure>
      )
    case 'unknownBlock':
      return (
        <div class="unknown">
          <p class="note">
            This version does not know the <code>rl:{node.tag}</code> block.
          </p>
          <pre class="code">
            <code>{node.value}</code>
          </pre>
        </div>
      )
    case 'error':
      return (
        <div class="block-error">
          <p class="note">{node.message}</p>
          <Show when={node.value}>
            {(value) => (
              <pre class="code">
                <code>{value()}</code>
              </pre>
            )}
          </Show>
        </div>
      )
  }
}

function listItems(items: DocNode[][]): JSX.Element {
  return (
    <For each={items}>
      {(blocks) => (
        <li>
          <Nodes nodes={blocks} />
        </li>
      )}
    </For>
  )
}

function Heading(props: { depth: number; children: JSX.Element }): JSX.Element {
  switch (props.depth) {
    case 1:
      return <h1>{props.children}</h1>
    case 2:
      return <h2>{props.children}</h2>
    case 3:
      return <h3>{props.children}</h3>
    case 4:
      return <h4>{props.children}</h4>
    case 5:
      return <h5>{props.children}</h5>
    default:
      return <h6>{props.children}</h6>
  }
}

export function FindingCard(props: { finding: Finding }): JSX.Element {
  const finding = props.finding
  return (
    <section
      class="finding"
      classList={{ [finding.severity]: true, open: finding.open === true }}
      id={finding.id}
    >
      <header>
        <span class="severity">{finding.severity}</span>
        <h3>{finding.title}</h3>
        <Show when={finding.ref}>
          {(ref) => <RefLink to={ref()}>{refLabel(ref())}</RefLink>}
        </Show>
      </header>
      <Nodes nodes={finding.children} />
    </section>
  )
}

function Inlines(props: { parts: Inline[] }): JSX.Element {
  return <For each={props.parts}>{(part) => <InlinePart part={part} />}</For>
}

function InlinePart(props: { part: Inline }): JSX.Element {
  const part = props.part
  switch (part.type) {
    case 'text':
      return <>{part.value}</>
    case 'break':
      return <br />
    case 'emphasis':
      return (
        <em>
          <Inlines parts={part.children} />
        </em>
      )
    case 'strong':
      return (
        <strong>
          <Inlines parts={part.children} />
        </strong>
      )
    case 'inlineCode':
      return <code>{part.value}</code>
    case 'link':
      return (
        <a href={part.url} rel="noreferrer noopener" target="_blank">
          <Inlines parts={part.children} />
        </a>
      )
    case 'image':
      return <img src={part.url} alt={part.alt} />
    case 'refLink':
      return (
        <RefLink to={part.ref}>
          <Inlines parts={part.children} />
        </RefLink>
      )
    case 'candidate':
      return <CandidateText candidate={part.candidate} />
  }
}

/**
 * A reference becomes a link only when the server said the file is there. An
 * unresolved one is `<code>`, never an anchor: a broken link is worse than no
 * link (dev/adr/0009-markdown-it-and-detected-references.md).
 */
function RefLink(props: { to: Ref; children: JSX.Element }): JSX.Element {
  const refs = useRefs()
  const fact = () => refs?.fact(props.to.path)

  return (
    <Show
      when={fact()}
      fallback={
        <code class="ref" title={`${refLabel(props.to)} is not a file right now`}>
          {props.children}
        </code>
      }
    >
      {(found) => (
        <a
          class="ref"
          classList={{ stale: found().changed === true }}
          href={refs?.href(props.to.path, props.to.start, props.to.end) ?? '#'}
          title={title(refLabel(props.to), found().changed === true)}
        >
          {props.children}
        </a>
      )}
    </Show>
  )
}

/**
 * A path detected in prose. Unresolved, it is the text the agent wrote and
 * nothing more: no styling, because nothing here is clickable.
 */
function CandidateText(props: { candidate: Candidate }): JSX.Element {
  const refs = useRefs()
  const path = () => props.candidate.path
  const fact = () => {
    const at = path()
    return at === undefined ? undefined : refs?.fact(at)
  }

  return (
    <Show when={fact()} fallback={<>{props.candidate.raw}</>}>
      {(found) => (
        <a
          class="ref"
          classList={{ stale: found().changed === true }}
          href={
            refs?.href(
              found().path,
              props.candidate.startLine,
              props.candidate.endLine,
            ) ?? '#'
          }
          title={title(props.candidate.raw, found().changed === true)}
        >
          {props.candidate.raw}
        </a>
      )}
    </Show>
  )
}

function title(label: string, changed: boolean): string {
  return changed ? `${label}, changed after this report was written` : label
}
