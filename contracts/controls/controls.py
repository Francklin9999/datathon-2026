import sys, csv, math, statistics as st
from collections import defaultdict
D = sys.argv[1]
px = defaultdict(dict)   # ticker -> date -> adj_close
for r in csv.DictReader(open(D+'/prices_daily.csv')):
    px[r['ticker']][r['date']] = float(r['adj_close'])
uni = {r['ticker']: r for r in csv.DictReader(open(D+'/assets_universe.csv'))}
fx = {r['date']: float(r['usdcad']) for r in csv.DictReader(open(D+'/fx_usdcad_daily.csv'))}

print("== per ticker rows / first / last")
for t in uni:
    ds = sorted(px[t]); print(f"{t:8s} {len(ds):5d} {ds[0]} {ds[-1]}")

tsx = set(px['XIU.TO']); us = set(px['SPY'])
master = sorted(tsx & us); union = sorted(tsx | us)
print("\n== calendars: TSX days", len(tsx), "US days", len(us), "intersection", len(master), "union", len(union), master[0], master[-1])
for t,u in uni.items():
    ref = tsx if u['currency']=='CAD' else us
    if u['asset_class']=='crypto': continue
    d = set(px[t])
    if d != ref: print("  calendar mismatch", t, "missing", sorted(ref-d)[:5], "extra", sorted(d-ref)[:5])
miss_fx = [d for d in master if d not in fx]
print("master days without FX rate:", len(miss_fx), miss_fx[:12])
print("union days without FX rate:", len([d for d in union if d not in fx]))
per_year = defaultdict(int)
for d in master: per_year[d[:4]] += 1
print("master days per year:", dict(per_year))

fxd = sorted(fx)
def fx_at(d):
    # last published rate on or before d
    import bisect
    i = bisect.bisect_right(fxd, d) - 1
    return fx[fxd[i]]
def last_on_or_before(t, d):
    ds = sorted(x for x in px[t] if x <= d); return ds[-1]
def cad(t, d):
    p = px[t][d]
    return p * fx_at(d) if uni[t]['currency']=='USD' else p

def series_cad(t, cal):
    return [cad(t, d) for d in cal]
def rets(v): return [v[i]/v[i-1]-1 for i in range(1,len(v))]
def annvol(r): return st.stdev(r)*math.sqrt(252)
def maxdd(v):
    peak=v[0]; m=0;
    for x in v:
        peak=max(peak,x); m=min(m,x/peak-1)
    return m

print("\n== asset controls (2022 return listing ccy on own calendar; CAD; full-window vol & maxDD in CAD on master calendar)")
ctl = ['TSLA','NVDA','SPY','QQQ','ESGV','AGG','TLT','GLD','XIU.TO','XBB.TO','ZST.TO','CNQ.TO','RY.TO','SHOP.TO','BTC-USD','ETH-USD']
for t in ctl:
    a=last_on_or_before(t,'2021-12-31'); b=last_on_or_before(t,'2022-12-31')
    r_l = px[t][b]/px[t][a]-1
    r_c = cad(t,b)/cad(t,a)-1
    v = series_cad(t, master)
    print(f"{t:8s} base {a} end {b} listing {100*r_l:7.1f}%  CAD {100*r_c:7.1f}%  volCAD {100*annvol(rets(v)):5.1f}%  maxDD_CAD {100*maxdd(v):6.1f}%  nret {len(v)-1}")

print("\n== single-stock CAD vol distribution (20 equities, master calendar, full window)")
vols = sorted((annvol(rets(series_cad(t,master))),t) for t,u in uni.items() if u['asset_class']=='equity')
print([f"{t}:{100*v:.1f}" for v,t in vols])
vv=[v for v,_ in vols]
q=st.quantiles(vv, n=4, method='inclusive'); print("quartiles (inclusive):", [round(100*x,1) for x in q], "median", round(100*st.median(vv),1))
cv = sorted((annvol(rets(series_cad(t,master))),t) for t,u in uni.items() if u['asset_class']=='crypto'); print("crypto vols", [(t,round(100*v,1)) for v,t in cv])

