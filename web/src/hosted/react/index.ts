// React bindings for Simple Hosted Files (SPEC v2.5): the provider, the hooks and the status
// vocabulary. The shared dialogs live in @/components/hosted-files/dialogs.

export {
  HostedFilesProvider,
  HostedFilesUiStore,
  useHostedFiles,
  useHostedFilesActions,
  useHostedFilesContext,
  useHostedFilesUi,
  type HostedFilesActions,
  type HostedFilesProviderProps,
  type NameAnswer,
  type Panel,
  type UiHost,
  type UiSnapshot,
} from "./provider"
export { describeStatus, StatusGlyph, STATUS_ICON, TONE_CLASS, useStatus, type StatusKind, type StatusView } from "./status"
export { matches, useFiles, useVersions, type Loaded } from "./use-files"
