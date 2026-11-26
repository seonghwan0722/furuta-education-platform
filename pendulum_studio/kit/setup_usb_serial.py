#!/usr/bin/env python3
"""Pi 5 USB-C serial setup. Default: inspect only; never opens CAN/I2C or runs a policy.

Run on the Pi after copying app/kit. --apply requires root, an explicit power
acknowledgement and the existing real pi_host directory. Reboot stays manual.
"""
import argparse
import datetime
import glob
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CONFIG = Path('/boot/firmware/config.txt')
MODULES = Path('/etc/modules-load.d/pendulum-usb-serial.conf')
UNIT = Path('/etc/systemd/system/pendulum-kit-usb.service')
BACKEND = ('run_policy.py', 'session.py', 'canguard.py', 'policy_np.py', 'kitparams.py')
MARK = '# Pendulum Studio USB serial - begin'
END_MARK = '# Pendulum Studio USB serial - end'
BLOCK = '\n' + MARK + '\n[all]\ndtoverlay=dwc2,dr_mode=peripheral\n' + END_MARK + '\n'


def read(path):
    try:
        return Path(path).read_text(errors='replace').replace('\x00', '').strip()
    except OSError:
        return ''


def service_state(name, action):
    result = subprocess.run(['systemctl', action, name], capture_output=True, text=True, check=False)
    return result.stdout.strip()


def active_control_processes():
    found = []
    for path in glob.glob('/proc/[0-9]*/cmdline'):
        try:
            words = Path(path).read_bytes().decode(errors='replace').split('\x00')
            if any(Path(word).name in ('kit_server.py', 'run_policy.py') for word in words if word):
                found.append(int(Path(path).parent.name))
        except (OSError, ValueError):
            pass
    return found


def unit_arg(value, command=True):
    # systemd command-line quoting, without invoking a shell or expanding specifiers.
    value = str(value)
    if any(c in value for c in '\n\r\x00'):
        raise ValueError('Paths must not contain newlines or NUL.')
    value = value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    return '"' + (value.replace('$', '$$') if command else value) + '"'


def boot_config(config):
    """Recognise only this helper's exact, complete block; never hide edited settings."""
    errors = []
    outside = config
    starts, ends = config.count(MARK), config.count(END_MARK)
    managed = False
    if starts or ends:
        expected = BLOCK.strip('\n')
        if starts != 1 or ends != 1 or expected not in config:
            errors.append('The managed USB block is incomplete, duplicated or edited. Restore/review it manually.')
        elif not re.search(r'^' + re.escape(expected) + r'$', config, re.M):
            errors.append('USB block markers must occupy their own lines. Review config.txt manually.')
        else:
            managed = True
            outside = config.replace(expected, '', 1)
    if re.search(r'^\s*include\s+\S+', config, re.M):
        errors.append('config.txt includes another file. Review all included USB settings manually before applying this helper.')
    if re.search(r'^\s*dtoverlay\s*=\s*dwc2(?:,|\s|$)|^\s*otg_mode\s*=\s*1', outside, re.M):
        errors.append('An existing USB controller setting needs manual review before applying.')
    return managed, errors


