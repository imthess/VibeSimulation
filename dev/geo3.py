from geo import *
items=[]
for w in (1,2,3,4,5,6,8,16,32): items.append((0,"Pin",{"width":w}))
for w in (1,2,4,8,16): items.append((0,"Pin",{"width":w,"output":"true","facing":"west"}))
for w in (1,4,8): items.append((0,"Constant",{"width":w}))
for l in dump(items):
    if l.startswith("COMP"): print(l.split(" [")[0], [x for x in l.split(" [") if x.startswith(("width","output"))])
