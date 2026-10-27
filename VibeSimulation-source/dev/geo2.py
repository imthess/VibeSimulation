from geo import *
import sys
def show(items):
    r = dump(items)
    cur=None
    for l in r:
        if l.startswith("COMP"):
            p=l.split(" [")[0]; at=" ".join(x for x in l.split(" [")[1:] if x.split("=")[0] in ("select","width","inputs","fanout","incoming","enable","facing","selloc","size","mode","shift","type","appear"))
            print(p, "|", at.replace("]",""))
        else: print(l)
if __name__=="__main__":
    which=sys.argv[1]
    S={
     "mux":[(2,"Multiplexer",{"select":s,"width":4,"enable":e}) for s in (1,2,3) for e in ("false","true")],
     "mux_loc":[(2,"Multiplexer",{"select":2,"width":4,"selloc":"tr"}),(2,"Multiplexer",{"select":2,"width":4,"selloc":"bl"})],
     "demux":[(2,"Demultiplexer",{"select":s,"width":4}) for s in (1,2,3)],
     "dec":[(2,"Decoder",{"select":s,"enable":e}) for s in (1,2,3) for e in ("false","true")],
     "prio":[(2,"Priority Encoder",{"select":s}) for s in (1,2,3)],
     "arith":[(3,n,{"width":4}) for n in ("Adder","Subtractor","Multiplier","Divider","Negator","Comparator","Shifter")],
     "bit":[(3,"BitAdder",{"width":4,"inputs":3}),(3,"BitFinder",{"width":4}),(2,"BitSelector",{"width":8,"group":2})],
     "wire":[(0,"Pin",{"width":4,"output":"true","facing":"west"}),(0,"Pin",{"width":1}),(0,"Constant",{"width":4,"value":"0x5"}),(0,"Splitter",{"fanout":4,"incoming":4}),(0,"Splitter",{"fanout":4,"incoming":4,"facing":"west"}),(0,"Splitter",{"fanout":2,"incoming":4})],
     "gate":[(1,"Odd Parity",{"inputs":3}),(1,"Buffer",{}),(1,"NOT Gate",{}),(1,"XNOR Gate",{"inputs":3})],
     "io":[(5,"LED",{}),(5,"7-Segment Display",{}),(5,"Hex Digit Display",{}),(5,"Button",{})],
    }[which]
    show(S)
