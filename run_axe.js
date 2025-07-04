const puppeteer = require('puppeteer');
const { AxePuppeteer } = require('@axe-core/puppeteer');

(async () => {
  const url = process.argv[2];
  if (!url) {
    const error = { error: 'Usage: node run_axe.js <url>' };
    console.error(error.error);
    console.log(JSON.stringify(error));
    process.exit(1);
  }
  let browser = null;
  try {
    browser = await puppeteer.launch({ args: ['--no-sandbox', '--disable-setuid-sandbox'] });
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 90000 });
    // Wait for the body to be present
    await page.waitForSelector('body', { timeout: 15000 });
    // Wait 3 seconds for dynamic content (compatible with all Puppeteer versions)
    await new Promise(resolve => setTimeout(resolve, 3000));
    const results = await new AxePuppeteer(page).analyze();
    console.log(JSON.stringify(results));
    await browser.close();
  } catch (err) {
    if (browser) {
      try { await browser.close(); } catch (e) {}
    }
    const error = { error: 'Error running axe-core: ' + (err && err.message ? err.message : String(err)) };
    console.error(error.error);
    console.log(JSON.stringify(error));
    process.exit(2);
  }
})(); 