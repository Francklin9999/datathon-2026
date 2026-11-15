import json,time,os
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path('docs/deliverables/demo');out.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
 ctx=b.new_context(viewport={'width':1280,'height':720},record_video_dir=str(out),record_video_size={'width':1280,'height':720});page=ctx.new_page()
 def pause(n):page.wait_for_timeout(n*1000)
 def caption(text):
  page.evaluate('''text=>{let x=document.getElementById('demo-caption');if(!x){x=document.createElement('div');x.id='demo-caption';Object.assign(x.style,{position:'fixed',bottom:'12px',left:'8%',width:'84%',zIndex:2147483647,background:'rgba(4,15,30,.94)',color:'white',font:'22px sans-serif',textAlign:'center',padding:'16px',borderRadius:'8px',boxShadow:'0 2px 10px #000'});document.body.appendChild(x)}x.textContent=text}''',text)
 def go(route):page.goto('https://d1r325uzu5fe7x.cloudfront.net'+route,wait_until='domcontentloaded',timeout=30000);pause(3)
 def show(locator):locator.first.scroll_into_view_if_needed();pause(1)
 def click(locator):show(locator);locator.first.click();pause(2)
 def set_move():page.locator('#move-ticker').fill('TSLA');page.locator('#move-size').fill('25');page.locator('#move-funding').select_option('pro_rata');pause(5)
 try:
  go('/');ctx.storage_state(path='/tmp/aplomb-demo-private.json');os.chmod('/tmp/aplomb-demo-private.json',0o600)
  caption('Aplomb: a fictional investor, a hypothetical portfolio, and evidence before conviction.');pause(14)
  caption('Robert values stability. Portfolio value is fictional; historical performance reconstructs current weights.');pause(16)
  go('/decision-desk/');caption('Test adding 25 percentage points of TSLA, financed by proportional sales. No orders are placed.');set_move();pause(12)
  click(page.get_by_role('button',name='Analyze evidence'));caption('A real AWS run plans, calculates, checks policy, writes, audits and signs.');print('decision started',flush=True)
  for i in range(100):
   pause(2);body=page.locator('body').inner_text()
   if 'Signed result' in body or 'run failed' in body.lower():break
  if 'Signed result' not in body:raise RuntimeError('Decision did not sign')
  decision=page.url.split('runId=')[1].split('&')[0];print('decision signed',flush=True)
  caption('The policy verdict and before/after calculations are deterministic. The writer explains the evidence.');pause(15)
  chip=page.locator('button.chip').first;click(chip);caption('Open a number to inspect its provenance, method, period and verification.');pause(15);page.keyboard.press('Escape')
  go('/evidence-audit/?runId='+decision);caption('The evidence ledger and auditor identify which claims survived the implemented checks.');pause(20)
  go('/agents-system/?runId='+decision+'#run-detail');caption('The execution timeline reports actual steps and models. It is not simulated progress.');pause(20)
  go('/time-machine/');caption('Time Machine freezes a historical assessment before later observations are revealed.');click(page.get_by_role('button',name='2025-02-19: before the largest later fall'));set_move();pause(5)
  click(page.get_by_role('button',name='Run historical replay'));caption('Data tools enforce the as-of date. A modern model may still know later events from training.');print('replay started',flush=True)
  for i in range(100):
   pause(2)
   if page.get_by_role('button',name='Reveal later outcomes').count():break
  reveal=page.get_by_role('button',name='Reveal later outcomes');reveal.wait_for(state='visible',timeout=5000);caption('The initial assessment is locked. Reveal adds subsequent observed results separately.');pause(8);click(reveal);pause(5)
  caption('Later observations are historical outcomes, not proof the original explanation predicted them.');pause(20);print('reveal clicked',flush=True)
  go('/world-explorer/');caption('World Explorer shows sourced historical events and the basis of each potential portfolio link.');pause(12);click(page.locator('button.feed-item'));caption('This official event includes its source and date. A proxy link does not establish financial impact.');pause(22)
  caption('Controlled sabotage tests exist locally. The sabotage feature is not enabled in this deployment.');pause(15)
  print('done',flush=True)
 except Exception as e:print('ERROR',type(e).__name__,str(e)[:600],flush=True)
 finally:
  print('VIDEO',page.video.path(),flush=True);ctx.close();b.close()
