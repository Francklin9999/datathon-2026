import sys, math, statistics as st
sys.argv = [sys.argv[0], sys.argv[1]]
src = open(sys.argv[0].replace('rules_ctl.py','controls.py')).read()
# reuse loaders/helpers from controls.py without its prints
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    exec(src)

GROUP = {'equity':'equity','etf_equity':'equity','etf_bond':'fixed_income','etf_commodity':'commodity','crypto':'crypto'}
SIGMA = {'low':6,'low_moderate':9,'moderate':12,'moderate_high':16,'high':22}
def round5(x): return 5*round(x/5)
def floor5(x): return 5*math.floor(x/5+1e-9)
sig_ref = st.quantiles([annvol(rets(series_cad(t,master))) for t,u in uni.items() if u['asset_class']=='equity'], n=4, method='inclusive')[2]*100
sig_crypto = st.median([annvol(rets(series_cad(t,master))) for t,u in uni.items() if u['asset_class']=='crypto'])*100
def ref_vol(we):
    w={'XIU.TO':we/2,'SPY':we/2,'XBB.TO':1-we}; w={k:v for k,v in w.items() if v>0}
    return stats(w)['vol']*100
print("sigma_ref(Q3 single-stock CAD vol) = %.2f  sigma_crypto(median) = %.2f" % (sig_ref, sig_crypto))
print("ref mix vol by 5%:", [(we, round(ref_vol(we/100),2)) for we in range(0,101,5)])
def derive(risk, horizon_mid, avoid_spec=False):
    s = SIGMA[risk]
    pos = max(5, min(25, round5(0.4*s/sig_ref*100)))
    sector = min(40, 2*pos)
    crypto = max(0, min(25, round5(0.4*s/sig_crypto*100)))
    if avoid_spec: crypto = floor5(crypto/2)
    eq = max([we for we in range(0,101,5) if ref_vol(we/100) <= s] or [0])
    fi_floor = max(0, 100-eq-10)
    m = 1.0 if horizon_mid<=5 else (1.25 if horizon_mid<=10 else 1.5)
    return dict(sigma=s, pos=pos, sector=sector, crypto=crypto, eq=eq, fi_floor=fi_floor, stress=round(m*s,2), dd=2.0*s, m=m)
T = {'robert': derive('low_moderate',4), 'mateo': derive('moderate',10, True), 'amira': derive('high',15)}
for k,v in T.items(): print(k, v)

def up(v,L): return 'conflict' if v>L+1e-9 else ('tension' if v>0.9*L+1e-9 else 'pass')
def lo(v,L): return 'conflict' if v<L-1e-9 else ('tension' if v<1.1*L-1e-9 else 'pass')
def evaluate(name, w):
    th=T[name]; s=stats(w); out=[]
    single = {t:x*100 for t,x in w.items() if uni[t]['asset_class'] in ('equity','crypto')}
    tmax = max(single, key=single.get) if single else None
    out.append(('cap.position', round(single.get(tmax,0),2), th['pos'], up(single.get(tmax,0), th['pos']), tmax))
    sec={}
    for t,x in w.items():
        if uni[t]['asset_class']=='equity': sec[uni[t]['sector']]=sec.get(uni[t]['sector'],0)+x*100
    smax=max(sec,key=sec.get) if sec else None
    out.append(('cap.sector', round(sec.get(smax,0),2), th['sector'], up(sec.get(smax,0), th['sector']), smax))
    grp={}
    for t,x in w.items(): grp[GROUP[uni[t]['asset_class']]]=grp.get(GROUP[uni[t]['asset_class']],0)+x*100
    cr=grp.get('crypto',0)
    if name=='robert': out.append(('exclude.asset_class.crypto', round(cr,2), 0, 'conflict' if cr>1e-9 else 'pass',''))
    else: out.append(('cap.asset_class.crypto', round(cr,2), th['crypto'], up(cr, th['crypto']),''))
    growth = grp.get('equity',0)+cr
    if th['eq']<100: out.append(('cap.growth_assets', round(growth,2), th['eq'], up(growth, th['eq']),''))
    if th['fi_floor']>0: out.append(('floor.fixed_income', round(grp.get('fixed_income',0),2), th['fi_floor'], lo(grp.get('fixed_income',0), th['fi_floor']),''))
    if name=='amira':
        dv = grp.get('fixed_income',0)+grp.get('commodity',0)
        out.append(('floor.diversifiers', round(dv,2), 8, lo(dv, 8),''))
    out.append(('limit.volatility', round(s['vol']*100,2), th['sigma'], up(s['vol']*100, th['sigma']),''))
    loss = max(0,-s['r22']*100)
    out.append(('limit.stress_2022', round(loss,2), th['stress'], up(loss, th['stress']),''))
    out.append(('limit.drawdown', round(-s['mdd']*100,2), th['dd'], up(-s['mdd']*100, th['dd']),''))
    if name=='mateo':
        out.append(('evidence.controversy', None, None, 'nee', 'no_evidence_loaded'))
        en = sum(x*100 for t,x in w.items() if uni[t]['asset_class']=='equity' and uni[t]['sector']=='Energy')
        out.append(('exclude.sector.energy', round(en,2), 0, 'conflict' if en>1e-9 else 'pass',''))
    return out
