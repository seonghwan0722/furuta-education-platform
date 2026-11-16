"""Desktop dashboard for simulated and measured Furuta state."""
import json
import math
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk

from .pi_sensor_gui import SensorControls
from .pose_view import HEIGHT, WIDTH, PoseRenderer
from .telemetry import ROOT, decode_sample, samples

BG, PANEL, INK, SUB = '#edf2f8', '#ffffff', '#182942', '#52647b'
GRID, BORDER, TINT = '#e0e8f1', '#d5e0ed', '#f5f8fc'
PRIMARY = '#2057a5'
COLORS = ('#00796d', '#b14a24')
GRAPH_HEIGHT = 150
GRAPHS = (
    ('각도  °', (('pendulum_deg', '진자'), ('arm_deg', '암'))),
    ('각속도  rad/s', (('pendulum_rad_s', '진자'), ('arm_rad_s', '암'))),
    ('토크  Nm', (('requested_nm', '정책 요청'), ('applied_nm', '실제 적용 / 모델 적용'))),
    ('정규화 정책 행동', (('action', '행동 [-1, 1]'),)),
)
DETAILS = (
    ('t_s', '경과 (s)'), ('seq', '샘플 번호'), ('arm_deg', '암 (°)'),
    ('pendulum_deg', '진자 직립 오차 (°)'), ('arm_rad_s', '암 속도 (rad/s)'),
    ('pendulum_rad_s', '진자 속도 (rad/s)'), ('action', '정책 행동'),
    ('requested_nm', '정책 요청 (Nm)'), ('applied_nm', '적용 (Nm)'),
    ('actuator_force_nm', '모델 관절 토크 (Nm)'), ('motor_current_a', '모터 전류 (A)'),
    ('command_sent', '모터 구동 명령 송신'), ('enable', '구동 활성'),
    ('observation', '정책 입력 [sin 암, cos 암, sin 진자, cos 진자, 속도 2축]'),
    ('qpos', '모델 관절 위치 (rad)'), ('qvel', '모델 관절 속도 (rad/s)'),
    ('qacc', '모델 관절 가속도 (rad/s²)'), ('reward', '보상'),
    ('reward_terms', '보상 항목'), ('arm_raw_deg', 'RMD 원시 각도 (°)'),
    ('pendulum_counts', 'AS5600 카운트'), ('sensor_status', 'AS5600 상태 바이트'),
    ('cycle_ms', '샘플 주기 (ms)'), ('can_ms', 'CAN 응답 (ms)'),
    ('sample_ms', '센서 읽기 (ms)'), ('axis_skew_ms', '센서 수신 시각 차 (ms)'),
    ('inference_ms', '정책 계산 (ms)'), ('simulation_step_ms', '시뮬레이션 스텝 (ms)'),
    ('fault', '오류'), ('policy_sha256', '정책 SHA-256'),
)
LIVE_FILE = ROOT / 'runs/pi_balance_live.jsonl'


def fmt(value, key=''):
    if value is None:
        return '—'
    if isinstance(value, bool):
        return '예' if value else '아니오'
    if key == 'sensor_status':
        return hex(value)
    if isinstance(value, float):
        return f'{value:.4g}'
    if isinstance(value, list):
        return ', '.join(fmt(item) for item in value)
    if isinstance(value, dict):
        return ', '.join(f'{k}={fmt(v)}' for k, v in value.items())
    return str(value)


