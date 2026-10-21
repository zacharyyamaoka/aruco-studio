// The in-app sign-in dialog's state (SPEC v2.7). Framework-free: the Lit bar and the React
// dialog both render `view` and call these methods, so the steps, the copy and the errors are
// the same in every front-end. HostedFiles supplies the network half through SignInDriver.

import { HostedFilesError } from "./errors.js";
import type { SignInMethods, User } from "./types.js";

export type SignInStep = "choose" | "code" | "google";

export interface SignInView {
  step: SignInStep;
  // null while loading, or when the server could not be reached (then `error` says so).
  methods: SignInMethods | null;
  loading: boolean;
  appName: string;
  appIcon: string;
  serviceName: string;
  termsUrl: string;
  privacyUrl: string;
  email: string;
  busy: boolean;
  error: string | null;
  notice: string | null;
}

export interface SignInDriver {
  methods(): Promise<SignInMethods>;
  startEmail(email: string): Promise<void>;
  verifyEmail(email: string, code: string): Promise<User>;
  // Opens the Google pop-up (or leaves for the redirect fallback); `close` abandons it.
  google(): { done: Promise<User>; close: () => void };
}

export interface SignInDefaults {
  server: string;
  appId: string;
  appName?: string;
  appIcon?: string;
}

export class SignInFlow {
  view: SignInView;
  private driver: SignInDriver;
  private defaults: SignInDefaults;
  private resolve: (user: User) => void;
  private reject: (err: HostedFilesError) => void;
  private googleClose: (() => void) | null = null;
  private listeners = new Set<() => void>();
  private settled = false;

  constructor(driver: SignInDriver, defaults: SignInDefaults, resolve: (user: User) => void, reject: (err: HostedFilesError) => void) {
    this.driver = driver;
    this.defaults = defaults;
    this.resolve = resolve;
    this.reject = reject;
    this.view = {
      step: "choose",
      methods: null,
      loading: true,
      appName: defaults.appName ?? defaults.appId,
      appIcon: defaults.appIcon ?? `${defaults.server}/brand/logo.svg`,
      serviceName: "Simple Hosted Files",
      termsUrl: `${defaults.server}/terms`,
      privacyUrl: `${defaults.server}/privacy`,
      email: "",
      busy: false,
      error: null,
      notice: null,
    };
    void this.loadMethods();
  }

  get done(): boolean {
    return this.settled;
  }

  // A stable snapshot between changes (React's useSyncExternalStore needs that).
  getView = (): SignInView => this.view;

  subscribe = (fn: () => void): (() => void) => {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  };

  private patch(next: Partial<SignInView>): void {
    if (this.settled) return;
    this.view = { ...this.view, ...next };
    for (const fn of this.listeners) fn();
  }

  private async loadMethods(): Promise<void> {
    try {
      const methods = await this.driver.methods();
      const absolute = (url: string | undefined, fallback: string) => (url ? new URL(url, this.defaults.server).href : fallback);
      this.patch({
        methods,
        loading: false,
        appName: this.defaults.appName ?? methods.appName ?? this.defaults.appId,
        appIcon: this.defaults.appIcon ?? absolute(methods.logoUrl, this.view.appIcon),
        serviceName: methods.serviceName || this.view.serviceName,
        // WHY absolute: the dialog runs on the app's origin, the pages live on the server's.
        termsUrl: absolute(methods.termsUrl, this.view.termsUrl),
        privacyUrl: absolute(methods.privacyUrl, this.view.privacyUrl),
      });
    } catch (err) {
      this.patch({ loading: false, error: describe(err, "methods") });
    }
  }

  retry(): void {
    this.patch({ loading: true, error: null });
    void this.loadMethods();
  }

  // Called inside the click, so the pop-up opens as a user gesture.
  google(): void {
    if (this.view.busy) return;
    this.googleClose?.();
    const { done, close } = this.driver.google();
    this.googleClose = close;
    this.patch({ step: "google", error: null, notice: null });
    done.then(
      (user) => this.succeed(user),
      (err) => {
        if (this.googleClose !== close) return; // replaced or cancelled on purpose
        this.googleClose = null;
        this.patch({ step: "choose", error: describe(err, "google") });
      },
    );
  }

  // "Cancel" while the Google window is open: back to the choices, the dialog stays.
  cancelGoogle(): void {
    const close = this.googleClose;
    this.googleClose = null;
    close?.();
    this.patch({ step: "choose", error: null });
  }

  async startEmail(email: string): Promise<void> {
    const address = email.trim();
    if (!address) return this.patch({ error: "Enter your email address." });
    if (this.view.busy) return;
    this.patch({ email: address, busy: true, error: null, notice: null });
    try {
      await this.driver.startEmail(address);
      this.patch({ step: "code", busy: false });
    } catch (err) {
      this.patch({ busy: false, error: describe(err, "start") });
    }
  }

  async verify(code: string): Promise<void> {
    const digits = code.replace(/\s+/g, "");
    if (!digits) return this.patch({ error: "Enter the 6-digit code from the email." });
    if (this.view.busy) return;
    this.patch({ busy: true, error: null, notice: null });
    try {
      this.succeed(await this.driver.verifyEmail(this.view.email, digits));
    } catch (err) {
      this.patch({ busy: false, error: describe(err, "verify") });
    }
  }

  async resend(): Promise<void> {
    if (this.view.busy) return;
    this.patch({ busy: true, error: null, notice: null });
    try {
      await this.driver.startEmail(this.view.email);
      this.patch({ busy: false, notice: `We sent a new code to ${this.view.email}.` });
    } catch (err) {
      this.patch({ busy: false, error: describe(err, "start") });
    }
  }

  // "Use a different email": back to the first step, the address kept in the field.
  back(): void {
    this.patch({ step: "choose", busy: false, error: null, notice: null });
  }

  // × / Escape / the backdrop: signIn() rejects with `cancelled` (the bars treat it quietly).
  cancel(): void {
    if (this.settled) return;
    this.googleClose?.();
    this.googleClose = null;
    this.settled = true;
    this.reject(new HostedFilesError("cancelled", "Sign-in cancelled"));
  }

  succeed(user: User): void {
    if (this.settled) return;
    this.googleClose = null;
    this.settled = true;
    this.resolve(user);
  }
}

function describe(err: unknown, during: "methods" | "start" | "verify" | "google"): string {
  const error = err instanceof HostedFilesError ? err : null;
  if (!error || error.code === "network") return "Can't reach Simple Hosted Files. Check your connection and try again.";
  switch (error.code) {
    case "popup_closed":
      return "The Google window closed before sign-in finished.";
    case "bad_code":
      return "That code isn't right, or it has expired. Check the email, or send a new code.";
    case "rate_limited":
      return "Too many codes asked for. Wait a few minutes, then try again.";
    case "email_unavailable":
      return "Email sign-in isn't available on this server yet.";
    case "bad_request":
      if (during === "start") return "Enter a valid email address.";
  }
  return error.message;
}