def verdict(ev):
    st_=[e[3] for e in ev]
    return 'conflict' if 'conflict' in st_ else ('tension' if 'tension' in st_ else ('insufficient' if 'nee' in st_ else 'compatible'))
def move(w, t, pct, funding='pro_rata', frm=None):
    cur=w.get(t,0.0)
    if funding=='new_money':
        out={k:v/(1+pct) for k,v in w.items()}; out[t]=(cur+pct)/(1+pct); return out
    if funding=='pro_rata':
        return move_prorata(w,t,pct)
    if funding=='from_holdings':
        out=dict(w); need=pct
        for f in frm:
            take=min(out.get(f,0),need); out[f]=out.get(f,0)-take; need-=take
        if need>1e-12:
            raise ValueError('Named donor holdings cannot fund this size')
        out[t]=cur+pct
        return {k:v for k,v in out.items() if v>1e-12}
def show_ev(title, name, w):
    ev=evaluate(name,w)
    print(f"\n-- {title}: verdict {verdict(ev).upper()}  conflicts={sum(e[3]=='conflict' for e in ev)} tensions={sum(e[3]=='tension' for e in ev)}")
    for e in ev: print(f"   {e[0]:28s} value {e[1]!s:>7} limit {e[2]!s:>6} {e[3]:9s} {e[4]}")
def max_size(name, t, funding='pro_rata', frm=None, step=0.5):
    best=0.0; s=0.0; cur=P[name].get(t,0)*100
    while s<=100-cur-step+1e-9:
        s2=s+step
        try: w=move(P[name],t,s2/100,funding,frm)
        except ZeroDivisionError: break
        if verdict(evaluate(name,w))=='conflict': break
        best=s2; s=s2
    return best
for n in P: show_ev(f"{n} baseline", n, P[n])
show_ev("CA-1 robert +25% TSLA pro_rata", 'robert', move(P['robert'],'TSLA',.25))
show_ev("CA-2 amira +25% TSLA pro_rata", 'amira', move(P['amira'],'TSLA',.25))
show_ev("amira +25% TSLA from QQQ,SPY,NVDA", 'amira', move(P['amira'],'TSLA',.25,'from_holdings',['QQQ','SPY','NVDA']))
show_ev("amira +25% TSLA new_money", 'amira', move(P['amira'],'TSLA',.25,'new_money'))
show_ev("CA-3 mateo +10% CNQ.TO pro_rata", 'mateo', move(P['mateo'],'CNQ.TO',.10))
show_ev("CA-6 robert +2% TSLA pro_rata", 'robert', move(P['robert'],'TSLA',.02))
print("\nmax compatible TSLA size (pro_rata, 0.5 step):", {n: max_size(n,'TSLA') for n in P})
print("max compatible TSLA size amira from QQQ,SPY:", max_size('amira','TSLA','from_holdings',['QQQ','SPY']))
print("max compatible TSLA size robert from XIU.TO,SPY:", max_size('robert','TSLA','from_holdings',['XIU.TO','SPY']))
print("max compatible NVDA add amira pro_rata:", max_size('amira','NVDA'))
print("max compatible TSLA mateo/robert/amira new_money:", {n: max_size(n,'TSLA','new_money') for n in P})
print("max compatible CNQ.TO mateo pro_rata:", max_size('mateo','CNQ.TO'))
for sz in (5,6,7,8,10,12):
    ev=evaluate('robert', move(P['robert'],'TSLA',sz/100)); print('robert TSLA',sz, verdict(ev), [(e[0],e[1],e[3]) for e in ev if e[3]!='pass'])
for sz in (5,10,12,13,15,20):
    ev=evaluate('amira', move(P['amira'],'TSLA',sz/100)); print('amira TSLA',sz, verdict(ev), [(e[0],e[1],e[3]) for e in ev if e[3]!='pass'])
show_ev("mateo +25% TSLA pro_rata", 'mateo', move(P['mateo'],'TSLA',.25))
show_ev("robert +5% BTC-USD pro_rata", 'robert', move(P['robert'],'BTC-USD',.05))
