import os,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError
record='--record' in sys.argv
out=Path('docs/deliverables/demo');out.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
 ctx=b.new_context(viewport={'width':1440,'height':900},**({'record_video_dir':str(out),'record_video_size':{'width':1440,'height':900}} if record else {}));page=ctx.new_page()
 def pause(ms=3000): page.wait_for_timeout(ms)
 def go(path): page.goto('https://d1r325uzu5fe7x.cloudfront.net'+path,wait_until='domcontentloaded',timeout=30000);pause(4000)
 def click(locator): locator.first.scroll_into_view_if_needed();pause(1000);locator.first.click();pause(1500)
 try:
  go('/');print('home',page.title(),flush=True);pause(4000)
  go('/decision-desk/');page.locator('#move-ticker').fill('TSLA');page.locator('#move-size').fill('25');page.locator('#move-funding').select_option('pro_rata');pause(6000);page.locator('#move-size').scroll_into_view_if_needed();pause(3000)
  click(page.get_by_role('button',name='Analyze evidence'));print('decision started',flush=True)
  for i in range(75):
   pause(2000);body=page.locator('body').inner_text()
   if 'Signed result' in body or 'run failed' in body.lower(): break
  print('decision status', 'Signed result' in body,flush=True)
  chips=page.locator('button.chip'); print('chips',chips.count(),flush=True)
  if chips.count(): click(chips.first);pause(4000);page.keyboard.press('Escape')
  pause(3000)
  go('/time-machine/'); pause(5000); print('replay screen only; no second run',flush=True)
  go('/world-explorer/');click(page.locator('button.feed-item'));pause(7000);print('world event shown',flush=True)
 except Exception as e: print('ERROR',type(e).__name__,str(e)[:400],flush=True)
 finally:
  if record: print('VIDEO',page.video.path(),flush=True)
  ctx.close();b.close()
