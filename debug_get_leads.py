import asyncio
import json
import sys

sys.path.append("modern_dashboard/backend")
import main as backend


async def main():
    res = await backend.get_leads("simulation_to_handoff", limit=2, offset=0)
    # Convert to JSON to check NaN
    print(json.dumps(res, allow_nan=False)[:1000])


asyncio.run(main())
