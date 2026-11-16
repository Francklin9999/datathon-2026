/** Optional T16 browser gate using Chrome's local debugging port and Node >=22.
 * Usage: node tests/browser-smoke.mjs <site URL> <output directory> [CDP URL]
 * Start a headless Chrome with --remote-debugging-port=9227 and a private profile.
 * Serve web/out and a local API separately. No models or fixtures are provided here.
 */
import fs from 'node:fs/promises';
import path from 'node:path';

const [site, directory, debugging = 'http://127.0.0.1:9227'] = process.argv.slice(2);
// Every page of the static app, derived like scripts/qa_smoke.py so new pages cannot be skipped.
const appDirectory = path.join(import.meta.dirname, '..', 'web', 'src', 'app');
const routes = (await fs.readdir(appDirectory, { recursive: true }))
  .filter(file => path.basename(file) === 'page.tsx')
  .map(file => path.dirname(file).split(path.sep).filter(part => part && part !== '.').join('/'))
  .map(route => (route ? `/${route}/` : '/'))
  .sort();
if (!site || !directory) throw new Error('Provide site URL and a fresh evidence directory');
await fs.mkdir(directory, { recursive: true });
const reportPath = path.join(directory, 'browser.json');
try { await fs.access(reportPath); throw new Error('Choose a new evidence directory'); }
catch (error) { if (error.code !== 'ENOENT') throw error; }
const target = await (await fetch(`${debugging}/json/new?about:blank`, { method: 'PUT' })).json();
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true });
  socket.addEventListener('error', reject, { once: true });
});
let sequence = 0;
const pending = new Map();
const exceptions = [];
socket.addEventListener('message', ({ data }) => {
  const message = JSON.parse(data);
  if (message.method === 'Runtime.exceptionThrown') {
    exceptions.push(message.params.exceptionDetails.exception?.description ?? message.params.exceptionDetails.text);
  }
  if (message.id && pending.has(message.id)) {
    const { resolve, reject, timer } = pending.get(message.id);
    clearTimeout(timer);
    pending.delete(message.id);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else resolve(message.result);
  }
});
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`Timeout: ${method}`)); }, 15000);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await call('Runtime.evaluate', { expression, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
await call('Runtime.enable');
await call('Page.enable');
const report = {
  startedAt: new Date().toISOString(),
  browser: await call('Browser.getVersion'), site,
  scope: 'Headless Chrome hydration, direct routes, page overflow, disclaimer and Tab focus only; no completed model run or full keyboard journey',
  results: [],
};
try {
  for (const width of [375, 768, 1440]) {
    await call('Emulation.setDeviceMetricsOverride', { width, height: 1000, deviceScaleFactor: 1, mobile: width === 375 });
    for (const route of routes) {
      const before = exceptions.length;
      await call('Page.navigate', { url: new URL(route, site).href });
      const deadline = Date.now() + 15000;
      while (Date.now() < deadline) {
        if (await evaluate(`location.pathname === ${JSON.stringify(route)} && document.readyState === 'complete' && !!document.querySelector('h1')`)) break;
        await pause(100);
      }
      await pause(1000);
      const state = await evaluate(`(() => {
        const text = document.body.innerText;
        // The top-bar simulation note (SimPill): short visible text, the full disclaimer in its title and sr-only text.
        const note = document.querySelector('.sim-pill[role="note"]');
        const noteText = note ? note.title + ' ' + note.textContent : '';
        return {
          title: document.querySelector('h1')?.innerText ?? '',
          hydrated: !!document.querySelector('next-route-announcer'),
          // The switcher name is not displayed at some widths, so read its text content as well.
          personaLoaded: text.includes('Robert') || (document.querySelector('.persona-name')?.textContent ?? '').includes('Robert'),
          disclaimer: !!note && note.getBoundingClientRect().width > 0 && noteText.includes('Simulation only.') && noteText.includes('Not financial advice.'),
          viewport: innerWidth, pageWidth: document.documentElement.scrollWidth,
          loading: text.includes('Loading profiles'),
          main: document.querySelector('main')?.innerText.slice(0, 800) ?? '',
        };
      })()`);
      await call('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
      await call('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
      state.tabFocus = await evaluate(`(() => { const e = document.activeElement; return e && e !== document.body ? {tag: e.tagName, label: e.textContent.trim().slice(0, 100)} : null; })()`);
      state.exceptions = exceptions.slice(before);
      const passed = !!state.title && state.hydrated && state.personaLoaded && state.disclaimer && !state.loading && state.pageWidth <= state.viewport + 1 && !!state.tabFocus && state.exceptions.length === 0;
      report.results.push({ width, route, passed, ...state });
      console.log(`${passed ? 'PASS' : 'FAIL'} ${width} ${route}`);
      if ((width === 375 && route === '/world-explorer/') || (width === 1440 && route === '/decision-desk/')) {
        const screenshot = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
        await fs.writeFile(path.join(directory, `browser-${width}-${route.split('/')[1]}.png`), Buffer.from(screenshot.data, 'base64'));
      }
    }
  }
  await call('Page.navigate', { url: new URL('/decision-desk/', site).href });
  await pause(1500);
  // The comparison lives in a <details> fold that is closed by default; hidden panes have no innerText.
  await evaluate(`(() => { const fold = document.getElementById('compare'); if (fold) fold.open = true; })()`);
  async function setField(id, value, select = false) {
    await evaluate(`(() => {
      const e = document.getElementById(${JSON.stringify(id)});
      if (!e) throw new Error('Missing field');
      Object.getOwnPropertyDescriptor(${select ? 'HTMLSelectElement' : 'HTMLInputElement'}.prototype, 'value').set.call(e, ${JSON.stringify(String(value))});
      e.dispatchEvent(new Event(${select ? "'change'" : "'input'"}, {bubbles:true}));
    })()`);
    await pause(100);
  }
  await setField('move-ticker', 'TSLA');
  await setField('move-funding', 'pro_rata', true);
  report.decisionChecks = [];
  for (const size of [25, 10]) {
    await setField('move-size', size);
    await pause(1000);
    await evaluate(`document.querySelector('#compare button').click()`);
    await pause(1500);
    const text = await evaluate(`document.querySelector('main').innerText`);
    const panes = await evaluate(`[...document.querySelectorAll('#compare .pane')].map(e => e.innerText)`);
    const verdicts = await evaluate(`[...document.querySelectorAll('#compare .pane .vbadge')].map(e => e.innerText)`);
    const counts = await evaluate(`document.querySelector('.counts')?.innerText ?? ''`);
    const expected = size === 25 ? ['Conflict', 'Conflict'] : ['Conflict', 'Tension'];
    const passed = panes.length === 2 && verdicts.length === 2 && verdicts.every((verdict, i) => verdict.toLowerCase().includes(expected[i].toLowerCase()))
      && panes[0].includes('6.0') && panes[1].includes('11.0')
      // Each count renders its figure and then a labelled figure ("6\n6 conflict"), so allow text between labels.
      // The preview table shows one decimal: volatility 16.96 -> 17.0%, drawdown 25.31 -> 25.3%, 2022 replay -21.88 -> -21.9%.
      && (size !== 25 || (['17.0%', '25.3%', '21.9%'].every(value => text.includes(value)) && /6 conflict[\s\S]*?1 tension[\s\S]*?1 fit/.test(counts)));
    report.decisionChecks.push({size, passed, verdicts, counts, panes, visibleText: text.slice(0, 16000)});
    console.log(`${passed ? 'PASS' : 'FAIL'} decision compare ${size}`);
    if (size === 25) {
      const image = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
      await fs.writeFile(path.join(directory, 'browser-decision-25.png'), Buffer.from(image.data, 'base64'));
    }
  }
  report.passed = report.results.every(result => result.passed) && report.decisionChecks.every(result => result.passed);
} catch (error) {
  report.passed = false;
  report.error = String(error);
} finally {
  report.finishedAt = new Date().toISOString();
  await fs.writeFile(reportPath, JSON.stringify(report, null, 2) + '\n');
  socket.close();
  await fetch(`${debugging}/json/close/${target.id}`).catch(() => {});
}
if (!report.passed) process.exitCode = 1;
