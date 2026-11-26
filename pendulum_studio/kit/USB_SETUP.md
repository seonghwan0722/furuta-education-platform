# Pi 5 USB-C 직결 — Pendulum Studio

2026-11-26. PC 앱 ↔ USB 데이터 케이블 ↔ Pi 5 USB-C ↔ 기존 SocketCAN 모터 구동부.

이 문서는 **USB 직렬 장치(COM)** 방식이다. Pi에서 `g_serial`로 `/dev/ttyGS0`를 만들고, PC 앱이 인식된 COM 포트를 연다. 정책과 상태를 전송하는 규약은 기존 v2이며 정책 추론·제어는 Pi 내부에서 50 Hz로 실행한다.

## 현재 완료 범위

- 앱: 포트 목록 → 선택 → H/Q 응답 확인 → L 보정값 조회. 연결만으로 G(보정 구동)·R(정책 구동)을 보내지 않는다.
- 실행: 사용자가 시뮬레이션 확인 후 실제 키트에서 시작하면 정책 전체를 올리고 CRC 응답을 확인한 뒤 실행한다.
- 수신기: 직렬 부분 쓰기, 끊김·재연결, 이전 연결 메시지, 정책 헤더 오류 처리를 보강했다.
- 설치 도구: 기본은 조회만 한다. 명시적인 적용 옵션으로 부팅 설정과 대기 서비스만 준비한다. 자동 재부팅·자동 정책 실행은 없다.
- **아직 이 변경을 Pi에 설치하거나 실제 USB로 시험하지 않았다.** PC에서 확인한 COM4·COM5는 Bluetooth 직렬 포트였다. 기존 Pi 주소에 대한 SSH 연결은 인증 거절로 끝났다.

## 1. 먼저 확정할 것

1. **현재 선택은 PC USB 케이블 하나로 Pi 전원도 공급하는 방식**이다. PC 포트의 출력 사양은 아직 미확인이다. Pi 5의 공식 부팅 전원 기준인 5V·3A급 공급과 주변장치 부하를 확인한 다음 설정한다. USB-C 모양만으로 공급 전류를 판단하지 않는다. 기존 CAN HAT에 GPIO 전원 배선을 추가하지 않는다.
2. 충전 전용이 아닌 USB 데이터 케이블. Pi 쪽은 **USB-C**다. 일반 USB-A↔USB-A 직결은 이 방식에 해당하지 않는다.
3. Pi의 최신 실기 코드 위치. 아래 예시는 `/home/pi/rev11_s2r/pi_host`이며 실제 폴더를 확인한다. PC에 있는 오래된 `pi_host` 사본으로 덮어쓰지 않는다.
4. Pi의 Python에 `numpy`, `python-can`, `smbus2`가 있고, 실행 계정에 `dialout`, `i2c` 권한이 있어야 한다. 해당 환경에 설치된 Python을 `--python`으로 지정할 수 있다.

`rpi-usb-gadget on`은 공식 USB **네트워크** 방식이다. 이 앱의 COM 경로와 다르므로 `g_serial`과 동시에 켜지 않는다. 기존 네트워크/복합 gadget 설정이 있으면 설치 도구가 적용을 거절한다.

**같은 케이블로 전원까지 공급하면 케이블 분리 시 Pi도 꺼진다.** 이때 Pi의 heartbeat 감시와 정지 명령은 동작하지 않는다. 별도 전원을 쓰는 모터의 CAN 통신 두절 차단 동작은 별도로 확인해야 한다. USB 분리를 정지 방법으로 쓰지 않는다. 이번 작업에서 이 차단 동작을 실물 검증하지 않았다.

## 2. Pi에 수신기 파일 복사

Pi의 `/home/pi/pendulum-studio-kit/`에 다음 파일을 함께 둔다.

- `kit_server.py`
- `kit_cal.py`
- `classical_control.py` (PID·LQR·LMPC 및 스윙업 계산)
- `setup_usb_serial.py`

