import argparse
import os
import threading
import queue
import time
from aggregator import Aggregator
from workers import gen_vatp, pipe
from ui import UI


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=os.path.join(os.getcwd(), 'Dashboard'))
    parser.add_argument('--total', type=int, default=750)
    parser.add_argument('--headless', action='store_true')
    args = parser.parse_args()

    SYSTEMS = ['VAT-P', 'USIP1', 'Neon', 'USIP2', 'Endur']
    HUBS = ["HUB 50HERTZ", "HUB TENNETDE", "HUB ENBW"]
    FAIL_LIMITS = {'USIP1': 0, 'Neon': 2, 'USIP2': 1, 'Endur': 3}

    aggregator = Aggregator(SYSTEMS, HUBS)
    ui_queue = queue.Queue()

    # ensure directories exist under root
    for s in [os.path.join(args.root, 'source'), os.path.join(args.root, 'VAT-P')]:
        os.makedirs(s, exist_ok=True)

    if args.headless:
        threading.Thread(target=gen_vatp, args=(aggregator, os.path.join(args.root, 'source'), os.path.join(args.root, 'VAT-P'), args.total, HUBS, None), daemon=True).start()
        time.sleep(1)
        threading.Thread(target=pipe, args=(os.path.join(args.root, 'VAT-P'), os.path.join(args.root, 'USIP1'), 'USIP1', aggregator, HUBS, FAIL_LIMITS, {}, args.total, None), daemon=True).start()
        # block until threads finish (simple)
        while threading.active_count() > 1:
            time.sleep(0.1)
    else:
        root = Tk()
        ui = UI(root, aggregator, ui_queue, SYSTEMS, HUBS)
        root.geometry("1700x800")
        root.mainloop()


if __name__ == "__main__":
    main()