def probe_service_user(account, python, host):
    """Check filesystem permissions and package discovery as the service account.

    This child process does not import the backend, open a hardware device or
    create a log file. Preserve the selected Python path (including venv links).
    """
    uid = pwd.getpwnam(account).pw_uid
    command = [str(python)]
    if os.geteuid() != uid:
        runuser = shutil.which('runuser')
        if os.geteuid() != 0 or not runuser:
            return {'error': 'Run inspection as the service account, or use sudo with --user and runuser available.'}
        command = [runuser, '-u', account, '--', str(python)]
    files = [HERE / 'kit_server.py', HERE / 'kit_cal.py', HERE / 'classical_control.py'] + [host / name for name in BACKEND]
    request = {
        'uid': uid, 'python': str(python), 'host': str(host),
        'files': [str(path) for path in files],
        'write_directories': [str(host / 'logs'), str(host / 'state'), str(host.parent / 'logs')]
    }
    code = '''import importlib.util,json,os,pathlib,sys
request=json.loads(sys.argv[1])
dependencies={}
for name in ("numpy","can","smbus2"):
    try:
        dependencies[name]=importlib.util.find_spec(name) is not None
    except (ImportError,ValueError,OSError):
        dependencies[name]=False
access={}
access["python_executable"]=os.path.isfile(request["python"]) and os.access(request["python"],os.X_OK)
access["host_directory"]=os.path.isdir(request["host"]) and os.access(request["host"],os.R_OK|os.X_OK)
for name in request["files"]:
    access[name]=os.path.isfile(name) and os.access(name,os.R_OK)
parents={}
for name in request["write_directories"]:
    target=pathlib.Path(name)
    parent=target
    while not os.path.lexists(parent) and parent != parent.parent:
        parent=parent.parent
    parents[name]=str(parent)
    access["write:"+name]=os.path.isdir(parent) and os.access(parent,os.W_OK|os.X_OK)
print(json.dumps({"uid":os.geteuid(),"dependencies":dependencies,"access":access,"write_parents":parents}))
'''
    environment = os.environ.copy()
    for name in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONUSERBASE', 'PYTHONSTARTUP', 'VIRTUAL_ENV'):
        environment.pop(name, None)
    try:
        result = subprocess.run(command + ['-c', code, json.dumps(request)], cwd='/',
                                capture_output=True, text=True, check=False, timeout=15, env=environment)
        if result.returncode != 0:
            return {'error': 'Service-account probe failed: ' + (result.stderr.strip() or str(result.returncode))}
        report = json.loads(result.stdout)
        if report.get('uid') != uid:
            return {'error': 'Dependency probe did not run as the service account.'}
        return report
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        return {'error': 'Service-account probe failed: ' + str(error)}


