/**
 * Investor Lab browser regression using a local API, web app and headless Chrome.
 * Start Chrome with --headless --remote-debugging-port=9224 and a temporary profile.
 * Run: node scripts/investor_lab_browser_smoke.mjs
 * Uses a new fictional session; never requests a model call or places an order.
 */
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const site = process.env.APLOMB_QA_SITE || 'http://localhost:3000';
const api = process.env.APLOMB_QA_API || 'http://localhost:8000/v1';
const cdp = process.env.APLOMB_QA_CDP || 'http://localhost:9224';
const artifacts = path.resolve('.artifacts/investor-lab');
await mkdir(artifacts, { recursive: true });
const tab = await (await fetch(`${cdp}/json/new?about:blank`, { method: 'PUT' })).json();
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise(resolve => ws.addEventListener('open', resolve, { once: true }));
let id = 0;
const pending = new Map();
const exceptions = [];
let intercept = null;
ws.addEventListener('message', event => {
  const message = JSON.parse(event.data);
  if (message.method === 'Runtime.exceptionThrown') exceptions.push(message.params);
  if (message.method === 'Fetch.requestPaused' && intercept) void intercept(message.params);
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
  if (response.exceptionDetails) throw Error(JSON.stringify(response.exceptionDetails));
  return response.result.value;
};
const waitFor = async expression => {
  for (let attempt = 0; attempt < 150; attempt++) {
    if (await evaluate(`Boolean(document.body) && Boolean(${expression})`)) return;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  throw Error(`Timed out: ${expression}\n${await evaluate('document.body.innerText')}`);
};
const click = async text => {
  const expression = `[...document.querySelectorAll('button')].find(el => el.textContent.trim() === ${JSON.stringify(text)})`;
  await waitFor(`${expression} && !${expression}.disabled`);
  await evaluate(`${expression}.click()`);
};
const field = async (label, value) => {
  await waitFor(`[...document.querySelectorAll('label')].some(el =>
    el.textContent.trim() === ${JSON.stringify(label)} ||
    el.querySelector(':scope > span')?.textContent.trim() === ${JSON.stringify(label)})`);
  await evaluate(`(() => {
    const label = [...document.querySelectorAll('label')].find(el =>
      el.textContent.trim() === ${JSON.stringify(label)} ||
      el.querySelector(':scope > span')?.textContent.trim() === ${JSON.stringify(label)});
    const el = label?.htmlFor ? document.getElementById(label.htmlFor) : label?.querySelector('input,select,textarea');
    if (!el) throw Error('Missing field: ' + ${JSON.stringify(label)});
    const proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype : el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(String(value))});
    el.dispatchEvent(new Event('input', {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
  })()`);
};
const profiles = () => evaluate(`fetch(${JSON.stringify(`${api}/profiles`)}, {headers:{'X-Aplomb-Session':localStorage.getItem('aplomb.session')}}).then(r=>r.json()).then(r=>r.items)`);
const navigate = async url => {
  await send('Page.navigate', { url });
  await waitFor("document.querySelector('.investor-lab')");
};
const capture = async (name, width = 1440, height = 1000, selector = null) => {
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 500 });
  await evaluate('window.scrollTo(0,0)');
  if (selector) await evaluate(`(() => {
    const el = document.querySelector(${JSON.stringify(selector)});
    const header = document.querySelector('.topbar')?.getBoundingClientRect().bottom ?? 0;
    window.scrollTo(0, el.getBoundingClientRect().top + scrollY - header - 20);
  })()`);
  await new Promise(resolve => setTimeout(resolve, 100));
  assert.ok(await evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), `Horizontal overflow at ${width}px`);
  const screenshot = await send('Page.captureScreenshot', { format: 'png' });
  await writeFile(path.join(artifacts, name), Buffer.from(screenshot.data, 'base64'));
};
const completeCheckpoint = async (number, { full = true } = {}) => {
  await waitFor("document.querySelector('.lab-decision-form') && document.body.innerText.includes('Your first instinct')");
  assert.equal(await evaluate("document.activeElement.tagName"), 'H2');
  assert.equal(await evaluate("document.querySelector('.lab-evidence') !== null"), false);
  assert.equal(await evaluate("/Microsoft|2022-05|2023-06|MSFT/.test(document.body.innerText)"), false);
  if (full && number === 1) {
    await evaluate("document.querySelector('.lab-actions input[value=\"sell\"]').click()");
    await field('Target allocation to Company C (%)', 5);
    await field('What is driving this choice?', 'cash_need');
  } else if (full && number === 3) {
    await evaluate("document.querySelector('.lab-actions input[value=\"buy\"]').click()");
    await field('Target allocation to Company C (%)', 30);
    await field('What is driving this choice?', 'portfolio_balance');
  } else {
    await field('What is driving this choice?', 'company_evidence');
  }
  await field('Explain your choice in relation to your goal', 'I am matching the position to my goal, cash requirements and available evidence.');
  await click('Record choice & investigate');
  await waitFor("document.querySelector('.lab-evidence')");
  await evaluate("document.querySelector('.lab-evidence-toggle').click()");
  await field('Why is this useful for your decision?', 'The allocation shows which other exposures fund this choice.');
  await click('Add to my evidence');
  await waitFor("document.body.innerText.includes('1 evidence note recorded')");
  if (full && number === 1) {
    await capture('research-desktop.png');
    await capture('research-mobile.png', 390, 844);
    await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
    await send('Page.reload');
    await waitFor("document.body.innerText.includes('1 evidence note recorded')");
  }
  await field('Explain your choice in relation to your goal', 'The evidence supports this deliberate size for my goal; future returns will not validate the reasoning.');
  await field('What would make you revisit this decision?', 'I would revisit this decision if cash needs or the company evidence change.');
  await click('Record final decision');
  await waitFor("document.body.innerText.includes('One thing changes')");
  await field('What does this contrast tell you?', 'The changed circumstance matters separately from my willingness to tolerate temporary losses.');
  await click('Continue');
  await waitFor("document.body.innerText.includes('Your first instinct') || document.body.innerText.includes('A profile you can explain')");
};

