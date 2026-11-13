import json,sys,statistics as st,collections
rows=[json.loads(l) for f in sys.argv[1:] for l in open(f) if l.strip()]
cpu={r['label']:r['model'].split(' Processor')[0].replace('Intel(R) ','').replace('(R)','') for r in rows if r['t']=='env'}
d=collections.defaultdict(dict)
for r in rows:
    if r['t']!='env': d[r['t']][r['label']]=r['v']
labels=sorted(cpu)
tests=[t for t in d if t not in('dl_go_bytes',)]
print('test'.ljust(16)+''.join(l.split('#')[0][:6]+l.split('#')[1]+' ' for l in labels))
print(''.ljust(16)+''.join(cpu[l][:7].ljust(8) for l in labels))
for t in tests:
    print(t.ljust(16)+''.join(str(round(d[t].get(l,float('nan')),1))[:7].ljust(8) for l in labels))
