// HostedFilesError carries the server's error code (SPEC §5) plus the client-only
// codes `network`, `popup_closed`, `empty` and `cancelled`.

export class HostedFilesError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;
  reported = false; // already shown in the status line / a dialog

  constructor(code: string, message: string, status = 0, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "HostedFilesError";
    this.code = code;
    this.status = status;
    this.details = details;
  }

  // WHY 5xx counts as retryable: the server never half-applies a write (one D1 batch),
  // so trying the same draft again can only land it once or be refused cleanly.
  // 507 storage_full is a plan answer, not an outage, so it is not retried.
  get retryable(): boolean {
    return this.code === "network" || (this.status >= 500 && this.code !== "storage_full");
  }
}
