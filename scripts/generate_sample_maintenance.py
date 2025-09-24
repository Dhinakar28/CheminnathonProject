"""Generate a synthetic predictive-maintenance dataset and save to data/sample_maintenance.csv

Columns produced:
- unit: engine/machine id
- cycle: time-step or cycle counter
- op_setting_1..3: operational settings
- s1..s8: sensor readings (vibration, temp, pressure, etc.)
- failure_flag: binary (0/1) indicating failure occurs at or after a cycle
- failure_mode: categorical failure mode ("none", "bearing", "wear", "electrical")
- RUL: Remaining Useful Life (max_cycle - cycle)

Run: python scripts/generate_sample_maintenance.py
"""
import random
from pathlib import Path
import pandas as pd
import numpy as np

OUT = Path('data') / 'sample_maintenance.csv'
OUT.parent.mkdir(parents=True, exist_ok=True)

random.seed(42)
np.random.seed(42)

rows = []
num_units = 25
for unit in range(1, num_units + 1):
    # each unit will have between 40 and 80 cycles
    max_cycle = random.randint(40, 80)
    # decide if this unit will experience a failure during these cycles
    will_fail = random.random() < 0.6  # 60% units have a failure
    if will_fail:
        # failure happens in the last 10 cycles
        fail_cycle = random.randint(max_cycle - 10, max_cycle)
        failure_mode = random.choice(['bearing', 'wear', 'electrical'])
    else:
        fail_cycle = None
        failure_mode = 'none'

    # baseline operational settings per unit
    op1 = round(random.uniform(0.5, 1.5), 3)
    op2 = round(random.uniform(0.0, 1.0), 3)
    op3 = round(random.uniform(100.0, 300.0), 2)

    for cycle in range(1, max_cycle + 1):
        # simulate sensors
        # s1: vibration - slowly increasing; sharp rise near failure
        base_vib = 0.5 + 0.01 * cycle + np.random.normal(0, 0.02)
        if will_fail and cycle >= (fail_cycle - 8):
            base_vib += 0.05 * (cycle - (fail_cycle - 8))
        s1 = round(max(0, base_vib), 4)

        # s2: temperature - slight trend up
        base_temp = 60 + 0.02 * cycle + np.random.normal(0, 0.5)
        if will_fail and cycle >= (fail_cycle - 5):
            base_temp += 0.5 * (cycle - (fail_cycle - 5))
        s2 = round(base_temp, 3)

        # s3: pressure - some noise
        s3 = round(30 + np.sin(cycle / 5.0) * 2 + np.random.normal(0, 0.3), 3)

        # s4: acoustic level - rises closer to failure
        s4 = round(40 + 0.1 * cycle + (2 if will_fail and cycle >= (fail_cycle - 6) else 0) + np.random.normal(0, 0.5), 3)

        # s5..s8: additional sensors random-ish
        s5 = round(100 + np.random.normal(0, 1), 3)
        s6 = round(0.01 * cycle + np.random.normal(0, 0.01), 4)
        s7 = round(500 + np.random.normal(0, 5), 3)
        s8 = round(np.random.uniform(0, 1), 3)

        failure_flag = 0
        fmode = 'none'
        if will_fail and cycle >= fail_cycle:
            failure_flag = 1
            fmode = failure_mode
        else:
            fmode = 'none'

        rows.append({
            'unit': unit,
            'cycle': cycle,
            'op_setting_1': op1,
            'op_setting_2': op2,
            'op_setting_3': op3,
            's1_vibration': s1,
            's2_temp': s2,
            's3_pressure': s3,
            's4_acoustic': s4,
            's5_flow': s5,
            's6_current': s6,
            's7_voltage': s7,
            's8_misc': s8,
            'failure_flag': failure_flag,
            'failure_mode': fmode,
            'RUL': max_cycle - cycle
        })

# create DataFrame and save
pdf = pd.DataFrame(rows)
pdf.to_csv(OUT, index=False)
print(f'Wrote sample dataset to: {OUT}  rows={len(pdf)}')
