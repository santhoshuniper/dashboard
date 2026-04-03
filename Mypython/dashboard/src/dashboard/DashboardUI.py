import os
import random
import time
import threading
import xml.etree.ElementTree as ET
from tkinter import Tk, Canvas, Button, Toplevel, Label

# ---------------- CONFIG ----------------
TOTAL_MESSAGES = 500

ROOT = r'C:\Dashboard'
SOURCE = os.path.join(ROOT, 'source')
VATP = os.path.join(ROOT, 'VAT-P')
USIP1 = os.path.join(ROOT, 'USIP1')
NEON = os.path.join(ROOT, 'Neon')
USIP2 = os.path.join(ROOT, 'USIP2')
ENDUR = os.path.join(ROOT, 'Endur')

SYSTEMS = ['VAT-P','USIP1','Neon','USIP2','Endur']
HUBS = ["HUB 50HERTZ","HUB TENNETDE","HUB ENBW"]

FAIL_LIMITS = {'USIP1':0,'Neon':2,'USIP2':1,'Endur':3}
fail_counts = {k:0 for k in FAIL_LIMITS}

BG="#1e1e1e"
BOX="#003A8F"
GREEN="#00cc66"
RED="#ff4d4d"
WHITE="white"

blink_state = True

# ---------------- CREATE FOLDERS ----------------
for f in [VATP,
          os.path.join(USIP1,'success'), os.path.join(USIP1,'failure'),
          os.path.join(NEON,'success'), os.path.join(NEON,'failure'),
          os.path.join(USIP2,'success'), os.path.join(USIP2,'failure'),
          os.path.join(ENDUR,'success'), os.path.join(ENDUR,'failure')]:
    os.makedirs(f, exist_ok=True)

# ---------------- AGG ----------------
aggregations = {
    k: {h:{hub:0 for hub in HUBS} for h in range(24)}
    for k in SYSTEMS
}

def update_agg(system, hour, hub, val):
    aggregations[system][hour][hub] += val

# ---------------- HELPERS ----------------
def rand_interval():
    h = random.randint(0,23)
    m = random.choice([0,15,30,45])
    endm=(m+15)%60
    endh=h if m<45 else h+1
    return f"2025-01-27T{h:02}:{m:02}:00Z",f"2025-01-27T{endh:02}:{endm:02}:00Z",h

