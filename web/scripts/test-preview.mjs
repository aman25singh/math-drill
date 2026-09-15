import { preview } from "astro";

// The programmatic API stays in the foreground even in an agent environment,
// so Playwright owns this server's lifecycle instead of Astro detaching it.
const server = await preview({ server: { host: "127.0.0.1", port: 4322 } });
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, async () => {
    await server.stop();
    process.exit(0);
  });
}
