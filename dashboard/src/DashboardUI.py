import os
import random
import time
import threading
import xml.etree.ElementTree as ET
from tkinter import Tk, Canvas, Button, Toplevel, Label

# ---------------- CONFIG ----------------
TOTAL_MESSAGES = 700

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

# ---------------- THEME / STYLE ----------------
THEME = {
    'bg': "#1e1e1e",
    'box': "#003A8F",
    'green': "#00cc66",
    'red': "#ff4d4d",
    'white': "white",
    'muted': "#aab0b8",
}

FONT_FAMILY = "Segoe UI"
FONT_SMALL = (FONT_FAMILY, 9)
FONT_MED = (FONT_FAMILY, 13, "bold")
FONT_LARGE = (FONT_FAMILY, 14, "bold")

HEADER_HEIGHT = 50

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
        self.root = root
        root.configure(bg=THEME['bg'])

        self.c = Canvas(root, bg=THEME['bg'])
        self.c.pack(fill="both", expand=True)

        self.refs = {}
        self.tables = {}
        self.cell_map = {}
        self.tooltip = None
        self.tooltip_label = None
        self.last_updated = time.strftime("%Y-%m-%d %H:%M:%S")

        self.c.bind("<Configure>", self.draw)
        self.c.bind("<Motion>", self.on_hover)
        self.c.bind("<Button-1>", self.on_click)

        Button(root, text="Start Processing", command=self.start,
               bg="#444", fg="white").pack()

    def draw_header(self, w):
        # Title left, last-updated right
        title = "Dashboard"
        self.c.create_text(20, 20, anchor="w", text=title,
                           fill=THEME['white'], font=FONT_MED)
        ts = getattr(self, 'last_updated', '')
        self.c.create_text(w - 20, 20, anchor="e", text=f"Last updated: {ts}",
                           fill=THEME['muted'], font=FONT_SMALL)

    def draw(self, e=None):
        self.c.delete("all")
        self.cell_map.clear()

        w = self.c.winfo_width()
        # header
        self.draw_header(w)

        spacing = max(200, w // (len(SYSTEMS) + 1))

        for i, sys in enumerate(SYSTEMS):
            cx = spacing * (i + 1)
            hw = 60 if sys in ['USIP1', 'USIP2'] else 100

            self.c.create_rectangle(cx - hw, 60, cx + hw, 140, fill=THEME['box'], outline="")
            self.c.create_text(cx, 90, text=sys, fill=THEME['white'], font=FONT_MED)

            # badges for success/failure
            badge_w = 110
            badge_h = 28
            s_x0 = cx - badge_w - 6
            s_x1 = cx - 6
            s_y0 = 150
            s_y1 = s_y0 + badge_h
            s_rect = self.c.create_rectangle(s_x0, s_y0, s_x1, s_y1, fill=THEME['green'], outline="")
            s_text = self.c.create_text((s_x0 + s_x1) // 2, s_y0 + badge_h // 2, text="Success:0",
                                         fill=THEME['white'], font=FONT_LARGE)

            f_x0 = cx + 6
            f_x1 = cx + 6 + badge_w
            f_rect = self.c.create_rectangle(f_x0, s_y0, f_x1, s_y1, fill=THEME['red'], outline="")
            f_text = self.c.create_text((f_x0 + f_x1) // 2, s_y0 + badge_h // 2, text="Failure:0",
                                         fill=THEME['white'], font=FONT_LARGE)

            self.refs[sys] = (s_rect, s_text, f_rect, f_text)

            start_y = 220
            self.c.create_text(cx - 100, start_y, text="Hr", anchor="w",
                               fill=THEME['white'], font=FONT_SMALL)

            for j, h in enumerate(["H1", "H2", "H3"]):
                self.c.create_text(cx - 20 + j * 55, start_y, text=h,
                                   fill=THEME['white'], font=FONT_SMALL)

            self.tables[sys] = []

            for h in range(24):
                row = []
                y = start_y + 18 + h * 16

                self.c.create_text(cx - 100, y,
                    text=f"{h:02}-{(h+1)%24:02}",
                    anchor="w", fill=THEME['white'], font=FONT_SMALL)

                for j in range(3):
                    x = cx - 20 + j * 55
                    t = self.c.create_text(x, y, text="0", fill=THEME['white'], font=FONT_SMALL)
                    row.append(t)

                    self.cell_map[t] = (sys, h, HUBS[j])

                self.tables[sys].append(row)

        if not hasattr(self, 'blink_started'):
            self.blink_started = True
            self.blink()

    def update_counts(self, sys, s, f):
        if sys in self.refs:
            _, s_text, _, f_text = self.refs[sys]
            self.c.itemconfig(s_text, text=f"Success:{s}")
            self.c.itemconfig(f_text, text=f"Failure:{f}")
        # refresh header timestamp
        self.last_updated = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.draw()
        except Exception:
            pass

    def update_tables(self):
        global blink_state

        for h in range(24):
            for hub in HUBS:
                base_val = round(aggregations['VAT-P'][h][hub], 1)

                for sys in SYSTEMS:
                    j = HUBS.index(hub)
                    val = round(aggregations[sys][h][hub], 1)

                    if sys == 'VAT-P' or val == base_val:
                        color = THEME['green']
                    else:
                        color = THEME['red'] if blink_state else THEME['white']

                    self.c.itemconfig(self.tables[sys][h][j],
                                      text=str(val),
                                      fill=color)

    def blink(self):
        global blink_state
        blink_state = not blink_state
        self.update_tables()
        self.root.after(500, self.blink)

    # -------- TOOLTIP / HOVER --------
    def on_hover(self, event):
        item = self.c.find_closest(event.x, event.y)
        if not item:
            return

        item = item[0]

        if item in self.cell_map:
            # change cursor to indicate clickability
            try:
                self.c.config(cursor='hand2')
            except Exception:
                pass

            sys, h, hub = self.cell_map[item]
            val = round(aggregations[sys][h][hub], 1)

            text = f"{sys}\nHour:{h}\nHub:{hub}\nVol:{val}"

            if not self.tooltip:
                self.tooltip = Toplevel(self.root)
                self.tooltip.overrideredirect(True)
                self.tooltip_label = Label(self.tooltip, text=text, bg="black", fg=THEME['white'], padx=6, pady=4)
                self.tooltip_label.pack()
            else:
                try:
                    self.tooltip_label.config(text=text)
                except Exception:
                    pass

            self.tooltip.geometry(f"+{event.x_root+10}+{event.y_root+10}")
        else:
            try:
                self.c.config(cursor='')
            except Exception:
                pass
            if self.tooltip:
                try:
                    self.tooltip.destroy()
                except Exception:
                    pass
                self.tooltip = None
                self.tooltip_label = None

    # -------- SMART CLICK --------
    def on_click(self, event):
        item = self.c.find_closest(event.x, event.y)
        if not item:
            return

        item = item[0]

        if item in self.cell_map:
            sys, h, hub = self.cell_map[item]

            if sys == 'VAT-P':
                try:
                    os.startfile(VATP)
                except Exception:
                    pass
                return

            vals = [round(aggregations[s][h][hub], 1) for s in SYSTEMS]
            base_val = vals[0]
            current_val = round(aggregations[sys][h][hub], 1)

            if current_val == base_val:
                path = os.path.join(ROOT, sys, 'success')
            else:
                path = os.path.join(ROOT, sys, 'failure')

            try:
                os.startfile(path)
            except Exception:
                pass

    def start(self):
        threading.Thread(target=self.run).start()

    def run(self):
        threading.Thread(target=gen_vatp, args=(self,)).start()
        time.sleep(1)
        threading.Thread(target=pipe, args=(VATP, USIP1, 'USIP1', self)).start()
        time.sleep(1)
        threading.Thread(target=pipe, args=(os.path.join(USIP1, 'success'), NEON, 'Neon', self)).start()
        time.sleep(1)
        threading.Thread(target=pipe, args=(os.path.join(NEON, 'success'), USIP2, 'USIP2', self)).start()
        time.sleep(1)
        threading.Thread(target=pipe, args=(os.path.join(USIP2, 'success'), ENDUR, 'Endur', self)).start()

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