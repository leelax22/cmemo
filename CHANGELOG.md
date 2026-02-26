# Changelog

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
