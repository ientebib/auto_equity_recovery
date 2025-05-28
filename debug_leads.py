import json
import math
import numbers
import sys

import pandas as pd

sys.path.append("modern_dashboard/backend")
import main as backend

df = pd.read_csv("output_run/simulation_to_handoff/latest.csv")
leads = backend.process_lead_data(df, "simulation_to_handoff")
print("Total leads", len(leads))
for i, lead in enumerate(leads):
    try:
        json.dumps(lead, allow_nan=False)
    except ValueError:
        print("Bad lead at index", i)
        for k, v in lead.items():
            if isinstance(v, numbers.Real) and (math.isnan(v) or math.isinf(v)):
                print("bad key", k, v)
            elif isinstance(v, dict):
                for kk, vv in v.items():
                    if isinstance(vv, numbers.Real) and (
                        math.isnan(vv) or math.isinf(vv)
                    ):
                        print("bad nested key", kk, vv)
        break
