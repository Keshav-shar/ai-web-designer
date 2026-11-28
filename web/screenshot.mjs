/**
 * screenshot.mjs — start next dev, take Playwright screenshots at multiple viewports, then stop.
 * Usage:  node screenshot.mjs
 * Expects: Playwright browsers cached on D:\caches\ms-playwright (or standard location)
 */
import { spawn } from "child_process";
import { chromium } from "playwright";
import { fileURLToPath } from "url";
import path from "path";
import fs from "fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(__dirname, "..", "..", ".gemini", "antigravity", "brain", "8ca1ab0f-cb93-43c7-9438-02f65db03b1d", "scratch");
const PORT = 3977;

async function waitForServer(url, timeoutMs = 60000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok || res.status === 404) return; // server is up
    } catch {}
    await new Promise(r => setTimeout(r, 1000));
  }
  throw new Error("Server did not start in time");
}

async function main() {
  // Start next dev
  const server = spawn("npx", ["next", "dev", "-p", String(PORT)], {
    cwd: path.join(__dirname),
    shell: true,
    stdio: "pipe",
    env: { ...process.env, NODE_OPTIONS: "" },
  });
  server.stdout.on("data", d => process.stdout.write(d));
  server.stderr.on("data", d => process.stderr.write(d));

  try {
    console.log(`Waiting for dev server on port ${PORT}...`);
    await waitForServer(`http://localhost:${PORT}/`);
    console.log("Server is up.");

    const browser = await chromium.launch({ headless: true });
    const widths = [390, 768, 1024, 1440];
    const pages = [
      { path: "/", name: "home" },
      { path: "/about", name: "about" },
    ];

    fs.mkdirSync(OUT, { recursive: true });

    for (const pg of pages) {
      for (const w of widths) {
        const ctx = await browser.newContext({ viewport: { width: w, height: 900 } });
        const page = await ctx.newPage();
        await page.goto(`http://localhost:${PORT}${pg.path}`, { waitUntil: "networkidle", timeout: 60000 });
        await page.waitForTimeout(1500);

        // Full page screenshot
        const fname = `${pg.name}-${w}px.png`;
        await page.screenshot({ path: path.join(OUT, fname), fullPage: true });
        console.log(`  ✓ ${fname}`);

        // If home page, check card h3 single-line
        if (pg.path === "/" && w >= 768) {
          const h3Check = await page.evaluate(() => {
            const cards = document.querySelectorAll("#prospects-title ~ * h3, [aria-labelledby='prospects-title'] h3");
            const results = [];
            for (const h3 of cards) {
              const style = getComputedStyle(h3);
              const lineHeight = parseFloat(style.lineHeight) || parseFloat(style.fontSize) * 1.08;
              const rect = h3.getBoundingClientRect();
              const singleLine = rect.height <= lineHeight * 1.3;
              const noOverflow = h3.scrollWidth <= h3.clientWidth + 1;
              results.push({
                text: h3.textContent?.trim(),
                height: Math.round(rect.height),
                lineHeight: Math.round(lineHeight),
                scrollWidth: h3.scrollWidth,
                clientWidth: h3.clientWidth,
                singleLine,
                noOverflow,
                ok: singleLine && noOverflow,
              });
            }
            return results;
          });
          console.log(`  h3 single-line check at ${w}px:`, JSON.stringify(h3Check, null, 2));
        }

        await ctx.close();
      }
    }

    await browser.close();
    console.log("\nAll screenshots saved to:", OUT);
  } finally {
    server.kill("SIGTERM");
    // force kill after 3s
    setTimeout(() => { try { server.kill("SIGKILL"); } catch {} }, 3000);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
