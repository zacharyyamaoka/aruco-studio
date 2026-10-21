// Where the Studio's cloud files live: Simple Hosted Files
// (/home/bam/simple-hosted-files, SPEC v2), app id "aruco-studio" (its
// server/apps.json: arucostudio.com, ".arucostudio-web.json").
// The server is VITE_HOSTED_FILES_SERVER at build time; else the live one in a
// build and a local one in dev.
// WHY localhost (not 127.0.0.1) in dev: the dev server's PUBLIC_URL is
// http://localhost:<port> (its scripts/dev.mjs), the origin the sign-in pop-up
// answers from, and the Studio on 127.0.0.1 then talks to it cross-site, as
// arucostudio.com will.

export const HOSTED_APP = "aruco-studio";
export const HOSTED_LIVE = "https://simple-hosted-files.zach-yamaoka.workers.dev";
export const HOSTED_DEV = "http://localhost:8790";

export function hostedServer(env: { VITE_HOSTED_FILES_SERVER?: string; DEV?: boolean } = import.meta.env): string {
  return (env.VITE_HOSTED_FILES_SERVER || (env.DEV ? HOSTED_DEV : HOSTED_LIVE)).replace(/\/+$/, "");
}