# ---------------- UI ----------------
class UI:
    def __init__(self, root):
        self.root=root
        root.configure(bg=BG)

        self.c=Canvas(root,bg=BG)
        self.c.pack(fill="both",expand=True)

        self.refs={}
        self.tables={}
        self.cell_map={}
        self.tooltip=None

        self.c.bind("<Configure>",self.draw)
        self.c.bind("<Motion>",self.on_hover)
        self.c.bind("<Button-1>",self.on_click)

        Button(root,text="Start Processing",command=self.start,
               bg="#444",fg="white").pack()

    def draw(self,e=None):
        self.c.delete("all")
        self.cell_map.clear()

        w=self.c.winfo_width()
        spacing=w//6

        for i,sys in enumerate(SYSTEMS):
            cx=spacing*(i+1)
            hw=60 if sys in ['USIP1','USIP2'] else 100

            self.c.create_rectangle(cx-hw,60,cx+hw,140,fill=BOX)
            self.c.create_text(cx,90,text=sys,fill=WHITE,font=("Arial",13,"bold"))

            s=self.c.create_text(cx,155,text="Success:0",fill=WHITE,font=("Arial",14,"bold"))
            f=self.c.create_text(cx,180,text="Failure:0",fill=WHITE,font=("Arial",14))
            self.refs[sys]=(s,f)

            start_y=220
            self.c.create_text(cx-100,start_y,text="Hr",anchor="w",
                               fill=WHITE,font=("Arial",9,"bold"))

            for j,h in enumerate(["H1","H2","H3"]):
                self.c.create_text(cx-20+j*55,start_y,text=h,
                                   fill=WHITE,font=("Arial",9,"bold"))

            self.tables[sys]=[]

            for h in range(24):
                row=[]
                y=start_y+18+h*16

                self.c.create_text(cx-100,y,
                    text=f"{h:02}-{(h+1)%24:02}",
                    anchor="w",fill=WHITE,font=("Arial",9))

                for j in range(3):
                    x = cx-20+j*55
                    t=self.c.create_text(x,y,text="0",fill=WHITE,font=("Arial",9))
                    row.append(t)

                    self.cell_map[t] = (sys,h,HUBS[j])

                self.tables[sys].append(row)

        if not hasattr(self,'blink_started'):
            self.blink_started=True
            self.blink()

    def update_counts(self,sys,s,f):
        self.c.itemconfig(self.refs[sys][0],text=f"Success:{s}")
        self.c.itemconfig(self.refs[sys][1],text=f"Failure:{f}")

    def update_tables(self):
        global blink_state

        for h in range(24):
            for hub in HUBS:
                vals=[round(aggregations[sys][h][hub],1) for sys in SYSTEMS]
                base_val = vals[0]

                for sys in SYSTEMS:
                    j=HUBS.index(hub)
                    val = round(aggregations[sys][h][hub],1)

                    if sys == 'VAT-P':
                        color = GREEN
                    else:
                        if val == base_val:
                            color = GREEN
                        else:
                            color = RED if blink_state else WHITE

                    self.c.itemconfig(self.tables[sys][h][j],
                        text=str(val),
                        fill=color)

    def blink(self):
        global blink_state
        blink_state = not blink_state
        self.update_tables()
        self.root.after(500, self.blink)

    # -------- TOOLTIP --------
    def on_hover(self,event):
        item = self.c.find_closest(event.x,event.y)
        if not item:
            return

        item = item[0]

        if item in self.cell_map:
            sys,h,hub = self.cell_map[item]
            val = round(aggregations[sys][h][hub],1)

            text=f"{sys}\nHour:{h}\nHub:{hub}\nVol:{val}"

            if self.tooltip:
                self.tooltip.destroy()

            self.tooltip = Toplevel(self.root)
            self.tooltip.overrideredirect(True)
            self.tooltip.geometry(f"+{event.x_root+10}+{event.y_root+10}")

            Label(self.tooltip,text=text,bg="black",fg="white").pack()
        else:
            if self.tooltip:
                self.tooltip.destroy()
                self.tooltip=None

    # -------- SMART CLICK --------
    def on_click(self,event):
        item = self.c.find_closest(event.x,event.y)
        if not item:
            return

        item=item[0]

        if item in self.cell_map:
            sys,h,hub = self.cell_map[item]

            if sys == 'VAT-P':
                os.startfile(VATP)
                return

            vals=[round(aggregations[s][h][hub],1) for s in SYSTEMS]
            base_val = vals[0]
            current_val = round(aggregations[sys][h][hub],1)

            if current_val == base_val:
                path = os.path.join(ROOT,sys,'success')
            else:
                path = os.path.join(ROOT,sys,'failure')

            os.startfile(path)

    def start(self):
        threading.Thread(target=self.run).start()

    def run(self):
        threading.Thread(target=gen_vatp,args=(self,)).start()
        time.sleep(1)
        threading.Thread(target=pipe,args=(VATP,USIP1,'USIP1',self)).start()
        time.sleep(1)
        threading.Thread(target=pipe,args=(os.path.join(USIP1,'success'),NEON,'Neon',self)).start()
        time.sleep(1)
        threading.Thread(target=pipe,args=(os.path.join(NEON,'success'),USIP2,'USIP2',self)).start()
        time.sleep(1)
        threading.Thread(target=pipe,args=(os.path.join(USIP2,'success'),ENDUR,'Endur',self)).start()

# ---------------- VATP ----------------
def gen_vatp(ui):
    src=os.path.join(SOURCE,os.listdir(SOURCE)[0])

    for i in range(TOTAL_MESSAGES):
        t=ET.parse(src)
        d=t.getroot()

        bs=random.choice(['Buy','Sell'])
        d.set('buy_sell',bs)

        ref=f"{d.get('reference')}_{i}"
        d.set('reference',ref)

        hub=random.choice(HUBS)
        d.find('.//receipt_point').set('name',hub)

        s,e,hour=rand_interval()
        vol=d.find('.//vol')

        val=random.uniform(0,10)
        val=val if bs=='Buy' else -val

        vol.set('val',str(val))
        vol.set('start',s)
        vol.set('end',e)

        t.write(os.path.join(VATP,ref+"_VATP.xml"))

        update_agg('VAT-P',hour,hub,val)

        ui.update_counts('VAT-P',len(os.listdir(VATP)),0)
        ui.update_tables()
        time.sleep(0.001)

# ---------------- PIPE ----------------
def pipe(src,dest,name,ui):
    processed=set()

    while True:
        files=[f for f in os.listdir(src) if f.endswith('.xml') and f not in processed]

        if not files and len(processed)>=TOTAL_MESSAGES:
            break

        for f in files:
            try:
                t=ET.parse(os.path.join(src,f))
                d=t.getroot()

                hub=d.find('.//receipt_point').get('name')
                vol=d.find('.//vol')
                val=float(vol.get('val'))
                hour=int(vol.get('start')[11:13])
            except:
                continue

            if name in FAIL_LIMITS and fail_counts[name] < FAIL_LIMITS[name]:
                target='failure'
                fail_counts[name]+=1
            else:
                target='success'

            t.write(os.path.join(dest,target,f"{f}_{name}.xml"))
            processed.add(f)

            if target=='success':
                update_agg(name,hour,hub,val)

            s=len(os.listdir(os.path.join(dest,'success')))
            fcount=len(os.listdir(os.path.join(dest,'failure')))

            ui.update_counts(name,s,fcount)
            ui.update_tables()
            time.sleep(0.001)

        time.sleep(0.01)

# ---------------- MAIN ----------------
root=Tk()
root.geometry("1700x800")
ui=UI(root)
root.mainloop()