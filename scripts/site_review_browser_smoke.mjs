/** Regression checks against a local API/web and headless Chrome on port 9224.
 * Run: node scripts/site_review_browser_smoke.mjs
 * Override APLOMB_QA_SITE / APLOMB_QA_CDP as needed. No model calls are requested by this script.
 */
import assert from 'node:assert/strict';

const site = process.env.APLOMB_QA_SITE || 'http://localhost:3000';
const cdp = process.env.APLOMB_QA_CDP || 'http://localhost:9224';
const tab = await (await fetch(`${cdp}/json/new?about:blank`, { method: 'PUT' })).json();
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise(resolve => ws.addEventListener('open', resolve, { once: true }));
let id = 0;
const pending = new Map();
ws.addEventListener('message', event => {
  const message = JSON.parse(event.data);
  if (!message.id) return;
  pending.get(message.id)?.(message);
  pending.delete(message.id);
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const next = ++id;
  pending.set(next, message => message.error ? reject(Error(JSON.stringify(message.error))) : resolve(message.result));
  ws.send(JSON.stringify({ id: next, method, params }));
});
const evaluate = async expression => {
  const response = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (response.exceptionDetails) throw Error(response.exceptionDetails.text);
  return response.result.value;
};
const waitFor = async expression => {
  for (let attempt = 0; attempt < 150; attempt++) {
    if (await evaluate(`Boolean(${expression})`)) return;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  throw Error(`Timed out: ${expression}`);
};
const key = async (value, modifiers = 0) => {
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: value, modifiers, windowsVirtualKeyCode: value === 'Tab' ? 9 : 27 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: value, modifiers, windowsVirtualKeyCode: value === 'Tab' ? 9 : 27 });
};

try {
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Page.navigate', { url: `${site}/markets/` });
  await waitFor("document.querySelector('#market-query')");
  await evaluate("localStorage.removeItem('aplomb.pref.tour.v1'); localStorage.setItem('aplomb.pref.window', 'full')");
  await send('Page.reload');
  await waitFor("document.querySelector('.tour-welcome') && document.querySelector('#market-query')");
  assert.equal(await evaluate("document.activeElement.textContent"), 'Start the tour');
  await key('Tab');
  assert.equal(await evaluate("document.activeElement.textContent"), 'Later');
  await key('Tab', 8);
  assert.equal(await evaluate("document.activeElement.textContent"), 'Start the tour');
  await key('Escape');
  await waitFor("!document.querySelector('.tour-welcome')");
  assert.notEqual(await evaluate("document.body.style.overflow"), 'hidden');
  console.log('PASS: welcome traps forward/backward Tab and Escape restores scrolling');

  for (const width of [1440, 390]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height: 1000, deviceScaleFactor: 1, mobile: width < 500 });
    await send('Page.navigate', { url: `${site}/markets/` });
    await waitFor("[...document.querySelectorAll('button')].some(x => x.textContent === 'SPY')");
    await evaluate("[...document.querySelectorAll('button')].find(x => x.textContent === 'SPY').click()");
    await waitFor("document.querySelector('#market-analytics')?.textContent.includes('Period return')");
    assert.equal(await evaluate("document.activeElement.getAttribute('aria-labelledby')"), 'market-analytics-title');
    assert.ok(await evaluate("document.querySelector('#market-analytics-title').getBoundingClientRect().top > document.querySelector('.topbar').getBoundingClientRect().bottom"));
    assert.ok(await evaluate("document.querySelector('#market-analytics-title').getBoundingClientRect().bottom < innerHeight"));
    console.log(`PASS: selected stock results receive focus and appear below the header at ${width}px`);

    const before = await evaluate("document.querySelector('#market-analytics').innerText");
    await evaluate("document.querySelector('[aria-label=\"Analysis period\"] button:last-child').click()");
    await waitFor("document.querySelector('#market-analytics')?.innerText.includes('Year to date') && document.querySelector('#market-analytics')?.innerText.includes('Period return')");
    assert.notEqual(await evaluate("document.querySelector('#market-analytics').innerText"), before);
    assert.equal(await evaluate("localStorage.getItem('aplomb.pref.window')"), 'ytd');
    await evaluate("document.querySelector('[aria-label=\"Analysis period\"] button:first-of-type').click()");
    await waitFor("document.querySelector('#market-analytics')?.innerText.includes('Full sample') && document.querySelector('#market-analytics')?.innerText.includes('Period return')");
    console.log(`PASS: analysis period is visible and changing it refreshes stock analytics at ${width}px`);
  }
} finally {
  ws.close();
  await fetch(`${cdp}/json/close/${tab.id}`);
}
