# 하드웨어 상태

현재 직립 시험 구성은 Raspberry Pi, RMD-X6-P20-60-E, 진자 AS5600이다. 모터 전원 설계 기준은 제조사 정격인 **48 V DC**다. Pi에서 CAN 출력축 각도 응답과 I²C 센서 읽기를 확인했다. 현장 공급 전압 실측, 영점·부호, 펌웨어, 구동 명령 변환과 시험 제한은 확인이 필요하다. [제조사 제품 자료](https://www.myactuator.com/x6-60details) · [48 V 정격 자료](https://myactuator.cn/uploadpic/20250516142200rpyh.pdf)

기구 D안, Teensy 4.1, CubeMars GL35 KV100, 24 V 및 rev11 산정은 이전 구성 계획으로 기록한다. 현재 RMD 시험 구성의 명세는 [Pi 직립 준비 문서](../../deployment/pi/BALANCE_BRINGUP.md)와 [하드웨어 프로필](../../deployment/pi/rmd_x6_48v.json)에 있다.
