# Changelog

## [2026-03-25]
- **지능형 멀티 모니터 좌표 관리 시스템 도입**:
    - 절대 좌표 대신 해상도 대비 **상대 비율(`ratio`)** 기반 위치 저장 방식을 적용하여 모니터 해상도 변경 및 스왑 시에도 위치 보존.
    - JSON 데이터에 `screen_index`, `is_primary_screen` 필드를 추가하여 모니터 식별성 강화.
- **`🎯 메모 위치 재조정` 기능 추가**:
    - 트레이 메뉴를 통해 보조 모니터 이탈이나 화면 밖으로 나간 메모를 주 모니터로 한꺼번에 소환하는 기능 구현.
    - 주 모니터의 기존 메모는 위치를 유지하며, 소환 시 원래의 배치 비율을 유지하여 사용자 경험 개선.
- **사용 가이드(`GUIDE.md`) 고도화**:
    - 멀티 모니터 및 화면 관리 섹션 추가.
    - 보조 모니터 재연결을 고려한 최적의 사용 팁 안내 문구 삽입.
- **시스템 품질 개선**:
    - 모니터 연결 해제 시 좌표가 마이너스나 화면 밖으로 고정되어 메모가 사라지던 버그 해결.
    - 데이터 로드 시 문자열/숫자 형 변환 안정성 코드 추가.

## [2026-02-26]
- Improved global hotkey observability and diagnosis flow.
- Added hotkey status tracking (registration attempts/success, last error, trigger counts).
- Switched Windows global hotkey backend priority to WinAPI `RegisterHotKey` (`WM_HOTKEY`) and kept `keyboard` as fallback.
- Added backend visibility (`winapi`/`keyboard`) in tray tooltip and hotkey status dialog.
- Added trigger source tracking (`winapi`/`keyboard`) to logs and status view for lock/resume diagnosis.
- Added tray menu group `⌨️ 단축키`:
  - `🔁 단축키 재등록`
  - `📊 상태 확인`
  - `📄 로그 파일 열기`
- Added tray notifications for hotkey registration success/failure.
- Added detailed hotkey log events for setup source (`startup`, `manual`, `resume`) and trigger actions (`show`, `hide`).
- Updated power-resume hotkey re-registration path to be explicitly logged as `resume`.
- Updated user guide (`README.md`) with hotkey troubleshooting steps and log file location.

## [2026-01-30]
- Renamed `GUIDE.md` to `README.md`.
- Migrated primary branch from `master` to `main`.
- Established `AGENT_PROTOCOLS.md` for automated change recording and workflow consistency.
- Refined macOS theme:
    - Left-aligned title.
    - Removed header bottom border.
    - Assigned traffic light buttons to Close (Red), Settings (Yellow), and Add (Green).
- Fixed Pin (Always on Top) functionality to prevent Z-order jumping.
- Implemented Scheduled Backup system with Cron expression helper.
