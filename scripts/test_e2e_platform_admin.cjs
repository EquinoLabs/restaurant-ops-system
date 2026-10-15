const path = require('path');
const puppeteer = require('puppeteer-core');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

async function runE2E() {
  console.log('Launching Chrome browser at', CHROME_PATH);
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const page = await browser.newPage();

  // Log all console messages
  page.on('console', (msg) => {
    console.log(`[BROWSER CONSOLE ${msg.type()}]:`, msg.text());
  });

  // Log failed requests
  page.on('requestfailed', (req) => {
    console.log(`[REQUEST FAILED]: ${req.method()} ${req.url()} - ${req.failure()?.errorText}`);
  });

  page.on('response', (res) => {
    if (res.url().includes('/api/v1/')) {
      console.log(`[API RESPONSE]: ${res.status()} ${res.url()}`);
    }
  });

  console.log('Navigating to http://localhost:5176/login...');
  await page.goto('http://localhost:5176/login', { waitUntil: 'networkidle0' });

  console.log('Current URL:', page.url());

  // Click demo button for admin@himachalhospitality.com
  console.log('Clicking demo button for admin@himachalhospitality.com...');
  const selectButton = await page.$('button[type="button"]');
  if (selectButton) {
    await selectButton.click();
  }

  // Verify inputs
  const emailVal = await page.$eval('input[type="email"]', (el) => el.value);
  console.log('Email filled:', emailVal);

  console.log('Submitting login form...');
  await page.click('button[type="submit"]');

  // Wait 4 seconds for response and navigation
  await new Promise((r) => setTimeout(r, 4000));

  console.log('URL after login:', page.url());

  // Check for error text if any
  const errorEl = await page.$('.bg-red-500\\/10');
  if (errorEl) {
    const errorText = await page.evaluate((el) => el.innerText, errorEl);
    console.log('Error displayed on page:', errorText);
  } else {
    console.log('No error message displayed on page.');
  }

  // Check page content
  const title = await page.title();
  console.log('Page Title:', title);

  const bodyText = await page.$eval('body', (el) => el.innerText.slice(0, 400));
  console.log('Page Content preview:\n', bodyText);

  await browser.close();
}

runE2E().catch((err) => {
  console.error('Test run failed:', err);
  process.exit(1);
});
