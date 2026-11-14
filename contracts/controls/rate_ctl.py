import sys, io, contextlib
src = open(sys.argv[0].replace('rate_ctl.py','controls.py')).read()
with contextlib.redirect_stdout(io.StringIO()):
    exec(src)
def window_ret(w, a, b):
    r = port_rets(w, master); v = cum(r)
    i0 = max(i for i,d in enumerate(master) if d<=a); i1 = max(i for i,d in enumerate(master) if d<=b)
    return master[i0], master[i1], v[i1]/v[i0]-1
for n,w in P.items():
    a,b,r = window_ret(w,'2022-03-02','2023-07-13'); print(n, a, b, f"{100*r:.2f}%")
for t in ('XBB.TO','TLT','AGG','SPY','XIU.TO','ZST.TO'):
    a,b,r = window_ret({t:1.0},'2022-03-02','2023-07-13'); print(t, a, b, f"{100*r:.2f}%")
print('robert +25% TSLA', "%.2f%%" % (100*window_ret(move_prorata(P['robert'],'TSLA',.25),'2022-03-02','2023-07-13')[2]))
# YTD / 1Y control for home page: robert
import datetime
def ret_between(w,a,b): return window_ret(w,a,b)
for n,w in P.items():
    print(n,'YTD2026', "%s %s %.2f%%" % tuple([*ret_between(w,'2025-12-31','2026-11-12')[:2], 100*ret_between(w,'2025-12-31','2026-11-12')[2]]),
          '1Y', "%s %.2f%%" % (ret_between(w,'2025-11-12','2026-11-12')[0], 100*ret_between(w,'2025-11-12','2026-11-12')[2]))
print('fx last', fxd[-1], fx[fxd[-1]])
print('last prices', {t: px[t]['2026-11-12'] for t in ('TSLA','XBB.TO','SPY')})
