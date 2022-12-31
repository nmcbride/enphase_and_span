import time

import schedule
from schedule import run_pending
from virtual_critical_load.enphase import Enphase


def process_ensemble_inventory(data: dict) -> dict:
    grid_status = None
    battery_levels = []

    enpower = next(item for item in data if item.get('type') == "ENPOWER")
    # this is hardcoded for one and probably shouldn't be
    grid_status = "UP" if enpower.get("devices")[0].get("mains_oper_state") == "closed" else "DOWN"

    encharge = next(item for item in data if item.get('type') == "ENCHARGE")
    for device in encharge.get("devices"):
        battery_levels.append(int(device.get("percentFull")))

    return {"grid_status": grid_status,
            "battery_levels": battery_levels,
            "battery_level": sum(battery_levels) / len(battery_levels)}


def print_process_ensemble_inventory_data(data: dict):
    print(f"Grid: {data.get('grid_status')}")
    print(f"Battery Level: {data.get('battery_level')} [{', '.join(str(x) for x in data.get('battery_levels'))}]")
    print()


def poll_enphase(enphase : Enphase):
    raw_data = enphase.ivp_ensemble_inventory()
    processed_data = process_ensemble_inventory(data=raw_data)
    print_process_ensemble_inventory_data(data=processed_data)
    if processed_data.get("grid_status") == "DOWN":
        print("Grid is down turning off breakers.")


if __name__ == "__main__":
    enphase = Enphase()
    enphase.envoy_ssl_verify = False
    enphase.load()

    schedule.every(10).seconds.do(poll_enphase, enphase=enphase)

    while True:
        run_pending()
        time.sleep(1)
