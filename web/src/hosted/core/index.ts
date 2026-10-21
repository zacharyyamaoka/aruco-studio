// Simple Hosted Files core — framework-free (SPEC v2.2). The shadcn registry copies this folder
// verbatim into React apps, so it imports nothing but its own files and idb-keyval.

export { DISCARD, HostedFiles, MSG_CONFLICT, MSG_EMPTY, MSG_FILE_LIMIT, MSG_OFFLINE, MSG_RESTORED, MSG_UPDATED, MSG_UPDATED_BY_AGENT } from "./hosted-files.js";
export type { UiHost } from "./hosted-files.js";
export { HostedFilesError } from "./errors.js";
export { SignInFlow } from "./signin.js";
export type { SignInDefaults, SignInDriver, SignInStep, SignInView } from "./signin.js";
export type { FilesApi, SaveKind } from "./api.js";
export { copyName, daysUntil, humanSize, relativeTime, withExtension } from "./format.js";
export type {
  AccountAgentLink,
  AgentLink,
  AgentLinkMode,
  AutosaveOptions,
  AutosavePolicy,
  Content,
  CreatedAgentLink,
  Draft,
  EventName,
  FileMeta,
  HostedFilesOptions,
  LiveUpdateOptions,
  Me,
  SignInMethods,
  State,
  Status,
  User,
  VersionKind,
  VersionMeta,
} from "./types.js";
