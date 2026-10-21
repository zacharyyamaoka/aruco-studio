// The app's last line (arucostudio.com went blank, 2026-10-21: React #185 in
// the floating panel): an error React cannot draw past shows this, never an
// empty page, and is logged with the components it happened in. Reload
// carries on where the viewer was (the document is in this browser's working
// copy, and signed in its cloud file); a blank document gets them working
// again when the one they were on is what fails.
import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "@bam/ui";
import { hostedFiles } from "../hosted/hosted";
import "./crash.css";

interface State { error: Error | null; busy: boolean }

export class CrashBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null, busy: false };

  static getDerivedStateFromError(error: unknown): Partial<State> {
    return { error: error instanceof Error ? error : new Error(String(error)) };
  }

  componentDidCatch(error: unknown, info: ErrorInfo): void {
    console.error("ArUco Studio stopped on an error:", error, info.componentStack);
  }

  // WHY File › New's way: it leaves the cloud file first (saved), so autosave
  // never writes the blank document into the file that was open
  private blank = async (): Promise<void> => {
    this.setState({ busy: true });
    try {
      await hostedFiles().newFile();
    } catch (err) {
      console.error("ArUco Studio: a blank document could not be opened:", err);
    }
    this.setState({ error: null, busy: false });
  };

  render(): ReactNode {
    const { error, busy } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="crash" role="alert" data-testid="crash">
        <div className="crash-card">
          <h1 className="crash-title">Something went wrong</h1>
          <p className="crash-text">ArUco Studio hit an error it could not get past. Reload to carry on where you were: your document is kept.</p>
          <div className="crash-actions">
            <Button variant="primary" testid="crash-reload" onClick={() => window.location.reload()}>Reload</Button>
            <Button testid="crash-blank" disabled={busy} onClick={() => void this.blank()}>Open a blank document</Button>
          </div>
          <details className="crash-detail">
            <summary>Details</summary>
            <pre data-testid="crash-message">{error.message}</pre>
          </details>
        </div>
      </div>
    );
  }
}
