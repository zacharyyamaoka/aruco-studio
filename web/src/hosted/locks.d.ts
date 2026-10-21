// The core (./core, verbatim) is typed against TypeScript 7's DOM library,
// where LockManager.request unwraps an async callback's promise; TypeScript
// 5.9's says Promise<Promise<T>> (core/drafts.ts underAppLock). This adds the
// unwrapping overload. Delete it once the core no longer needs it upstream.
interface LockManager {
  request<T>(name: string, callback: (lock: Lock | null) => Promise<T>): Promise<T>;
  request<T>(name: string, options: LockOptions, callback: (lock: Lock | null) => Promise<T>): Promise<T>;
}
