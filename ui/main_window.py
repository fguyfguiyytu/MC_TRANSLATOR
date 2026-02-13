from __future__ import annotations

import json
import os
import queue
import threading
import time
import webbrowser
import urllib.parse
import ctypes
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

BUILD_TAG = "2026-02-10.01"

from PyQt6.QtCore import Qt, QTimer, QEasingCurve, QPropertyAnimation, QRect
from PyQt6.QtGui import QAction, QKeySequence, QShortcut, QCursor, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QGraphicsOpacityEffect,
    QProgressBar,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QInputDialog,
    QVBoxLayout,
    QWidget,
)

from core.cache import TranslationCache
from license.machine_id import get_machine_code
from license.online import (
    activate_with_server,
    register_with_server,
    revoke_with_server,
    verify_with_server,
)
from license.state import (
    can_consume,
    can_claim_weekly_welfare,
    claim_weekly_welfare,
    claim_welfare,
    consume,
    get_status,
    has_claimed_welfare,
    is_time_paused,
    load_state,
    pause_time,
    resume_time,
    save_state,
    set_entitlement,
)
from license import state as license_state
from minecraft_translator_complete_enhanced import (
    BaiduTranslator,
    EnhancedMinecraftLogMonitor,
    GoogleTranslator,
    Language,
    LanguageDetector,
    MessageFilter,
)
try:
    from core.game_send import send_to_minecraft_chat, find_game_window
except Exception:
    send_to_minecraft_chat = None
    find_game_window = None


def _cfg_path() -> Path:
    return Path.home() / ".minecraft_translator_enhanced" / "config.json"


def _default_config() -> dict:
    return {
        "language": "zh-CN",
        "auto_translate": True,
        "auto_detect": True,
        "filter_messages": True,
        "filter_keep_system": False,
        "filter_keep_rewards": False,
        "save_path": str(Path.home() / "MinecraftTranslations"),
        "baidu_app_id": "",
        "baidu_secret_key": "",
        "translation_engine": "baidu",
        "license_server_url": "https://xyxsb.shop",
        "mc_api_secret": "",
        "overlay_opacity": 0.82,
        "ui_language": "zh",
    }


def load_config() -> dict:
    cfg = _default_config()
    p = _cfg_path()
    if p.exists():
        try:
            user = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(user, dict):
                cfg.update(user)
        except Exception:
            pass
    return cfg


def save_config(cfg: dict) -> None:
    p = _cfg_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _app_icon_path() -> str:
    bases = []
    try:
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            bases.append(Path(meipass))
    except Exception:
        pass
    try:
        bases.append(Path(__file__).resolve().parent.parent)
    except Exception:
        pass
    bases.append(Path.cwd())

    names = ["y\u56fe\u6807.png", "app.ico", os.path.join("assets", "icon.ico")]
    for base in bases:
        for name in names:
            p = base / name
            if p.exists():
                return str(p)
    return ""


def _cjk_count(text: str) -> int:
    return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")


def _repair_zh_text(text: str) -> str:
    if not isinstance(text, str):
        return text
    # Keep Chinese text stable. Aggressive re-decoding causes false mojibake.
    # We only keep this hook for future targeted fixes.
    return text




def _pick_text(texts: dict, lang: str, key: str) -> str:
    bundle = texts.get(lang, texts.get("en", {}))
    val = bundle.get(key, key)
    if lang == "zh":
        return _repair_zh_text(val)
    return val

class ApiSettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None, ui_lang: str | None = None):
        super().__init__(parent)
        self.cfg = cfg
        self.ui_lang = str(ui_lang if ui_lang is not None else cfg.get("ui_language", "zh")).lower()
        if self.ui_lang not in ("zh", "en"):
            self.ui_lang = "zh"
        self.setWindowTitle(self._t("title"))
        self.setModal(True)
        self.resize(520, 260)
        icon_path = _app_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        lay = QVBoxLayout(self)
        grid = QGridLayout()

        self.server_edit = QLineEdit(cfg.get("license_server_url", ""))
        self.secret_edit = QLineEdit(cfg.get("mc_api_secret", ""))
        self.baidu_id_edit = QLineEdit(cfg.get("baidu_app_id", ""))
        self.baidu_key_edit = QLineEdit(cfg.get("baidu_secret_key", ""))

        grid.addWidget(QLabel(self._t("server_url")), 0, 0)
        grid.addWidget(self.server_edit, 0, 1)
        grid.addWidget(QLabel(self._t("api_secret")), 1, 0)
        grid.addWidget(self.secret_edit, 1, 1)
        grid.addWidget(QLabel(self._t("baidu_app_id")), 2, 0)
        grid.addWidget(self.baidu_id_edit, 2, 1)
        grid.addWidget(QLabel(self._t("baidu_secret_key")), 3, 0)
        grid.addWidget(self.baidu_key_edit, 3, 1)
        lay.addLayout(grid)

        btns = QHBoxLayout()
        ok_btn = QPushButton(self._t("save"))
        cancel_btn = QPushButton(self._t("cancel"))
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        lay.addLayout(btns)

    def _t(self, key: str) -> str:
        texts = {
            "en": {
                "title": "API Settings",
                "server_url": "License Server URL",
                "api_secret": "License API Secret",
                "baidu_app_id": "Baidu APP ID",
                "baidu_secret_key": "Baidu Secret Key",
                "save": "Save",
                "cancel": "Cancel",
            },
            "zh": {
                "title": "\u0041\u0050\u0049 \u8bbe\u7f6e",
                "server_url": "\u6388\u6743\u670d\u52a1\u5668\u5730\u5740",
                "api_secret": "\u6388\u6743 API \u5bc6\u94a5",
                "baidu_app_id": "\u767e\u5ea6 APP ID",
                "baidu_secret_key": "\u767e\u5ea6\u5bc6\u94a5",
                "save": "\u4fdd\u5b58",
                "cancel": "\u53d6\u6d88",
            },
        }
        return _pick_text(texts, self.ui_lang, key)

    def get_values(self) -> dict:
        return {
            "license_server_url": self.server_edit.text().strip(),
            "mc_api_secret": self.secret_edit.text().strip(),
            "baidu_app_id": self.baidu_id_edit.text().strip(),
            "baidu_secret_key": self.baidu_key_edit.text().strip(),
        }


class ActivationDialog(QDialog):
    def __init__(self, cfg: dict, parent=None, ui_lang: str | None = None):
        super().__init__(parent)
        self.cfg = cfg
        self.ui_lang = str(ui_lang if ui_lang is not None else cfg.get("ui_language", "zh")).lower()
        if self.ui_lang not in ("zh", "en"):
            self.ui_lang = "zh"
        self.setWindowTitle(self._t("title"))
        self.setModal(True)
        self.resize(560, 220)
        icon_path = _app_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.result = None

        lay = QVBoxLayout(self)

        self.machine_edit = QLineEdit(get_machine_code())
        self.machine_edit.setReadOnly(True)
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText(self._t("placeholder_key"))

        lay.addWidget(QLabel(self._t("machine_code")))
        lay.addWidget(self.machine_edit)
        lay.addWidget(QLabel(self._t("license_key")))
        lay.addWidget(self.key_edit)

        btns = QHBoxLayout()
        self.api_btn = QPushButton(self._t("server_settings"))
        self.ok_btn = QPushButton(self._t("activate"))
        self.cancel_btn = QPushButton(self._t("cancel"))
        btns.addWidget(self.api_btn)
        btns.addStretch(1)
        btns.addWidget(self.ok_btn)
        btns.addWidget(self.cancel_btn)
        lay.addLayout(btns)

        self.api_btn.clicked.connect(self._show_api_settings)
        self.ok_btn.clicked.connect(self._activate)
        self.cancel_btn.clicked.connect(self.reject)

    def _show_api_settings(self):
        dlg = ApiSettingsDialog(self.cfg, self, self.ui_lang)
        if dlg.exec():
            self.cfg.update(dlg.get_values())
            save_config(self.cfg)

    def _activate(self):
        key = self.key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, self._t("notice"), self._t("enter_key_first"))
            return
        try:
            resp = activate_with_server(key, self.machine_edit.text().strip())
            set_entitlement(
                int(resp.get("time_left", 0)),
                float(resp.get("credits", 0.0)),
                bool(resp.get("is_permanent", False)),
                session_token=resp.get("session_token", ""),
            )
            self.result = resp
            QMessageBox.information(self, self._t("success"), self._t("activate_ok"))
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, self._t("failed"), str(e))

    def _t(self, key: str) -> str:
        texts = {
            "en": {
                "title": "License Activation",
                "placeholder_key": "Enter license key",
                "machine_code": "Machine Code",
                "license_key": "License Key",
                "server_settings": "Server Settings",
                "activate": "Activate",
                "cancel": "Cancel",
                "notice": "Notice",
                "success": "Success",
                "failed": "Failed",
                "enter_key_first": "Please enter a license key.",
                "activate_ok": "Activation successful.",
            },
            "zh": {
                "title": "\u5361\u5bc6\u6fc0\u6d3b",
                "placeholder_key": "\u8bf7\u8f93\u5165\u5361\u5bc6",
                "machine_code": "\u673a\u5668\u7801",
                "license_key": "\u5361\u5bc6",
                "server_settings": "\u670d\u52a1\u5668\u8bbe\u7f6e",
                "activate": "\u6fc0\u6d3b",
                "cancel": "\u53d6\u6d88",
                "notice": "\u63d0\u793a",
                "success": "\u6210\u529f",
                "failed": "\u5931\u8d25",
                "enter_key_first": "\u8bf7\u5148\u8f93\u5165\u5361\u5bc6\u3002",
                "activate_ok": "\u6fc0\u6d3b\u6210\u529f\u3002",
            },
        }
        return _pick_text(texts, self.ui_lang, key)


