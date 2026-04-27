"""
結構化日誌設定 + 自動輪換

目錄結構：
  platform/logs/
    ├── tenant/
    │   ├── tenant.log               ← 目前寫入中
    │   ├── tenant-2026-04-24-09.log ← 輪換後的舊檔
    │   └── tenant-2026-04-24-10.log
    ├── sandbox/
    │   └── sandbox-2026-04-24-10.log
    └── inference-gw/
        └── inference-gw-2026-04-24-10.log

輪換策略：
  - 預設：每小時輪換（可改為 "midnight" 每天輪換）
  - 保留最近 168 個檔案（= 7 天 × 24 小時）
  - 壓縮舊檔：可選

使用方式（在各 service 的 main.py 最頂端）：
  from shared.logging_config import setup_logging
  setup_logging("tenant", logs_root=Path(__file__).parents[4] / "logs")
"""
import logging
import logging.handlers
import sys
from pathlib import Path

import structlog


class _ServiceFileHandler(logging.handlers.TimedRotatingFileHandler):
    """
    繼承 TimedRotatingFileHandler，覆寫 namer 讓輪換後的檔名包含日期。

    例：
      當前寫入：tenant.log
      輪換後：  tenant-2026-04-24-10.log（舊的）
      新建立：  tenant.log（新的）
    """

    def __init__(
        self,
        log_dir:      Path,
        service_name: str,
        when:         str = "h",
        backup_count: int = 168,
    ) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        base_file = log_dir / f"{service_name}.log"

        super().__init__(
            filename=str(base_file),
            when=when,
            interval=1,
            backupCount=backup_count,
            encoding="utf-8",
            delay=False,
        )

        # 輪換後的舊檔後綴（依輪換類型決定格式）
        if when.lower() in ("h",):
            self.suffix = "-%Y-%m-%d-%H"
        else:
            self.suffix = "-%Y-%m-%d"

        # 自訂 namer：把 tenant.log-2026-04-24-10 → tenant-2026-04-24-10.log
        def _namer(default_name: str) -> str:
            p = Path(default_name)
            stem = p.name  # "tenant.log-2026-04-24-10"
            if ".log-" in stem:
                service, timestamp = stem.split(".log-", 1)
                return str(p.parent / f"{service}-{timestamp}.log")
            return default_name

        self.namer = _namer


def setup_logging(
    service_name: str,
    *,
    logs_root:    Path,
    level:        str = "INFO",
    rotation:     str = "h",        # "h" = 每小時, "midnight" = 每天
    backup_count: int = 168,        # 保留筆數（168 = 7天×24小時）
    console:      bool = True,      # 是否同時輸出至 console
    json_console: bool = False,     # console 是否用 JSON 格式（預設 dev-friendly）
) -> None:
    """
    設定 structlog + 檔案輪換日誌。

    參數：
        service_name: 服務名稱（決定子目錄和檔名）
        logs_root:    platform/logs/ 的路徑
        level:        日誌等級（INFO / DEBUG / WARNING）
        rotation:     "h"=每小時, "midnight"=每天
        backup_count: 保留的輪換檔案數量
        console:      是否同時輸出至 stdout
        json_console: console 是否輸出 JSON（預設是 dev-friendly 彩色格式）
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    log_dir   = logs_root / service_name

    handlers: list[logging.Handler] = []

    # ─── 檔案 Handler（JSON 格式，易於解析）────────────────────
    file_handler = _ServiceFileHandler(
        log_dir=log_dir,
        service_name=service_name,
        when=rotation,
        backup_count=backup_count,
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    handlers.append(file_handler)

    # ─── Console Handler ────────────────────────────────────────
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        handlers.append(console_handler)

    # ─── 設定 root logger ───────────────────────────────────────
    root = logging.getLogger()
    root.handlers.clear()   # 清除 uvicorn 預設的 handler
    root.setLevel(log_level)
    for h in handlers:
        root.addHandler(h)

    # ─── 抑制過於詳細的第三方 logger ─────────────────────────────
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # ─── Structlog 設定 ─────────────────────────────────────────
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]

    # 檔案：JSON 格式
    file_processors = shared_processors + [structlog.processors.JSONRenderer()]

    # Console：dev-friendly（彩色）或 JSON（依 json_console 參數）
    if json_console or not sys.stdout.isatty():
        console_processors = file_processors
    else:
        console_processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 為所有 handler 設定 ProcessorFormatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )
    for h in handlers:
        h.setFormatter(formatter)

    log = structlog.get_logger()
    log.info(
        "logging.initialized",
        service=service_name,
        log_dir=str(log_dir),
        level=level,
        rotation=rotation,
        backup_count=backup_count,
    )
