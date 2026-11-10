import { Component, type ReactNode } from 'react'

type Props = { label: string; children: ReactNode }

/** Keeps one broken panel from taking the whole page down. */
export class ErrorBoundary extends Component<Props, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div role="alert" className="grid min-h-[440px] place-items-center p-6 font-mono text-[11px] text-down">
        {`The ${this.props.label} stopped: ${this.state.error.message}. Reload the page.`}
      </div>
    )
  }
}
