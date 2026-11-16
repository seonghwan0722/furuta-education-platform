"""Desktop controls for read-only Pi sensor commissioning."""
import json
import math
from pathlib import Path
import subprocess
import sys
from tkinter import messagebox, ttk
from uuid import uuid4

from .telemetry import ROOT

PROFILE = ROOT / 'deployment/pi/rmd_x6_48v.local.json'
DEFAULT_PROFILE = ROOT / 'deployment/pi/rmd_x6_48v.json'
SCRIPT = ROOT / 'tools/gui_pi_sensors.py'
POSE_GUIDE = {
    'zero': '암을 홈 위치에 두고 진자를 직립에 맞추세요.',
    'arm': '암을 홈에서 위에서 봤을 때 반시계 방향으로 약 10° 돌리고 멈추세요.',
    'pendulum': '진자를 직립에서 모터 중심 쪽에서 관절을 봤을 때 반시계 방향으로 약 10° 기울여 멈추세요.',
}


class SensorControls:
    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.job = None
        self.buttons = []
        for mode, title in (('check', '연결·센서 확인'), ('zero', '홈·직립 영점'),
                            ('arm', '암 방향'), ('pendulum', '진자 방향'),
                            ('live', '실시간 측정')):
            button = ttk.Button(parent, text=title, style='Control.TButton',
                                command=lambda key=mode: self.start(key))
            button.pack(side='left', padx=(0, 4))
            self.buttons.append(button)

    def start(self, mode):
        if self.job is not None:
            return
        root = self.dashboard.root
        if mode in POSE_GUIDE and not messagebox.askokcancel(
                '센서 보정', POSE_GUIDE[mode] +
                '\n\nPi 인증 후 터미널에 안내가 뜨면 5초 뒤 읽습니다. 측정이 끝날 때까지 자세를 유지하세요.',
                parent=root):
            return
        output = ROOT / 'runs' / f'pi_gui_{uuid4().hex[:12]}.jsonl'
        try:
            output.parent.mkdir(exist_ok=True)
            process = subprocess.Popen(
                [str(Path(sys.executable).with_name('python.exe')), str(SCRIPT),
                 '--mode', 'live' if mode == 'live' else 'pose', '--log', str(output)],
                cwd=ROOT, creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except (AttributeError, OSError) as exc:
            messagebox.showerror('Pi 실행 오류', str(exc), parent=root)
            return
        self.job = (mode, output, process)
        for button in self.buttons:
            button.state(['disabled'])
        if mode == 'live':
            self.dashboard.follow(output)
        self.dashboard.real.status.set('Pi 접속 중 · 터미널에 SSH 암호 입력')

    def poll(self):
        if self.job is None:
            return
        mode, output, process = self.job
        code = process.poll()
        if code is None:
            return
        self.job = None
        for button in self.buttons:
            button.state(['!disabled'])
        if code:
            try:
                detail = output.read_text(encoding='utf-8').splitlines()[-1]
            except (OSError, IndexError):
                detail = f'Pi 작업 실패 · 종료 코드 {code}'
            self.dashboard.real.status.set(detail)
            return
        if mode == 'live':
            self.dashboard.real.status.set(f'실시간 측정 완료 · {output.name}')
            return
        try:
            lines = output.read_text(encoding='utf-8-sig').splitlines()
            sample = json.loads(lines[-1])
            self.handle_pose(mode, sample)
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            self.dashboard.real.status.set(f'센서 결과 처리 실패 · {exc}')

    def handle_pose(self, mode, sample):
        root = self.dashboard.root
        arm = sample['arm_deg_median']
        counts = sample['pendulum_count_median']
        arm_span = sample['arm_span_deg']
        pend_span = sample['pendulum_span_counts']
        values = (arm, counts, arm_span, pend_span)
        if not all(math.isfinite(value) for value in values):
            raise ValueError('센서값이 유한하지 않습니다.')
        summary = (f"CAN 암 {arm:.2f}° (범위 {arm_span:.2f}°)\n"
                   f"AS5600 {counts:.1f}카운트 (범위 {pend_span:g}카운트)\n"
                   f"유효 샘플 {sample['samples']}개")
        self.dashboard.real.status.set(f'센서 응답 확인 · 암 {arm:.2f}° / 진자 {counts:.1f}카운트')
        if mode == 'check':
            messagebox.showinfo('CAN · I²C 응답', summary, parent=root)
            return

        if arm_span > 1 or pend_span > 12:
            messagebox.showwarning('자세가 변했습니다', summary + '\n\n자세를 고정하고 다시 측정하세요.', parent=root)
            return
        source = PROFILE if PROFILE.is_file() else DEFAULT_PROFILE
        profile = json.loads(source.read_text(encoding='utf-8-sig'))
        pendulum = profile['pendulum_sensor']
        if mode == 'zero':
            profile['arm_home_deg'] = arm
            pendulum['upright_count'] = counts
            profile['zero_calibration'] = sample
            prompt = '이 자세를 암 홈과 진자 직립 영점으로 저장할까요?'
        else:
            arm_test = mode == 'arm'
            reference = profile['arm_home_deg'] if arm_test else pendulum['upright_count']
            if reference is None:
                raise ValueError('홈·직립 영점을 먼저 저장하세요.')
            delta = arm - reference if arm_test else (counts - reference + 2048) % 4096 - 2048
            degrees = delta if arm_test else delta * 360 / 4096
            if not 2 <= abs(degrees) <= 30:
                messagebox.showwarning('방향을 확인할 수 없습니다',
                                       f'{degrees:+.2f}° 변화가 감지됐습니다. 기준점에서 약 10°로 다시 측정하세요.',
                                       parent=root)
                return
            sign = 1 if delta > 0 else -1
            target = profile if arm_test else pendulum
            target['arm_sign' if arm_test else 'sign'] = sign
            target['arm_sign_calibration' if arm_test else 'sign_calibration'] = {
                'reference': reference, 'raw_delta': delta, 'sample': sample,
            }
            prompt = f'원시 각도 변화 {degrees:+.2f}° · 보정 부호 {sign:+d}\n이 방향을 저장할까요?'
        if messagebox.askyesno('보정값 저장', summary + '\n\n' + prompt, parent=root):
            pending = PROFILE.with_suffix('.json.tmp')
            pending.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            pending.replace(PROFILE)
            self.dashboard.real.status.set('보정값 저장 완료 · 다음 GUI 측정에 적용')
