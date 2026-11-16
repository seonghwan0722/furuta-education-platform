"""Run Pi sensor acquisition in a console so OpenSSH can prompt for credentials."""
import argparse
import base64
import json
from pathlib import Path
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
CONNECTION = ROOT / 'deployment/pi/connection.local.json'
PROFILE = ROOT / 'deployment/pi/rmd_x6_48v.local.json'
DEFAULT_PROFILE = ROOT / 'deployment/pi/rmd_x6_48v.json'


def remote_command(mode, remote_dir, seconds):
    if mode == 'pose':
        source = ROOT / 'deployment/pi/rmd_read_pose.py'
        encoded = base64.b64encode(source.read_bytes()).decode('ascii')
        return ("echo 'Sensor read in 5 seconds. Hold the requested pose.' && sleep 5 && "
                f"printf %s {encoded} | base64 -d | python3 -")
    source = PROFILE if PROFILE.is_file() else DEFAULT_PROFILE
    profile = base64.b64encode(source.read_bytes()).decode('ascii')
    return (
        f"cd {shlex.quote(remote_dir)} && umask 077 && profile=$(mktemp) && "
        "trap 'rm -f \"$profile\"' EXIT && "
        f"printf %s {profile} | base64 -d > \"$profile\" && "
        'python3 -m deployment.pi.rmd_policy_shadow "$profile" '
        f'runs/balance_lqr_ppo_s42/export --seconds {seconds} --telemetry'
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('pose', 'live'), required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--seconds', type=int, choices=range(1, 31), default=20)
    args = parser.parse_args()
    with args.log.open('w', encoding='utf-8', buffering=1) as log:
        try:
            connection = json.loads(CONNECTION.read_text(encoding='utf-8-sig'))
            target = connection['target']
            if not isinstance(target, str) or not target or target.startswith('-') or any(c.isspace() for c in target):
                raise ValueError('Invalid SSH destination in connection.local.json')
            command = remote_command(args.mode, connection['remote_dir'], args.seconds)
            with subprocess.Popen(
                    ['ssh', '-T', '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=5',
                     '-o', 'ServerAliveCountMax=2', target, command],
                    stdout=subprocess.PIPE, text=True, encoding='utf-8', errors='replace') as process:
                for line in process.stdout:
                    log.write(line)
                    print(line, end='', flush=True)
                if process.wait():
                    raise RuntimeError(f'SSH or sensor command exited with code {process.returncode}')
        except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
            message = f'Pi 센서 오류 · {exc}'
            log.write(message + '\n')
            print(message, flush=True)
            time.sleep(4)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
