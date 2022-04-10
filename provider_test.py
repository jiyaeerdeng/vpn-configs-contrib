import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from tempfile import mkstemp

base_dir = "/etc/openvpn"
openvpn_config_paths = Path(base_dir).rglob("*.ovpn")
number_of_configs = len(list(openvpn_config_paths))

_, auth_file_path = mkstemp()
with open(auth_file_path, "w") as auth_file:
    auth_file.writelines(["username\n", "password\n"])
print(f"Crated dummy auth file at {auth_file_path}")

results = {"providers": {}}
count = 0
for config_path in Path(base_dir).rglob("*.ovpn"):
    provider = config_path.relative_to(base_dir).parts[0]
    config = config_path.relative_to(Path(base_dir).joinpath(provider))

    if provider not in results["providers"]:
        results["providers"][provider] = {}

    # TODO: Remove. Initial testing, do max 10 configs per provider
    if len(results["providers"][provider].keys()) >= 10:
        continue

    print(f"Testing number {count} of {number_of_configs}")
    start = time.perf_counter()
    try:
        process = subprocess.run(
            [
                "openvpn",
                "--config",
                config_path,
                "--auth-user-pass",
                auth_file_path,
                "--connect-timeout",
                "3",
                "--resolv-retry",
                "1",
                "--connect-retry-max",
                "1",
            ],
            capture_output=True,
            timeout=10,
            encoding="UTF-8",
        )
    except Exception:
        server_responded = False
        auth_failed = None
        resolve_error = None
        retry_max = None
    else:
        server_responded = "Peer Connection Initiated" in process.stdout
        auth_failed = "AUTH_FAILED" in process.stdout
        resolve_error = "RESOLVE: Cannot resolve host address" in process.stdout

        retry_max_regex = re.compile(
            "All connections have been connect-retry-max .* times unsuccessful, exiting"
        )
        retry_max = bool(retry_max_regex.search(process.stdout))

        print(process.stdout)

    stop = time.perf_counter()

    results["providers"][provider][str(config)] = {
        "responded": server_responded,
        "auth_failed": auth_failed,
        "retry_max": retry_max,
        "resolve_error": resolve_error,
        "duration": round(stop - start, 2),
    }

    count = count + 1

# Collect results
results["summary"] = {}

for provider in results["providers"]:
    sucessful_connects = 0
    provider_duration = 0.0
    for config in results["providers"][provider]:
        provider_duration = (
            provider_duration + results["providers"][provider][config]["duration"]
        )
        if results["providers"][provider][config]["responded"]:
            sucessful_connects = sucessful_connects + 1
    total_configs = len(results["providers"][provider].keys())
    results["summary"][provider] = {
        "total": total_configs,
        "success": sucessful_connects,
    }

    results["summary"][provider]["duration"] = provider_duration
    results["summary"][provider]["rate"] = round(sucessful_connects / total_configs, 2)

timestamp = datetime.now().strftime("%d%m%Y%H%M")
with open(f"/tmp/data/result{timestamp}.json", "w") as outfile:
    json.dump(results, outfile, indent=4, sort_keys=True)
