from geo import *
import sys, subprocess
def render(items, png, sc=2):
    open("r.circ","w").write(gen(items))
    r = subprocess.run(["java","-Djava.awt.headless=true","-cp","logisim.jar:.","Render","r.circ",png,str(sc)],capture_output=True,text=True)
    print(r.stderr[-500:] if "Exception" in r.stderr else "ok")
if __name__=="__main__":
    items=[(2,"Multiplexer",{"select":2,"width":4}),(2,"Decoder",{"select":2}),(3,"Adder",{"width":4}),(2,"Demultiplexer",{"select":2,"width":4}),
           (2,"Priority Encoder",{"select":2}),(3,"Comparator",{"width":4}),(1,"XOR Gate",{}),(5,"7-Segment Display",{})]
    render(items,"r1.png")
