#!/usr/bin/env node
// Opens a page in a headless browser and prints what a person would see: the visible text of every frame and the
// labels of the form fields. Used when a page builds its form with JavaScript. Usage: node render.js <url>
const { chromium } = require("playwright-core");
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await (await browser.newContext({ userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36" })).newPage();
    await page.goto(process.argv[2], { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(5000);
    const frames = await Promise.all(page.frames().map(f => f.evaluate(() => {
      const label = el => (el.labels && el.labels[0] && el.labels[0].innerText) || el.getAttribute("aria-label") || el.placeholder || el.name || "";
      const fields = [...document.querySelectorAll("input, select, textarea")]
        .filter(el => !["hidden", "submit", "button", "search"].includes(el.type) && el.offsetParent !== null)
        .map(el => label(el).trim().slice(0, 60)).filter(Boolean);
      return { text: document.body ? document.body.innerText : "", fields };
    }).catch(() => ({ text: "", fields: [] }))));
    console.log(JSON.stringify({ text: frames.map(f => f.text).join(" ").replace(/\s+/g, " "), fields: [...new Set(frames.flatMap(f => f.fields))].slice(0, 25) }));
  } catch (e) {
    console.log(JSON.stringify({ error: String(e.message || e) }));
  } finally {
    await browser.close();
  }
})();
