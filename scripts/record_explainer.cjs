#!/usr/bin/env node
// Screenshots and a narrated video of the explainer page (docs/midsem/explainer/).
// Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
//
// Run scripts/make_explainer.py first (it writes narration/full.wav). Then:
//   node scripts/record_explainer.cjs --shots out/dir            one picture per scene + phone views
//   node scripts/record_explainer.cjs --video docs/midsem/DiaCausal_explainer.mp4
// Options: --fonts DIR   serve Google Fonts from DIR/map.json (made offline) instead of the network
//          CHROMIUM_PATH  a Chromium to use (default: Playwright's own)
// Needs Playwright (the copy in e2e/node_modules) and ffmpeg.
"use strict";
const fs = require("fs");
const path = require("path");
const http = require("http");
const { execFileSync } = require("child_process");
const { chromium } = require(path.join(__dirname, "..", "e2e", "node_modules", "playwright"));

const DIR = path.join(__dirname, "..", "docs", "midsem", "explainer");
const arg = (name) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : null; };
const TYPES = { ".html": "text/html; charset=utf-8", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".css": "text/css", ".woff2": "font/woff2" };

function serve() {
  const server = http.createServer((req, res) => {
    const rel = decodeURIComponent(new URL(req.url, "http://x").pathname).replace(/^\/+/, "") || "index.html";
    const file = path.join(DIR, rel);
    if (!file.startsWith(DIR) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((ok) => server.listen(0, "127.0.0.1", () => ok(server)));
}

async function routeFonts(context) {
  const dir = arg("--fonts");
  if (!dir) return;
  const map = JSON.parse(fs.readFileSync(path.join(dir, "map.json"), "utf8"));
  await context.route(/https:\/\/fonts\.(googleapis|gstatic)\.com\/.*/, (route) => {
    const url = route.request().url();
    if (url.startsWith(map.css_url_prefix)) return route.fulfill({ contentType: "text/css", body: fs.readFileSync(path.join(dir, map.css)) });
    const file = map.files[url];
    return file ? route.fulfill({ contentType: "font/woff2", body: fs.readFileSync(path.join(dir, file)) }) : route.abort();
  });
}

(async () => {
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}/index.html`;
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  try {
    const shots = arg("--shots");
    if (shots) {
      fs.mkdirSync(shots, { recursive: true });
      for (const [name, viewport, scheme] of [["desktop", { width: 1280, height: 900 }, "light"], ["phone", { width: 390, height: 844 }, "light"], ["dark", { width: 1280, height: 900 }, "dark"]]) {
        const context = await browser.newContext({ viewport, deviceScaleFactor: 1, colorScheme: scheme });
        await routeFonts(context);
        const page = await context.newPage();
        const errors = [];
        page.on("pageerror", (e) => errors.push(e.message));
        page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
        await page.goto(base);
        await page.evaluate(() => document.fonts.ready);
        const chips = page.locator("#chips button");
        const n = await chips.count();
        for (let i = 0; i < n; i++) {
          if (name !== "desktop" && ![0, 3, 8, 11].includes(i)) continue;
          await chips.nth(i).click();
          await page.waitForTimeout(1600);
          await page.locator("#stage").screenshot({ path: path.join(shots, `${name}-scene${String(i + 1).padStart(2, "0")}.png`) });
        }
        await chips.nth(0).click();
        await page.screenshot({ path: path.join(shots, `${name}-page.png`), fullPage: true });
        console.log(name, "errors:", errors.length ? errors : "none");
        await context.close();
      }
    }

    const video = arg("--video");
    if (video) {
      const tmp = fs.mkdtempSync(path.join(require("os").tmpdir(), "explainer-"));
      const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: tmp, size: { width: 1280, height: 720 } } });
      await routeFonts(context);
      const created = Date.now();
      const page = await context.newPage();
      await page.goto(base + "#record");
      await page.waitForFunction(() => window.__rec && window.__rec.t0Wall, null, { timeout: 30000 });
      const rec = await page.evaluate(() => window.__rec);
      console.log(`recording ${(rec.total / 60).toFixed(1)} min …`);
      await page.waitForFunction(() => window.__rec.done === true, null, { timeout: (rec.total + 120) * 1000, polling: 1000 });
      const offset = (rec.t0Wall - created) / 1000;
      await context.close();
      const webm = fs.readdirSync(tmp).find((f) => f.endsWith(".webm"));
      execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-ss", offset.toFixed(3), "-i", path.join(tmp, webm),
        "-i", path.join(DIR, "narration", "full.wav"), "-map", "0:v", "-map", "1:a", "-t", rec.total.toFixed(3),
        "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p", "-r", "25",
        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", video], { stdio: "inherit" });
      fs.rmSync(tmp, { recursive: true, force: true });
      console.log("wrote", video, `(offset ${offset.toFixed(2)} s)`);
    }
  } finally {
    await browser.close();
    server.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });
