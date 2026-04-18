import os
import random
import time
import threading
import xml.etree.ElementTree as ET
from tkinter import Tk, Canvas, Button, Toplevel, Label
import tkinter.font as tkfont

# ---------------- CONFIG ----------------
TOTAL_MESSAGES = 750

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

# color palette (blue theme)
BG = "#0b3b6f"
BOX = "#cfe8ff"
ACCENT = "#00aaff"
NEON_COLOR = "#bff1ff"
GREEN = "#00cc66"
RED = "#ff4d4d"
WHITE = "white"

# extra colors / surfaces
DARK_CELL = "#052a41"
GOOD_BG = "#0f4f33"
BAD_BG = "#3d1212"
HEADER_BG = "#042044"
SHADOW_BG = "#011229"
SHADOW_LIGHT = "#06293b"
PANEL_BORDER = "#9fdcff"
SYS_LABEL_COLOR = "#023049"
TOOLTIP_BG = "#052a3b"

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

        self.c=Canvas(root,bg=BG,highlightthickness=0)
        self.c.pack(fill="both",expand=True)

        self.refs={}
        self.tables={}
        self.cell_map={}
        self.tooltip=None

        self.c.bind("<Configure>",self.draw)
        self.c.bind("<Motion>",self.on_hover)
        self.c.bind("<Button-1>",self.on_click)

        # UI layout & fonts
        self.header_h = 90
        self.title = "Neon Dashboard"
        self.subtitle = "Real-time aggregation view"
        self.font_title = ("Segoe UI", 18, "bold")
        self.font_sub = ("Segoe UI", 10)
        self.font_cell = ("Segoe UI", 10)
        self.font_badge = ("Segoe UI", 10, "bold")
        # graph/layout settings
        self.graph_pad = 12
        # flow animation state
        self.flow_paths = []
        self.flow_dots = []
        self.flow_after_id = None
        self.flow_dot_radius = 4

        # draw once shortly after init so items exist for background threads
        self.root.after(50, self.draw)

    def draw(self,e=None):
        self.c.delete("all")
        self.cell_map.clear()

        w = max(800, self.c.winfo_width())
        h = max(400, self.c.winfo_height())

        # top header with subtle shadow/glow
        self.c.create_rectangle(0,0,w,self.header_h,fill=HEADER_BG,outline="")
        # title shadow
        self.c.create_text(25,self.header_h//2+1,anchor="w",text=self.title,fill="#001a24",font=self.font_title)
        self.c.create_text(24,self.header_h//2,anchor="w",text=self.title,fill=NEON_COLOR,font=self.font_title)
        # subtitle shadow and main
        self.c.create_text(27,self.header_h//2+29,anchor="w",text=self.subtitle,fill="#063d52",font=self.font_sub)
        self.c.create_text(26,self.header_h//2+28,anchor="w",text=self.subtitle,fill="#9bb0c9",font=self.font_sub)

        # start button (canvas-based) with glow outline
        btn_w, btn_h = 160, 36
        bx = w - 24 - btn_w
        by = self.header_h//2 - btn_h//2
        bex = bx + btn_w
        bey = by + btn_h
        # glow outline behind button
        self.c.create_rectangle(bx-4, by-4, bex+4, bey+4, outline=ACCENT, width=2, tags=("startbtn_glow",))
        self.c.create_rectangle(bx,by,bex,bey,fill=ACCENT,outline="",tags=("startbtn","startbtn_rect"))
        self.c.create_text((bx+bex)//2,(by+bey)//2, text="Start Processing",
                   fill="white",font=self.font_badge,tags=("startbtn","startbtn_text"))
        self.c.tag_bind("startbtn","<Button-1>",lambda ev: self.start())
        self.c.tag_bind("startbtn","<Enter>",lambda ev: self.c.itemconfig("startbtn_rect",fill="#33b7ff"))
        self.c.tag_bind("startbtn","<Leave>",lambda ev: self.c.itemconfig("startbtn_rect",fill=ACCENT))

        spacing = w//6

        # draw system panels and tables
        top_panel = self.header_h + 12
        badge_h = 28

        for i,sys in enumerate(SYSTEMS):
            cx = spacing*(i+1)
            hw = 80 if sys in ['USIP1','USIP2'] else 110

            panel_y1 = top_panel
            panel_y2 = panel_y1 + 76

            # panel drop shadow (layered) for 3D feel
            self.c.create_rectangle(cx-hw+8,panel_y1+8,cx+hw+8,panel_y2+8,fill=SHADOW_BG,outline="")
            self.c.create_rectangle(cx-hw+4,panel_y1+4,cx+hw+4,panel_y2+4,fill=SHADOW_LIGHT,outline="")

            # panel body
            self.c.create_rectangle(cx-hw,panel_y1,cx+hw,panel_y2,fill=BOX,outline="")
            # subtle border/glow
            self.c.create_rectangle(cx-hw+1,panel_y1+1,cx+hw-1,panel_y2-1,outline=PANEL_BORDER,width=1)
            # system name with small shadow and clear label color
            self.c.create_text(cx+1,(panel_y1+panel_y2)//2+1,text=sys,fill=SHADOW_BG,font=("Segoe UI",13,"bold"))
            self.c.create_text(cx,(panel_y1+panel_y2)//2,text=sys,fill=SYS_LABEL_COLOR,font=("Segoe UI",13,"bold"))

            # badges for success / failure
            bx_s = cx - 74
            bx_f = cx + 6
            by_bad = panel_y2 + 12
            s_rect = self.c.create_rectangle(bx_s,by_bad,bx_s+70,by_bad+badge_h,fill=GREEN,outline="")
            f_rect = self.c.create_rectangle(bx_f,by_bad,bx_f+70,by_bad+badge_h,fill=RED,outline="")

            s_text = self.c.create_text(bx_s+35,by_bad+badge_h//2,text="0",fill="white",font=self.font_badge)
            f_text = self.c.create_text(bx_f+35,by_bad+badge_h//2,text="0",fill="white",font=self.font_badge)
            self.refs[sys] = (s_text,f_text)

            # table headers (use hub short names)
            start_y = by_bad + badge_h + 18
            self.c.create_text(cx-100,start_y,text="Hr",anchor="w",fill="#9fb4cc",font=("Segoe UI",9,"bold"))
            hub_labels = [h.replace('HUB ','') for h in HUBS]
            for j,hdr in enumerate(hub_labels):
                self.c.create_text(cx-20+j*70,start_y,text=hdr,fill="#9fb4cc",font=("Segoe UI",9,"bold"))

            self.tables[sys] = []

            # rows (24 hours)
            row_h = 18
            for h_idx in range(24):
                row = []
                y = start_y + 18 + h_idx*row_h
                self.c.create_text(cx-100,y,
                    text=f"{h_idx:02}-{(h_idx+1)%24:02}",anchor="w",fill="#aebfd1",font=("Segoe UI",9))

                for j in range(3):
                    x = cx-20+j*70
                    rect_id = self.c.create_rectangle(x-26,y-10,x+26,y+10,fill=DARK_CELL,outline=PANEL_BORDER)
                    txt_id = self.c.create_text(x,y,text="0",fill=WHITE,font=self.font_cell)
                    row.append((rect_id,txt_id))

                    self.cell_map[rect_id] = (sys,h_idx,HUBS[j])
                    self.cell_map[txt_id] = (sys,h_idx,HUBS[j])

                self.tables[sys].append(row)

        if not hasattr(self,'blink_started'):
            self.blink_started=True
            self.blink()
        # prepare and start flow animations between panels
        try:
            panel_info = []
            for i, sys in enumerate(SYSTEMS):
                cx = spacing*(i+1)
                hw = 80 if sys in ['USIP1','USIP2'] else 110
                panel_y1 = top_panel
                panel_y2 = panel_y1 + 76
                center_y = (panel_y1 + panel_y2) // 2
                panel_info.append((cx, hw, center_y))
            self._setup_flows(panel_info)
        except Exception:
            pass

    def update_counts(self,sys,s,f):
        # schedule UI update on main thread
        def _u():
            try:
                if sys in self.refs:
                    self.c.itemconfig(self.refs[sys][0],text=str(s))
                    self.c.itemconfig(self.refs[sys][1],text=str(f))
            except Exception:
                pass
        self.root.after(0,_u)

    def update_tables(self):
        global blink_state

        def _u():
            try:
                for sys in SYSTEMS:
                    for h in range(24):
                        for j,hub in enumerate(HUBS):
                            rect_id, text_id = self.tables[sys][h][j]
                            val = round(aggregations[sys][h][hub],1)

                            if sys == 'VAT-P':
                                color = GREEN
                            else:
                                base_val = round(aggregations['VAT-P'][h][hub],1)
                                if val == base_val:
                                    color = GREEN
                                else:
                                    color = RED if blink_state else WHITE

                            # text color and rect background
                            self.c.itemconfig(text_id, text=str(val), fill=color)
                            if color == GREEN:
                                self.c.itemconfig(rect_id, fill=GOOD_BG)
                            elif color == RED:
                                self.c.itemconfig(rect_id, fill=BAD_BG)
                            else:
                                self.c.itemconfig(rect_id, fill=DARK_CELL)
                # (graphs removed)
            except Exception:
                pass

        self.root.after(0,_u)

    def blink(self):
        global blink_state
        blink_state = not blink_state
        self.update_tables()
        self.root.after(500, self.blink)

    def _setup_flows(self, panel_info):
        # cancel previous animation
        try:
            if self.flow_after_id:
                self.root.after_cancel(self.flow_after_id)
        except Exception:
            pass

        # clear previous packet items
        try:
            for d in self.flow_dots:
                try:
                    ids = d.get('ids') or [d.get('id')]
                    for oid in ids:
                        if oid:
                            self.c.delete(oid)
                except Exception:
                    pass
        except Exception:
            pass

        self.flow_dots = []
        self.flow_paths = []

        # create paths between consecutive panels
        for i in range(len(panel_info)-1):
            sx, shw, sy = panel_info[i]
            ex, ehw, ey = panel_info[i+1]
            start_x = sx + shw + 8
            end_x = ex - ehw - 8
            y = int((sy + ey) / 2)
            if end_x - start_x > 8:
                self.flow_paths.append((start_x, y, end_x, y))

        # create moving packet icons along each path
        for p_idx, (sx, sy, ex, ey) in enumerate(self.flow_paths):
            num = max(3, int((ex - sx) // 80))
            num = min(num, 8)
            for k in range(num):
                progress = k / num
                x = sx + (ex - sx) * progress
                y = sy
                r = self.flow_dot_radius
                try:
                    # packet: small rectangle with a seam line
                    box_id = self.c.create_rectangle(x - r*1.5, y - r, x + r*1.5, y + r, fill=ACCENT, outline=PANEL_BORDER, tags=("flow_packet",))
                    seam_id = self.c.create_line(x - r*1.1, y, x + r*1.1, y, fill=SHADOW_BG, width=1, tags=("flow_packet",))
                except Exception:
                    box_id = None
                    seam_id = None
                dot = {'ids': [box_id, seam_id], 'path_idx': p_idx, 'progress': progress, 'speed': 0.01 + random.random() * 0.02}
                self.flow_dots.append(dot)

        # start animator
        self.flow_after_id = self.root.after(60, self._animate_flows)

    def _animate_flows(self):
        try:
            for dot in list(self.flow_dots):
                try:
                    dot['progress'] += dot['speed']
                    if dot['progress'] > 1:
                        dot['progress'] -= 1

                    p = self.flow_paths[dot['path_idx']]
                    sx, sy, ex, ey = p
                    x = sx + (ex - sx) * dot['progress']
                    y = sy + (ey - sy) * dot['progress']
                    r = self.flow_dot_radius
                    box_w = r * 1.5
                    box_h = r * 1.0
                    line_w = r * 1.1
                    ids = dot.get('ids', [])
                    try:
                        if ids:
                            box_id = ids[0]
                            seam_id = ids[1] if len(ids) > 1 else None
                            if box_id is not None:
                                self.c.coords(box_id, x-box_w, y-box_h, x+box_w, y+box_h)
                            if seam_id is not None:
                                self.c.coords(seam_id, x-line_w, y, x+line_w, y)
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

        # schedule next frame
        try:
            self.flow_after_id = self.root.after(60, self._animate_flows)
        except Exception:
            self.flow_after_id = None

    # graphs removed: mini-graph rendering was intentionally removed per request

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
            Label(self.tooltip,text=text,bg=TOOLTIP_BG,fg="white",padx=8,pady=6,font=self.font_sub).pack()
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

    print(f"[PIPE] {name} watching {src} -> {dest}")

    while True:
        try:
            files=[f for f in os.listdir(src) if f.endswith('.xml') and f not in processed]
        except Exception as e:
            print(f"[PIPE] {name} error listing {src}: {e}")
            files = []

        if files:
            print(f"[PIPE] {name} found {len(files)} files in {src}")

        if not files and len(processed)>=TOTAL_MESSAGES:
            break

        for f in files:
            fullpath = os.path.join(src,f)
            try:
                print(f"[PIPE] {name} processing {fullpath}")
                t=ET.parse(fullpath)
                d=t.getroot()

                rp = d.find('.//receipt_point')
                hub = rp.get('name') if rp is not None else 'UNKNOWN'

                vol=d.find('.//vol')
                if vol is None:
                    print(f"[PIPE] {name} missing <vol> in {fullpath}")
                    continue

                val=float(vol.get('val'))
                hour=int(vol.get('start')[11:13])
            except Exception as e:
                print(f"[PIPE] {name} error parsing {fullpath}: {e}")
                continue

            if name in FAIL_LIMITS and fail_counts.get(name,0) < FAIL_LIMITS[name]:
                target='failure'
                fail_counts[name]+=1
            else:
                target='success'

            out_dir = os.path.join(dest, target)
            try:
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, f"{f}_{name}.xml")
                t.write(out_path)
                print(f"[PIPE] {name} wrote {out_path} -> {target}")
            except Exception as e:
                print(f"[PIPE] {name} error writing to {out_dir}: {e}")
                continue

            processed.add(f)

            if target=='success':
                update_agg(name,hour,hub,val)

            try:
                s=len(os.listdir(os.path.join(dest,'success')))
            except Exception:
                s=0
            try:
                fcount=len(os.listdir(os.path.join(dest,'failure')))
            except Exception:
                fcount=0

            ui.update_counts(name,s,fcount)
            ui.update_tables()
            time.sleep(0.001)

        time.sleep(0.01)

# ---------------- MAIN ----------------
root=Tk()
root.geometry("1700x800")
ui=UI(root)
root.mainloop()