def inspect(args, account, python):
    host = Path(args.host_dir).expanduser().resolve()
    groups = {pwd.getpwnam(account).pw_gid}
    import grp
    groups.update(g.gr_gid for g in grp.getgrall() if account in g.gr_mem)
    group_names = sorted(grp.getgrgid(g).gr_name for g in groups)
    probe = probe_service_user(account, python, host)
    dependencies = probe.get('dependencies', {})
    config = read(CONFIG)
    errors = []
    if not read('/proc/device-tree/model').startswith('Raspberry Pi 5'):
        errors.append('This helper is for Raspberry Pi 5. Do not apply on another board.')
    if not CONFIG.is_file():
        errors.append('Missing /boot/firmware/config.txt; OS boot layout must be checked.')
    missing = [name for name in BACKEND if not (host / name).is_file()]
    if missing:
        errors.append('Existing pi_host files missing: ' + ', '.join(missing))
    if not all(dependencies.get(m) for m in ('numpy', 'can', 'smbus2')):
        errors.append('Selected Python must expose numpy, python-can and smbus2 to the service account.')
    if probe.get('error'):
        errors.append(probe['error'])
    denied = [name for name, allowed in probe.get('access', {}).items() if not allowed]
    if denied:
        errors.append('Service-account access denied or missing: ' + ', '.join(denied))
    if 'dialout' not in group_names or 'i2c' not in group_names:
        errors.append('Service user must already belong to dialout and i2c groups.')
    # Existing USB networking/composite gadgets need an explicit migration, not replacement.
    managed, config_errors = boot_config(config)
    errors.extend(config_errors)
    other_modules = read('/boot/firmware/cmdline.txt') + '\n' + read('/etc/modules')
    for path in glob.glob('/etc/modules-load.d/*.conf'):
        if Path(path) != MODULES:
            other_modules += '\n' + read(path)
    if re.search(r'\bg_(?:ether|multi|serial|mass_storage|hid|midi|acm_ms)\b', other_modules):
        errors.append('An existing boot gadget module needs manual review before applying.')
    usb_gadget = service_state('rpi-usb-gadget.service', 'is-enabled')
    if usb_gadget in ('enabled', 'enabled-runtime', 'static') or service_state('rpi-usb-gadget.service', 'is-active') == 'active':
        errors.append('rpi-usb-gadget manages USB networking; do not enable g_serial alongside it.')
    if glob.glob('/sys/kernel/config/usb_gadget/*'):
        errors.append('A ConfigFS USB gadget already exists; preserve it until migration is reviewed.')
    old_server = service_state('kit-server.service', 'is-enabled')
    if old_server in ('enabled', 'enabled-runtime') or service_state('kit-server.service', 'is-active') == 'active':
        errors.append('Existing kit-server service must be reviewed before installing a second receiver.')
    processes = active_control_processes()
    if processes:
        errors.append('A kit/policy process is running. Stop it yourself before applying setup.')
    if UNIT.exists() and 'Managed by Pendulum Studio setup_usb_serial.py' not in read(UNIT):
        errors.append('Target service already exists and is not managed by this helper.')
    target_state = service_state(UNIT.name, 'is-enabled')
    if target_state not in ('', 'not-found', 'disabled', 'enabled'):
        errors.append('Target service enable state requires manual review: ' + target_state)
    if MODULES.exists() and read(MODULES) != 'dwc2\ng_serial':
        errors.append('Target modules file already has different content; preserve it for review.')
    return {
        'mode': 'read-only inspection', 'board': read('/proc/device-tree/model'),
        'os': read('/etc/os-release'), 'user': account, 'groups': group_names,
        'python': str(python), 'dependencies': dependencies, 'host_dir': str(host),
        'service_account_probe': probe, 'managed_boot_block': managed, 'target_service_enabled': target_state,
        'missing_backend_files': missing, 'serial_devices': sorted(set(glob.glob('/dev/ttyGS*') + glob.glob('/dev/serial/by-id/*'))),
        'i2c1_present': Path('/dev/i2c-1').exists(), 'can0_present': Path('/sys/class/net/can0').exists(),
        'controller_process_ids': processes, 'setup_errors': errors,
        'note': 'No CAN/I2C/serial device was opened. Hardware readiness and watchdog cutoff are not verified.'
    }


def replace_with_backup(path, content, changes):
    record = {'file': str(path), 'existed': path.exists(), 'backup': None, 'backup_ready': False, 'status': 'preparing'}
    changes.append(record)
    if path.exists() and path.read_text() == content:
        record['status'] = 'unchanged'
        print(json.dumps({'file_action': record}), flush=True)
        return
    backup = None
    if path.exists():
        suffix = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        backup = path.with_name(path.name + '.pendulum-backup-' + suffix)
        record['backup'] = str(backup)
        shutil.copy2(path, backup)
        record['backup_ready'] = True
    record['status'] = 'backed-up' if backup else 'new-file-planned'
    print(json.dumps({'file_action': record}), flush=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.pendulum-tmp-' + str(os.getpid()))
    created = False
    try:
        with temporary.open('x') as handle:
            created = True
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o644)
        temporary.replace(path)
        record['status'] = 'applied'
        print(json.dumps({'file_action': record}), flush=True)
    finally:
        if created and temporary.exists():
            temporary.unlink()