def port_rets(w, cal):
    R = {t: rets(series_cad(t,cal)) for t in w}
    n = len(cal)-1
    return [sum(w[t]*R[t][i] for t in w) for i in range(n)]
def cum(r):
    v=[1.0]
    for x in r: v.append(v[-1]*(1+x))
    return v
def stats(w, cal=master, label=""):
    assert abs(sum(w.values())-1)<1e-9, sum(w.values())
    r = port_rets(w, cal); v = cum(r)
    i0 = max(i for i,d in enumerate(cal) if d<='2021-12-31'); i1 = max(i for i,d in enumerate(cal) if d<='2022-12-31')
    r22 = v[i1]/v[i0]-1
    return dict(vol=annvol(r), mdd=maxdd(v), r22=r22, tot=v[-1]-1)
def show(name, w):
    s = stats(w)
    ac = defaultdict(float); sec = defaultdict(float)
    for t,x in w.items(): ac[uni[t]['asset_class']]+=x; sec[uni[t]['sector']]+=x
    top = max(w.items(), key=lambda kv: kv[1])
    print(f"{name:34s} vol {100*s['vol']:5.2f}%  maxDD {100*s['mdd']:6.2f}%  2022 {100*s['r22']:6.2f}%  total {100*s['tot']:6.1f}%  top {top[0]} {100*top[1]:.1f}%")
    return s, dict(ac), dict(sec)
def move_prorata(w, t, pct):
    # target: position t increases by pct points of portfolio, funded by selling all OTHER holdings pro-rata
    cur = w.get(t,0.0); new = cur + pct
    scale = (1-new)/(1-cur)
    out = {k: v*scale for k,v in w.items() if k!=t}; out[t]=new
    return out

P = {
 'robert': {'XBB.TO':.30,'ZST.TO':.15,'AGG':.05,'XIU.TO':.15,'SPY':.10,'RY.TO':.05,'FTS.TO':.05,'ENB.TO':.04,'JNJ':.04,'PG':.04,'GLD':.03},
 'amira':  {'NVDA':.08,'MSFT':.08,'GOOGL':.06,'SHOP.TO':.05,'AMZN':.05,'QQQ':.12,'SPY':.12,'XIU.TO':.10,'BTC-USD':.06,'ETH-USD':.03,'JPM':.04,'CNR.TO':.04,'ATD.TO':.04,'JNJ':.03,'XBB.TO':.05,'GLD':.05},
 'mateo':  {'ESGV':.28,'XBB.TO':.25,'AGG':.07,'ZST.TO':.05,'MSFT':.05,'CNR.TO':.05,'RY.TO':.05,'FTS.TO':.04,'ATD.TO':.04,'JNJ':.04,'PG':.04,'GLD':.04},
}
print("\n== default portfolios (constant weights, daily rebalanced, CAD, master calendar, full window)")
for n,w in P.items():
    s,ac,sec = show(n, w)
    print("   asset classes:", {k: round(100*v,1) for k,v in sorted(ac.items())})
    print("   sectors:", {k: round(100*v,1) for k,v in sorted(sec.items(), key=lambda kv:-kv[1])})
print("\n== after moves (pro-rata funding)")
for n,t,p in [('robert','TSLA',.25),('amira','TSLA',.25),('mateo','TSLA',.25),('mateo','CNQ.TO',.10),('robert','TSLA',.02),('robert','TSLA',.05),('robert','TSLA',.10),('amira','TSLA',.10),('amira','TSLA',.15),('amira','NVDA',.10)]:
    show(f"{n} +{int(p*100)}% {t}", move_prorata(P[n],t,p))

print("\n== reference mixes: equity proxy = 50% XIU.TO + 50% SPY, bond proxy = XBB.TO (CAD, master, full window)")
for we in [0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.0]:
    w={'XIU.TO':we/2,'SPY':we/2,'XBB.TO':1-we}
    w={k:v for k,v in w.items() if v>0}
    s=stats(w); print(f"  equity {int(we*100):3d}%  vol {100*s['vol']:5.2f}%  maxDD {100*s['mdd']:6.2f}%  2022 {100*s['r22']:6.2f}%")
