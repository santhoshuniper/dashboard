import os
import random
import time
import threading
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)


def rand_interval():
    h = random.randint(0, 23)
    m = random.choice([0, 15, 30, 45])
    endm = (m + 15) % 60
    endh = h if m < 45 else (h + 1) % 24
    return f"2025-01-27T{h:02}:{m:02}:00Z", f"2025-01-27T{endh:02}:{endm:02}:00Z", h


def gen_vatp(aggregator, source_template, vatp_dir, total_messages, hubs, ui_queue=None):
    os.makedirs(vatp_dir, exist_ok=True)
    if os.path.isdir(source_template):
        files = [f for f in os.listdir(source_template) if f.endswith('.xml')]
        if not files:
            raise FileNotFoundError("No xml templates in source_template directory")
        src = os.path.join(source_template, files[0])
    else:
        src = source_template

    for i in range(total_messages):
        try:
            t = ET.parse(src)
            d = t.getroot()
        except Exception:
            logger.exception("Failed to parse template %s", src)
            raise

        bs = random.choice(['Buy', 'Sell'])
        d.set('buy_sell', bs)
        ref = f"{d.get('reference')}_{i}" if d.get('reference') else f"REF_{i}"
        d.set('reference', ref)
        hub = random.choice(hubs)
        rpp = d.find('.//receipt_point')
        if rpp is not None:
            rpp.set('name', hub)
        s, e, hour = rand_interval()
        vol = d.find('.//vol')
        val = random.uniform(0, 10)
        val = val if bs == 'Buy' else -val
        if vol is not None:
            vol.set('val', str(val))
            vol.set('start', s)
            vol.set('end', e)

        outpath = os.path.join(vatp_dir, f"{ref}_VATP.xml")
        t.write(outpath)

        aggregator.update('VAT-P', hour, hub, val)
        if ui_queue:
            ui_queue.put({'type': 'agg', 'system': 'VAT-P', 'hour': hour, 'hub': hub, 'val': val})
            s_count = len([n for n in os.listdir(vatp_dir) if n.endswith('.xml')])
            ui_queue.put({'type': 'counts', 'system': 'VAT-P', 'success': s_count, 'failure': 0})

        time.sleep(0.001)


def pipe(src, dest, name, aggregator, hubs, fail_limits, fail_counts, total_messages, ui_queue=None):
    os.makedirs(dest, exist_ok=True)
    os.makedirs(os.path.join(dest, 'success'), exist_ok=True)
    os.makedirs(os.path.join(dest, 'failure'), exist_ok=True)
    processed = set()

    while True:
        try:
            files = [f for f in os.listdir(src) if f.endswith('.xml') and f not in processed]
        except FileNotFoundError:
            time.sleep(0.01)
            continue

        if not files and len(processed) >= total_messages:
            break

        for f in files:
            inpath = os.path.join(src, f)
            try:
                t = ET.parse(inpath)
                d = t.getroot()
                rpp = d.find('.//receipt_point')
                hub = rpp.get('name') if rpp is not None else None
                vol = d.find('.//vol')
                val = float(vol.get('val')) if vol is not None and vol.get('val') else 0.0
                hour = int(vol.get('start')[11:13]) if vol is not None and vol.get('start') else 0
            except Exception:
                logger.exception("Skipping invalid file: %s", inpath)
                processed.add(f)
                continue

            if name in fail_limits and fail_counts.get(name, 0) < fail_limits[name]:
                target = 'failure'
                fail_counts[name] = fail_counts.get(name, 0) + 1
            else:
                target = 'success'

            outpath = os.path.join(dest, target, f"{f}_{name}.xml")
            t.write(outpath)
            processed.add(f)

            if target == 'success':
                aggregator.update(name, hour, hub, val)
                if ui_queue:
                    ui_queue.put({'type': 'agg', 'system': name, 'hour': hour, 'hub': hub, 'val': val})

            s_count = len(os.listdir(os.path.join(dest, 'success')))
            f_count = len(os.listdir(os.path.join(dest, 'failure')))
            if ui_queue:
                ui_queue.put({'type': 'counts', 'system': name, 'success': s_count, 'failure': f_count})

            time.sleep(0.001)

        time.sleep(0.01)
