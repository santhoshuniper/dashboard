import queue
import threading
from tkinter import Tk, Canvas, Button, Toplevel, Label
import os


class UI:
    def __init__(self, root, aggregator, ui_queue, systems, hubs):
        self.root = root
        self.aggregator = aggregator
        self.ui_queue = ui_queue
        self.systems = systems
        self.hubs = hubs
        root.configure(bg="#1e1e1e")
        self.c = Canvas(root, bg="#1e1e1e")
        self.c.pack(fill="both", expand=True)
        self.refs = {}
        self.tables = {}
        self.cell_map = {}
        self.tooltip = None
        self.c.bind("<Configure>", self.draw)
        self.c.bind("<Motion>", self.on_hover)
        self.c.bind("<Button-1>", self.on_click)
        Button(root, text="Start Processing", command=self.start, bg="#444", fg="white").pack()
        self.blink_state = True
        self.root.after(200, self.process_queue)

    def process_queue(self):
        try:
            while True:
                item = self.ui_queue.get_nowait()
                # aggregator holds authoritative state; counts updates are shown directly
                if item.get('type') == 'counts':
                    self.update_counts(item['system'], item.get('success', 0), item.get('failure', 0))
        except queue.Empty:
            pass
        self.root.after(200, self.process_queue)

    def draw(self, e=None):
        # simple layout: create placeholders if missing
        self.c.delete("all")
        self.cell_map.clear()
        w = self.c.winfo_width() or 1000
        spacing = w // (len(self.systems) + 1)
        start_y = 120
        for i, sys in enumerate(self.systems):
            cx = spacing * (i + 1)
            hw = 60 if sys in ['USIP1', 'USIP2'] else 100
            self.c.create_rectangle(cx - hw, 60, cx + hw, 140, fill="#003A8F")
            self.c.create_text(cx, 90, text=sys, fill="white", font=("Arial", 13, "bold"))
            s = self.c.create_text(cx, 155, text="Success:0", fill="white", font=("Arial", 14, "bold"))
            f = self.c.create_text(cx, 180, text="Failure:0", fill="white", font=("Arial", 14))
            self.refs[sys] = (s, f)
            for h in range(24):
                y = start_y + 18 + h * 16
                self.c.create_text(cx - 100, y, text=f"{h:02}-{(h+1)%24:02}", anchor="w", fill="white", font=("Arial", 9))
                for j, hub in enumerate(self.hubs[:3]):
                    x = cx - 20 + j * 55
                    t = self.c.create_text(x, y, text="0", fill="white", font=("Arial", 9))
                    self.cell_map[t] = (sys, h, hub)
        if not hasattr(self, 'blink_started'):
            self.blink_started = True
            self.blink()

    def update_counts(self, sys, s, f):
        if sys in self.refs:
            self.c.itemconfig(self.refs[sys][0], text=f"Success:{s}")
            self.c.itemconfig(self.refs[sys][1], text=f"Failure:{f}")

    def update_tables(self):
        # pull snapshot from aggregator
        snap = self.aggregator.snapshot()
        for sys in self.systems:
            for h in range(24):
                for j, hub in enumerate(self.hubs[:3]):
                    val = round(snap[sys][h][hub], 1)
                    for item_id, (s_sys, s_h, s_hub) in list(self.cell_map.items()):
                        if s_sys == sys and s_h == h and s_hub == hub:
                            color = "white"
                            if sys == 'VAT-P':
                                color = "#00cc66"
                            self.c.itemconfig(item_id, text=str(val), fill=color)

    def blink(self):
        self.blink_state = not self.blink_state
        self.update_tables()
        self.root.after(500, self.blink)

    def on_hover(self, event):
        item = self.c.find_closest(event.x, event.y)
        if not item:
            return
        item = item[0]
        if item in self.cell_map:
            sys, h, hub = self.cell_map[item]
            val = self.aggregator.get(sys, h, hub)
            text = f"{sys}\nHour:{h}\nHub:{hub}\nVol:{round(val,1)}"
            if self.tooltip:
                self.tooltip.destroy()
            self.tooltip = Toplevel(self.root)
            self.tooltip.overrideredirect(True)
            self.tooltip.geometry(f"+{event.x_root+10}+{event.y_root+10}")
            Label(self.tooltip, text=text, bg="black", fg="white").pack()
        else:
            if self.tooltip:
                self.tooltip.destroy()
                self.tooltip = None

    def on_click(self, event):
        item = self.c.find_closest(event.x, event.y)
        if not item:
            return
        item = item[0]
        if item in self.cell_map:
            sys, h, hub = self.cell_map[item]
            path = None
            if sys == 'VAT-P':
                path = os.path.join(os.getcwd(), 'VAT-P')
            else:
                path = os.path.join(os.getcwd(), sys, 'success')
            try:
                os.startfile(path)
            except Exception:
                pass

    def start(self):
        # UI start is left to app orchestrator; placeholder
        pass