기존 `pi_host`에는 `run_policy.py`, `session.py`, `canguard.py`, `policy_np.py`, `kitparams.py`가 있어야 한다. 이 파일들은 이 작업에서 교체하지 않는다.

SSH 인증이 가능한 PC PowerShell에서는 다음처럼 복사할 수 있다. `pi@raspberrypi.local`은 실제 접근 가능한 Pi 주소로 바꾼다.

```powershell
cd C:\Capstone1\furuta-pendulum-rl\app
ssh pi@raspberrypi.local "mkdir -p /home/pi/pendulum-studio-kit"
scp .\kit\kit_server.py .\kit\kit_cal.py .\kit\classical_control.py .\kit\setup_usb_serial.py pi@raspberrypi.local:/home/pi/pendulum-studio-kit/
```

## 3. Pi에서 조회만 하기

```bash
python3 /home/pi/pendulum-studio-kit/setup_usb_serial.py --host-dir /home/pi/rev11_s2r/pi_host
```

보드/OS, Python 의존성, 필요한 파일, 사용자 그룹, 기존 USB 설정, 실행 중인 제어 프로세스를 출력한다. CAN·I²C·직렬 장치를 열지 않는다. `setup_errors`가 있으면 먼저 원인을 정리한다. 이 결과는 모터 watchdog 실측이나 동작 검증을 대신하지 않는다.

가상환경을 쓰는 경우에는 조회와 적용에 같은 Python 경로를 지정한다.

```bash
python3 /home/pi/pendulum-studio-kit/setup_usb_serial.py --host-dir /home/pi/rev11_s2r/pi_host --python /home/pi/rev11_s2r/.venv/bin/python
```

## 4. 전원과 경로 확인 후 설정 적용

모터 시험을 끝내고 기존 제어 프로그램과 수신기를 사용자가 직접 종료한 상태에서 진행한다. `--power-confirmed`는 사용자가 전원 구성을 확인했다는 표시이며 전원을 측정하거나 보호 설정을 변경하는 옵션이 아니다.

```bash
sudo python3 /home/pi/pendulum-studio-kit/setup_usb_serial.py --host-dir /home/pi/rev11_s2r/pi_host --user pi --apply --power-confirmed
```

도구는 다음만 수행한다.

- `/boot/firmware/config.txt`를 백업하고 `dtoverlay=dwc2,dr_mode=peripheral` 설정을 추가한다. CAN·I²C 설정은 보존한다.
- `/etc/modules-load.d/pendulum-usb-serial.conf`에 `dwc2`, `g_serial`을 넣는다.
- `/etc/systemd/system/pendulum-kit-usb.service`를 만들고 **다음 부팅의 대기 서비스**로 등록한다. 즉시 시작하지 않는다.
- 기존 파일의 백업 위치를 출력한다. 모터 전류·속도·방향·제어 게인·watchdog 설정을 바꾸지 않는다.

사용자가 준비됐을 때만 재부팅한다.

```bash
sudo reboot
```

재부팅 후 Pi에서:

```bash
ls -l /dev/ttyGS0
systemctl status pendulum-kit-usb.service --no-pager
journalctl -u pendulum-kit-usb.service -n 50 --no-pager
```

수신기는 모터 실행 명령이 올 때까지 대기한다. 서비스가 `active`여도 USB 포트가 없어 재시도 중일 수 있으므로 `/dev/ttyGS0` 존재와 로그를 함께 확인한다.

## 5. 앱에서 연결하고 사용자가 실행

```powershell
cd C:\Capstone1\furuta-pendulum-rl\app
npm.cmd start
```