def recovery_instructions(changes, enabled_before, enable_attempted):
    commands = []
    # Do not disable a service that was enabled before this invocation.
    if enable_attempted and enabled_before not in ('enabled', 'enabled-runtime'):
        commands.append('sudo systemctl disable ' + shlex.quote(UNIT.name))
    for record in reversed(changes):
        if record['status'] != 'applied':
            continue
        if record['backup_ready']:
            commands.append('sudo cp -- ' + shlex.quote(record['backup']) + ' ' + shlex.quote(record['file']))
        elif not record['existed']:
            commands.append('sudo rm -- ' + shlex.quote(record['file']))
    commands.append('sudo systemctl daemon-reload')
    return commands


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-dir', required=True, help='Existing, current pi_host directory; never overwritten')
    parser.add_argument('--user', default=os.environ.get('SUDO_USER') or pwd.getpwuid(os.getuid()).pw_name)
    parser.add_argument('--python', default=sys.executable, help='Python containing the real backend dependencies')
    parser.add_argument('--apply', action='store_true', help='Back up and configure boot + service; no reboot or motor run')
    parser.add_argument('--power-confirmed', action='store_true', help='Operator has confirmed suitable power while USB-C is used for data')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Run this helper on the Raspberry Pi, not Windows.')
    try:
        account = pwd.getpwnam(args.user)
    except KeyError:
        parser.error('Service user does not exist.')
    if account.pw_uid == 0:
        parser.error('Specify the normal Pi account with --user; the receiver must not run as root.')
    python = Path(args.python).expanduser().absolute()
    if not python.is_file():
        parser.error('Selected Python does not exist.')
    report = inspect(args, args.user, python)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not args.apply:
        return 0 if not report['setup_errors'] else 2
    if os.geteuid() != 0 or not args.power_confirmed:
        parser.error('--apply needs sudo and --power-confirmed. Confirm power before changing USB-C mode.')
    if report['setup_errors']:
        print('NOT APPLIED: resolve the setup_errors above first.', file=sys.stderr)
        return 2
    host = Path(report['host_dir'])
    service = '\n'.join([
        '# Managed by Pendulum Studio setup_usb_serial.py', '[Unit]',
        'Description=Pendulum Studio USB serial policy receiver', 'After=systemd-modules-load.service',
        '', '[Service]', 'Type=simple', 'User=' + args.user,
        'WorkingDirectory=' + unit_arg(host, command=False), 'Environment=PYTHONUNBUFFERED=1',
        'Environment=OPENBLAS_NUM_THREADS=1', 'Environment=OMP_NUM_THREADS=1', 'Environment=MKL_NUM_THREADS=1',
        'ExecStart=' + ' '.join(unit_arg(v) for v in (python, HERE / 'kit_server.py', '--serial', '/dev/ttyGS0', '--host-dir', host)),
        'Restart=on-failure', 'RestartSec=2', 'KillSignal=SIGTERM', 'TimeoutStopSec=8',
        '', '[Install]', 'WantedBy=multi-user.target', ''
    ])
    original = CONFIG.read_text()
    managed, config_errors = boot_config(original)
    if config_errors:
        raise ValueError('Boot configuration changed or needs review: ' + '; '.join(config_errors))
    changes = []
    enabled_before = service_state(UNIT.name, 'is-enabled')
    enable_attempted = False
    try:
        for path, content in ((CONFIG, original if managed else original.rstrip() + BLOCK), (MODULES, 'dwc2\ng_serial\n'), (UNIT, service)):
            replace_with_backup(path, content, changes)
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        enable_attempted = True
        subprocess.run(['systemctl', 'enable', UNIT.name], check=True)  # Deliberately no --now.
    except (OSError, ValueError, subprocess.CalledProcessError):
        print('PARTIAL SETUP: do not reboot yet. Review the applied files and recovery commands below. No rollback was run automatically.', file=sys.stderr, flush=True)
        print(json.dumps({'file_actions': changes, 'service_enabled_before': enabled_before,
                          'service_enable_attempted': enable_attempted,
                          'recovery_commands': recovery_instructions(changes, enabled_before, enable_attempted)}, indent=2), file=sys.stderr, flush=True)
        raise
    print(json.dumps({'configured': changes, 'service': UNIT.name, 'reboot_required': True,
                      'service_enabled_before': enabled_before,
                      'recovery_commands': recovery_instructions(changes, enabled_before, enable_attempted)}, indent=2))
    print('Setup saved. Reboot manually when ready. The receiver waits for app commands; no policy was run.')
    print('After reboot: systemctl status ' + UNIT.name + ' --no-pager')
    print('Recovery commands above restore only this invocation\'s changes and preserve a previously enabled service. Review before running; reboot remains manual.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print('Setup failed: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
