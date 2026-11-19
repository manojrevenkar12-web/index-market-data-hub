import { Component, type ReactNode } from "react";

/** A render error shows a message and a way back instead of a blank page. */
export class Boundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="mx-auto flex max-w-prose flex-col gap-3 p-7">
        <p className="text-lead font-semibold text-ink">This view stopped working.</p>
        <p>{this.state.error.message}</p>
        <button
          type="button"
          className="self-start rounded-soft bg-ink px-4 py-2 font-semibold text-sheet"
          onClick={() => this.setState({ error: null })}
        >
          Reload the view
        </button>
      </div>
    );
  }
}