1. USB 데이터 케이블을 연결하고 **키트 연결하기 → 다시 찾기**.
2. 새로 나타난 Pi COM 포트를 선택하고 **연결**. 이름·프로그램 버전·제어 주기가 확인되면 통신 연결 완료다. 잘못 고른 포트는 실패로 안내한다.
3. 연결 창을 닫고 **키트 점검**. 모터·센서 응답을 조회한다.
4. 정책을 **시뮬레이션**에서 학습·확인한다. 앱의 기존 실물 실행 조건을 통과해야 한다.
5. 사용자가 **실제 키트 → 시작하기**를 누른다. 정책 전송 완료 후 Pi가 수평 측정과 정책 구동을 수행한다. 수평 측정부터 팔이 움직인다.
6. 앱의 **정지하기**로 정지를 요청한다. 재연결만으로 재시작하지 않는다.

`키트 맞추기`는 별도 동작이며 모터가 움직인다. 단순 USB 연결 확인용으로 실행하지 않는다.

PID·LQR·LMPC 실험은 메인 앱의 **제어 실험실 → 실제 키트**에서 같은 연결을 사용한다. 새 수신기는 인사 응답에 `control1`을 표시한다. 구버전이면 실물 시작을 허용하지 않는다. 아래 자세에서 자동 스윙업한 뒤 선택한 제어기로 전환하는 순서와 현재 미검증 범위는 [CLASSICAL_CONTROL.md](CLASSICAL_CONTROL.md)를 따른다.

기존 설치 파일 `dist-ux`는 이번 소스 변경을 포함해 다시 빌드하지 않았다. 이번 기능은 위 `npm.cmd start`로 소스를 실행해 확인한다. 수신기 파일만 복사한 경우에도 기존 실행 프로세스는 예전 코드를 계속 사용하므로, 모터 시험이 종료된 뒤 사용자가 수신기를 다시 시작해야 한다.

## 현재 실기 경로의 값과 기록

이 수신기의 기존 값은 최대 토크 2.52 N·m, 전류 1.2 A, 팔 1100 °/s, 진자 25 rad/s, 제어 주기 20 ms다. 이전 MATLAB 모델의 조건과 혼합하지 않는다. 이번 작업은 통신 연결을 위한 것으로 이 값을 재설정하지 않았다.

모터 응답 감시 0.1초, 앱 heartbeat 끊김 판정 2초를 유지한다. **프로세스 내 응답 감시와 강제 종료 시 모터 자체 차단 검증은 별개**다. USB 통신 구현만으로 강제 종료 watchdog 시험이 통과했다고 표시하지 않는다.

기본 로그는 `<host-dir>/logs/kit_server_<시각>.csv`, 종료 정보 `.txt`, 지원하는 정책 구조의 `_policy.npz`다. 서비스 로그는 위 `journalctl` 명령으로 확인한다.

## 되돌리기

실물 시험을 끝낸 후 대기 서비스를 사용자가 종료·해제한다.

```bash
sudo systemctl disable --now pendulum-kit-usb.service
```

적용 시 출력한 백업으로 변경 파일을 복원한다. 원래 없었던 서비스/모듈 파일만 제거하고, `config.txt` 전체를 삭제하지 않는다. 이후 사용자 판단으로 재부팅한다. 다른 USB gadget 방식으로 전환할 때도 먼저 이 설정을 정리한다.

## 근거

- [Raspberry Pi 공식 OTG 백서](https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-009276-WP-1-Using%20OTG%20mode%20on%20Raspberry%20Pi%20SBCs.pdf): Pi 5 USB-C peripheral 모드, `g_serial`, COM/ttyGS 경로.
- [공식 USB gadget 네트워크 안내](https://www.raspberrypi.com/news/usb-gadget-mode-in-raspberry-pi-os-ssh-over-usb/): Trixie `rpi-usb-gadget`는 USB Ethernet이며 CDC-ACM serial을 포함하지 않는다.
- [공식 Pi 5 전원 사양](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#raspberry-pi-5): 부팅 전원과 주변장치 전력 제한.

변경 코드와 설치 도구는 소스만 검토했으며, 이번 작업에서 앱·시뮬레이션·자동 테스트·실물 구동은 실행하지 않았다.