class Screen:
    def __init__(self, parent, title, subtitle, pose_title):
        self.rows = []
        self.frame = tk.Frame(parent, bg=PANEL, padx=14, pady=9,
                              highlightthickness=1, highlightbackground=BORDER)
        tk.Label(self.frame, text=title, bg=PANEL, fg=INK, font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        tk.Label(self.frame, text=subtitle, bg=PANEL, fg=SUB).pack(anchor='w')
        self.status = tk.StringVar(value='대기')
        tk.Label(self.frame, textvariable=self.status, bg=PANEL, fg=PRIMARY,
                 anchor='w', font=('Segoe UI', 9, 'bold')).pack(fill='x', pady=4)
        metrics = tk.Frame(self.frame, bg=PANEL)
        metrics.pack(fill='x', pady=(1, 7))
        self.metric_values = {}
        for col, (key, label, color) in enumerate((
                ('pendulum_deg', '진자 · °', COLORS[0]), ('arm_deg', '암 · °', COLORS[1]),
                ('action', '정책 행동', INK), ('requested_nm', '요청 토크 · Nm', INK))):
            metrics.columnconfigure(col, weight=1, uniform='metric')
            tile = tk.Frame(metrics, bg=TINT, padx=8, pady=4)
            tile.grid(row=0, column=col, sticky='nsew', padx=(0, 4) if col < 3 else 0)
            tk.Label(tile, text=label, bg=TINT, fg=SUB, font=('Segoe UI', 9)).pack(anchor='w')
            self.metric_values[key] = tk.StringVar(value='—')
            tk.Label(tile, textvariable=self.metric_values[key], bg=TINT, fg=color,
                     font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        charts = tk.Frame(self.frame, bg=PANEL)
        charts.pack(fill='both', expand=True)
        preview = tk.Frame(charts, bg=TINT, padx=8, pady=8)
        preview.pack(side='right', anchor='n', padx=(10, 0))
        tk.Label(preview, text=pose_title, bg=TINT, fg=INK,
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 6))
        self.pose = tk.Canvas(preview, bg=GRID, width=WIDTH, height=HEIGHT, highlightthickness=0)
        self.pose.pack()
        self.pose_image = None
        self.pose_item = self.pose.create_image(0, 0, anchor='nw')
        self.pose_message = self.pose.create_text(WIDTH / 2, HEIGHT / 2, fill=SUB,
                                                  text='자세 데이터 대기', width=WIDTH - 28)
        self.canvas = tk.Canvas(charts, bg=PANEL, height=GRAPH_HEIGHT * len(GRAPHS),
                                highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda _: self.draw())
        detail_panel = tk.Frame(self.frame, bg=TINT)
        detail_panel.pack(fill='x', pady=(5, 0))
        tk.Label(detail_panel, text='샘플 상세', bg=TINT, fg=INK, padx=8,
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(3, 0))
        scroll = ttk.Scrollbar(detail_panel)
        scroll.pack(side='right', fill='y')
        self.details = tk.Text(detail_panel, height=5, bg=TINT, fg=SUB, font=('Segoe UI', 9),
                               padx=8, wrap='word', relief='flat', state='disabled',
                               yscrollcommand=scroll.set)
        self.details.pack(fill='x')
        scroll.configure(command=self.details.yview)

    def draw(self):
        cv = self.canvas
        cv.delete('all')
        width, height = cv.winfo_width(), cv.winfo_height()
        row = self.rows[-1] if self.rows else {}
        for key, metric in self.metric_values.items():
            metric.set(fmt(row.get(key)))
        # Keep the details scroll position during acquisition.
        scroll = self.details.yview()[0]
        self.details.configure(state='normal')
        self.details.delete('1.0', 'end')
        self.details.insert('1.0', '\n'.join(f'{label}  {fmt(row.get(key), key)}' for key, label in DETAILS))
        self.details.yview_moveto(scroll)
        self.details.configure(state='disabled')
        end = row.get('t_s', 0)
        left = max(0, end - 10)
        right = max(left + 10, end)
        visible = [sample for sample in self.rows if sample['t_s'] >= left]
        for index, (label, series) in enumerate(GRAPHS):
            y = index * height / len(GRAPHS)
            top, bottom = y + 28, (index + 1) * height / len(GRAPHS) - 16
            x0, x1 = 66, max(67, width - 12)
            if index:
                cv.create_line(0, y, width, y, fill=GRID)
            cv.create_text(8, y+12, text=label, anchor='w', fill=INK, font=('Segoe UI', 9, 'bold'))
            values = [sample.get(key) for sample in visible for key, _ in series]
            lim = max([abs(v) for v in values if isinstance(v, (int,float)) and math.isfinite(v)] + [0.01])
            mid = (top + bottom) / 2
            for yy, text in [(top, f'{lim:.3g}'), (mid, '0'), (bottom, f'{-lim:.3g}')]:
                cv.create_line(x0, yy, x1, yy, fill=GRID)
                cv.create_text(x0-5, yy, text=text, anchor='e', fill=SUB)
            for color, (key, name) in zip(COLORS, series):
                points = []
                for sample in visible:
                    value = sample.get(key)
                    if isinstance(value, (int,float)) and math.isfinite(value):
                        points.extend((x0 + (sample['t_s']-left)/(right-left)*(x1-x0),
                                       mid - value/lim*(bottom-top)/2))
                if len(points) >= 4:
                    cv.create_line(*points, fill=color, width=2)
                elif points:
                    x, yy = points
                    cv.create_oval(x-2, yy-2, x+2, yy+2, fill=color, outline=color)
            legend_x = x1
            for color, (_, name) in reversed(list(zip(COLORS, series))):
                item = cv.create_text(legend_x, y+12, text=name, anchor='e', fill=color)
                legend_x = cv.bbox(item)[0] - 10
            cv.create_text(x1, bottom+9, text=f'{left:.1f}–{right:.1f} s', anchor='e', fill=SUB)

    def show_pose(self, data=None, message='자세 데이터 대기'):
        self.pose_image = tk.PhotoImage(master=self.pose, data=data, format='ppm') if data else None
        self.pose.itemconfigure(self.pose_item, image=self.pose_image or '')
        self.pose.itemconfigure(self.pose_message, text='' if data else message)


class Dashboard:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.simulating = False
        self.stop = threading.Event()
        self.log_path = None
        self.offset = 0
        self.log_updated = None
        self.log_signature = None
        self.pose_renderer = None
        self.pose_error = None
        self.preview_sample = None
        self.root.title('Furuta | 직립 균형 모니터')
        width = min(1340, self.root.winfo_screenwidth() - 24)
        height = min(890, self.root.winfo_screenheight() - 100)
        self.root.geometry(f'{width}x{height}')
        self.root.minsize(min(970, width), min(680, height))
        self.root.configure(bg=BG)
        style = ttk.Style(root)
        style.theme_use('clam')
        for name, bg, fg, hover in (
                ('Control.TButton', PANEL, INK, '#e8eff9'),
                ('Start.TButton', PRIMARY, PANEL, '#174885')):
            style.configure(name, background=bg, foreground=fg, bordercolor=BORDER,
                            lightcolor=bg, darkcolor=bg, padding=(11, 5),
                            font=('Segoe UI', 9))
            style.map(name, background=[('active', hover)])
        self.viewport = tk.Canvas(root, bg=BG, highlightthickness=0, yscrollincrement=24)
        page_scroll = ttk.Scrollbar(root, orient='vertical', command=self.viewport.yview)
        page_scroll.pack(side='right', fill='y')
        self.viewport.configure(yscrollcommand=page_scroll.set)
        self.viewport.pack(side='left', fill='both', expand=True)
        page = tk.Frame(self.viewport, bg=BG)
        page_window = self.viewport.create_window(0, 0, anchor='nw', window=page)
        self.viewport.bind('<Configure>', lambda event: self.viewport.itemconfigure(page_window, width=event.width))
        page.bind('<Configure>', lambda _: self.viewport.configure(scrollregion=self.viewport.bbox(page_window)))

        tk.Label(page, text='Furuta 직립 균형 모니터', fg=INK, bg=BG,
                 font=('Segoe UI', 22, 'bold')).pack(anchor='w', padx=18, pady=(10, 5))
        tabs = tk.Frame(page, bg=BG)
        tabs.pack(fill='x', padx=18, pady=(3, 8))
        self.selection = tk.StringVar(value='simulation')
        self.tabs = {}
        for key, label in (('simulation', '시뮬레이션'), ('hardware', '실물 센서')):
            tab = ttk.Radiobutton(tabs, text=label, value=key, variable=self.selection,
                                  command=self.show_selected)
            tab.pack(side='left', padx=(0, 16), pady=3)
            self.tabs[key] = tab
        bar = tk.Frame(page, bg=BG)
        bar.pack(fill='x', padx=18, pady=(0, 8))
        self.sim_controls = tk.Frame(bar, bg=BG)
        self.real_controls = tk.Frame(bar, bg=BG)
        ttk.Button(self.sim_controls, text='시뮬레이션 시작', style='Start.TButton',
                   command=self.start_simulation).pack(side='left')
        ttk.Button(self.sim_controls, text='정지', style='Control.TButton',
                   command=self.stop.set).pack(side='left', padx=5)
        sensors = tk.Frame(self.real_controls, bg=BG)
        sensors.pack(anchor='w')
        log_controls = tk.Frame(self.real_controls, bg=BG)
        log_controls.pack(anchor='w', pady=(4, 0))
        self.sensor_controls = SensorControls(sensors, self)
        ttk.Button(log_controls, text='Pi 실시간 로그', style='Control.TButton',
                   command=lambda: self.follow(LIVE_FILE)).pack(side='left', padx=5)
        ttk.Button(log_controls, text='실물 로그 열기', style='Control.TButton',
                   command=self.open_log).pack(side='left', padx=5)
        ttk.Button(bar, text='데이터 저장', style='Control.TButton', command=self.save).pack(side='right')
        panels = tk.Frame(page, bg=BG)
        panels.pack(fill='both', expand=True, padx=18, pady=(0, 12))
        self.sim = Screen(panels, '시뮬레이션', 'MuJoCo   •   직립 시작   •   동일한 균형 정책',
                          'MuJoCo 자세')
        self.real = Screen(panels, '실물 센서 / 정책', 'Pi   •   센서 조회 모드   •   모터 출력 비활성',
                           'Pi 측정 각도로 재현한 자세')
        self.show_selected()
        self.bind_page_scroll(root)
        self.follow(LIVE_FILE)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(100, self.refresh)

    def close(self):
        self.stop.set()
        if self.pose_renderer is not None:
            self.pose_renderer.close()
        self.root.destroy()

    def update_pose(self):
        screen = self.sim if self.selection.get() == 'simulation' else self.real
        row = screen.rows[-1] if screen.rows else None
        if self.preview_sample is not None:
            previous_screen, previous_row = self.preview_sample
            if screen is previous_screen and row is previous_row:
                return
        self.preview_sample = (screen, row)
        if row is None:
            screen.show_pose()
            return
        if self.pose_error is None:
            try:
                if self.pose_renderer is None:
                    self.pose_renderer = PoseRenderer()
                screen.show_pose(self.pose_renderer.image_data(row))
                return
            except Exception as exc:
                self.pose_error = f'3D 렌더링 오류\n{exc}'
        screen.show_pose(message=self.pose_error)

    def show_selected(self):
        for widget in (self.sim.frame, self.real.frame, self.sim_controls, self.real_controls):
            widget.pack_forget()
        simulation = self.selection.get() == 'simulation'
        screen = self.sim if simulation else self.real
        controls = self.sim_controls if simulation else self.real_controls
        screen.frame.pack(fill='both', expand=True)
        controls.pack(side='left')
        self.viewport.yview_moveto(0)

    def bind_page_scroll(self, widget):
        # Bind before Tk's Text class handler so one wheel event scrolls only once.
        widget.bind('<MouseWheel>', self.scroll_page)
        for child in widget.winfo_children():
            self.bind_page_scroll(child)

    def scroll_page(self, event):
        if event.delta:
            units = max(1, abs(event.delta) // 120) * 3
            self.viewport.yview_scroll(-units if event.delta > 0 else units, 'units')
        return 'break'

    def start_simulation(self):
        if self.simulating:
            return
        self.simulating = True
        self.stop.clear()
        self.sim.rows.clear()
        self.sim.status.set('실행 중')

        def worker():
            try:
                for row in samples():
                    if self.stop.is_set():
                        break
                    self.events.put(('sample', row))
                self.events.put(('status', '중지' if self.stop.is_set() else '완료'))
            except Exception as exc:
                self.events.put(('status', f'오류 · {exc}'))
        threading.Thread(target=worker, daemon=True).start()

    def follow(self, path):
        self.log_path = path
        self.offset = 0
        self.real.rows.clear()
        self.log_updated = None
        self.log_signature = None
        self.real.status.set(f'로그 대기 · {path.name}')
        self.real.draw()

    def open_log(self):
        filename = filedialog.askopenfilename(filetypes=[('Telemetry JSONL', '*.jsonl *.log'), ('All files', '*.*')])
        if filename:
            self.follow(Path(filename))

    def save(self):
        filename = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON', '*.json')])
        if filename:
            try:
                Path(filename).write_text(json.dumps({'simulation':self.sim.rows, 'hardware':self.real.rows},
                                                     indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            except (OSError, ValueError) as exc:
                self.real.status.set(f'저장 실패 · {exc}')

    def read_log(self):
        if not self.log_path or not self.log_path.exists():
            return False
        changed = False
        try:
            with self.log_path.open('rb') as stream:
                first = stream.readline()
                if first.endswith(b'\n') and self.log_signature not in (None, first):
                    self.offset = 0
                    self.real.rows.clear()
                    changed = True
                if first.endswith(b'\n'):
                    self.log_signature = first
                stream.seek(0, 2)
                if stream.tell() < self.offset:
                    self.offset = 0
                    self.real.rows.clear()
                    changed = True
                stream.seek(self.offset)
                for raw in stream:
                    if not raw.endswith(b'\n'):
                        break
                    self.offset += len(raw)
                    text = raw.decode('utf-8-sig', errors='replace').strip()
                    row = decode_sample(text)
                    if row:
                        if self.real.rows and row['t_s'] < self.real.rows[-1]['t_s']:
                            self.real.rows.clear()
                        self.real.rows.append(row)
                        self.log_updated = time.monotonic()
                        self.real.status.set(f'수신 중 · {self.log_path.name}')
                        changed = True
                    elif text:
                        self.real.status.set(text[-140:])
        except OSError as exc:
            self.real.status.set(f'로그 읽기 오류 · {exc}')
        if self.log_updated and time.monotonic() - self.log_updated > 1 and self.real.status.get().startswith('수신 중'):
            self.real.status.set(f'최근 수신 종료 · {self.log_path.name}')
        return changed

    def refresh(self):
        changed = False
        while not self.events.empty():
            kind, item = self.events.get_nowait()
            if kind == 'sample':
                self.sim.rows.append(item)
                changed = True
            else:
                self.simulating = False
                self.sim.status.set(item)
        if changed and self.sim.rows[-1].get('fault'):
            self.sim.status.set('시뮬레이션 제한 도달 · ' + fmt(self.sim.rows[-1]['fault']))
        if changed:
            self.sim.draw()
        if self.read_log():
            self.real.draw()
        self.sensor_controls.poll()
        self.update_pose()
        self.root.after(100, self.refresh)


def main():
    root = tk.Tk()
    Dashboard(root)
    root.mainloop()


if __name__ == '__main__':
    main()
