// Simple Hosted Files core — framework-free (SPEC v2.2). The shadcn registry copies this folder
// verbatim into React apps, so it imports nothing but its own files and idb-keyval.

export { DISCARD, HostedFiles, MSG_CONFLICT, MSG_EMPTY, MSG_OFFLINE, MSG_RESTORED, MSG_UPDATED } from "./hosted-files.js";
export type { UiHost } from "./hosted-files.js";
export { HostedFilesError } from "./errors.js";
export type { FilesApi, SaveKind } from "./api.js";
export { daysUntil, humanSize, relativeTime, withExtension } from "./format.js";
export type {
  AutosaveOptions,
  Content,
  Draft,
  EventName,
  FileMeta,
  HostedFilesOptions,
  Me,
  State,
  Status,
  User,
  VersionMeta,
} from "./types.js";
