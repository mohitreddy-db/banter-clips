import puppeteer from "puppeteer-core";
import { readFileSync } from "fs";
const OUT = "/home/mohit/.claude/jobs/61cf1cf9/tmp/shots";
const SCRATCH = "/tmp/claude-1000/-home-mohit-Documents-appx-banter-clips/61cf1cf9-91da-451e-91d7-c9150f4343c6/scratchpad";
const url = readFileSync(`${SCRATCH}/checkout-url.txt`, "utf8").trim();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({ executablePath: "/usr/bin/google-chrome", headless: "new", args: ["--no-sandbox"] });
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 1000 });
await page.goto(url, { waitUntil: "networkidle2", timeout: 60000 });
await sleep(2500);
await page.screenshot({ path: `${OUT}/50-stripe-checkout.png` });

const typeIf = async (sel, val) => {
  const el = await page.$(sel);
  if (el) { await el.click({ clickCount: 3 }); await el.type(val, { delay: 20 }); return true; }
  return false;
};
await typeIf("#cardNumber", "4242424242424242");
await typeIf("#cardExpiry", "12/34");
await typeIf("#cardCvc", "123");
await typeIf("#billingName", "Banter Tester");
// country / postal vary by account settings
const country = await page.$("#billingCountry");
if (country) await page.select("#billingCountry", "US").catch(() => {});
await typeIf("#billingPostalCode", "10001");
await typeIf("#billingAddressLine1", "1 Test Street");
await typeIf("#billingLocality", "New York");
await sleep(400);
await page.screenshot({ path: `${OUT}/51-stripe-filled.png` });

const submit = await page.$(".SubmitButton, button[type=submit]");
if (submit) await submit.click();
console.log("submitted, waiting for redirect…");
try {
  await page.waitForFunction(() => location.hostname.includes("banterclips.com"), { timeout: 45000 });
  console.log("redirected to:", page.url());
} catch {
  console.log("no redirect — current url:", page.url().slice(0, 90));
  console.log("page says:", (await page.evaluate(() => document.body.innerText)).slice(0, 300));
}
await sleep(1500);
await page.screenshot({ path: `${OUT}/52-after-payment.png` });
await browser.close();
