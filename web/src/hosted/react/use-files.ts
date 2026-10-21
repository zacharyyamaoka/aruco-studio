// Data hooks over hostedFiles.files.* — stale-while-revalidate, refetched whenever the session or
// the UI's revision moves (after any rename / trash / restore / duplicate / save).

import { useEffect, useState } from "react"
import type { FileMeta, VersionMeta } from "@/lib/hosted-files/core"
import { useHostedFiles, useHostedFilesUi } from "./provider"

export interface Loaded<T> {
  data: T | null
  error: string | null
  loading: boolean
}

export function useFiles(opts: { trashed?: boolean; enabled?: boolean } = {}): Loaded<FileMeta[]> {
  const { hostedFiles, state } = useHostedFiles()
  const { revision } = useHostedFilesUi()
  const enabled = opts.enabled !== false && !!state.user
  const trashed = !!opts.trashed
  const [result, setResult] = useState<Loaded<FileMeta[]>>({ data: null, error: null, loading: false })
  const key = `${state.user?.id}:${state.file?.id}:${state.file?.version}:${state.file?.name}:${state.me?.app?.files}:${state.me?.plan}`

  useEffect(() => {
    if (!enabled) {
      setResult({ data: null, error: null, loading: false })
      return
    }
    let live = true
    setResult((r) => ({ ...r, loading: true }))
    hostedFiles.files.list({ trashed }).then(
      (data) => live && setResult({ data, error: null, loading: false }),
      (err) => live && setResult((r) => ({ data: r.data, error: err instanceof Error ? err.message : String(err), loading: false })),
    )
    return () => {
      live = false
    }
  }, [hostedFiles, enabled, trashed, revision, key])

  return result
}

export function useVersions(fileId: string | null | undefined): Loaded<VersionMeta[]> {
  const { hostedFiles, state } = useHostedFiles()
  const { revision } = useHostedFilesUi()
  const [result, setResult] = useState<Loaded<VersionMeta[]>>({ data: null, error: null, loading: false })
  const headVersion = state.file?.id === fileId ? state.file?.version : undefined
  const signedIn = !!state.user

  useEffect(() => {
    if (!fileId || !signedIn) {
      setResult({ data: null, error: null, loading: false })
      return
    }
    let live = true
    setResult((r) => ({ ...r, loading: true }))
    hostedFiles.files.versions(fileId).then(
      (data) => live && setResult({ data, error: null, loading: false }),
      (err) => live && setResult((r) => ({ data: r.data, error: err instanceof Error ? err.message : String(err), loading: false })),
    )
    return () => {
      live = false
    }
  }, [hostedFiles, fileId, signedIn, revision, headVersion])

  return result
}

export function matches(file: FileMeta, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  // WHY subsequence matching: "nta" finds "Notes A" the way palette users expect.
  const name = file.name.toLowerCase()
  if (name.includes(q)) return true
  let i = 0
  for (const ch of name) if (ch === q[i]) i++
  return i === q.length
}