class OverlayWindow(QWidget):
    def __init__(self, translate_cb=None, parent=None, ui_lang: str = "zh"):
        super().__init__(parent)
        self.translate_cb = translate_cb
        self.ui_lang = "en" if str(ui_lang).lower() == "en" else "zh"
        self.setWindowTitle(self._t("title"))
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(440, 260)
        icon_path = _app_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.follow_enabled = False
        self.follow_offset = (20, 20)

        lay = QVBoxLayout(self)
        self.mode_btn = QPushButton(self._t("toggle_input_mode"))
        self.mode_btn.clicked.connect(self.toggle_mode)
        lay.addWidget(self.mode_btn)

        self.follow_cb = QCheckBox(self._t("follow_game_window"))
        self.follow_cb.stateChanged.connect(self._toggle_follow)
        lay.addWidget(self.follow_cb)

        self.display = QTextEdit()
        self.display.setReadOnly(True)
        lay.addWidget(self.display)

        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText(self._t("overlay_input_hint"))
        self.input_box.hide()
        lay.addWidget(self.input_box)

        btn_row = QHBoxLayout()
        self.translate_btn = QPushButton(self._t("btn_translate"))
        self.translate_btn.clicked.connect(self.translate_input)
        self.translate_btn.hide()
        btn_row.addWidget(self.translate_btn)
        self.clear_input_btn = QPushButton(self._t("btn_clear_input"))
        self.clear_input_btn.clicked.connect(self.clear_input_text)
        self.clear_input_btn.hide()
        btn_row.addWidget(self.clear_input_btn)
        self.send_btn = QPushButton(self._t("btn_send_to_game"))
        self.send_btn.clicked.connect(self.send_to_game)
        self.send_btn.hide()
        btn_row.addWidget(self.send_btn)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        self.follow_timer = QTimer(self)
        self.follow_timer.setInterval(500)
        self.follow_timer.timeout.connect(self._follow_tick)

    def set_ui_language(self, lang: str):
        self.ui_lang = "en" if str(lang).lower() == "en" else "zh"
        self.setWindowTitle(self._t("title"))
        self.mode_btn.setText(self._t("toggle_input_mode"))
        self.follow_cb.setText(self._t("follow_game_window"))
        self.input_box.setPlaceholderText(self._t("overlay_input_hint"))
        self.translate_btn.setText(self._t("btn_translate"))
        self.clear_input_btn.setText(self._t("btn_clear_input"))
        self.send_btn.setText(self._t("btn_send_to_game"))

    def _t(self, key: str) -> str:
        texts = {
            "en": {
                "title": "Overlay",
                "toggle_input_mode": "Toggle Input Mode",
                "follow_game_window": "Follow Game Window",
                "overlay_input_hint": "Type text then click Translate",
                "btn_translate": "Translate",
                "btn_clear_input": "Clear Input",
                "btn_send_to_game": "Send To Game",
                "translator_not_configured": "Translator not configured.",
                "translation_failed": "Translation failed",
                "translation_failed_prefix": "Translation failed: {err}",
            },
            "zh": {
                "title": "\u60ac\u6d6e\u7a97",
                "toggle_input_mode": "\u5207\u6362\u8f93\u5165\u6a21\u5f0f",
                "follow_game_window": "\u8ddf\u968f\u6e38\u620f\u7a97\u53e3",
                "overlay_input_hint": "\u8f93\u5165\u6587\u672c\u540e\u70b9\u51fb\u7ffb\u8bd1",
                "btn_translate": "\u7ffb\u8bd1",
                "btn_clear_input": "\u6e05\u7a7a\u8f93\u5165",
                "btn_send_to_game": "\u53d1\u9001\u5230\u6e38\u620f",
                "translator_not_configured": "\u7ffb\u8bd1\u5668\u672a\u914d\u7f6e\u3002",
                "translation_failed": "\u7ffb\u8bd1\u5931\u8d25",
                "translation_failed_prefix": "\u7ffb\u8bd1\u5931\u8d25: {err}",
            },
        }
        return _pick_text(texts, self.ui_lang, key)

    def toggle_mode(self):
        in_mode = self.input_box.isVisible()
        if in_mode:
            self.input_box.hide()
            self.translate_btn.hide()
            self.clear_input_btn.hide()
            self.send_btn.hide()
        else:
            self.input_box.show()
            self.translate_btn.show()
            self.clear_input_btn.show()
            self.send_btn.show()

    def translate_input(self):
        if not self.translate_cb:
            self.display.append(self._t("translator_not_configured"))
            return
        text = self.input_box.toPlainText().strip()
        if not text:
            return
        out = self.translate_cb(text, "en")
        if out:
            self.display.append(out)
        else:
            self.display.append(self._t("translation_failed"))

    def clear_input_text(self):
        self.input_box.clear()
        self.display.clear()

    def send_to_game(self):
        if not send_to_minecraft_chat:
            return
        text = self.input_box.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        send_to_minecraft_chat()

    def _toggle_follow(self):
        self.follow_enabled = bool(self.follow_cb.isChecked())
        if self.follow_enabled:
            self.follow_timer.start()
        else:
            self.follow_timer.stop()

    def _follow_tick(self):
        if not self.follow_enabled or not find_game_window:
            return
        hwnd = find_game_window(
            keywords=["Minecraft", "Lunar", "Lunar Client", "Badlion", "Badlion Client"],
            exclude_keywords=["minecraft translator", "translator", "overlay"],
        )
        if not hwnd:
            return
        rect = wintypes.RECT()
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return
        x = rect.left + self.follow_offset[0]
        y = rect.top + self.follow_offset[1]
        self.move(int(x), int(y))

    def append_line(self, original: str, translated: str):
        self.display.append(f"{original}\n=> {translated}\n")

    def clear_all(self):
        self.display.clear()
        self.input_box.clear()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        icon_path = _app_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.cfg = load_config()
        self.cache = TranslationCache()
        self.lang_detector = LanguageDetector()
        self.filter = MessageFilter(
            enabled=self.cfg.get("filter_messages", True),
            keep_system=self.cfg.get("filter_keep_system", False),
            keep_rewards=self.cfg.get("filter_keep_rewards", False),
        )
        self.hide_all_messages = bool(self.cfg.get("hide_all_messages", False))
        self.show_all_logs = bool(self.cfg.get("show_all_logs", False))
        self.no_translate_names = bool(self.cfg.get("no_translate_names", True))
        self.ui_language = self._normalize_ui_lang(self.cfg.get("ui_language", "zh"))

        self.google = GoogleTranslator()
        self.baidu = None
        if self.cfg.get("baidu_app_id") and self.cfg.get("baidu_secret_key"):
            self.baidu = BaiduTranslator(self.cfg["baidu_app_id"], self.cfg["baidu_secret_key"])

        self.monitor = EnhancedMinecraftLogMonitor(self.on_log)
        self.monitor.message_filter = self.filter
        try:
            bl = self.cfg.get("badlion_log_file")
            ln = self.cfg.get("lunar_log_file")
            mf = self.cfg.get("manual_log_file")
            if bl:
                self.monitor.default_paths.insert(0, Path(bl))
            if ln:
                self.monitor.default_paths.insert(0, Path(ln))
            if mf and Path(mf).exists():
                self.monitor.log_file = mf
        except Exception:
            pass

        self.pending_ui = queue.Queue()
        self.auto_q = queue.Queue(maxsize=8)
        self.history = []
        self.overlay = None
        self._stats = {"total": 0, "success": 0, "fail": 0, "cache_hit": 0, "total_ms": 0.0}
        self._stats_by_engine = {}
        self._page_anim = None
        self._startup_anim_done = False
        self._startup_geo_anim = None
        self._startup_opacity_anim = None
        self._loading_count = 0
        self._loading_phase = 0
        self._loading_text = ""

        self.setWindowTitle(f"Minecraft Smart Translator v3 build {BUILD_TAG}")
        self.resize(1320, 860)
        self._build_ui()
        self._apply_ui_language()
        self._apply_dark_theme()
        self._refresh_welfare_page()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._drain_ui_queue)
        self.timer.start(120)

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_license_status)
        self.status_timer.start(2000)
        self.loading_timer = QTimer(self)
        self.loading_timer.setInterval(260)
        self.loading_timer.timeout.connect(self._tick_loading)

        self.auto_thread = threading.Thread(target=self._auto_worker, daemon=True)
        self.auto_thread.start()

        self._load_history()
        self.refresh_license_status()
        self._register_machine_async()
        self.shortcut_overlay = QShortcut(QKeySequence("F8"), self, activated=self.toggle_overlay)
        self.shortcut_restore = QShortcut(
            QKeySequence("Ctrl+Alt+Shift+F12"),
            self,
            activated=self.restore_defaults_and_revoke_server,
        )
        self.shortcut_restore.setContext(Qt.ShortcutContext.ApplicationShortcut)

    def _build_ui(self):
        root = QWidget(self)
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        sb = QVBoxLayout(self.sidebar)
        self.btn_home = QPushButton("Home")
        self.btn_tools = QPushButton("Tools")
        self.btn_settings = QPushButton("Settings")
        self.btn_welfare = QPushButton("Welfare")
        sb.addWidget(self.btn_home)
        sb.addWidget(self.btn_tools)
        sb.addWidget(self.btn_settings)
        sb.addWidget(self.btn_welfare)
        sb.addStretch(1)

        self.btn_theme = QPushButton("Toggle Theme")
        self._theme_dark = True
        self.btn_theme.clicked.connect(self.toggle_theme)
        sb.addWidget(self.btn_theme)
        self.ui_lang_combo = QComboBox()
        self.ui_lang_combo.addItem("\u4e2d\u6587", "zh")
        self.ui_lang_combo.addItem("English", "en")
        self.ui_lang_combo.currentIndexChanged.connect(self.on_ui_language_changed)
        sb.addWidget(self.ui_lang_combo)

        outer.addWidget(self.sidebar, 0)

        self.pages = QStackedWidget()
        outer.addWidget(self.pages, 1)

        home = QWidget()
        home_wrap = QVBoxLayout(home)

        top = QHBoxLayout()
        self.engine = QComboBox()
        self.engine.addItems(["baidu", "google"])
        self.engine.setCurrentText(self.cfg.get("translation_engine", "baidu"))
        self.lang = QComboBox()
        self.lang.addItems(["zh-CN", "en", "ja", "ko", "fr", "de", "es", "ru"])
        self.lang.setCurrentText(self.cfg.get("language", "zh-CN"))
        self.cb_auto = QCheckBox("Auto Translate")
        self.cb_auto.setChecked(self.cfg.get("auto_translate", True))
        self.cb_detect = QCheckBox("Auto Detect")
        self.cb_detect.setChecked(self.cfg.get("auto_detect", True))
        self.cb_filter = QCheckBox("Filter Logs")
        self.cb_filter.setChecked(self.cfg.get("filter_messages", True))

        self.monitor_status = QLabel("Monitor: Stopped")
        self.btn_toggle = QPushButton("Start Monitor")
        self.btn_test = QPushButton("Test API")

        self.lbl_engine = QLabel("Engine")
        top.addWidget(self.lbl_engine)
        top.addWidget(self.engine)
        self.lbl_target = QLabel("Target")
        top.addWidget(self.lbl_target)
        top.addWidget(self.lang)
        top.addWidget(self.cb_auto)
        top.addWidget(self.cb_detect)
        top.addWidget(self.cb_filter)
        top.addStretch(1)
        top.addWidget(self.monitor_status)
        top.addWidget(self.btn_toggle)
        top.addWidget(self.btn_test)
        home_wrap.addLayout(top)

        split = QSplitter(Qt.Orientation.Horizontal)
        home_wrap.addWidget(split, 1)

        left = QWidget()
        left_lay = QVBoxLayout(left)

        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText("Input text")
        self.lbl_input = QLabel("Input")
        left_lay.addWidget(self.lbl_input)
        left_lay.addWidget(self.input_box, 1)

        btn_row = QHBoxLayout()
        self.btn_smart = QPushButton("Smart Translate")
        self.btn_plain = QPushButton("Translate")
        self.btn_clear = QPushButton("Clear")
        btn_row.addWidget(self.btn_smart)
        btn_row.addWidget(self.btn_plain)
        btn_row.addWidget(self.btn_clear)
        left_lay.addLayout(btn_row)

        self.lbl_live_monitor = QLabel("Live Monitor")
        left_lay.addWidget(self.lbl_live_monitor)
        monitor_tools = QHBoxLayout()
        self.cb_show_all = QCheckBox("Show All Logs")
        self.cb_show_all.setChecked(self.show_all_logs)
        monitor_tools.addWidget(self.cb_show_all)
        monitor_tools.addStretch(1)
        left_lay.addLayout(monitor_tools)

        self.monitor_view = QTextEdit()
        self.monitor_view.setReadOnly(True)
        left_lay.addWidget(self.monitor_view, 1)

        right = QWidget()
        right_lay = QVBoxLayout(right)

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.lbl_result = QLabel("Translation Result")
        right_lay.addWidget(self.lbl_result)
        right_lay.addWidget(self.result_box, 1)

        res_btn = QHBoxLayout()
        self.btn_copy = QPushButton("Copy")
        self.btn_save = QPushButton("Save")
        self.btn_analyze = QPushButton("Analyze")
        res_btn.addWidget(self.btn_copy)
        res_btn.addWidget(self.btn_save)
        res_btn.addWidget(self.btn_analyze)
        right_lay.addLayout(res_btn)

        self.history_list = QListWidget()
        self.lbl_recent_history = QLabel("Recent History")
        right_lay.addWidget(self.lbl_recent_history)
        right_lay.addWidget(self.history_list, 1)

        hist_btn = QHBoxLayout()
        self.btn_hist_view = QPushButton("View Detail")
        self.btn_hist_clear = QPushButton("Clear History")
        hist_btn.addWidget(self.btn_hist_view)
        hist_btn.addWidget(self.btn_hist_clear)
        right_lay.addLayout(hist_btn)

        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([640, 640])

        bottom = QHBoxLayout()
        self.status_label = QLabel("Ready")
        bottom.addWidget(self.status_label)
        self.loading_label = QLabel("")
        self.loading_label.hide()
        bottom.addWidget(self.loading_label)
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setFixedWidth(110)
        self.loading_bar.hide()
        bottom.addWidget(self.loading_bar)
        bottom.addStretch(1)

        corner = QFrame()
        c_lay = QVBoxLayout(corner)
        self.license_label = QLabel("License: Not activated")
        self.btn_pause = QPushButton("Pause Time")
        self.btn_overlay = QPushButton("Overlay Toggle (F8)")
        self.btn_activate = QPushButton("Activate / Machine Code")
        self.btn_sync = QPushButton("Force Sync")
        c_lay.addWidget(self.license_label)
        c_lay.addWidget(self.btn_pause)
        c_lay.addWidget(self.btn_overlay)
        c_lay.addWidget(self.btn_activate)
        c_lay.addWidget(self.btn_sync)
        bottom.addWidget(corner)
        home_wrap.addLayout(bottom)

        tools = QWidget()
        tools_lay = QVBoxLayout(tools)
        self.tools_title = QLabel("Minecraft 智能翻译工具")
        tools_lay.addWidget(self.tools_title)
        self.btn_select_badlion = QPushButton("Select Badlion Log")
        self.btn_select_lunar = QPushButton("Select Lunar Log")
        self.btn_select_manual = QPushButton("Select Log Manually")
        self.btn_view_format = QPushButton("View Log Format")
        self.btn_test_monitor = QPushButton("Test Monitor")
        self.btn_test_lang = QPushButton("Test Language Detect")
        self.btn_web_translate = QPushButton("Web Translate")
        self.btn_select_badlion.clicked.connect(self.select_badlion_log)
        self.btn_select_lunar.clicked.connect(self.select_lunar_log)
        self.btn_select_manual.clicked.connect(self.manual_select_log)
        self.btn_view_format.clicked.connect(self.view_log_format)
        self.btn_test_monitor.clicked.connect(self.test_monitor)
        self.btn_test_lang.clicked.connect(self.test_language_detection)
        self.btn_web_translate.clicked.connect(self.web_translate)
        tools_lay.addWidget(self.btn_select_badlion)
        tools_lay.addWidget(self.btn_select_lunar)
        tools_lay.addWidget(self.btn_select_manual)
        tools_lay.addWidget(self.btn_view_format)
        tools_lay.addWidget(self.btn_test_monitor)
        tools_lay.addWidget(self.btn_test_lang)
        tools_lay.addWidget(self.btn_web_translate)
        tools_lay.addStretch(1)

        settings = QWidget()
        settings_lay = QVBoxLayout(settings)
        self.settings_title = QLabel("Settings")
        settings_lay.addWidget(self.settings_title)
        self.btn_api = QPushButton("API Settings")
        self.btn_save_path = QPushButton("Set Save Path")
        self.btn_toggle_theme = QPushButton("Toggle Theme")
        self.btn_api.clicked.connect(self.show_api_settings)
        self.btn_save_path.clicked.connect(self.set_save_path)
        self.btn_toggle_theme.clicked.connect(self.toggle_theme)
        settings_lay.addWidget(self.btn_api)
        settings_lay.addWidget(self.btn_save_path)
        settings_lay.addWidget(self.btn_toggle_theme)
        settings_lay.addStretch(1)

        welfare = QWidget()
        welfare_lay = QVBoxLayout(welfare)
        self.welfare_title = QLabel("Welfare")
        welfare_lay.addWidget(self.welfare_title)
        self.welfare_info = QLabel("")
        welfare_lay.addWidget(self.welfare_info)
        self.btn_welfare_first_credits = QPushButton("First reward: +150 credits")
        self.btn_welfare_first_time = QPushButton("First reward: +7 days")
        self.btn_welfare_weekly_credits = QPushButton("Weekly reward: +50 credits")
        self.btn_welfare_weekly_time = QPushButton("Weekly reward: +1 day")
        self.btn_welfare_refresh = QPushButton("Refresh welfare status")
        welfare_lay.addWidget(self.btn_welfare_first_credits)
        welfare_lay.addWidget(self.btn_welfare_first_time)
        welfare_lay.addWidget(self.btn_welfare_weekly_credits)
        welfare_lay.addWidget(self.btn_welfare_weekly_time)
        welfare_lay.addWidget(self.btn_welfare_refresh)
        welfare_lay.addStretch(1)

        self.btn_welfare_first_credits.clicked.connect(lambda: self._claim_welfare_once("credits"))
        self.btn_welfare_first_time.clicked.connect(lambda: self._claim_welfare_once("time"))
        self.btn_welfare_weekly_credits.clicked.connect(lambda: self._claim_welfare_weekly("credits"))
        self.btn_welfare_weekly_time.clicked.connect(lambda: self._claim_welfare_weekly("time"))
        self.btn_welfare_refresh.clicked.connect(self._refresh_welfare_page)

        self.pages.addWidget(home)
        self.pages.addWidget(tools)
        self.pages.addWidget(settings)
        self.pages.addWidget(welfare)
        self.pages.setCurrentIndex(0)

        self.btn_toggle.clicked.connect(self.toggle_monitor)
        self.btn_test.clicked.connect(self.test_api)
        self.btn_smart.clicked.connect(self.smart_translate)
        self.btn_plain.clicked.connect(self.translate_text)
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_copy.clicked.connect(self.copy_result)
        self.btn_save.clicked.connect(self.save_result)
        self.btn_analyze.clicked.connect(self.show_analysis)
        self.btn_hist_view.clicked.connect(self.view_history)
        self.btn_hist_clear.clicked.connect(self.clear_history)
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_overlay.clicked.connect(self.toggle_overlay)
        self.btn_activate.clicked.connect(self.open_activation)
        self.btn_sync.clicked.connect(self.force_sync)
        self.btn_home.clicked.connect(self._nav_home)
        self.btn_tools.clicked.connect(self._nav_tools)
        self.btn_settings.clicked.connect(self._nav_settings)
        self.btn_welfare.clicked.connect(self._nav_welfare)

        self.cb_filter.stateChanged.connect(self._on_filter_changed)
        self.engine.currentTextChanged.connect(self._on_cfg_changed)
        self.lang.currentTextChanged.connect(self._on_cfg_changed)
        self.cb_auto.stateChanged.connect(self._on_cfg_changed)
        self.cb_detect.stateChanged.connect(self._on_cfg_changed)
        self.cb_show_all.stateChanged.connect(self._on_show_all_logs)

        self._build_menu()


    def _build_menu(self):
        m = self.menuBar()

        self.menu_file = m.addMenu("File")
        self.act_save_current = QAction("Save Current Translation", self)
        self.act_save_current.triggered.connect(self.save_current_translation)
        self.menu_file.addAction(self.act_save_current)
        self.act_export_history = QAction("Export History JSON", self)
        self.act_export_history.triggered.connect(self.export_history)
        self.menu_file.addAction(self.act_export_history)
        self.act_set_save_path = QAction("Set Save Path", self)
        self.act_set_save_path.triggered.connect(self.set_save_path)
        self.menu_file.addAction(self.act_set_save_path)
        self.menu_file.addSeparator()
        self.act_exit = QAction("Exit", self)
        self.act_exit.triggered.connect(self.close)
        self.menu_file.addAction(self.act_exit)

        self.menu_translate = m.addMenu("Translate")
        self.act_translate = QAction("Translate", self)
        self.act_translate.triggered.connect(self.translate_text)
        self.menu_translate.addAction(self.act_translate)
        self.act_smart_translate = QAction("Smart Translate", self)
        self.act_smart_translate.triggered.connect(self.smart_translate)
        self.menu_translate.addAction(self.act_smart_translate)
        self.act_web_translate = QAction("Web Translate", self)
        self.act_web_translate.triggered.connect(self.web_translate)
        self.menu_translate.addAction(self.act_web_translate)
        self.menu_translate.addSeparator()
        self.act_clear = QAction("Clear", self)
        self.act_clear.triggered.connect(self.clear_all)
        self.menu_translate.addAction(self.act_clear)

        self.menu_tools = m.addMenu("Tools")
        self.act_api_settings = QAction("API Settings", self)
        self.act_api_settings.triggered.connect(self.show_api_settings)
        self.menu_tools.addAction(self.act_api_settings)
        self.act_test_api = QAction("Test Translation API", self)
        self.act_test_api.triggered.connect(self.test_translation_api)
        self.menu_tools.addAction(self.act_test_api)
        self.act_test_lang = QAction("Language Detection Test", self)
        self.act_test_lang.triggered.connect(self.test_language_detection)
        self.menu_tools.addAction(self.act_test_lang)
        self.menu_tools.addSeparator()
        self.act_select_manual = QAction("Select Log Manually", self)
        self.act_select_manual.triggered.connect(self.manual_select_log)
        self.menu_tools.addAction(self.act_select_manual)
        self.act_test_monitor = QAction("Test Monitor", self)
        self.act_test_monitor.triggered.connect(self.test_monitor)
        self.menu_tools.addAction(self.act_test_monitor)
        self.act_select_badlion = QAction("Select Badlion Log", self)
        self.act_select_badlion.triggered.connect(self.select_badlion_log)
        self.menu_tools.addAction(self.act_select_badlion)
        self.act_select_lunar = QAction("Select Lunar Log", self)
        self.act_select_lunar.triggered.connect(self.select_lunar_log)
        self.menu_tools.addAction(self.act_select_lunar)
        self.act_view_log_format = QAction("View Log Format", self)
        self.act_view_log_format.triggered.connect(self.view_log_format)
        self.menu_tools.addAction(self.act_view_log_format)
        self.menu_tools.addSeparator()
        self.act_stats = QAction("Stats Panel", self)
        self.act_stats.triggered.connect(self.show_stats_panel)
        self.menu_tools.addAction(self.act_stats)

        self.menu_settings = m.addMenu("Settings")
        self.act_hide_all = QAction("Hide All Messages", self, checkable=True)
        self.act_hide_all.setChecked(self.hide_all_messages)
        self.act_hide_all.triggered.connect(self.toggle_hide_all)
        self.menu_settings.addAction(self.act_hide_all)

        self.act_keep_system = QAction("Keep System Messages", self, checkable=True)
        self.act_keep_system.setChecked(self.cfg.get("filter_keep_system", False))
        self.act_keep_system.triggered.connect(self.toggle_keep_system)
        self.menu_settings.addAction(self.act_keep_system)

        self.act_keep_rewards = QAction("Keep Reward Messages", self, checkable=True)
        self.act_keep_rewards.setChecked(self.cfg.get("filter_keep_rewards", False))
        self.act_keep_rewards.triggered.connect(self.toggle_keep_rewards)
        self.menu_settings.addAction(self.act_keep_rewards)

        self.act_no_names = QAction("Do Not Translate Names", self, checkable=True)
        self.act_no_names.setChecked(self.no_translate_names)
        self.act_no_names.triggered.connect(self.toggle_no_translate_names)
        self.menu_settings.addAction(self.act_no_names)

        self.menu_help = m.addMenu("Help")
        self.act_usage = QAction("Usage", self)
        self.act_usage.triggered.connect(self.show_help)
        self.menu_help.addAction(self.act_usage)
        self.act_sponsor = QAction("Sponsor", self)
        self.act_sponsor.triggered.connect(self.show_sponsor)
        self.menu_help.addAction(self.act_sponsor)
        self.act_about = QAction("About", self)
        self.act_about.triggered.connect(self.show_about)
        self.menu_help.addAction(self.act_about)
    def _texts(self) -> dict:
        return {
            "en": {
                "window_title": f"Minecraft Smart Translator v3 build {BUILD_TAG}",
                "btn_home": "Home",
                "btn_tools": "Tools",
                "btn_settings": "Settings",
                "btn_welfare": "Welfare",
                "btn_theme": "Toggle Theme",
                "lbl_engine": "Engine",
                "lbl_target": "Target",
                "cb_auto": "Auto Translate",
                "cb_detect": "Auto Detect",
                "cb_filter": "Filter Logs",
                "monitor_stopped": "Monitor: Stopped",
                "monitor_running": "Monitor: Running",
                "btn_start_monitor": "Start Monitor",
                "btn_stop_monitor": "Stop Monitor",
                "btn_test_api": "Test API",
                "lbl_input": "Input",
                "placeholder_input": "Input text",
                "btn_smart": "Smart Translate",
                "btn_translate": "Translate",
                "btn_clear": "Clear",
                "lbl_live_monitor": "Live Monitor",
                "cb_show_all": "Show All Logs",
                "lbl_result": "Translation Result",
                "lbl_recent_history": "Recent History",
                "btn_copy": "Copy",
                "btn_save": "Save",
                "btn_analyze": "Analyze",
                "btn_view_detail": "View Detail",
                "btn_clear_history": "Clear History",
                "status_ready": "Ready",
                "status_home": "Home",
                "loading": "Loading",
                "loading_translating": "Translating",
                "loading_testing": "Testing API",
                "loading_sync": "Syncing",
                "btn_pause": "Pause Time",
                "btn_resume": "Resume Time",
                "btn_overlay": "Overlay Toggle (F8)",
                "btn_activate": "Activate / Machine Code",
                "btn_sync": "Force Sync",
                "tools_title": "Tools",
                "btn_select_badlion": "Select Badlion Log",
                "btn_select_lunar": "Select Lunar Log",
                "btn_select_manual": "Select Log Manually",
                "btn_view_log_format": "View Log Format",
                "btn_test_monitor": "Test Monitor",
                "btn_test_lang": "Test Language Detect",
                "btn_web_translate": "Web Translate",
                "settings_title": "Settings",
                "btn_api": "API Settings",
                "btn_save_path": "Set Save Path",
                "welfare_title": "Welfare",
                "btn_welfare_first_credits": "First reward: +150 credits",
                "btn_welfare_first_time": "First reward: +7 days",
                "btn_welfare_weekly_credits": "Weekly reward: +50 credits",
                "btn_welfare_weekly_time": "Weekly reward: +1 day",
                "btn_welfare_refresh": "Refresh welfare status",
                "welfare_first_label": "First-time welfare",
                "welfare_weekly_label": "Weekly welfare",
                "welfare_claimed": "Claimed",
                "welfare_not_claimed": "Not claimed",
                "welfare_available": "Available",
                "welfare_cooldown_fmt": "Cooldown: {d}d {h}h {m}m",
                "welfare_need_first": "Claim first-time welfare first",
                "msg_welfare_title": "Welfare",
                "msg_welfare_claimed_ok": "Claimed successfully.",
                "msg_welfare_claimed_fail": "First-time welfare already claimed or condition not met.",
                "msg_welfare_weekly_ok": "Weekly welfare claimed.",
                "msg_welfare_weekly_wait": "Not available yet, please wait for cooldown.",
                "menu_file": "File",
                "act_save_current": "Save Current Translation",
                "act_export_history": "Export History JSON",
                "act_set_save_path": "Set Save Path",
                "act_exit": "Exit",
                "menu_translate": "Translate",
                "act_translate": "Translate",
                "act_smart_translate": "Smart Translate",
                "act_web_translate": "Web Translate",
                "act_clear": "Clear",
                "menu_tools": "Tools",
                "act_api_settings": "API Settings",
                "act_test_api": "Test Translation API",
                "act_test_lang": "Language Detection Test",
                "act_select_manual": "Select Log Manually",
                "act_test_monitor": "Test Monitor",
                "act_select_badlion": "Select Badlion Log",
                "act_select_lunar": "Select Lunar Log",
                "act_view_log_format": "View Log Format",
                "act_stats": "Stats Panel",
                "menu_settings": "Settings",
                "act_hide_all": "Hide All Messages",
                "act_keep_system": "Keep System Messages",
                "act_keep_rewards": "Keep Reward Messages",
                "act_no_names": "Do Not Translate Names",
                "menu_help": "Help",
                "act_usage": "Usage",
                "act_sponsor": "Sponsor",
                "act_about": "About",
                "license_label_fmt": "License: {status} | Credits: {credits:.1f} | Time: {days}d {hours}h{paused}",
                "license_status_activated": "Activated",
                "license_status_not_activated": "Not activated",
                "license_status_developer": "Developer",
                "paused_suffix": " | Paused",
                "msg_restore_title": "Restore Default",
                "msg_restore_confirm": "Reset all local settings/license/welfare to defaults and clear server entitlement?\n\nShortcut: Ctrl+Alt+Shift+F12",
                "msg_restore_server_ok": "Defaults restored. Server entitlement cleared.",
                "msg_restore_server_failed": "Defaults restored locally, but server clear failed:\n{err}",
                "status_restoring": "Restoring defaults...",
                "status_restore_done_local": "Defaults restored locally",
                "status_restore_done_server": "Defaults restored and server entitlement cleared",
                "status_restore_server_failed": "Server clear failed",
                "notice_title": "Notice",
                "sync_title": "Sync",
                "sync_need_activate": "Please activate a license key first.",
                "sync_skipped_no_token": "Sync skipped: no session token",
                "sync_running": "Syncing...",
                "sync_success": "Sync success",
                "sync_failed_title": "Sync failed",
                "sync_fatal_title": "Sync fatal error",
                "startup_sync_done": "Startup sync done",
                "startup_sync_failed_title": "Startup sync failed",
                "startup_sync_failed_fmt": "Startup sync failed: {err}",
                "startup_sync_failed_cleared_fmt": "Startup sync failed, local license cleared: {err}",
                "startup_sync_handler_failed_fmt": "Startup sync handler error: {err}",
                "startup_sync_handler_alert_fmt": "Sync error: {sync_err}\\nHandler error: {handler_err}",
                "startup_sync_fatal_fmt": "Startup sync fatal error: {err}",
                "sync_err_session_expired": "Session expired. Please activate again.",
                "sync_err_unauthorized": "Unauthorized. Check server secret or activate again.",
                "sync_err_forbidden": "Forbidden by server policy.",
                "sync_err_unknown": "Unknown sync error",
                "history_detail_title": "History Detail",
                "msg_pause_not_needed": "Permanent license does not need pause.",
                "msg_pause_no_time": "No remaining time to pause.",
                "msg_pause_ok": "Paused.",
                "msg_pause_fail": "Pause failed.",
                "msg_resume_ok": "Resumed.",
                "msg_resume_fail": "Resume failed.",
                "status_insufficient_entitlement": "Insufficient entitlement, skipped auto translation.",
                "status_translation_failed_fmt": "Translation failed: {err}",
                "status_translation_done": "Translation completed.",
                "status_smart_translating": "Smart translating...",
                "status_translating": "Translating...",
                "msg_enter_text_first": "Please enter text to translate.",
                "status_copied": "Copied result.",
                "msg_no_content_save": "No content to save.",
                "status_saved_ok": "Saved successfully.",
                "detail_analysis_title": "Detailed Analysis",
                "detail_analysis_fmt": "Detected language: {lang}\nLength: {length}",
                "lang_detect_title": "Language Detection",
                "lang_detect_fmt": "Detected: {lang}",
                "api_ok": "OK",
                "api_failed": "FAILED",
                "api_test_result_fmt": "Google: {g}\nBaidu: {b}",
                "from_to_label": "From/To",
                "status_web_opened": "Web translation opened.",
                "status_save_path_set_fmt": "Save path set: {path}",
                "dialog_select_save_folder": "Select Save Folder",
                "dialog_export_history": "Export History",
                "dialog_select_log_file": "Select Log File",
                "dialog_select_badlion_file": "Select Badlion Log File",
                "dialog_select_lunar_file": "Select Lunar Log File",
                "save_record_title": "Save Translation Record",
                "save_record_header": "Minecraft Translation Record",
                "save_record_time_prefix": "Time",
                "save_record_engine_prefix": "Engine",
                "save_record_target_prefix": "Target language",
                "save_record_original_prefix": "Original",
                "save_record_translated_prefix": "Translated",
                "save_success_title": "Success",
                "save_success_fmt": "Saved to:\n{path}",
                "status_saved_file_fmt": "Saved: {name}",
                "save_error_title": "Error",
                "save_error_fmt": "Save failed: {err}",
                "export_none": "No history to export.",
                "status_history_exported": "History exported.",
                "export_error_fmt": "Export failed: {err}",
                "status_badlion_selected_fmt": "Selected Badlion log file: {name}",
                "status_lunar_selected_fmt": "Selected Lunar log file: {name}",
                "status_manual_selected_fmt": "Selected log file: {name}",
                "msg_log_not_found": "Minecraft log file not found.",
                "monitor_test_title": "Monitor Test",
                "monitor_test_fmt": "Log: {log}\nLines: {total}\nKept: {kept}/{max_lines}\nFilter rate: {rate:.1f}%",
                "log_format_title": "Log Format Analysis",
                "log_format_tab_raw": "Raw Log",
                "log_format_tab_filter": "Filter Result",
                "log_format_tab_lang": "Language Detection",
                "log_format_filter_report": "Filter Analysis Report",
                "log_format_lang_report": "Language Detection Report",
                "log_format_kept": "Kept",
                "log_format_filtered": "Filtered",
                "log_format_filter_stats_fmt": "Filter stats: kept {kept}/{total} ({rate:.1f}%)",
                "stats_title": "Translation Stats",
                "stats_summary_fmt": "Total: {total}\nSuccess: {success}\nFailed: {fail}\nCache hit: {cache_hit}\nAvg ms: {avg_ms:.1f}",
                "stats_engine_header": "Engine Statistics",
                "stats_engine_line_fmt": "{engine}: total={total}, ok={success}, fail={fail}, cache={cache}, avg_ms={avg_ms:.1f}",
                "about_title": "About",
                "about_app_name": "Minecraft Translator",
                "about_arch": "Architecture: PyQt6 + monitor thread + async translation queue",
                "about_license": "License",
                "about_credits": "Credits",
                "about_time": "Time",
                "about_time_permanent": "Permanent",
                "about_config_file": "Config file",
                "about_state_file": "License state file",
                "about_history_file": "History file",
                "about_save_folder": "Save folder",
            },
                        "zh": {
                "window_title": f"Minecraft\u667a\u80fd\u7ffb\u8bd1\u5de5\u5177 v3 build {BUILD_TAG}",
                "btn_home": "\u4e3b\u9875",
                "btn_tools": "\u5de5\u5177",
                "btn_settings": "\u8bbe\u7f6e",
                "btn_welfare": "\u798f\u5229",
                "btn_theme": "\u5207\u6362\u4e3b\u9898",
                "lbl_engine": "\u7ffb\u8bd1\u5f15\u64ce",
                "lbl_target": "\u76ee\u6807\u8bed\u8a00",
                "cb_auto": "\u81ea\u52a8\u7ffb\u8bd1",
                "cb_detect": "\u81ea\u52a8\u68c0\u6d4b",
                "cb_filter": "\u65e5\u5fd7\u8fc7\u6ee4",
                "monitor_stopped": "\u76d1\u63a7\uff1a\u505c\u6b62",
                "monitor_running": "\u76d1\u63a7\uff1a\u8fd0\u884c\u4e2d",
                "btn_start_monitor": "\u542f\u52a8\u76d1\u63a7",
                "btn_stop_monitor": "\u505c\u6b62\u76d1\u63a7",
                "btn_test_api": "\u6d4b\u8bd5 API",
                "lbl_input": "\u8f93\u5165\u6587\u672c",
                "placeholder_input": "\u8bf7\u8f93\u5165\u8981\u7ffb\u8bd1\u7684\u5185\u5bb9",
                "btn_smart": "\u667a\u80fd\u7ffb\u8bd1",
                "btn_translate": "\u7ffb\u8bd1",
                "btn_clear": "\u6e05\u7a7a",
                "lbl_live_monitor": "\u5b9e\u65f6\u76d1\u63a7",
                "cb_show_all": "\u663e\u793a\u5168\u90e8\u65e5\u5fd7",
                "lbl_result": "\u7ffb\u8bd1\u7ed3\u679c",
                "lbl_recent_history": "\u6700\u8fd1\u5386\u53f2",
                "btn_copy": "\u590d\u5236\u7ed3\u679c",
                "btn_save": "\u4fdd\u5b58",
                "btn_analyze": "\u8be6\u7ec6\u5206\u6790",
                "btn_view_detail": "\u67e5\u770b\u8be6\u60c5",
                "btn_clear_history": "\u6e05\u7a7a\u5386\u53f2",
                "status_ready": "\u5c31\u7eea",
                "status_home": "\u4e3b\u9875",
                "loading": "\u52a0\u8f7d\u4e2d",
                "loading_translating": "\u7ffb\u8bd1\u4e2d",
                "loading_testing": "\u6d4b\u8bd5 API",
                "loading_sync": "\u540c\u6b65\u4e2d",
                "btn_pause": "\u6682\u505c\u65f6\u957f",
                "btn_resume": "\u6062\u590d\u65f6\u957f",
                "btn_overlay": "\u60ac\u6d6e\u7a97\u5f00/\u5173 (F8)",
                "btn_activate": "\u5361\u5bc6\u6fc0\u6d3b / \u67e5\u770b\u673a\u5668\u7801",
                "btn_sync": "\u5f3a\u5236\u540c\u6b65",
                "tools_title": "\u5de5\u5177",
                "btn_select_badlion": "\u9009\u62e9 Badlion \u65e5\u5fd7",
                "btn_select_lunar": "\u9009\u62e9 Lunar \u65e5\u5fd7",
                "btn_select_manual": "\u624b\u52a8\u9009\u62e9\u65e5\u5fd7",
                "btn_view_log_format": "\u67e5\u770b\u65e5\u5fd7\u683c\u5f0f",
                "btn_test_monitor": "\u6d4b\u8bd5\u76d1\u63a7",
                "btn_test_lang": "\u6d4b\u8bd5\u8bed\u8a00\u68c0\u6d4b",
                "btn_web_translate": "\u7f51\u9875\u7ffb\u8bd1",
                "settings_title": "\u8bbe\u7f6e",
                "btn_api": "\u7ffb\u8bd1 API",
                "btn_save_path": "\u8bbe\u7f6e\u4fdd\u5b58\u8def\u5f84",
                "welfare_title": "\u798f\u5229",
                "btn_welfare_first_credits": "\u9996\u6b21\u798f\u5229\uff1a+150 \u91d1\u5e01",
                "btn_welfare_first_time": "\u9996\u6b21\u798f\u5229\uff1a+7 \u5929",
                "btn_welfare_weekly_credits": "\u6bcf\u5468\u798f\u5229\uff1a+50 \u91d1\u5e01",
                "btn_welfare_weekly_time": "\u6bcf\u5468\u798f\u5229\uff1a+1 \u5929",
                "btn_welfare_refresh": "\u5237\u65b0\u798f\u5229\u72b6\u6001",
                "welfare_first_label": "\u9996\u6b21\u798f\u5229",
                "welfare_weekly_label": "\u6bcf\u5468\u798f\u5229",
                "welfare_claimed": "\u5df2\u9886\u53d6",
                "welfare_not_claimed": "\u672a\u9886\u53d6",
                "welfare_available": "\u53ef\u9886\u53d6",
                "welfare_cooldown_fmt": "\u51b7\u5374\uff1a{d}\u5929 {h}\u5c0f\u65f6 {m}\u5206\u949f",
                "welfare_need_first": "\u8bf7\u5148\u9886\u53d6\u9996\u6b21\u798f\u5229",
                "msg_welfare_title": "\u798f\u5229",
                "msg_welfare_claimed_ok": "\u9886\u53d6\u6210\u529f\u3002",
                "msg_welfare_claimed_fail": "\u9996\u6b21\u798f\u5229\u5df2\u9886\u53d6\u6216\u6761\u4ef6\u4e0d\u6ee1\u8db3\u3002",
                "msg_welfare_weekly_ok": "\u6bcf\u5468\u798f\u5229\u9886\u53d6\u6210\u529f\u3002",
                "msg_welfare_weekly_wait": "\u5f53\u524d\u4e0d\u53ef\u9886\u53d6\uff0c\u8bf7\u7b49\u5f85\u51b7\u5374\u3002",
                "menu_file": "\u6587\u4ef6",
                "act_save_current": "\u4fdd\u5b58\u5f53\u524d\u7ffb\u8bd1",
                "act_export_history": "\u5bfc\u51fa\u5386\u53f2 JSON",
                "act_set_save_path": "\u8bbe\u7f6e\u4fdd\u5b58\u8def\u5f84",
                "act_exit": "\u9000\u51fa",
                "menu_translate": "\u7ffb\u8bd1",
                "act_translate": "\u7ffb\u8bd1",
                "act_smart_translate": "\u667a\u80fd\u7ffb\u8bd1",
                "act_web_translate": "\u7f51\u9875\u7ffb\u8bd1",
                "act_clear": "\u6e05\u7a7a",
                "menu_tools": "\u5de5\u5177",
                "act_api_settings": "API \u8bbe\u7f6e",
                "act_test_api": "\u6d4b\u8bd5\u7ffb\u8bd1 API",
                "act_test_lang": "\u6d4b\u8bd5\u8bed\u8a00\u68c0\u6d4b",
                "act_select_manual": "\u624b\u52a8\u9009\u62e9\u65e5\u5fd7",
                "act_test_monitor": "\u6d4b\u8bd5\u76d1\u63a7",
                "act_select_badlion": "\u9009\u62e9 Badlion \u65e5\u5fd7",
                "act_select_lunar": "\u9009\u62e9 Lunar \u65e5\u5fd7",
                "act_view_log_format": "\u67e5\u770b\u65e5\u5fd7\u683c\u5f0f",
                "act_stats": "\u7edf\u8ba1\u9762\u677f",
                "menu_settings": "\u8bbe\u7f6e",
                "act_hide_all": "\u9690\u85cf\u5168\u90e8\u6d88\u606f",
                "act_keep_system": "\u4fdd\u7559\u7cfb\u7edf\u6d88\u606f",
                "act_keep_rewards": "\u4fdd\u7559\u5956\u52b1\u6d88\u606f",
                "act_no_names": "\u4e0d\u7ffb\u8bd1\u4eba\u540d",
                "menu_help": "\u5e2e\u52a9",
                "act_usage": "\u4f7f\u7528\u8bf4\u660e",
                "act_sponsor": "\u8d5e\u52a9",
                "act_about": "\u5173\u4e8e",
                "license_label_fmt": "\u6388\u6743\uff1a{status} | \u91d1\u5e01\uff1a{credits:.1f} | \u65f6\u957f\uff1a{days}\u5929 {hours}\u5c0f\u65f6{paused}",
                "license_status_activated": "\u5df2\u6fc0\u6d3b",
                "license_status_not_activated": "\u672a\u6fc0\u6d3b",
                "license_status_developer": "\u5f00\u53d1\u8005(\u6c38\u4e45)",
                "paused_suffix": " | \u5df2\u6682\u505c",
                "msg_restore_title": "\u6062\u590d\u9ed8\u8ba4",
                "msg_restore_confirm": "\u5c06\u672c\u5730\u8bbe\u7f6e/\u6388\u6743/\u798f\u5229\u6062\u590d\u9ed8\u8ba4\uff0c\u5e76\u6e05\u7a7a\u670d\u52a1\u5668\u6388\u6743\u6570\u636e\uff1f\n\n\u5feb\u6377\u952e\uff1aCtrl+Alt+Shift+F12",
                "msg_restore_server_ok": "\u5df2\u6062\u590d\u9ed8\u8ba4\uff0c\u5e76\u6e05\u7a7a\u670d\u52a1\u5668\u6388\u6743\u3002",
                "msg_restore_server_failed": "\u672c\u5730\u5df2\u6062\u590d\u9ed8\u8ba4\uff0c\u4f46\u670d\u52a1\u5668\u6e05\u7a7a\u5931\u8d25\uff1a\n{err}",
                "status_restoring": "\u6b63\u5728\u6062\u590d\u9ed8\u8ba4\u914d\u7f6e...",
                "status_restore_done_local": "\u5df2\u6062\u590d\u672c\u5730\u9ed8\u8ba4\u914d\u7f6e",
                "status_restore_done_server": "\u5df2\u6062\u590d\u9ed8\u8ba4\u5e76\u6e05\u7a7a\u670d\u52a1\u5668\u6388\u6743",
                "status_restore_server_failed": "\u670d\u52a1\u5668\u6e05\u7a7a\u5931\u8d25",
                "notice_title": "\u63d0\u793a",
                "sync_title": "\u540c\u6b65",
                "sync_need_activate": "\u8bf7\u5148\u6fc0\u6d3b\u5361\u5bc6\u3002",
                "sync_skipped_no_token": "\u5df2\u8df3\u8fc7\u540c\u6b65\uff1a\u65e0\u4f1a\u8bdd\u4ee4\u724c",
                "sync_running": "\u540c\u6b65\u4e2d...",
                "sync_success": "\u540c\u6b65\u6210\u529f",
                "sync_failed_title": "\u540c\u6b65\u5931\u8d25",
                "sync_fatal_title": "\u540c\u6b65\u4e25\u91cd\u9519\u8bef",
                "startup_sync_done": "\u542f\u52a8\u540c\u6b65\u5b8c\u6210",
                "startup_sync_failed_title": "\u542f\u52a8\u540c\u6b65\u5931\u8d25",
                "startup_sync_failed_fmt": "\u542f\u52a8\u540c\u6b65\u5931\u8d25\uff1a{err}",
                "startup_sync_failed_cleared_fmt": "\u542f\u52a8\u540c\u6b65\u5931\u8d25\uff0c\u5df2\u6e05\u7a7a\u672c\u5730\u6388\u6743\uff1a{err}",
                "startup_sync_handler_failed_fmt": "\u542f\u52a8\u540c\u6b65\u5904\u7406\u51fa\u9519\uff1a{err}",
                "startup_sync_handler_alert_fmt": "\u540c\u6b65\u9519\u8bef\uff1a{sync_err}\\n\u5904\u7406\u9519\u8bef\uff1a{handler_err}",
                "startup_sync_fatal_fmt": "\u542f\u52a8\u540c\u6b65\u4e25\u91cd\u9519\u8bef\uff1a{err}",
                "sync_err_session_expired": "\u4f1a\u8bdd\u5df2\u8fc7\u671f\uff0c\u8bf7\u91cd\u65b0\u6fc0\u6d3b\u3002",
                "sync_err_unauthorized": "\u672a\u6388\u6743\uff0c\u8bf7\u68c0\u67e5\u5bc6\u94a5\u6216\u91cd\u65b0\u6fc0\u6d3b\u3002",
                "sync_err_forbidden": "\u670d\u52a1\u5668\u62d2\u7edd\u8bf7\u6c42\u3002",
                "sync_err_unknown": "\u672a\u77e5\u540c\u6b65\u9519\u8bef",
                "history_detail_title": "\u5386\u53f2\u8be6\u60c5",
                "msg_pause_not_needed": "\u6c38\u4e45\u6388\u6743\u65e0\u9700\u6682\u505c\u3002",
                "msg_pause_no_time": "\u5269\u4f59\u65f6\u957f\u4e0d\u8db3\u3002",
                "msg_pause_ok": "\u5df2\u6682\u505c\u3002",
                "msg_pause_fail": "\u6682\u505c\u5931\u8d25\u3002",
                "msg_resume_ok": "\u5df2\u6062\u590d\u3002",
                "msg_resume_fail": "\u6062\u590d\u5931\u8d25\u3002",
                "status_insufficient_entitlement": "\u6388\u6743\u4e0d\u8db3\uff0c\u5df2\u8df3\u8fc7\u81ea\u52a8\u7ffb\u8bd1\u3002",
                "status_translation_failed_fmt": "\u7ffb\u8bd1\u5931\u8d25\uff1a{err}",
                "status_translation_done": "\u7ffb\u8bd1\u5b8c\u6210\u3002",
                "status_smart_translating": "\u667a\u80fd\u7ffb\u8bd1\u4e2d...",
                "status_translating": "\u7ffb\u8bd1\u4e2d...",
                "msg_enter_text_first": "\u8bf7\u5148\u8f93\u5165\u9700\u8981\u7ffb\u8bd1\u7684\u6587\u672c\u3002",
                "status_copied": "\u5df2\u590d\u5236\u7ed3\u679c\u3002",
                "msg_no_content_save": "\u6ca1\u6709\u53ef\u4fdd\u5b58\u5185\u5bb9\u3002",
                "status_saved_ok": "\u4fdd\u5b58\u6210\u529f\u3002",
                "detail_analysis_title": "\u8be6\u7ec6\u5206\u6790",
                "detail_analysis_fmt": "\u68c0\u6d4b\u8bed\u8a00\uff1a{lang}\n\u6587\u672c\u957f\u5ea6\uff1a{length}",
                "lang_detect_title": "\u8bed\u8a00\u68c0\u6d4b",
                "lang_detect_fmt": "\u68c0\u6d4b\u7ed3\u679c\uff1a{lang}",
                "api_ok": "\u6b63\u5e38",
                "api_failed": "\u5931\u8d25",
                "api_test_result_fmt": "Google\uff1a{g}\nBaidu\uff1a{b}",
                "from_to_label": "\u6e90/\u76ee\u6807",
                "status_web_opened": "\u5df2\u6253\u5f00\u7f51\u9875\u7ffb\u8bd1\u3002",
                "status_save_path_set_fmt": "\u4fdd\u5b58\u8def\u5f84\u5df2\u8bbe\u7f6e\uff1a{path}",
                "dialog_select_save_folder": "\u9009\u62e9\u4fdd\u5b58\u76ee\u5f55",
                "dialog_export_history": "\u5bfc\u51fa\u5386\u53f2",
                "dialog_select_log_file": "\u9009\u62e9\u65e5\u5fd7\u6587\u4ef6",
                "dialog_select_badlion_file": "\u9009\u62e9 Badlion \u65e5\u5fd7\u6587\u4ef6",
                "dialog_select_lunar_file": "\u9009\u62e9 Lunar \u65e5\u5fd7\u6587\u4ef6",
                "save_record_title": "\u4fdd\u5b58\u7ffb\u8bd1\u8bb0\u5f55",
                "save_record_header": "Minecraft \u7ffb\u8bd1\u8bb0\u5f55",
                "save_record_time_prefix": "\u65f6\u95f4",
                "save_record_engine_prefix": "\u5f15\u64ce",
                "save_record_target_prefix": "\u76ee\u6807\u8bed\u8a00",
                "save_record_original_prefix": "\u539f\u6587",
                "save_record_translated_prefix": "\u8bd1\u6587",
                "save_success_title": "\u6210\u529f",
                "save_success_fmt": "\u5df2\u4fdd\u5b58\u5230\uff1a\n{path}",
                "status_saved_file_fmt": "\u5df2\u4fdd\u5b58\uff1a{name}",
                "save_error_title": "\u9519\u8bef",
                "save_error_fmt": "\u4fdd\u5b58\u5931\u8d25\uff1a{err}",
                "export_none": "\u6ca1\u6709\u5386\u53f2\u53ef\u5bfc\u51fa\u3002",
                "status_history_exported": "\u5386\u53f2\u5df2\u5bfc\u51fa\u3002",
                "export_error_fmt": "\u5bfc\u51fa\u5931\u8d25\uff1a{err}",
                "status_badlion_selected_fmt": "\u5df2\u9009\u62e9 Badlion \u65e5\u5fd7\u6587\u4ef6\uff1a{name}",
                "status_lunar_selected_fmt": "\u5df2\u9009\u62e9 Lunar \u65e5\u5fd7\u6587\u4ef6\uff1a{name}",
                "status_manual_selected_fmt": "\u5df2\u9009\u62e9\u65e5\u5fd7\u6587\u4ef6\uff1a{name}",
                "msg_log_not_found": "\u672a\u627e\u5230 Minecraft \u65e5\u5fd7\u6587\u4ef6\u3002",
                "monitor_test_title": "\u76d1\u63a7\u6d4b\u8bd5",
                "monitor_test_fmt": "\u65e5\u5fd7\u6587\u4ef6\uff1a{log}\n\u603b\u884c\u6570\uff1a{total}\n\u4fdd\u7559\uff1a{kept}/{max_lines}\n\u8fc7\u6ee4\u7387\uff1a{rate:.1f}%",
                "log_format_title": "\u65e5\u5fd7\u683c\u5f0f\u5206\u6790",
                "log_format_tab_raw": "\u539f\u59cb\u65e5\u5fd7",
                "log_format_tab_filter": "\u8fc7\u6ee4\u7ed3\u679c",
                "log_format_tab_lang": "\u8bed\u8a00\u68c0\u6d4b",
                "log_format_filter_report": "\u8fc7\u6ee4\u5206\u6790\u62a5\u544a",
                "log_format_lang_report": "\u8bed\u8a00\u68c0\u6d4b\u62a5\u544a",
                "log_format_kept": "\u4fdd\u7559",
                "log_format_filtered": "\u8fc7\u6ee4",
                "log_format_filter_stats_fmt": "\u8fc7\u6ee4\u7edf\u8ba1\uff1a\u4fdd\u7559 {kept}/{total} ({rate:.1f}%)",
                "stats_title": "\u7ffb\u8bd1\u7edf\u8ba1",
                "stats_summary_fmt": "\u603b\u6570\uff1a{total}\n\u6210\u529f\uff1a{success}\n\u5931\u8d25\uff1a{fail}\n\u7f13\u5b58\u547d\u4e2d\uff1a{cache_hit}\n\u5e73\u5747\u8017\u65f6\uff1a{avg_ms:.1f}ms",
                "stats_engine_header": "\u5f15\u64ce\u7edf\u8ba1",
                "stats_engine_line_fmt": "{engine}: \u603b\u6570={total}, \u6210\u529f={success}, \u5931\u8d25={fail}, \u7f13\u5b58={cache}, \u5e73\u5747\u8017\u65f6={avg_ms:.1f}ms",
                "about_title": "\u5173\u4e8e",
                "about_app_name": "Minecraft \u667a\u80fd\u7ffb\u8bd1\u5de5\u5177",
                "about_arch": "\u67b6\u6784\uff1aPyQt6 + \u76d1\u63a7\u7ebf\u7a0b + \u5f02\u6b65\u7ffb\u8bd1\u961f\u5217",
                "about_license": "\u6388\u6743\u72b6\u6001",
                "about_credits": "\u91d1\u5e01",
                "about_time": "\u65f6\u957f",
                "about_time_permanent": "\u6c38\u4e45",
                "about_config_file": "\u914d\u7f6e\u6587\u4ef6",
                "about_state_file": "\u6388\u6743\u72b6\u6001\u6587\u4ef6",
                "about_history_file": "\u5386\u53f2\u6587\u4ef6",
                "about_save_folder": "\u4fdd\u5b58\u76ee\u5f55",
            },
        }
    def _normalize_ui_lang(self, value, text: str | None = None) -> str:
        """Normalize UI language robustly from either combo data or display text."""
        v = str(value or "").strip().lower()
        raw_t = str(text or "")
        t = raw_t.strip().lower()
        if v.startswith("zh") or ("chinese" in t) or (t in {"zh", "\u4e2d\u6587", "\u7b80\u4f53\u4e2d\u6587", "\u7b80\u4e2d"}):
            return "zh"
        if v.startswith("en") or ("english" in t) or (t in {"en", "\u82f1\u6587"}):
            return "en"
        if _cjk_count(raw_t) > 0:
            return "zh"
        return "zh"

    def _effective_ui_language(self) -> str:
        lang = self.ui_language
        try:
            if hasattr(self, "ui_lang_combo"):
                lang = self._normalize_ui_lang(
                    self.ui_lang_combo.currentData(),
                    self.ui_lang_combo.currentText(),
                )
        except Exception:
            pass
        return self._normalize_ui_lang(lang)

    def _t(self, key: str) -> str:
        return _pick_text(self._texts(), self._effective_ui_language(), key)

    def on_ui_language_changed(self):
        self.ui_language = self._normalize_ui_lang(
            self.ui_lang_combo.currentData(),
            self.ui_lang_combo.currentText(),
        )
        self.cfg["ui_language"] = self.ui_language
        save_config(self.cfg)
        self._apply_ui_language()

    def _apply_ui_language(self):
        self.setWindowTitle(self._t("window_title"))
        self.btn_home.setText(self._t("btn_home"))
        self.btn_tools.setText(self._t("btn_tools"))
        self.btn_settings.setText(self._t("btn_settings"))
        self.btn_welfare.setText(self._t("btn_welfare"))
        self.btn_theme.setText(self._t("btn_theme"))
        idx = 1 if self.ui_language == "en" else 0
        old = self.ui_lang_combo.blockSignals(True)
        self.ui_lang_combo.setCurrentIndex(idx)
        self.ui_lang_combo.blockSignals(old)
        self.lbl_engine.setText(self._t("lbl_engine"))
        self.lbl_target.setText(self._t("lbl_target"))
        self.cb_auto.setText(self._t("cb_auto"))
        self.cb_detect.setText(self._t("cb_detect"))
        self.cb_filter.setText(self._t("cb_filter"))
        self.monitor_status.setText(self._t("monitor_running") if self.monitor.running else self._t("monitor_stopped"))
        self.btn_toggle.setText(self._t("btn_stop_monitor") if self.monitor.running else self._t("btn_start_monitor"))
        self.btn_test.setText(self._t("btn_test_api"))
        self.lbl_input.setText(self._t("lbl_input"))
        self.input_box.setPlaceholderText(self._t("placeholder_input"))
        self.btn_smart.setText(self._t("btn_smart"))
        self.btn_plain.setText(self._t("btn_translate"))
        self.btn_clear.setText(self._t("btn_clear"))
        self.lbl_live_monitor.setText(self._t("lbl_live_monitor"))
        self.cb_show_all.setText(self._t("cb_show_all"))
        self.lbl_result.setText(self._t("lbl_result"))
        self.lbl_recent_history.setText(self._t("lbl_recent_history"))
        self.btn_copy.setText(self._t("btn_copy"))
        self.btn_save.setText(self._t("btn_save"))
        self.btn_analyze.setText(self._t("btn_analyze"))
        self.btn_hist_view.setText(self._t("btn_view_detail"))
        self.btn_hist_clear.setText(self._t("btn_clear_history"))
        if self.status_label.text() in ("Ready", "就绪"):
            self.status_label.setText(self._t("status_ready"))
        self.btn_overlay.setText(self._t("btn_overlay"))
        self.btn_activate.setText(self._t("btn_activate"))
        self.btn_sync.setText(self._t("btn_sync"))
        self.tools_title.setText(self._t("tools_title"))
        self.btn_select_badlion.setText(self._t("btn_select_badlion"))
        self.btn_select_lunar.setText(self._t("btn_select_lunar"))
        self.btn_select_manual.setText(self._t("btn_select_manual"))
        self.btn_view_format.setText(self._t("btn_view_log_format"))
        self.btn_test_monitor.setText(self._t("btn_test_monitor"))
        self.btn_test_lang.setText(self._t("btn_test_lang"))
        self.btn_web_translate.setText(self._t("btn_web_translate"))
        self.settings_title.setText(self._t("settings_title"))
        self.btn_api.setText(self._t("btn_api"))
        self.btn_save_path.setText(self._t("btn_save_path"))
        self.btn_toggle_theme.setText(self._t("btn_theme"))
        self.welfare_title.setText(self._t("welfare_title"))
        self.btn_welfare_first_credits.setText(self._t("btn_welfare_first_credits"))
        self.btn_welfare_first_time.setText(self._t("btn_welfare_first_time"))
        self.btn_welfare_weekly_credits.setText(self._t("btn_welfare_weekly_credits"))
        self.btn_welfare_weekly_time.setText(self._t("btn_welfare_weekly_time"))
        self.btn_welfare_refresh.setText(self._t("btn_welfare_refresh"))
        # Keep welfare text in sync with active UI language.
        self._refresh_welfare_page()
        self.menu_file.setTitle(self._t("menu_file"))
        self.act_save_current.setText(self._t("act_save_current"))
        self.act_export_history.setText(self._t("act_export_history"))
        self.act_set_save_path.setText(self._t("act_set_save_path"))
        self.act_exit.setText(self._t("act_exit"))
        self.menu_translate.setTitle(self._t("menu_translate"))
        self.act_translate.setText(self._t("act_translate"))
        self.act_smart_translate.setText(self._t("act_smart_translate"))
        self.act_web_translate.setText(self._t("act_web_translate"))
        self.act_clear.setText(self._t("act_clear"))
        self.menu_tools.setTitle(self._t("menu_tools"))
        self.act_api_settings.setText(self._t("act_api_settings"))
        self.act_test_api.setText(self._t("act_test_api"))
        self.act_test_lang.setText(self._t("act_test_lang"))
        self.act_select_manual.setText(self._t("act_select_manual"))
        self.act_test_monitor.setText(self._t("act_test_monitor"))
        self.act_select_badlion.setText(self._t("act_select_badlion"))
        self.act_select_lunar.setText(self._t("act_select_lunar"))
        self.act_view_log_format.setText(self._t("act_view_log_format"))
        self.act_stats.setText(self._t("act_stats"))
        self.menu_settings.setTitle(self._t("menu_settings"))
        self.act_hide_all.setText(self._t("act_hide_all"))
        self.act_keep_system.setText(self._t("act_keep_system"))
        self.act_keep_rewards.setText(self._t("act_keep_rewards"))
        self.act_no_names.setText(self._t("act_no_names"))
        self.menu_help.setTitle(self._t("menu_help"))
        self.act_usage.setText(self._t("act_usage"))
        self.act_sponsor.setText(self._t("act_sponsor"))
        self.act_about.setText(self._t("act_about"))
        if self._loading_count > 0:
            self._tick_loading()
        if self.overlay is not None:
            self.overlay.set_ui_language(self.ui_language)
        self.refresh_license_status()


    def _apply_dark_theme(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #0f172a; color: #e5e7eb; font-family: 'PingFang SC', 'Microsoft YaHei', 'Segoe UI'; }
            QFrame#Sidebar { background: #111827; border-radius: 14px; }
            QFrame { border-radius: 12px; }
            QPushButton {
                background: #1f2937;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 8px 12px;
                color: #e5e7eb;
            }
            QPushButton:hover { background: #273449; }
            QPushButton:pressed { background: #111827; }
            QLineEdit, QTextEdit, QListWidget, QComboBox {
                background: #0b1220;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 6px;
                color: #e5e7eb;
            }
            QCheckBox { spacing: 8px; }
            QLabel { color: #d1d5db; }
            QMenuBar, QMenu { background: #111827; color: #e5e7eb; }
            """
        )
        self._theme_dark = True

    def _apply_light_theme(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f2f5f9; color: #0f172a; font-family: 'PingFang SC', 'Microsoft YaHei', 'Segoe UI'; }
            QFrame#Sidebar { background: #e8edf5; border-radius: 14px; }
            QFrame { border-radius: 12px; }
            QPushButton {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 12px;
                padding: 8px 12px;
                color: #0f172a;
            }
            QPushButton:hover { background: #f1f5f9; }
            QPushButton:pressed { background: #e2e8f0; }
            QLineEdit, QTextEdit, QListWidget, QComboBox {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 12px;
                padding: 6px;
                color: #0f172a;
            }
            QCheckBox { spacing: 8px; }
            QLabel { color: #0f172a; }
            QMenuBar, QMenu { background: #ffffff; color: #0f172a; }
            """
        )
        self._theme_dark = False

    def toggle_theme(self):
        if self._theme_dark:
            self._apply_light_theme()
        else:
            self._apply_dark_theme()

    def _on_cfg_changed(self):
        self.cfg["translation_engine"] = self.engine.currentText()
        self.cfg["language"] = self.lang.currentText()
        self.cfg["auto_translate"] = self.cb_auto.isChecked()
        self.cfg["auto_detect"] = self.cb_detect.isChecked()
        save_config(self.cfg)

    def _on_filter_changed(self):
        enabled = self.cb_filter.isChecked()
        self.cfg["filter_messages"] = enabled
        self.filter.set_options(enabled=enabled)
        save_config(self.cfg)

    def _on_show_all_logs(self):
        self.show_all_logs = bool(self.cb_show_all.isChecked())
        self.cfg["show_all_logs"] = self.show_all_logs
        save_config(self.cfg)

    def toggle_hide_all(self):
        self.hide_all_messages = bool(self.act_hide_all.isChecked())
        self.cfg["hide_all_messages"] = self.hide_all_messages
        save_config(self.cfg)

    def toggle_keep_system(self):
        val = bool(self.act_keep_system.isChecked())
        self.cfg["filter_keep_system"] = val
        self.filter.set_options(keep_system=val)
        save_config(self.cfg)

    def toggle_keep_rewards(self):
        val = bool(self.act_keep_rewards.isChecked())
        self.cfg["filter_keep_rewards"] = val
        self.filter.set_options(keep_rewards=val)
        save_config(self.cfg)

    def toggle_no_translate_names(self):
        self.no_translate_names = bool(self.act_no_names.isChecked())
        self.cfg["no_translate_names"] = self.no_translate_names
        save_config(self.cfg)

    def _set_checked_silent(self, widget, value: bool) -> None:
        old = widget.blockSignals(True)
        widget.setChecked(bool(value))
        widget.blockSignals(old)

    def _set_current_text_silent(self, widget, value: str) -> None:
        old = widget.blockSignals(True)
        idx = widget.findText(value)
        if idx >= 0:
            widget.setCurrentIndex(idx)
        widget.blockSignals(old)

    def _apply_runtime_config(self) -> None:
        # Apply config to controls without triggering change events repeatedly.
        self._set_current_text_silent(self.engine, self.cfg.get("translation_engine", "baidu"))
        self._set_current_text_silent(self.lang, self.cfg.get("language", "zh-CN"))
        self._set_checked_silent(self.cb_auto, self.cfg.get("auto_translate", True))
        self._set_checked_silent(self.cb_detect, self.cfg.get("auto_detect", True))
        self._set_checked_silent(self.cb_filter, self.cfg.get("filter_messages", True))
        self._set_checked_silent(self.cb_show_all, self.cfg.get("show_all_logs", False))

        self.show_all_logs = bool(self.cfg.get("show_all_logs", False))
        self.hide_all_messages = bool(self.cfg.get("hide_all_messages", False))
        self.no_translate_names = bool(self.cfg.get("no_translate_names", True))

        self.filter.set_options(
            enabled=bool(self.cfg.get("filter_messages", True)),
            keep_system=bool(self.cfg.get("filter_keep_system", False)),
            keep_rewards=bool(self.cfg.get("filter_keep_rewards", False)),
        )

        self._set_checked_silent(self.act_hide_all, self.hide_all_messages)
        self._set_checked_silent(self.act_keep_system, self.cfg.get("filter_keep_system", False))
        self._set_checked_silent(self.act_keep_rewards, self.cfg.get("filter_keep_rewards", False))
        self._set_checked_silent(self.act_no_names, self.no_translate_names)

        if self.cfg.get("baidu_app_id") and self.cfg.get("baidu_secret_key"):
            self.baidu = BaiduTranslator(self.cfg["baidu_app_id"], self.cfg["baidu_secret_key"])
        else:
            self.baidu = None

        # Clear manual file override when restoring defaults.
        self.monitor.log_file = None

    def restore_defaults_and_revoke_server(self):
        confirm = QMessageBox.question(
            self,
            self._t("msg_restore_title"),
            self._t("msg_restore_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        current_state = load_state()
        token = str(current_state.get("session_token", "") or "")
        machine_code = get_machine_code()

        self.status_label.setText(self._t("status_restoring"))

        # 1) Local restore (config + entitlement + welfare)
        try:
            defaults = _default_config()
            defaults["ui_language"] = self.ui_language
            self.cfg = defaults
            save_config(self.cfg)
            reset_fn = getattr(license_state, "reset_all", None)
            if callable(reset_fn):
                reset_fn()
            else:
                self._clear_local_entitlement_safe()
            self._apply_runtime_config()
            self._refresh_welfare_page()
            self.refresh_license_status()
            self.status_label.setText(self._t("status_restore_done_local"))
        except Exception as e:
            QMessageBox.critical(self, self._t("msg_restore_title"), str(e))
            return

        # 2) Server-side clear (async; local reset already done)
        def _job():
            try:
                # Try with current session first; if session is invalid/expired,
                # retry without session token (server allows machine-code based clear).
                try:
                    revoke_with_server(token, machine_code)
                except Exception as first_err:
                    msg = str(first_err).lower()
                    if ("session" in msg) or ("unauthorized" in msg) or ("invalid" in msg) or ("expired" in msg):
                        revoke_with_server("", machine_code)
                    else:
                        raise
                self.pending_ui.put(("status", self._t("status_restore_done_server")))
                self.pending_ui.put(("alert", (self._t("msg_restore_title"), self._t("msg_restore_server_ok"))))
            except Exception as e:
                self.pending_ui.put(("status", f"{self._t('status_restore_server_failed')}: {e}"))
                self.pending_ui.put(
                    (
                        "alert",
                        (
                            self._t("msg_restore_title"),
                            self._t("msg_restore_server_failed").format(err=str(e)),
                        ),
                    )
                )
            self.pending_ui.put(("refresh_license", None))

        threading.Thread(target=_job, daemon=True).start()

    def _nav_home(self):
        self._switch_page(0)
        self.input_box.setFocus()
        self.status_label.setText(self._t("status_home"))

    def _nav_tools(self):
        self._switch_page(1)

    def _nav_settings(self):
        self._switch_page(2)

    def _nav_welfare(self):
        self._switch_page(3)
        self._refresh_welfare_page()

    def _switch_page(self, index: int):
        if self.pages.currentIndex() == index:
            return
        self.pages.setCurrentIndex(index)
        self._animate_current_page()

    def _animate_current_page(self):
        page = self.pages.currentWidget()
        if page is None:
            return
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(320)
        anim.setStartValue(0.15)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        end_rect = page.geometry()
        start_rect = QRect(end_rect.x() + 18, end_rect.y(), end_rect.width(), end_rect.height())
        page.setGeometry(start_rect)
        slide = QPropertyAnimation(page, b"geometry", self)
        slide.setDuration(320)
        slide.setStartValue(start_rect)
        slide.setEndValue(end_rect)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _cleanup():
            try:
                page.setGraphicsEffect(None)
            except Exception:
                pass

        anim.finished.connect(_cleanup)
        self._page_anim = anim
        self._page_slide_anim = slide
        anim.start()
        slide.start()

    def _start_loading(self, text: str = ""):
        self._loading_count += 1
        if text:
            self._loading_text = text
        if self._loading_count == 1:
            self._loading_phase = 0
            self.loading_label.show()
            self.loading_bar.show()
            self.loading_timer.start()
            self._tick_loading()

    def _stop_loading(self):
        self._loading_count = max(0, self._loading_count - 1)
        if self._loading_count == 0:
            self.loading_timer.stop()
            self.loading_label.hide()
            self.loading_bar.hide()
            self.loading_label.setText("")
            self._loading_text = ""

    def _tick_loading(self):
        base = self._loading_text or self._t("loading")
        dots = "." * ((self._loading_phase % 3) + 1)
        self._loading_phase += 1
        self.loading_label.setText(f"{base}{dots}")

    def _refresh_welfare_page(self):
        self.ui_language = self._effective_ui_language()
        claimed = has_claimed_welfare()
        can_weekly, wait = can_claim_weekly_welfare()
        if claimed:
            if can_weekly:
                weekly_text = self._t("welfare_available")
            else:
                d = wait // 86400
                h = (wait % 86400) // 3600
                m = (wait % 3600) // 60
                weekly_text = self._t("welfare_cooldown_fmt").format(d=d, h=h, m=m)
            first_text = self._t("welfare_claimed")
        else:
            first_text = self._t("welfare_not_claimed")
            weekly_text = self._t("welfare_need_first")
        self.welfare_info.setText(
            f"{self._t('welfare_first_label')}: {first_text}\n"
            f"{self._t('welfare_weekly_label')}: {weekly_text}"
        )

    def _claim_welfare_once(self, choice: str):
        ok = claim_welfare(choice)
        if ok:
            QMessageBox.information(self, self._t("msg_welfare_title"), self._t("msg_welfare_claimed_ok"))
            self.refresh_license_status()
        else:
            QMessageBox.information(self, self._t("msg_welfare_title"), self._t("msg_welfare_claimed_fail"))
        self._refresh_welfare_page()

    def _claim_welfare_weekly(self, choice: str):
        ok = claim_weekly_welfare(choice)
        if ok:
            QMessageBox.information(self, self._t("msg_welfare_title"), self._t("msg_welfare_weekly_ok"))
            self.refresh_license_status()
        else:
            QMessageBox.information(self, self._t("msg_welfare_title"), self._t("msg_welfare_weekly_wait"))
        self._refresh_welfare_page()

    def _open_tools_dialog(self):
        if hasattr(self, "menu_tools"):
            self.menu_tools.exec(QCursor.pos())

    def _open_settings_dialog(self):
        if hasattr(self, "menu_settings"):
            self.menu_settings.exec(QCursor.pos())

    def _append_monitor(self, text: str):
        self.monitor_view.append(text)
        c = self.monitor_view.textCursor()
        c.movePosition(c.MoveOperation.End)
        self.monitor_view.setTextCursor(c)

    def on_log(self, message, msg_type, raw_line=None, keep_for_translation=True):
        ts = time.strftime("%H:%M:%S")
        is_chat = str(msg_type or "").lower() == "chat"
        if not self.hide_all_messages:
            if self.show_all_logs and raw_line:
                display_line = raw_line
                self.pending_ui.put(("monitor", f"[{ts}] {display_line}"))
            elif keep_for_translation and is_chat:
                self.pending_ui.put(("monitor", f"[{ts}] {message}"))

        if keep_for_translation and self.cb_auto.isChecked():
            payload = {"text": message, "player": None, "raw": message}
            if str(msg_type or "").lower() == "chat" and self.no_translate_names:
                try:
                    player, content = self.filter.extract_player_message(message)
                    if player and content:
                        payload = {
                            "text": content,
                            "player": player,
                            "raw": message,
                        }
                except Exception:
                    pass
            try:
                self.auto_q.put_nowait(payload)
            except queue.Full:
                pass

    def _drain_ui_queue(self):
        while True:
            try:
                kind, payload = self.pending_ui.get_nowait()
            except queue.Empty:
                break
            if kind == "monitor":
                self._append_monitor(payload)
            elif kind == "result":
                self.result_box.setPlainText(payload)
            elif kind == "status":
                self.status_label.setText(payload)
            elif kind == "refresh_license":
                self.refresh_license_status()
            elif kind == "overlay":
                if self.overlay is None:
                    self.overlay = OverlayWindow(self._overlay_translate_cb, None, self.ui_language)
                    self.overlay.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
                    self.overlay.setWindowFlag(Qt.WindowType.Tool, True)
                    self.overlay.show()
                if self.overlay:
                    if not self.overlay.isVisible():
                        self.overlay.show()
                        self.overlay.raise_()
                    original, translated = payload
                    self.overlay.append_line(original, translated)
            elif kind == "alert":
                title, msg = payload
                QMessageBox.information(self, title, msg)
            elif kind == "loading_start":
                self._start_loading(str(payload or ""))
            elif kind == "loading_stop":
                self._stop_loading()

    def _auto_worker(self):
        while True:
            item = self.auto_q.get()
            if item is None:
                return
            if isinstance(item, dict):
                text = item.get("text", "")
                player = item.get("player")
                raw = item.get("raw") or text
            else:
                text = str(item)
                player = None
                raw = text
            self._translate_worker(text, smart=True, from_monitor=True, raw=raw, player=player)

    def _translate_with_engine(self, text: str, from_lang: str, to_lang: str):
        engine = self.engine.currentText()
        if engine == "baidu" and self.baidu:
            return self.baidu.translate(text, from_lang, "zh")
        mapped = {
            "zh-CN": "zh-CN",
            "en": "en",
            "ja": "ja",
            "ko": "ko",
            "fr": "fr",
            "de": "de",
            "es": "es",
            "ru": "ru",
        }
        return self.google.translate(text, from_lang, mapped.get(to_lang, "zh-CN"))

    def _stats_record(self, success: bool, duration_ms: float, cache_hit: bool, engine: str):
        self._stats["total"] += 1
        if success:
            self._stats["success"] += 1
        else:
            self._stats["fail"] += 1
        if cache_hit:
            self._stats["cache_hit"] += 1
        self._stats["total_ms"] += float(duration_ms)
        st = self._stats_by_engine.get(engine)
        if not st:
            st = {"total": 0, "success": 0, "fail": 0, "cache_hit": 0, "total_ms": 0.0}
            self._stats_by_engine[engine] = st
        st["total"] += 1
        if success:
            st["success"] += 1
        else:
            st["fail"] += 1
        if cache_hit:
            st["cache_hit"] += 1
        st["total_ms"] += float(duration_ms)

    def _translate_core(self, text: str, smart: bool):
        target = self.lang.currentText()
        engine = self.engine.currentText()
        cache_hit = self.cache.get(text, engine, target)
        if cache_hit:
            return cache_hit, None, True, "auto"

        detected = self.lang_detector.detect(text) if smart and self.cb_detect.isChecked() else Language.UNKNOWN
        from_lang = "auto"
        if smart and detected != Language.UNKNOWN:
            from_lang = detected.value
            simple_target = target.replace("-CN", "")
            if detected.value == simple_target or (detected == Language.CHINESE and simple_target == "zh"):
                return text, None, False, from_lang

        translated, error = self._translate_with_engine(text, from_lang, target)
        if translated and not error:
            self.cache.set(text, engine, target, translated)
        return translated, error, False, from_lang

    def _translate_worker(self, text: str, smart=False, from_monitor=False, raw=None, player=None):
        target = self.lang.currentText()
        key_engine = self.engine.currentText()
        try:
            if from_monitor and not can_consume(0.5):
                self.pending_ui.put(("status", self._t("status_insufficient_entitlement")))
                return

            start_ts = time.time()
            translated, error, cache_hit, from_lang = self._translate_core(text, smart)
            duration_ms = max(0.0, (time.time() - start_ts) * 1000.0)
            self._stats_record(success=(error is None), duration_ms=duration_ms, cache_hit=cache_hit, engine=key_engine)

            if error:
                msg = self._t("status_translation_failed_fmt").format(err=error)
                self.pending_ui.put(("status", msg))
                self.pending_ui.put(("result", msg))
                return

            if from_monitor:
                consume(0.5)
                display_original = raw or text
                display_translated = f"<{player}> {translated}" if player else translated
                self.pending_ui.put(("overlay", (display_original, display_translated)))
            else:
                self.pending_ui.put(("result", translated))

            self._add_history(text, translated, key_engine, from_lang, target)
            self.pending_ui.put(("status", self._t("status_translation_done")))
        finally:
            if not from_monitor:
                self.pending_ui.put(("loading_stop", None))

    def smart_translate(self):
        text = self.input_box.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, self._t("notice_title"), self._t("msg_enter_text_first"))
            return
        self.pending_ui.put(("status", self._t("status_smart_translating")))
        self._start_loading(self._t("loading_translating"))
        threading.Thread(target=self._translate_worker, args=(text, True, False), daemon=True).start()

    def translate_text(self):
        text = self.input_box.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, self._t("notice_title"), self._t("msg_enter_text_first"))
            return
        self.pending_ui.put(("status", self._t("status_translating")))
        self._start_loading(self._t("loading_translating"))
        threading.Thread(target=self._translate_worker, args=(text, False, False), daemon=True).start()

    def test_api(self):
        txt = "Hello World"
        self._start_loading(self._t("loading_testing"))
        def run_test():
            try:
                r1, e1 = self.google.translate(txt, "auto", "zh-CN")
                ok1 = (e1 is None and bool(r1))
                ok2 = False
                if self.baidu:
                    r2, e2 = self.baidu.translate(txt, "auto", "zh")
                    ok2 = (e2 is None and bool(r2))
                msg = self._t("api_test_result_fmt").format(
                    g=self._t("api_ok") if ok1 else self._t("api_failed"),
                    b=self._t("api_ok") if ok2 else self._t("api_failed"),
                )
                self.pending_ui.put(("status", msg.replace("\n", " | ")))
                self.pending_ui.put(("result", msg))
            finally:
                self.pending_ui.put(("loading_stop", None))
        threading.Thread(target=run_test, daemon=True).start()

    def toggle_monitor(self):
        if self.monitor.running:
            self.monitor.stop()
            self.monitor_status.setText(self._t("monitor_stopped"))
            self.btn_toggle.setText(self._t("btn_start_monitor"))
            return
        if not self.monitor.log_file and not self.monitor.find_log_file():
            QMessageBox.warning(self, self._t("notice_title"), self._t("msg_log_not_found"))
            return
        self.monitor.start()
        self.monitor_status.setText(self._t("monitor_running"))
        self.btn_toggle.setText(self._t("btn_stop_monitor"))

    def clear_all(self):
        self.input_box.clear()
        self.result_box.clear()
        self.monitor_view.clear()

    def copy_result(self):
        QApplication.clipboard().setText(self.result_box.toPlainText())
        self.status_label.setText(self._t("status_copied"))

    def save_result(self):
        text = self.result_box.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, self._t("notice_title"), self._t("msg_no_content_save"))
            return
        save_dir = Path(self.cfg.get("save_path", str(Path.home() / "MinecraftTranslations")))
        save_dir.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, self._t("save_record_title"), str(save_dir / "translation.txt"), "Text (*.txt)"
        )
        if not path:
            return
        Path(path).write_text(text, encoding="utf-8")
        self.status_label.setText(self._t("status_saved_ok"))

    def show_analysis(self):
        text = self.input_box.toPlainText().strip()
        if not text:
            return
        lang = self.lang_detector.detect(text)
        QMessageBox.information(
            self,
            self._t("detail_analysis_title"),
            self._t("detail_analysis_fmt").format(lang=lang.value, length=len(text)),
        )

    def test_language_detection(self):
        text = self.input_box.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, self._t("notice_title"), self._t("msg_enter_text_first"))
            return
        lang = self.lang_detector.detect(text)
        QMessageBox.information(self, self._t("lang_detect_title"), self._t("lang_detect_fmt").format(lang=lang.value))

    def test_translation_api(self):
        txt = "Hello World"
        self._start_loading(self._t("loading_testing"))

        def run_test():
            try:
                r1, e1 = self.google.translate(txt, "auto", "zh-CN")
                ok1 = (e1 is None and bool(r1))
                ok2 = False
                if self.baidu:
                    r2, e2 = self.baidu.translate(txt, "auto", "zh")
                    ok2 = (e2 is None and bool(r2))
                msg = self._t("api_test_result_fmt").format(
                    g=self._t("api_ok") if ok1 else self._t("api_failed"),
                    b=self._t("api_ok") if ok2 else self._t("api_failed"),
                )
                self.pending_ui.put(("result", msg))
                self.pending_ui.put(("status", msg.replace("\n", " | ")))
            finally:
                self.pending_ui.put(("loading_stop", None))

        threading.Thread(target=run_test, daemon=True).start()

    def web_translate(self):
        text = self.input_box.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, self._t("notice_title"), self._t("msg_enter_text_first"))
            return
        target_lang = self.lang.currentText()
        encoded = urllib.parse.quote(text)
        url = f"https://translate.google.com/?sl=auto&tl={target_lang}&text={encoded}&op=translate"
        webbrowser.open(url)
        self.status_label.setText(self._t("status_web_opened"))

    def set_save_path(self):
        folder = QFileDialog.getExistingDirectory(self, self._t("dialog_select_save_folder"))
        if folder:
            self.cfg["save_path"] = folder
            save_config(self.cfg)
            self.status_label.setText(self._t("status_save_path_set_fmt").format(path=folder))

    def save_current_translation(self):
        text = self.input_box.toPlainText().strip()
        result = self.result_box.toPlainText().strip()
        if not text and not result:
            QMessageBox.warning(self, self._t("notice_title"), self._t("msg_no_content_save"))
            return
        save_dir = Path(self.cfg.get("save_path", str(Path.home() / "MinecraftTranslations")))
        save_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = save_dir / f"translation_{timestamp}.txt"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"{self._t('save_record_header')}\n")
                f.write(f"{self._t('save_record_time_prefix')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{self._t('save_record_engine_prefix')}: {self.engine.currentText()}\n")
                f.write(f"{self._t('save_record_target_prefix')}: {self.lang.currentText()}\n")
                f.write("=" * 50 + "\n\n")
                if text:
                    f.write(f"{self._t('save_record_original_prefix')}:\n{text}\n\n")
                if result:
                    f.write(f"{self._t('save_record_translated_prefix')}:\n{result}\n\n")
                f.write("=" * 50 + "\n")
            QMessageBox.information(self, self._t("save_success_title"), self._t("save_success_fmt").format(path=filename))
            self.status_label.setText(self._t("status_saved_file_fmt").format(name=filename.name))
        except Exception as e:
            QMessageBox.critical(self, self._t("save_error_title"), self._t("save_error_fmt").format(err=e))

    def export_history(self):
        if not self.history:
            QMessageBox.information(self, self._t("notice_title"), self._t("export_none"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._t("dialog_export_history"),
            "history.json",
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(self.history, ensure_ascii=False, indent=2), encoding="utf-8")
            self.status_label.setText(self._t("status_history_exported"))
        except Exception as e:
            QMessageBox.critical(self, self._t("save_error_title"), self._t("export_error_fmt").format(err=e))

    def manual_select_log(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._t("dialog_select_log_file"),
            "",
            "Log (*.log);;All (*.*)",
        )
        if path:
            self.monitor.log_file = path
            self.cfg["manual_log_file"] = path
            save_config(self.cfg)
            self.status_label.setText(self._t("status_manual_selected_fmt").format(name=Path(path).name))

    def select_badlion_log(self):
        default_dir = Path.home() / "AppData" / "Roaming" / ".minecraft" / "logs" / "blclient" / "minecraft"
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("dialog_select_badlion_file"), str(default_dir), "Log (*.log);;All (*.*)"
        )
        if path:
            self.cfg["badlion_log_file"] = path
            save_config(self.cfg)
            self.monitor.default_paths.insert(0, Path(path))
            self.status_label.setText(self._t("status_badlion_selected_fmt").format(name=Path(path).name))

    def select_lunar_log(self):
        default_dir = Path.home() / ".lunarclient" / "profiles" / "lunar" / "1.8" / "logs"
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("dialog_select_lunar_file"), str(default_dir), "Log (*.log);;All (*.*)"
        )
        if path:
            self.cfg["lunar_log_file"] = path
            save_config(self.cfg)
            self.monitor.default_paths.insert(0, Path(path))
            self.status_label.setText(self._t("status_lunar_selected_fmt").format(name=Path(path).name))

    def _tail_lines(self, file_path: str, max_lines: int = 50):
        try:
            with open(file_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                end = f.tell()
                size = min(8192, end)
                f.seek(-size, os.SEEK_END)
                data = f.read().decode("utf-8", errors="ignore")
            lines = data.splitlines()
            return lines[-max_lines:] if max_lines else lines
        except Exception:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.readlines()[-max_lines:]
            except Exception:
                return []

    def test_monitor(self):
        if not self.monitor.find_log_file():
            QMessageBox.warning(self, self._t("notice_title"), self._t("msg_log_not_found"))
            return
        lines = self._tail_lines(self.monitor.log_file, max_lines=50)
        kept = 0
        for line in lines:
            if self.filter.should_keep(line):
                kept += 1
        QMessageBox.information(
            self,
            self._t("monitor_test_title"),
            self._t("monitor_test_fmt").format(
                log=self.monitor.log_file,
                total=len(lines),
                kept=kept,
                max_lines=50,
                rate=(1 - kept / 50) * 100,
            ),
        )

    def view_log_format(self):
        if not self.monitor.find_log_file():
            QMessageBox.warning(self, self._t("notice_title"), self._t("msg_log_not_found"))
            return
        lines = self._tail_lines(self.monitor.log_file, max_lines=50)

        dlg = QDialog(self)
        dlg.setWindowTitle(self._t("log_format_title"))
        dlg.resize(900, 600)
        layout = QVBoxLayout(dlg)
        tabs = QTabWidget(dlg)
        layout.addWidget(tabs)

        raw = QTextEdit()
        raw.setReadOnly(True)
        raw.setPlainText("\n".join(lines))
        tabs.addTab(raw, self._t("log_format_tab_raw"))

        filt = QTextEdit()
        filt.setReadOnly(True)
        kept = 0
        total = len(lines)
        parts = [self._t("log_format_filter_report"), "=" * 60, ""]
        for line in lines:
            if self.filter.should_keep(line):
                kept += 1
                parts.append(f"{self._t('log_format_kept')}: {line.strip()}")
            else:
                parts.append(f"{self._t('log_format_filtered')}: {line.strip()}")
        if total:
            parts.append("")
            parts.append(
                self._t("log_format_filter_stats_fmt").format(
                    kept=kept,
                    total=total,
                    rate=kept / total * 100,
                )
            )
        filt.setPlainText("\n".join(parts))
        tabs.addTab(filt, self._t("log_format_tab_filter"))

        lang_tab = QTextEdit()
        lang_tab.setReadOnly(True)
        lang_parts = [self._t("log_format_lang_report"), "=" * 60, ""]
        for line in lines:
            clean = self.filter.clean_message(line.strip())
            if not clean:
                continue
            lang = self.lang_detector.detect(clean)
            lang_parts.append(f"[{lang.value}] {clean}")
        lang_tab.setPlainText("\n".join(lang_parts))
        tabs.addTab(lang_tab, self._t("log_format_tab_lang"))

        dlg.exec()

    def show_stats_panel(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(self._t("stats_title"))
        dlg.resize(520, 320)
        lay = QVBoxLayout(dlg)
        total = self._stats["total"] or 0
        avg_ms = (self._stats["total_ms"] / total) if total else 0.0
        top = QLabel(
            self._t("stats_summary_fmt").format(
                total=total,
                success=self._stats["success"],
                fail=self._stats["fail"],
                cache_hit=self._stats["cache_hit"],
                avg_ms=avg_ms,
            )
        )
        lay.addWidget(top)
        per = QTextEdit()
        per.setReadOnly(True)
        lines = [self._t("stats_engine_header"), "=" * 40]
        for k, st in self._stats_by_engine.items():
            t = st["total"] or 0
            avg = (st["total_ms"] / t) if t else 0.0
            lines.append(
                self._t("stats_engine_line_fmt").format(
                    engine=k,
                    total=t,
                    success=st["success"],
                    fail=st["fail"],
                    cache=st["cache_hit"],
                    avg_ms=avg,
                )
            )
        per.setPlainText("\n".join(lines))
        lay.addWidget(per)
        dlg.exec()

    def show_help(self):
        text = (
            "1. 先选择日志文件或直接启动监控。\n"
            "2. 选择翻译引擎和目标语言。\n"
            "3. 可使用智能翻译或普通翻译。"
        ) if self.ui_language == "zh" else (
            "1. Select a log file or start monitor.\n"
            "2. Select translation engine and target language.\n"
            "3. Use auto translation or manual translation."
        )
        QMessageBox.information(self, self._t("menu_help"), text)

    def show_sponsor(self):
        text = "赞助信息请联系作者。" if self.ui_language == "zh" else "For sponsor info, please contact the author."
        QMessageBox.information(self, self._t("act_sponsor"), text)

    def show_about(self):
        version_text = f"build {BUILD_TAG}"
        try:
            vpath = Path.cwd() / "VERSION.txt"
            if vpath.exists():
                lines = [x.strip() for x in vpath.read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()]
                if lines:
                    version_text = " | ".join(lines[:2]).replace("(PyQt6)", "").replace("PyQt6 UI", "").strip(" |")
        except Exception:
            pass

        status, credits, permanent, time_left = get_status()
        days = time_left // 86400
        hours = (time_left % 86400) // 3600
        save_dir = Path(self.cfg.get("save_path", str(Path.home() / "MinecraftTranslations")))
        config_file = _cfg_path()
        lic_state_file = Path.home() / ".mc_translator" / "license_state.json"

        time_text = self._t("about_time_permanent") if permanent else f"{days}d {hours}h"
        msg = (
            f"{self._t('about_app_name')}\n"
            f"{version_text}\n\n"
            f"{self._t('about_license')}: {status}\n"
            f"{self._t('about_credits')}: {credits:.1f}\n"
            f"{self._t('about_time')}: {time_text}\n\n"
            f"{self._t('about_config_file')}: {config_file}\n"
            f"{self._t('about_state_file')}: {lic_state_file}\n"
            f"{self._t('about_history_file')}: {self._history_file()}\n"
            f"{self._t('about_save_folder')}: {save_dir}\n"
        )
        QMessageBox.information(self, self._t("about_title"), msg)

    def _history_file(self) -> Path:
        save_dir = Path(self.cfg.get("save_path", str(Path.home() / "MinecraftTranslations")))
        save_dir.mkdir(parents=True, exist_ok=True)
        return save_dir / "history.json"

    def _add_history(self, original, translated, engine, from_lang, to_lang):
        item = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "engine": engine,
            "from": from_lang,
            "to": to_lang,
            "original": original,
            "translated": translated,
        }
        self.history.insert(0, item)
        self.history = self.history[:200]
        self._refresh_history_list()
        self._save_history()

    def _normalize_history_item(self, it: dict) -> dict:
        if not isinstance(it, dict):
            return {
                "time": "",
                "engine": "",
                "from": "auto",
                "to": self.lang.currentText(),
                "original": "",
                "translated": "",
            }
        time_val = it.get("time") or it.get("ts") or ""
        engine_val = it.get("engine") or it.get("translator") or ""
        from_val = it.get("from") or it.get("from_lang") or it.get("src_lang") or "auto"
        to_val = it.get("to") or it.get("to_lang") or it.get("dst_lang") or self.lang.currentText()
        original_val = it.get("original") or it.get("src") or it.get("text") or ""
        translated_val = it.get("translated") or it.get("dst") or it.get("result") or ""
        return {
            "time": time_val,
            "engine": engine_val,
            "from": from_val,
            "to": to_val,
            "original": original_val,
            "translated": translated_val,
        }

    def _refresh_history_list(self):
        self.history_list.clear()
        for it in self.history:
            it = self._normalize_history_item(it)
            self.history_list.addItem(
                f"[{it['time']}] [{it['from']}->{it['to']}] {str(it['original'])[:42]}"
            )

    def _save_history(self):
        try:
            self._history_file().write_text(json.dumps(self.history, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_history(self):
        f = self._history_file()
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.history = [self._normalize_history_item(x) for x in data[:200]]
            except Exception:
                self.history = []
        self._refresh_history_list()

    def view_history(self):
        row = self.history_list.currentRow()
        if row < 0 or row >= len(self.history):
            return
        it = self._normalize_history_item(self.history[row])
        QMessageBox.information(
            self,
            self._t("history_detail_title"),
            f"{self._t('save_record_time_prefix')}: {it['time']}\n"
            f"{self._t('save_record_engine_prefix')}: {it['engine']}\n"
            f"{self._t('from_to_label')}: {it['from']} -> {it['to']}\n\n"
            f"{self._t('save_record_original_prefix')}:\n{it['original']}\n\n"
            f"{self._t('save_record_translated_prefix')}:\n{it['translated']}",
        )

    def clear_history(self):
        self.history = []
        self._refresh_history_list()
        self._save_history()

    def refresh_license_status(self):
        self.ui_language = self._effective_ui_language()
        status, credits, permanent, time_left = get_status()
        days = time_left // 86400
        hours = (time_left % 86400) // 3600
        paused = self._t("paused_suffix") if is_time_paused() else ""
        status_norm = str(status).strip().lower()
        if status_norm in ("activated", "已激活"):
            status_text = self._t("license_status_activated")
        elif status_norm in ("not activated", "未激活"):
            status_text = self._t("license_status_not_activated")
        elif status_norm in ("developer", "开发者"):
            status_text = self._t("license_status_developer")
        else:
            status_text = str(status)
        self.license_label.setText(
            self._t("license_label_fmt").format(
                status=status_text,
                credits=credits,
                days=days,
                hours=hours,
                paused=paused,
            )
        )
        self.btn_pause.setText(self._t("btn_resume") if is_time_paused() else self._t("btn_pause"))
        self.btn_pause.setEnabled(True)

    def toggle_pause(self):
        status, credits, permanent, time_left = get_status()
        if permanent:
            QMessageBox.information(self, self._t("notice_title"), self._t("msg_pause_not_needed"))
            return
        if time_left <= 0 and not is_time_paused():
            QMessageBox.information(self, self._t("notice_title"), self._t("msg_pause_no_time"))
            return
        if is_time_paused():
            ok = resume_time()
            QMessageBox.information(self, self._t("notice_title"), self._t("msg_resume_ok") if ok else self._t("msg_resume_fail"))
        else:
            ok = pause_time()
            QMessageBox.information(self, self._t("notice_title"), self._t("msg_pause_ok") if ok else self._t("msg_pause_fail"))
        self.refresh_license_status()

    def show_api_settings(self):
        dlg = ApiSettingsDialog(self.cfg, self, self._effective_ui_language())
        if dlg.exec():
            self.cfg.update(dlg.get_values())
            save_config(self.cfg)
            if self.cfg.get("baidu_app_id") and self.cfg.get("baidu_secret_key"):
                self.baidu = BaiduTranslator(self.cfg["baidu_app_id"], self.cfg["baidu_secret_key"])

    def open_activation(self):
        dlg = ActivationDialog(self.cfg, self, self._effective_ui_language())
        dlg.exec()
        save_config(self.cfg)
        self.refresh_license_status()

    def force_sync(self):
        st = load_state()
        token = st.get("session_token", "")
        if not token:
            QMessageBox.information(self, self._t("sync_title"), self._t("sync_need_activate"))
            self.status_label.setText(self._t("sync_skipped_no_token"))
            return
        self.status_label.setText(self._t("sync_running"))
        self._start_loading(self._t("loading_sync"))
        mc = get_machine_code()

        def run_sync():
            try:
                resp = verify_with_server(token, mc)
                set_entitlement(
                    int(resp.get("time_left", 0)),
                    float(resp.get("credits", 0.0)),
                    bool(resp.get("is_permanent", False)),
                    session_token=resp.get("session_token", token),
                )
                self.pending_ui.put(("status", self._t("sync_success")))
                self.pending_ui.put(("alert", (self._t("sync_title"), self._t("sync_success"))))
            except Exception as e:
                try:
                    msg = str(e)
                    if self._should_clear_on_sync_error(msg):
                        self._clear_local_entitlement_safe()
                        pretty = self._format_sync_error(msg)
                        self.pending_ui.put(("status", f"{self._t('sync_failed_title')}, local cleared: {pretty}"))
                        self.pending_ui.put(("alert", (self._t("sync_failed_title"), f"{self._t('sync_failed_title')}, local cleared:\n{pretty}")))
                    else:
                        self.pending_ui.put(("status", f"{self._t('sync_failed_title')}: {msg}"))
                        self.pending_ui.put(("alert", (self._t("sync_failed_title"), f"{self._t('sync_failed_title')}:\n{msg}")))
                except Exception as inner:
                    self.pending_ui.put(("status", f"{self._t('sync_failed_title')}: {inner}"))
                    self.pending_ui.put(("alert", (self._t("sync_failed_title"), f"Sync error: {e}\nHandler error: {inner}")))
            except BaseException as e:  # pragma: no cover
                self.pending_ui.put(("status", f"{self._t('sync_fatal_title')}: {e}"))
                self.pending_ui.put(("alert", (self._t("sync_fatal_title"), str(e))))
            self.pending_ui.put(("refresh_license", None))
            self.pending_ui.put(("loading_stop", None))

        threading.Thread(target=run_sync, daemon=True).start()

    def _register_machine_async(self):
        mc = get_machine_code()
        def _job():
            try:
                register_with_server(mc, client_version="v3-pyqt6")
            except Exception:
                pass
        threading.Thread(target=_job, daemon=True).start()
        self._auto_sync_on_start()

    def _auto_sync_on_start(self):
        st = load_state()
        token = st.get("session_token", "")
        if not token:
            return
        mc = get_machine_code()

        def _job():
            try:
                resp = verify_with_server(token, mc)
                set_entitlement(
                    int(resp.get("time_left", 0)),
                    float(resp.get("credits", 0.0)),
                    bool(resp.get("is_permanent", False)),
                    session_token=resp.get("session_token", token),
                )
                self.pending_ui.put(("status", self._t("startup_sync_done")))
            except Exception as e:
                try:
                    msg = str(e)
                    if self._should_clear_on_sync_error(msg):
                        self._clear_local_entitlement_safe()
                        pretty = self._format_sync_error(msg)
                        self.pending_ui.put(("status", self._t("startup_sync_failed_cleared_fmt").format(err=pretty)))
                        self.pending_ui.put(("alert", (self._t("startup_sync_failed_title"), pretty)))
                    else:
                        self.pending_ui.put(("status", self._t("startup_sync_failed_fmt").format(err=msg)))
                        self.pending_ui.put(("alert", (self._t("startup_sync_failed_title"), msg)))
                except Exception as inner:
                    self.pending_ui.put(("status", self._t("startup_sync_handler_failed_fmt").format(err=inner)))
                    self.pending_ui.put(
                        (
                            "alert",
                            (
                                self._t("startup_sync_failed_title"),
                                self._t("startup_sync_handler_alert_fmt").format(sync_err=e, handler_err=inner),
                            ),
                        )
                    )
            except BaseException as e:  # pragma: no cover
                self.pending_ui.put(("status", self._t("startup_sync_fatal_fmt").format(err=e)))
                self.pending_ui.put(("alert", (self._t("sync_fatal_title"), str(e))))
            self.pending_ui.put(("refresh_license", None))

        threading.Thread(target=_job, daemon=True).start()

    def _should_clear_on_sync_error(self, msg: str) -> bool:
        low = (msg or "").lower()
        keywords = [
            "revoked",
            "invalid",
            "expired",
            "session expired",
            "not found",
            "unauthorized",
            "forbidden",
            "session",
            "token",
        ]
        return any(k in low for k in keywords)

    def _format_sync_error(self, msg: str) -> str:
        low = (msg or "").lower()
        if "session expired" in low:
            return self._t("sync_err_session_expired")
        if "unauthorized" in low:
            return self._t("sync_err_unauthorized")
        if "forbidden" in low:
            return self._t("sync_err_forbidden")
        return msg or self._t("sync_err_unknown")

    def _clear_local_entitlement_safe(self) -> None:
        # Never let cleanup errors break the sync thread.
        try:
            clear_fn = getattr(license_state, "clear_entitlement", None)
            if callable(clear_fn):
                clear_fn()
                return
        except Exception:
            pass

        try:
            st = load_state()
            st["activated"] = False
            st["permanent"] = False
            st["credits"] = 0.0
            st["expires_at"] = 0
            st["session_token"] = ""
            st["time_paused"] = False
            st["paused_remaining"] = 0
            save_state(st)
        except Exception:
            pass

    def toggle_overlay(self):
        if self.overlay is None:
            self.overlay = OverlayWindow(self._overlay_translate_cb, None, self.ui_language)
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.overlay.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.overlay.setWindowFlag(Qt.WindowType.Tool, True)
            self.overlay.show()
            self.overlay.raise_()
            self.overlay.activateWindow()

    def _overlay_translate_cb(self, text: str, target_lang: str):
        try:
            translated, error = self._translate_with_engine(text, "auto", target_lang)
            if error:
                return self._t("status_translation_failed_fmt").format(err=error)
            return translated
        except Exception as e:
            return self._t("status_translation_failed_fmt").format(err=e)

    def play_startup_animation(self):
        if self._startup_anim_done:
            return
        self._startup_anim_done = True

        try:
            end_rect = self.geometry()
            start_rect = QRect(
                end_rect.x(),
                end_rect.y() + 24,
                end_rect.width(),
                end_rect.height(),
            )
            self.setGeometry(start_rect)
            self.setWindowOpacity(0.0)
            self._startup_geo_anim = QPropertyAnimation(self, b"geometry", self)
            self._startup_geo_anim.setDuration(280)
            self._startup_geo_anim.setStartValue(start_rect)
            self._startup_geo_anim.setEndValue(end_rect)
            self._startup_geo_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            self._startup_opacity_anim = QPropertyAnimation(self, b"windowOpacity", self)
            self._startup_opacity_anim.setDuration(280)
            self._startup_opacity_anim.setStartValue(0.0)
            self._startup_opacity_anim.setEndValue(1.0)
            self._startup_opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            self._startup_geo_anim.start()
            self._startup_opacity_anim.start()
        except Exception:
            # Fallback for platforms/drivers that do not support window opacity.
            self.setWindowOpacity(1.0)


class MainApp:
    def __init__(self):
        self.app = QApplication.instance() or QApplication([])
        self.window = None
        self.splash = None
        self._splash_progress_anim = None

    def _build_splash(self):
        splash = QWidget()
        splash.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        splash.setFixedSize(480, 170)
        splash.setStyleSheet(
            """
            QWidget { background: #0b1220; color: #e5e7eb; border: 1px solid #334155; border-radius: 14px; }
            QLabel#Title { font-size: 18px; font-weight: 700; color: #e5e7eb; border: none; }
            QLabel#Desc { font-size: 13px; color: #94a3b8; border: none; }
            QProgressBar {
                border: 1px solid #334155;
                border-radius: 10px;
                background: #111827;
                color: #e5e7eb;
                text-align: center;
                height: 22px;
            }
            QProgressBar::chunk {
                border-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #06b6d4);
            }
            """
        )
        lay = QVBoxLayout(splash)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)

        title = QLabel("Minecraft 智能翻译工具")
        title.setObjectName("Title")
        desc = QLabel("\u6b63\u5728\u542f\u52a8...")
        desc.setObjectName("Desc")
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setFormat("%p%")

        lay.addWidget(title)
        lay.addWidget(desc)
        lay.addWidget(bar)
        lay.addStretch(1)

        splash._desc = desc
        splash._bar = bar
        return splash

    def _set_splash_progress(self, value: int, text: str, duration_ms: int = 220):
        if not self.splash:
            return
        target = max(0, min(100, int(value)))
        self.splash._desc.setText(text)
        try:
            current = int(self.splash._bar.value())
        except Exception:
            current = 0
        if target == current or duration_ms <= 0:
            self.splash._bar.setValue(target)
            self.app.processEvents()
            return

        # Smooth progress transition between startup stages.
        anim = QPropertyAnimation(self.splash._bar, b"value", self.splash)
        anim.setDuration(int(duration_ms))
        anim.setStartValue(current)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._splash_progress_anim = anim
        anim.start()
        self.app.processEvents()

    def _center_widget(self, widget: QWidget):
        screen = self.app.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - widget.width()) // 2
        y = geo.y() + (geo.height() - widget.height()) // 2
        widget.move(x, y)

    def _startup_step_create_window(self):
        self._set_splash_progress(35, "\u6b63\u5728\u521d\u59cb\u5316\u6838\u5fc3\u6a21\u5757...", 320)
        self.window = MainWindow()
        self._set_splash_progress(78, "\u6b63\u5728\u52a0\u8f7d\u754c\u9762\u8d44\u6e90...", 360)
        QTimer.singleShot(180, self._startup_step_show_window)

    def _startup_step_show_window(self):
        if self.window is None:
            return
        self._set_splash_progress(95, "\u5373\u5c06\u5b8c\u6210...", 240)
        self.window.show()
        QTimer.singleShot(180, self._startup_finish)

    def _startup_finish(self):
        if self.window is None:
            return
        self._set_splash_progress(100, "\u542f\u52a8\u5b8c\u6210", 180)
        if self.splash is not None:
            QTimer.singleShot(200, self.splash.close)
        QTimer.singleShot(200, self.window.play_startup_animation)

    def run(self):
        self.splash = self._build_splash()
        self._center_widget(self.splash)
        self.splash.show()
        self._set_splash_progress(10, "\u51c6\u5907\u542f\u52a8\u73af\u5883...", 220)
        QTimer.singleShot(160, self._startup_step_create_window)
        self.app.exec()


__all__ = ["MainApp"]