try {
  await send('Page.enable');
  await send('Runtime.enable');
  const session = `s_${randomUUID()}`;
  await send('Page.addScriptToEvaluateOnNewDocument', {
    source: `if (!sessionStorage.getItem('lab-qa')) {
      localStorage.setItem('aplomb.session', ${JSON.stringify(session)});
      localStorage.setItem('aplomb.pref.tour.v1', JSON.stringify({welcomed:true,done:[]}));
      localStorage.setItem('aplomb.pref.lang','en');
      localStorage.setItem('aplomb.pref.theme','light');
      sessionStorage.setItem('lab-qa','1');
    }`,
  });
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await navigate(`${site}/investor-lab/`);
  await waitFor("document.querySelector('.lab-situation-form')");
  const before = await profiles();
  assert.ok(before.length >= 3);
  assert.equal(await evaluate("document.querySelector('.lab-recent') !== null"), false);
  await capture('entry-desktop.png');
  await capture('entry-mobile.png', 390, 844);
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await field('Profile label', 'Lab browser investor');
  await field('Financial capacity to absorb losses', 'moderate');
  await field('Willingness to experience losses', 'moderate_high');
  await field('Planned withdrawal (% of portfolio)', 5);
  await waitFor("[...document.querySelectorAll('label')].some(x=>x.textContent === 'When will that cash be needed? (months)')");
  await field('When will that cash be needed? (months)', 6);
  await click('Begin with these circumstances');
  for (let checkpoint = 1; checkpoint <= 3; checkpoint++) await completeCheckpoint(checkpoint);
  assert.deepEqual(await profiles(), before, 'Simulation changed a profile before confirmation');
  assert.ok(await evaluate("document.querySelector('.lab-settings').innerText.includes('Fictional starting portfolio')"));
  assert.equal(await evaluate("document.querySelectorAll('.lab-setting input[type=checkbox]:checked').length"), 0);
  await capture('review-desktop.png');
  await capture('review-mobile.png', 390, 844);
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await click('Accept all proposed settings');
  await field('Why these settings reflect my intended approach', 'I confirm the reviewed circumstances and limits; the exercise explains my reasoning without predicting returns.');
  await click('Confirm & save profile');
  await waitFor("document.querySelector('.lab-saved') && document.querySelector('#playbook')");
  const saved = (await profiles()).find(p => p.name === 'Lab browser investor');
  assert.ok(saved?.investorContext?.playbook);
  assert.equal(saved.investorContext.playbook.reviews.length, 1);
  assert.equal(saved.investorContext.playbook.reviews[0].observations.length, 3);
  assert.equal(saved.riskLevel, 'moderate_high');
  await capture('saved-desktop.png');
  await evaluate("document.documentElement.dataset.theme = 'dark'");
  await capture('saved-dark-mobile.png', 390, 844);
  await evaluate("document.documentElement.dataset.theme = 'light'");
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  console.log('PASS new profile: three masked checkpoints, evidence notes, restoration, explicit confirmation and saved playbook');

  // Browser-only fixture proves denominator handling; it never enters the API store.
  const sharedTicker = saved.portfolio.positions[0].ticker;
  const filing = {
    filingId: 'qa_disclosure', manager: 'QA Example Manager (test fixture)',
    reportDate: '2024-03-31', filingDate: '2024-05-10', retrievedAt: '2026-11-15T00:00:00Z',
    modeledCoveragePct: 40, holdingCount: 4, secUrl: 'https://www.sec.gov/',
    sourceUrl: 'https://example.invalid/test-fixture', limitations: ['Browser-only test fixture.'],
    holdings: [
      { ticker: sharedTicker, valueUsd: 100, optionType: null },
      { ticker: sharedTicker, valueUsd: 100, optionType: null },
      { ticker: null, valueUsd: 800, optionType: null },
      { ticker: sharedTicker, valueUsd: 500, optionType: 'call' },
    ],
  };
  intercept = async event => {
    const body = event.request.url.endsWith('/qa_disclosure') ? filing : { items: [filing] };
    await send('Fetch.fulfillRequest', {
      requestId: event.requestId, responseCode: 200,
      responseHeaders: [
        { name: 'Content-Type', value: 'application/json' },
        { name: 'Access-Control-Allow-Origin', value: site },
        { name: 'Access-Control-Allow-Headers', value: 'X-Aplomb-Session,Content-Type' },
      ],
      body: Buffer.from(JSON.stringify(body)).toString('base64'),
    });
  };
  await send('Fetch.enable', { patterns: [{ urlPattern: `${api}/research/13f*`, requestStage: 'Request' }] });
  await click('Open 13F comparison');
  await waitFor("[...document.querySelectorAll('select')].some(el=>el.querySelector('option[value=\"qa_disclosure\"]'))");
  await field('Manager and reporting date', 'qa_disclosure');
  await waitFor("document.querySelector('.lab-disclosure tbody tr')");
  const disclosedPct = await evaluate("document.querySelector('.lab-disclosure tbody tr td:last-child').textContent");
  assert.equal(Number(disclosedPct.replace(/[^0-9.]/g, '')), 20, 'Options or unmapped long positions corrupted the disclosure denominator');
  assert.ok(await evaluate("document.querySelector('.lab-disclosure').innerText.includes('2024')"));
  assert.equal((await profiles()).find(p => p.profileId === saved.profileId).version, saved.version);
  await capture('disclosure-fixture-desktop.png', 1440, 1000, '.lab-disclosure');
  await send('Fetch.disable');
  intercept = null;
  console.log('PASS 13F browser fixture: dated allocation, duplicate rows, excluded options, unmapped coverage and no profile write');

  await navigate(`${site}/investor-lab/?mode=quick&profileId=${encodeURIComponent(saved.profileId)}`);
  await waitFor("document.querySelector('.lab-situation-form')");
  await field('Willingness to experience losses', 'low');
  await click('Begin with these circumstances');
  await completeCheckpoint(1, { full: false });
  await waitFor("document.body.innerText.includes('A profile you can explain')");
  assert.equal(await evaluate("document.querySelectorAll('.lab-setting input[type=checkbox]:checked').length"), 0);
  await field('Why these settings reflect my intended approach', 'I retain my existing willingness and limits after reviewing this contrasting situation.');
  await click('Confirm & save profile');
  await waitFor("document.querySelector('.lab-saved')");
  const retained = (await profiles()).find(p => p.profileId === saved.profileId);
  assert.equal(retained.riskLevel, saved.riskLevel, 'Unaccepted setting changed the profile');
  assert.deepEqual(retained.portfolio, saved.portfolio, 'Quick check changed holdings');
  assert.equal(retained.investorContext.playbook.reviews.length, 2);
  console.log('PASS quick check: unaccepted settings and holdings retained; explained history appended');

  await waitFor("[...document.querySelectorAll('button')].some(x=>x.textContent==='Edit playbook')");
  await click('Edit playbook');
  await field('Decision principle', 'Keep allocations within the confirmed limits and review company evidence before changing the thesis.');
  await field('When would you revisit it?', 'Revisit when a planned withdrawal changes or two reporting periods contradict the thesis.');
  await field('Why are you changing it?', 'The contrasting situation helped me define a concrete review trigger.');
  await click('Review changes');
  await waitFor("document.body.innerText.includes('Confirm your changes')");
  assert.ok(await evaluate("document.querySelector('#playbook').innerText.includes('Current') && document.querySelector('#playbook').innerText.includes('Proposed')"));
  await click('Confirm and save');
  await waitFor("!document.querySelector('#playbook form')");
  const edited = (await profiles()).find(p => p.profileId === saved.profileId);
  assert.equal(edited.investorContext.playbook.reviews.length, 3);
  assert.equal(edited.investorContext.playbook.reviews.at(-1).changes.length, 2);
  console.log('PASS playbook edit: current/proposed review and explicit saved explanation');

  await send('Page.navigate', { url: `${site}/decision-desk/` });
  await waitFor("document.body.innerText.includes('Your investment playbook')");
  assert.ok(await evaluate("document.body.innerText.includes('Keep allocations within the confirmed limits')"));
  await send('Page.navigate', { url: `${site}/portfolio/?tab=rules` });
  await waitFor("document.querySelector('#playbook')");
  assert.ok(await evaluate("document.querySelector('#playbook').innerText.includes('Revisit when a planned withdrawal changes')"));
  console.log('PASS confirmed playbook appears in Portfolio and Decision Desk');

  await navigate(`${site}/investor-lab/?lab=lab_unavailable`);
  await waitFor("document.querySelector('.state-error')");
  await capture('unavailable-session.png');
  assert.equal(exceptions.length, 0, 'Uncaught browser exception');
  await writeFile(path.join(artifacts, 'smoke-result.json'), JSON.stringify({
    status: 'pass', capturedAt: new Date().toISOString(), profileId: saved.profileId,
    checks: ['new full flow', 'masked progressive evidence', 'resume', 'explicit confirmation',
      'quick check retains unchecked settings', 'playbook review and history',
      'portfolio and decision integration', 'responsive light/dark', 'unavailable session',
      '13F allocation browser fixture'],
    browserExceptions: exceptions,
  }, null, 2));
  console.log(`PASS responsive views and error state; screenshots in ${artifacts}`);
} finally {
  ws.close();
  await fetch(`${cdp}/json/close/${tab.id}`);
}
