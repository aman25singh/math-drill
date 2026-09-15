import fs from "node:fs";
import { syncBuiltinESMExports } from "node:module";
import { resolve, sep } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

// Windows scanners can briefly lock freshly generated bundles. Retry only
// Astro/Vite temporary-file operations, never source files or user history.
const root = fileURLToPath(new URL("../", import.meta.url));
const generatedRoots = [
  resolve(root, ".astro/vite-cache"),
  resolve(root, "dist/.prerender"),
];
const isGenerated = (path) => {
  const target = resolve(
    path instanceof URL ? fileURLToPath(path) : String(path),
  );
  return generatedRoots.some(
    (directory) => target === directory || target.startsWith(directory + sep),
  );
};

if (process.platform === "win32") {
  const remove = fs.promises.rm.bind(fs.promises);
  fs.promises.rm = (path, options) =>
    remove(
      path,
      isGenerated(path)
        ? { ...options, maxRetries: 8, retryDelay: 100 }
        : options,
    );
  const rename = fs.promises.rename.bind(fs.promises);
  fs.promises.rename = async (from, to) => {
    if (!isGenerated(from) || !isGenerated(to)) return rename(from, to);
    for (let attempt = 0; ; attempt++) {
      try {
        return await rename(from, to);
      } catch (cause) {
        if (
          attempt >= 8 ||
          !["EBUSY", "EPERM", "ENOTEMPTY"].includes(cause.code)
        )
          throw cause;
        await delay((attempt + 1) * 100);
      }
    }
  };
  const callbackRename = fs.rename.bind(fs);
  fs.rename = (from, to, callback) => {
    if (!isGenerated(from) || !isGenerated(to))
      return callbackRename(from, to, callback);
    fs.promises.rename(from, to).then(() => callback(null), callback);
  };
  syncBuiltinESMExports();
}

const cli = new URL("../node_modules/astro/bin/astro.mjs", import.meta.url);
process.argv[1] = fileURLToPath(cli);
await import(cli.href);
