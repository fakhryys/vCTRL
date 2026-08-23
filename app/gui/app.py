# -*- coding: utf-8 -*-
"""
Main application window and GUI coordinator.
"""

import tkinter as tk
from tkinter import ttk
import logging
import webbrowser
from pathlib import Path

from ..config import AppConfig, ConfigManager, ProfileManager
from ..controller import MouseJoystickMapper
from ..input import KeyboardHook, HotkeyConfig
from ..overlays import CrosshairOverlay, TriggerOverlay, ProfileMessageOverlay
from ..system.paths import get_resource_dir
from ..system.tray import TrayIcon, TRAY_AVAILABLE
from .theme import Theme, get_theme, set_window_title_bar_theme
from .widgets import build_slider, build_toggle_switch, build_hotkey_row, build_trigger_bar

logger = logging.getLogger(__name__)


class App(tk.Tk):
    """Main application window."""
    
    FONT = ("Segoe UI", 10)
    FONT_BIG = ("Segoe UI", 13, "bold")
    FONT_MONO = ("Consolas", 10)
    
    def __init__(self, mapper: MouseJoystickMapper, keyboard_hook: KeyboardHook,
                 config_manager: ConfigManager, config: AppConfig):
        super().__init__()
        
        self.mapper = mapper
        self.keyboard_hook = keyboard_hook
        self.config_manager = config_manager
        self.profile_manager = ProfileManager()
        self.config = config
        
        self.crosshair = CrosshairOverlay()
        self.trigger_overlay = TriggerOverlay()
        self.profile_message = ProfileMessageOverlay()
        self.tray_icon = None
        
        self.current_profile = config.last_profile
        self._load_profile_config()
        
        self.theme = get_theme(self.config.theme)
        self._active_tab = "overview"
        
        self._init_ui_variables()
        self._init_window()
        self._build_ui()
        self._apply_all_settings()
        self._start_services()
        
        if TRAY_AVAILABLE:
            self._start_tray()
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.update_idletasks()
        self._center_window()
        
        if self.config.run_minimized and TRAY_AVAILABLE:
            self.after(100, self.withdraw)
            # Show profile message overlay for 5 seconds
            self.after(150, lambda: self.profile_message.show(self.current_profile, 5000))
    
    def _init_ui_variables(self):
        """Initialize Tkinter variables."""
        self._enabled_var = tk.BooleanVar(value=False)
        self._sens_var = tk.DoubleVar(value=self.config.sensitivity)
        self._dz_var = tk.DoubleVar(value=self.config.deadzone)
        self._stick_var = tk.StringVar(value=self.config.stick)
        self._trigger_intensity_var = tk.DoubleVar(value=self.config.trigger_intensity)
        
        self._hk_toggle_var = tk.StringVar(value=self.config.hotkey_toggle)
        self._hk_center_var = tk.StringVar(value=self.config.hotkey_center)
        self._hk_trigger_up_var = tk.StringVar(value=self.config.hotkey_trigger_up)
        self._hk_trigger_down_var = tk.StringVar(value=self.config.hotkey_trigger_down)
        self._hk_lt_up_var = tk.StringVar(value=self.config.hotkey_lt_up)
        self._hk_lt_down_var = tk.StringVar(value=self.config.hotkey_lt_down)
        self._hk_rt_up_var = tk.StringVar(value=self.config.hotkey_rt_up)
        self._hk_rt_down_var = tk.StringVar(value=self.config.hotkey_rt_down)
        self._hk_switch_stick_var = tk.StringVar(value=self.config.hotkey_switch_stick)
        self._hk_reset_triggers_var = tk.StringVar(value=self.config.hotkey_reset_triggers)
        self._hk_crosshair_var = tk.StringVar(value=self.config.hotkey_crosshair)
        self._hk_trigger_overlay_var = tk.StringVar(value=self.config.hotkey_trigger_overlay)
        
        self._listening_for = None
        self._original_hotkey_values = {}
        self._timeout_id = None
        
        self._crosshair_var = tk.BooleanVar(value=self.config.crosshair)
        self._trigger_overlay_var = tk.BooleanVar(value=self.config.trigger_overlay)
        self._sep_triggers_var = tk.BooleanVar(value=self.config.separate_triggers)
        self._reset_opposite_trigger_var = tk.BooleanVar(value=self.config.reset_opposite_trigger)
        self._run_minimized_var = tk.BooleanVar(value=self.config.run_minimized)
        self._show_status_var = tk.BooleanVar(value=self.config.show_status)
        self._invert_y_var = tk.BooleanVar(value=self.config.invert_y)
        
        self._lt_var = tk.IntVar(value=0)
        self._rt_var = tk.IntVar(value=0)
        
        self._theme_var = tk.StringVar(value=self.config.theme.title())
        self._profile_var = tk.StringVar(value=self.current_profile)
        
        self._toggle_switch_drawers = {}
        self._slider_label_updaters = {}
        self._hk_entry_widgets = []
        self._preview_running = False
        self._dirty_panels = set()
        self._reset_opposite_row = None
        self._trig_section_separator = None
    
    def _init_window(self):
        """Initialize window properties."""
        self.title("vCTRL — Virtual Controller")
        self.resizable(False, False)
        self.minsize(500, 100)
        self.configure(bg=self.theme.background)
        self._set_icon()
    
    def _load_profile_config(self):
        """Load configuration from the selected profile."""
        if self.current_profile != "Default":
            profile_config = self.profile_manager.load(self.current_profile)
            if profile_config:
                self.config = profile_config
            else:
                self.current_profile = "Default"
    
    def _build_ui(self):
        """Build the complete user interface."""
        self._build_header()
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16, pady=(4, 0))
        
        self._build_tab_bar()
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16, pady=(0, 0))
        
        self._build_profile_manager()
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16, pady=(0, 0))
        
        self._build_status_banner()
        
        self._build_tab_content()
        
        self._build_footer()
        
        self.after(100, lambda: set_window_title_bar_theme(
            self.winfo_id(), self.config.theme == "dark"))
    
    def _build_header(self):
        """Build the header with title and theme selector."""
        hdr = tk.Frame(self, bg=self.theme.background)
        hdr.pack(fill="x", padx=16, pady=4)
        
        tk.Label(hdr, text="vCTRL", font=self.FONT_BIG,
                 bg=self.theme.background, fg=self.theme.accent).pack(side="left")
        
        theme_frame = tk.Frame(hdr, bg=self.theme.background)
        theme_frame.pack(side="right")
        tk.Label(theme_frame, text="Theme:", font=self.FONT,
                 bg=self.theme.background, fg=self.theme.foreground).pack(side="left", padx=(0, 8))
        
        for theme_name in ("Dark", "Light"):
            tk.Radiobutton(
                theme_frame, text=theme_name, variable=self._theme_var, value=theme_name,
                font=self.FONT, bg=self.theme.background, fg=self.theme.foreground,
                selectcolor=self.theme.accent, activebackground=self.theme.background,
                relief="flat", cursor="hand2",
                command=self._on_theme_change
            ).pack(side="left", padx=2)
    
    def _build_tab_bar(self):
        """Build the tab navigation bar."""
        tab_bar = tk.Frame(self, bg=self.theme.background)
        tab_bar.pack(fill="x", padx=16, pady=(6, 6))
        
        self._tab_overview_lbl = tk.Label(
            tab_bar, text="Overview", font=("Segoe UI", 10, "bold"),
            bg=self.theme.background, cursor="hand2"
        )
        self._tab_overview_lbl.pack(side="left", padx=(0, 16))
        self._tab_overview_lbl.bind("<Button-1>", lambda e: self._switch_tab("overview"))
        
        self._tab_hotkeys_lbl = tk.Label(
            tab_bar, text="Hotkeys", font=("Segoe UI", 10, "bold"),
            bg=self.theme.background, cursor="hand2"
        )
        self._tab_hotkeys_lbl.pack(side="left", padx=(0, 16))
        self._tab_hotkeys_lbl.bind("<Button-1>", lambda e: self._switch_tab("hotkeys"))
        
        self._tab_options_lbl = tk.Label(
            tab_bar, text="Options", font=("Segoe UI", 10, "bold"),
            bg=self.theme.background, cursor="hand2"
        )
        self._tab_options_lbl.pack(side="left")
        self._tab_options_lbl.bind("<Button-1>", lambda e: self._switch_tab("options"))
        
        self._update_tab_labels()
    
    def _build_profile_manager(self):
        """Build the profile management row."""
        profile_frame = tk.Frame(self, bg=self.theme.background, pady=4)
        profile_frame.pack(fill="x", padx=16, pady=0)
        
        tk.Label(profile_frame, text="Profile:", font=self.FONT,
                 bg=self.theme.background, fg=self.theme.foreground).pack(side="left", padx=(0, 8))
        
        btn_container = tk.Frame(profile_frame, bg=self.theme.background)
        btn_container.pack(side="right")
        
        tk.Button(
            btn_container, text="Delete",
            font=("Segoe UI", 9, "bold"),
            bg=self.theme.error, fg="white",
            activebackground=self.theme.error, activeforeground="white",
            relief="flat", padx=12, pady=2, cursor="hand2",
            command=self._delete_profile
        ).pack(side="right", padx=(4, 0))
        
        self._save_as_btn = tk.Button(
            btn_container, text="Save As...",
            font=("Segoe UI", 9, "bold"),
            bg=self.theme.accent, fg="white",
            activebackground=self.theme.success, activeforeground="white",
            relief="flat", padx=12, pady=2, cursor="hand2",
            command=self._save_profile_as
        )
        self._save_as_btn.pack(side="right", padx=(4, 0))
        
        self._profile_combo = ttk.Combobox(
            profile_frame, textvariable=self._profile_var,
            values=["Default"] + self.profile_manager.list_profiles(),
            state="readonly", width=32, font=self.FONT
        )
        self._profile_combo.pack(side="left", padx=(0, 0))
        self._profile_combo.bind("<<ComboboxSelected>>", lambda e: self._load_profile())
    
    def _build_status_banner(self):
        """Build the status message banner."""
        self._status_frame = tk.Frame(self, bg=self.theme.background_secondary, pady=6)
        self._status_label = tk.Label(
            self._status_frame, text="Initialising…",
            font=self.FONT, bg=self.theme.background_secondary,
            fg=self.theme.foreground_dim, anchor="center"
        )
        self._status_label.pack()
        
        if self._show_status_var.get():
            self._status_frame.pack(fill="x", padx=16, pady=0)
        
        self._status_separator = ttk.Separator(self, orient="horizontal")
        if self._show_status_var.get():
            self._status_separator.pack(fill="x", padx=16, pady=(0, 0))
    
    def _build_tab_content(self):
        """Build tab content panels."""
        self._tab_frame = tk.Frame(self, bg=self.theme.background)
        self._tab_frame.pack(fill="both", expand=True)
        
        self._panel_overview = tk.Frame(self._tab_frame, bg=self.theme.background)
        self._panel_hotkeys = tk.Frame(self._tab_frame, bg=self.theme.background)
        self._panel_options = tk.Frame(self._tab_frame, bg=self.theme.background)
        
        self._panels = {
            "overview": self._panel_overview,
            "hotkeys": self._panel_hotkeys,
            "options": self._panel_options,
        }
        
        self._build_overview_panel(self._panel_overview)
        self._hk_entry_widgets = []
        self._build_hotkeys_panel(self._panel_hotkeys)
        self._build_options_panel(self._panel_options)
        
        self._switch_tab(self._active_tab)
        
        if not self._preview_running:
            self._preview_running = True
            self._update_preview()
    
    def _build_footer(self):
        """Build the footer."""
        footer = tk.Label(
            self, text="—",
            font=self.FONT_BIG,
            bg=self.theme.background, fg=self.theme.accent,
            cursor="hand2"
        )
        footer.pack(pady=(0, 8))
        footer.bind("<Button-1>", lambda e: self._open_website())
    
    def _build_overview_panel(self, panel):
        """Build the Overview tab content."""
        cursor_hdr = tk.Frame(panel, bg=self.theme.background)
        cursor_hdr.pack(fill="x", padx=16, pady=(8, 4))
        tk.Label(cursor_hdr, text="Cursor", font=("Segoe UI", 10, "bold"),
                 bg=self.theme.background, fg=self.theme.foreground).pack(side="left")
        
        stick_frame = tk.Frame(cursor_hdr, bg=self.theme.background)
        stick_frame.pack(side="right")
        tk.Label(stick_frame, text="Stick:", font=self.FONT,
                 bg=self.theme.background, fg=self.theme.foreground).pack(side="left", padx=(0, 8))
        for label in ("Left", "Right"):
            tk.Radiobutton(
                stick_frame, text=label, variable=self._stick_var, value=label,
                font=self.FONT, bg=self.theme.background, fg=self.theme.foreground,
                selectcolor=self.theme.accent, activebackground=self.theme.background,
                relief="flat", cursor="hand2",
                command=self._on_stick_change
            ).pack(side="left", padx=4)
        
        canvas_frame = tk.Frame(panel, bg=self.theme.background)
        canvas_frame.pack(pady=(0, 4))
        
        left_preview = tk.Frame(canvas_frame, bg=self.theme.background)
        left_preview.pack(side="left", padx=4)
        tk.Label(left_preview, text="L", font=("Segoe UI", 9, "bold"),
                 bg=self.theme.background, fg=self.theme.foreground).pack()
        self._canvas_left = tk.Canvas(left_preview, width=100, height=100,
                                      bg=self.theme.background_secondary, highlightthickness=1,
                                      highlightbackground=self.theme.foreground_dim)
        self._canvas_left.pack()
        
        right_preview = tk.Frame(canvas_frame, bg=self.theme.background)
        right_preview.pack(side="left", padx=4)
        tk.Label(right_preview, text="R", font=("Segoe UI", 9, "bold"),
                 bg=self.theme.background, fg=self.theme.foreground).pack()
        self._canvas_right = tk.Canvas(right_preview, width=100, height=100,
                                       bg=self.theme.background_secondary, highlightthickness=1,
                                       highlightbackground=self.theme.foreground_dim)
        self._canvas_right.pack()
        
        self._draw_joystick_preview(0.0, 0.0)
        
        pos_frame = tk.Frame(panel, bg=self.theme.background)
        pos_frame.pack(fill="x", padx=16, pady=(0, 4))
        self._pos_label = tk.Label(pos_frame, text="X: +0.000   Y: +0.000",
                                   font=self.FONT_MONO, bg=self.theme.background,
                                   fg=self.theme.foreground)
        self._pos_label.pack()
        
        ctrl = tk.Frame(panel, bg=self.theme.background)
        ctrl.pack(pady=(0, 4))
        
        self._toggle_btn = tk.Button(
            ctrl, text="▶",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme.background_secondary, fg=self.theme.foreground,
            activebackground=self.theme.accent, activeforeground="white",
            relief="flat", padx=32, pady=4, cursor="hand2",
            command=self._toggle_enabled
        )
        self._toggle_btn.pack(side="left")
        if self._enabled_var.get():
            self._toggle_btn.config(text="■", bg=self.theme.accent, fg="white")
        
        tk.Button(
            ctrl, text="Center",
            font=("Segoe UI", 10),
            bg=self.theme.background_secondary, fg=self.theme.foreground,
            activebackground=self.theme.background_secondary,
            activeforeground=self.theme.foreground,
            relief="flat", padx=20, pady=4, cursor="hand2",
            command=self._do_center
        ).pack(side="left", padx=(8, 0))
        
        ttk.Separator(panel, orient="horizontal").pack(fill="x", padx=16, pady=6)
        
        trig_hdr = tk.Frame(panel, bg=self.theme.background)
        trig_hdr.pack(fill="x", padx=16, pady=(4, 2))
        tk.Label(trig_hdr, text="Triggers", font=("Segoe UI", 10, "bold"),
                 bg=self.theme.background, fg=self.theme.foreground).pack(side="left")
        
        self._lt_bar, self._lt_pct_label = build_trigger_bar(
            panel, self.theme, "LT", self._lt_var
        )
        self._rt_bar, self._rt_pct_label = build_trigger_bar(
            panel, self.theme, "RT", self._rt_var
        )
        
        trig_reset_row = tk.Frame(panel, bg=self.theme.background)
        trig_reset_row.pack(pady=(2, 8))
        tk.Button(
            trig_reset_row, text="Reset Triggers",
            font=("Segoe UI", 10),
            bg=self.theme.background_secondary, fg=self.theme.foreground,
            activebackground=self.theme.background_secondary,
            activeforeground=self.theme.foreground,
            relief="flat", width=20, pady=4, cursor="hand2",
            command=self._reset_triggers
        ).pack()
    
    def _build_hotkeys_panel(self, panel):
        """Build the Hotkeys tab content."""
        cursor_hdr = tk.Frame(panel, bg=self.theme.background)
        cursor_hdr.pack(fill="x", padx=16, pady=(8, 4))
        tk.Label(cursor_hdr, text="Cursor Hotkeys", font=("Segoe UI", 10, "bold"),
                 bg=self.theme.background, fg=self.theme.foreground).pack(side="left")
        tk.Label(cursor_hdr, text="", width=6, bg=self.theme.background).pack(side="left")
        tk.Label(cursor_hdr, text="(click to customize)",
                 font=self.FONT, bg=self.theme.background,
                 fg=self.theme.foreground_dim, anchor="w").pack(side="left")
        
        build_hotkey_row(panel, self.theme, "Toggle", self._hk_toggle_var, "toggle",
                        self._start_listening, self._clear_hotkey, self._hk_entry_widgets)
        build_hotkey_row(panel, self.theme, "Center", self._hk_center_var, "center",
                        self._start_listening, self._clear_hotkey, self._hk_entry_widgets)
        build_hotkey_row(panel, self.theme, "Switch Stick", self._hk_switch_stick_var,
                        "switch_stick", self._start_listening, self._clear_hotkey,
                        self._hk_entry_widgets)
        
        ttk.Separator(panel, orient="horizontal").pack(fill="x", padx=16, pady=6)
        
        trig_hdr = tk.Frame(panel, bg=self.theme.background)
        trig_hdr.pack(fill="x", padx=16, pady=(4, 2))
        tk.Label(trig_hdr, text="Trigger Hotkeys", font=("Segoe UI", 10, "bold"),
                 bg=self.theme.background, fg=self.theme.foreground).pack(side="left")
        tk.Label(trig_hdr, text="", width=6, bg=self.theme.background).pack(side="left")
        tk.Label(trig_hdr, text="(click to customize)",
                 font=self.FONT, bg=self.theme.background,
                 fg=self.theme.foreground_dim, anchor="w").pack(side="left")
        
        if self._sep_triggers_var.get():
            build_hotkey_row(panel, self.theme, "LT +", self._hk_lt_up_var, "lt_up",
                            self._start_listening, self._clear_hotkey, self._hk_entry_widgets)
            build_hotkey_row(panel, self.theme, "LT −", self._hk_lt_down_var, "lt_down",
                            self._start_listening, self._clear_hotkey, self._hk_entry_widgets)
            build_hotkey_row(panel, self.theme, "RT +", self._hk_rt_up_var, "rt_up",
                            self._start_listening, self._clear_hotkey, self._hk_entry_widgets)
            build_hotkey_row(panel, self.theme, "RT −", self._hk_rt_down_var, "rt_down",
                            self._start_listening, self._clear_hotkey, self._hk_entry_widgets)
        else:
            build_hotkey_row(panel, self.theme, "Trigger +", self._hk_trigger_up_var,
                            "trigger_up", self._start_listening, self._clear_hotkey,
                            self._hk_entry_widgets)
            build_hotkey_row(panel, self.theme, "Trigger −", self._hk_trigger_down_var,
                            "trigger_down", self._start_listening, self._clear_hotkey,
                            self._hk_entry_widgets)
        
        build_hotkey_row(panel, self.theme, "Reset Triggers", self._hk_reset_triggers_var,
                        "reset_triggers", self._start_listening, self._clear_hotkey,
                        self._hk_entry_widgets)
        
        ttk.Separator(panel, orient="horizontal").pack(fill="x", padx=16, pady=6)
        
        overlay_hdr = tk.Frame(panel, bg=self.theme.background)
        overlay_hdr.pack(fill="x", padx=16, pady=(4, 2))
        tk.Label(overlay_hdr, text="Overlay Hotkeys", font=("Segoe UI", 10, "bold"),
                 bg=self.theme.background, fg=self.theme.foreground).pack(side="left")
        
        build_hotkey_row(panel, self.theme, "Crosshair", self._hk_crosshair_var,
                        "crosshair", self._start_listening, self._clear_hotkey,
                        self._hk_entry_widgets)
        build_hotkey_row(panel, self.theme, "Trigger overlay", self._hk_trigger_overlay_var,
                        "trigger_overlay", self._start_listening, self._clear_hotkey,
                        self._hk_entry_widgets)
        
        save_btn_frame = tk.Frame(panel, bg=self.theme.background)
        save_btn_frame.pack(pady=(12, 8))
        self._save_btn_hotkeys = tk.Button(
            save_btn_frame, text="Save Settings",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme.accent, fg="white",
            activebackground=self.theme.success, activeforeground="white",
            relief="flat", width=20, pady=6, cursor="hand2",
            command=self._on_save_button_click
        )
        self._save_btn_hotkeys.pack()
        
        tk.Frame(panel, bg=self.theme.background, height=8).pack()
    
    def _build_options_panel(self, panel):
        """Build the Options tab content."""
        app_hdr = tk.Frame(panel, bg=self.theme.background)
        app_hdr.pack(fill="x", padx=16, pady=(8, 4))
        tk.Label(app_hdr, text="Main Application", font=("Segoe UI", 10, "bold"),
                 bg=self.theme.background, fg=self.theme.foreground).pack(side="left")
        
        build_toggle_switch(panel, self.theme, "Run Minimized", self._run_minimized_var,
                           None, self._toggle_switch_drawers)
        build_toggle_switch(panel, self.theme, "Show Status", self._show_status_var,
                           self._on_show_status_change, self._toggle_switch_drawers)
        
        ttk.Separator(panel, orient="horizontal").pack(fill="x", padx=16, pady=6)
        
        cursor_hdr = tk.Frame(panel, bg=self.theme.background)
        cursor_hdr.pack(fill="x", padx=16, pady=(4, 4))
        tk.Label(cursor_hdr, text="Cursor", font=("Segoe UI", 10, "bold"),
                 bg=self.theme.background, fg=self.theme.foreground).pack(side="left")
        
        _, update_sens = build_slider(panel, self.theme, "Sensitivity", self._sens_var,
                    0.1, 3.0, 0.05, lambda v: f"{v:.2f}x", self._on_sens_change)
        self._slider_label_updaters[id(self._sens_var)] = update_sens
        
        _, update_dz = build_slider(panel, self.theme, "Dead-zone", self._dz_var,
                    0.0, 0.5, 0.01, lambda v: f"{int(v*100)}%", self._on_dz_change)
        self._slider_label_updaters[id(self._dz_var)] = update_dz
        
        build_toggle_switch(panel, self.theme, "Invert Y Axis", self._invert_y_var,
                           self._on_invert_y_change, self._toggle_switch_drawers)
        
        ttk.Separator(panel, orient="horizontal").pack(fill="x", padx=16, pady=6)
        
        trig_hdr = tk.Frame(panel, bg=self.theme.background)
        trig_hdr.pack(fill="x", padx=16, pady=(4, 2))
        tk.Label(trig_hdr, text="Triggers", font=("Segoe UI", 10, "bold"),
                 bg=self.theme.background, fg=self.theme.foreground).pack(side="left")
        
        _, update_trig_int = build_slider(panel, self.theme, "Intensity", self._trigger_intensity_var,
                    0.01, 0.5, 0.01, lambda v: f"{int(v*100)}%",
                    self._on_trigger_intensity_change)
        self._slider_label_updaters[id(self._trigger_intensity_var)] = update_trig_int
        
        build_toggle_switch(panel, self.theme, "Separate Triggers", self._sep_triggers_var,
                           self._on_separate_triggers_change, self._toggle_switch_drawers)
        
        self._reset_opposite_row = build_toggle_switch(
            panel, self.theme, "Reset Opposite",
            self._reset_opposite_trigger_var,
            self._on_reset_opposite_trigger_change,
            self._toggle_switch_drawers
        )
        
        self._trig_section_separator = ttk.Separator(panel, orient="horizontal")
        self._trig_section_separator.pack(fill="x", padx=16, pady=6)
        
        self._update_reset_opposite_visibility()
        
        overlay_hdr = tk.Frame(panel, bg=self.theme.background)
        overlay_hdr.pack(fill="x", padx=16, pady=(4, 2))
        tk.Label(overlay_hdr, text="Overlay", font=("Segoe UI", 10, "bold"),
                 bg=self.theme.background, fg=self.theme.foreground).pack(side="left")
        
        build_toggle_switch(panel, self.theme, "Crosshair", self._crosshair_var,
                           self._on_crosshair_change, self._toggle_switch_drawers)
        build_toggle_switch(panel, self.theme, "Triggers", self._trigger_overlay_var,
                           self._on_trigger_overlay_change, self._toggle_switch_drawers)
        
        save_btn_frame = tk.Frame(panel, bg=self.theme.background)
        save_btn_frame.pack(pady=(12, 8))
        self._save_btn_options = tk.Button(
            save_btn_frame, text="Save Settings",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme.accent, fg="white",
            activebackground=self.theme.success, activeforeground="white",
            relief="flat", width=20, pady=6, cursor="hand2",
            command=self._on_save_button_click
        )
        self._save_btn_options.pack()
        
        tk.Frame(panel, bg=self.theme.background, height=8).pack()
    
    def _update_tab_labels(self):
        """Update tab label colors to reflect the active tab."""
        tabs = {
            "overview": self._tab_overview_lbl,
            "hotkeys": self._tab_hotkeys_lbl,
            "options": self._tab_options_lbl
        }
        for tab_name, label in tabs.items():
            if tab_name == self._active_tab:
                label.config(fg=self.theme.accent)
            else:
                label.config(fg=self.theme.foreground)
    
    def _switch_tab(self, tab_name: str):
        """Switch active tab by showing its pre-built panel."""
        self._active_tab = tab_name
        self._update_tab_labels()
        
        if self._listening_for:
            self._cancel_listening()
        
        if tab_name in self._dirty_panels:
            self._rebuild_panel(tab_name)
            self._dirty_panels.discard(tab_name)
        
        for name, panel in self._panels.items():
            if name == tab_name:
                panel.pack(fill="both", expand=True)
            else:
                panel.pack_forget()
    
    def _rebuild_panel(self, tab_name: str):
        """Tear down and rebuild one tab's panel in place."""
        panel = self._panels[tab_name]
        for widget in panel.winfo_children():
            widget.destroy()
        
        if tab_name == "hotkeys":
            self._hk_entry_widgets = []
            self._build_hotkeys_panel(panel)
        elif tab_name == "options":
            # Clear slider updaters before rebuilding
            self._slider_label_updaters.clear()
            self._build_options_panel(panel)
        else:
            self._build_overview_panel(panel)
    
    def _invalidate_panel(self, tab_name: str):
        """Mark a panel as needing a rebuild to reflect a settings change.
        
        A hidden panel is only flagged dirty — the actual rebuild happens
        lazily in _switch_tab, just before it's shown, which is invisible
        to the user. Rebuilding a panel while it's hidden is safe because
        an unmapped widget's geometry doesn't affect the window on screen.
        
        The active panel is rebuilt immediately instead, since it's what
        the user is currently looking at. Prefer avoiding this path where
        possible (e.g. via a show/hide toggle on a pre-built widget, as
        _update_reset_opposite_visibility does) — rebuilding a panel that's
        currently visible is exactly the destroy/recreate pattern that
        causes the window to briefly collapse and regrow.
        """
        if tab_name == self._active_tab:
            self._rebuild_panel(tab_name)
            self._dirty_panels.discard(tab_name)
        else:
            self._dirty_panels.add(tab_name)
    
    def _apply_all_settings(self):
        """Apply configuration to mapper and keyboard hook."""
        self.mapper.set_sensitivity(self.config.sensitivity)
        self.mapper.set_deadzone(self.config.deadzone)
        self.mapper.set_stick(self.config.stick == "Right")
        self.mapper.set_invert_y(self.config.invert_y)
        
        self._apply_hotkeys()
        
        if self.config.crosshair:
            self.after(100, self.crosshair.show)
        
        if self.config.trigger_overlay:
            self.after(100, self.trigger_overlay.show)
    
    def _apply_hotkeys(self):
        """Apply hotkey configuration to keyboard hook."""
        hotkey_config = HotkeyConfig(
            toggle=self._hk_toggle_var.get(),
            center=self._hk_center_var.get(),
            trigger_up=self._hk_trigger_up_var.get(),
            trigger_down=self._hk_trigger_down_var.get(),
            lt_up=self._hk_lt_up_var.get(),
            lt_down=self._hk_lt_down_var.get(),
            rt_up=self._hk_rt_up_var.get(),
            rt_down=self._hk_rt_down_var.get(),
            switch_stick=self._hk_switch_stick_var.get(),
            reset_triggers=self._hk_reset_triggers_var.get(),
            crosshair=self._hk_crosshair_var.get(),
            trigger_overlay=self._hk_trigger_overlay_var.get(),
            separate_triggers=self._sep_triggers_var.get(),
            reset_opposite_trigger=self._reset_opposite_trigger_var.get(),
            trigger_intensity=self._trigger_intensity_var.get()
        )
        self.keyboard_hook.update_config(hotkey_config)
    
    def _start_services(self):
        """Start background services."""
        try:
            self.mapper.start()
            self._set_status("Virtual controller connected", ok=True)
        except Exception as e:
            self._set_status(str(e), ok=False)
            logger.error(f"Failed to start mapper: {e}")
        
        self.keyboard_hook.set_callbacks(
            on_toggle=self._toggle_enabled_threadsafe,
            on_center=self._do_center_threadsafe,
            on_switch_stick=self._switch_stick_threadsafe,
            on_reset_triggers=self._reset_triggers_threadsafe,
            on_toggle_crosshair=self._toggle_crosshair_threadsafe,
            on_toggle_trigger_overlay=self._toggle_trigger_overlay_threadsafe,
            on_trigger_change=self._on_trigger_change
        )
        self.keyboard_hook.start()
    
    def _start_tray(self):
        """Start system tray icon."""
        try:
            self.tray_icon = TrayIcon(
                on_show=lambda: self.after(0, self._tray_show),
                on_quit=lambda: self.after(0, self._actual_close)
            )
            self.tray_icon.start()
        except Exception as e:
            logger.error(f"Failed to start tray icon: {e}")
    
    def _update_preview(self):
        """Update joystick preview display."""
        try:
            if self._enabled_var.get():
                import ctypes
                from ..controller.math_utils import normalize_cursor_position, apply_sensitivity, apply_deadzone, invert_y_axis
                
                class POINT(ctypes.Structure):
                    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                
                pt = POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                cursor_x, cursor_y = pt.x, pt.y
                
                screen_width = ctypes.windll.user32.GetSystemMetrics(0)
                screen_height = ctypes.windll.user32.GetSystemMetrics(1)
                
                nx, ny = normalize_cursor_position(cursor_x, cursor_y, screen_width, screen_height)
                nx, ny = apply_sensitivity(nx, ny, self._sens_var.get())
                
                if self._invert_y_var.get():
                    ny = invert_y_axis(ny)
                
                nx, ny = apply_deadzone(nx, ny, self._dz_var.get())
                
                self._pos_label.config(text=f"X: {nx:+.3f}   Y: {ny:+.3f}")
                self._draw_joystick_preview(nx, ny)
                
                lt, rt = self.mapper.get_trigger_values()
                self._lt_var.set(int(lt * 100))
                self._rt_var.set(int(rt * 100))
            else:
                self._pos_label.config(text=f"X: {0.0:+.3f}   Y: {0.0:+.3f}")
                self._draw_joystick_preview(0.0, 0.0)
        except Exception:
            pass
        self.after(33, self._update_preview)
    
    def _draw_joystick_preview(self, nx: float, ny: float):
        """Draw joystick position on both L and R previews."""
        use_right = self._stick_var.get() == "Right"
        
        for canvas, active in [(self._canvas_left, not use_right),
                              (self._canvas_right, use_right)]:
            canvas.delete("all")
            cx, cy, r = 50, 50, 40
            
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                             outline=self.theme.foreground_dim, width=1)
            canvas.create_line(cx - r, cy, cx + r, cy,
                             fill=self.theme.foreground_dim, dash=(3, 4))
            canvas.create_line(cx, cy - r, cx, cy + r,
                             fill=self.theme.foreground_dim, dash=(3, 4))
            
            dz_r = int(r * self._dz_var.get())
            if dz_r > 0:
                canvas.create_oval(cx - dz_r, cy - dz_r, cx + dz_r, cy + dz_r,
                                 outline="#555577", width=1, dash=(2, 3))
            
            px = cx + (nx if active else 0) * r
            py = cy - (ny if active else 0) * r
            dot_r = 6
            
            color = self.theme.success if self._enabled_var.get() and active else self.theme.foreground_dim
            
            canvas.create_oval(px - dot_r, py - dot_r, px + dot_r, py + dot_r,
                             fill=color, outline="")
    
    def _toggle_enabled(self):
        """Toggle joystick enabled state."""
        new_state = not self._enabled_var.get()
        self._enabled_var.set(new_state)
        self.mapper.set_enabled(new_state)
        
        if new_state:
            self._toggle_btn.config(text="■", bg=self.theme.accent, fg="white")
            self._set_status("Joystick active", ok=True)
        else:
            self._toggle_btn.config(text="▶", bg=self.theme.background_secondary,
                                   fg=self.theme.foreground)
            self._set_status("Joystick disabled", ok=False)
    
    def _do_center(self):
        """Center cursor and zero the stick."""
        self.mapper.center_cursor()
        self._set_status("Cursor centered", ok=True)
    
    def _reset_triggers(self):
        """Reset both triggers to zero."""
        self.mapper.reset_triggers()
        lt, rt = self.mapper.get_trigger_values()
        self._refresh_trigger_ui(lt, rt)
        self._set_status("Triggers reset", ok=True)
    
    def _on_sens_change(self, val: float):
        """Handle sensitivity change."""
        self.mapper.set_sensitivity(val)
    
    def _on_dz_change(self, val: float):
        """Handle deadzone change."""
        self.mapper.set_deadzone(val)
    
    def _on_stick_change(self):
        """Handle stick selection change."""
        self.mapper.set_stick(self._stick_var.get() == "Right")
    
    def _on_invert_y_change(self):
        """Handle Y-axis inversion toggle."""
        self.mapper.set_invert_y(self._invert_y_var.get())
        self._do_center()
        status = "Y axis inverted" if self._invert_y_var.get() else "Y axis normal"
        self._set_status(status, ok=True)
    
    def _on_trigger_intensity_change(self, val: float):
        """Handle trigger intensity change."""
        self._apply_hotkeys()
    
    def _on_crosshair_change(self):
        """Handle crosshair toggle."""
        if self._crosshair_var.get():
            self.crosshair.show()
        else:
            self.crosshair.hide()
    
    def _on_trigger_overlay_change(self):
        """Handle trigger overlay toggle."""
        if self._trigger_overlay_var.get():
            self.trigger_overlay.show()
        else:
            self.trigger_overlay.hide()
    
    def _on_show_status_change(self):
        """Handle status visibility toggle."""
        if self._show_status_var.get():
            self._status_frame.pack(fill="x", padx=16, pady=0, before=self._tab_frame)
            self._status_separator.pack(fill="x", padx=16, pady=(0, 0), before=self._tab_frame)
        else:
            self._status_frame.pack_forget()
            self._status_separator.pack_forget()
    
    def _on_separate_triggers_change(self):
        """Handle separate triggers toggle."""
        self._apply_hotkeys()
        self._invalidate_panel("hotkeys")
        self._update_reset_opposite_visibility()
    
    def _update_reset_opposite_visibility(self):
        """Show or hide the Reset Opposite row to match separate-triggers
        state, without rebuilding the rest of the Options panel.
        
        This used to be handled by calling _rebuild_panel("options"),
        which destroys and recreates every widget on the tab. Since
        Options is the tab visible on screen when Separate Triggers is
        toggled, that rebuild briefly left the panel empty and made the
        window collapse and regrow around it — visible as a black flash.
        Packing/forgetting this one pre-built row avoids that entirely.
        """
        if self._reset_opposite_row is None or self._trig_section_separator is None:
            return
        
        if self._sep_triggers_var.get():
            self._reset_opposite_row.pack(fill="x", padx=16, pady=4,
                                         before=self._trig_section_separator)
        else:
            self._reset_opposite_row.pack_forget()
    
    def _on_reset_opposite_trigger_change(self):
        """Handle reset opposite trigger toggle."""
        self._apply_hotkeys()
    
    def _on_theme_change(self):
        """Handle theme change."""
        new_theme_name = self._theme_var.get().lower()
        if new_theme_name == self.config.theme:
            return
        
        self.config.theme = new_theme_name
        
        for widget in self.winfo_children():
            widget.destroy()
        
        self.theme = get_theme(new_theme_name)
        self.configure(bg=self.theme.background)
        
        self.after(100, lambda: set_window_title_bar_theme(
            self.winfo_id(), new_theme_name == "dark"))
        
        self._build_ui()
    
    def _start_listening(self, hk_name: str, entry_label: tk.Label, var: tk.StringVar):
        """Start listening for hotkey input."""
        if self._listening_for == hk_name:
            self._stop_listening()
            return
        
        self._stop_listening()
        self._listening_for = hk_name
        
        self._original_hotkey_values[hk_name] = var.get()
        
        var.set("Press a key combo…")
        entry_label.config(fg=self.theme.warning)
        
        self.bind("<KeyPress>", self._on_key_press_listen)
        self.bind("<FocusOut>", lambda e: self._cancel_listening())
        self.focus_force()
        
        if self._timeout_id:
            self.after_cancel(self._timeout_id)
        self._timeout_id = self.after(15000, self._timeout_listening)
    
    def _stop_listening(self):
        """Stop listening for hotkey input."""
        if self._timeout_id:
            self.after_cancel(self._timeout_id)
            self._timeout_id = None
        
        self._listening_for = None
        self.unbind("<KeyPress>")
        self.unbind("<FocusOut>")
        
        for entry_label in self._hk_entry_widgets:
            try:
                entry_label.config(fg=self.theme.foreground)
            except Exception:
                pass
    
    def _timeout_listening(self):
        """Handle listening timeout."""
        if self._listening_for:
            self._cancel_listening()
    
    def _cancel_listening(self):
        """Cancel listening and restore original value."""
        if self._listening_for and self._listening_for in self._original_hotkey_values:
            var_map = self._get_hotkey_var_map()
            if self._listening_for in var_map:
                var_map[self._listening_for].set(
                    self._original_hotkey_values[self._listening_for]
                )
        self._stop_listening()
    
    def _on_key_press_listen(self, event: tk.Event):
        """Handle key press during hotkey listening."""
        keysym = event.keysym.lower()
        
        if keysym == "escape":
            self._cancel_listening()
            return
        
        mods = []
        state = event.state
        if state & 0x1:
            mods.append("shift")
        if state & 0x4:
            mods.append("ctrl")
        if state & 0x20000:
            mods.append("alt")
        
        if keysym in ("shift_l", "shift_r", "control_l", "control_r",
                     "alt_l", "alt_r", "super_l", "super_r",
                     "caps_lock", "num_lock", "scroll_lock"):
            return
        
        key = keysym.replace("_l", "").replace("_r", "")
        if len(key) == 1 and key.isalpha():
            key = key.lower()
        
        parts = mods + [key]
        combo = "+".join(parts)
        
        if self._timeout_id:
            self.after_cancel(self._timeout_id)
            self._timeout_id = None
        
        hk_name = self._listening_for
        self._stop_listening()
        
        var_map = self._get_hotkey_var_map()
        if hk_name in var_map:
            var_map[hk_name].set(combo)
        
        self._apply_hotkeys()
    
    def _clear_hotkey(self, hk_name: str, var: tk.StringVar):
        """Clear a hotkey binding."""
        var.set("")
        self._apply_hotkeys()
    
    def _get_hotkey_var_map(self):
        """Get mapping of hotkey names to StringVars."""
        return {
            "toggle": self._hk_toggle_var,
            "center": self._hk_center_var,
            "switch_stick": self._hk_switch_stick_var,
            "trigger_up": self._hk_trigger_up_var,
            "trigger_down": self._hk_trigger_down_var,
            "lt_up": self._hk_lt_up_var,
            "lt_down": self._hk_lt_down_var,
            "rt_up": self._hk_rt_up_var,
            "rt_down": self._hk_rt_down_var,
            "reset_triggers": self._hk_reset_triggers_var,
            "crosshair": self._hk_crosshair_var,
            "trigger_overlay": self._hk_trigger_overlay_var,
        }
    
    def _toggle_enabled_threadsafe(self):
        """Thread-safe toggle enabled."""
        self.after(0, self._toggle_enabled)
    
    def _do_center_threadsafe(self):
        """Thread-safe center."""
        self.after(0, self._do_center)
    
    def _switch_stick_threadsafe(self):
        """Thread-safe switch stick."""
        self.after(0, self._switch_stick)
    
    def _switch_stick(self):
        """Switch between left and right stick."""
        current = self._stick_var.get()
        new_stick = "Right" if current == "Left" else "Left"
        self._stick_var.set(new_stick)
        self.mapper.set_stick(new_stick == "Right")
        self._set_status(f"Switched to {new_stick} stick", ok=True)
    
    def _reset_triggers_threadsafe(self):
        """Thread-safe reset triggers."""
        self.after(0, self._reset_triggers)
    
    def _toggle_crosshair_threadsafe(self):
        """Thread-safe toggle crosshair."""
        self.after(0, self._toggle_crosshair)
    
    def _toggle_crosshair(self):
        """Toggle crosshair overlay."""
        new_state = not self._crosshair_var.get()
        self._crosshair_var.set(new_state)
        self._on_crosshair_change()
        if id(self._crosshair_var) in self._toggle_switch_drawers:
            self._toggle_switch_drawers[id(self._crosshair_var)]()
    
    def _toggle_trigger_overlay_threadsafe(self):
        """Thread-safe toggle trigger overlay."""
        self.after(0, self._toggle_trigger_overlay)
    
    def _toggle_trigger_overlay(self):
        """Toggle trigger overlay."""
        new_state = not self._trigger_overlay_var.get()
        self._trigger_overlay_var.set(new_state)
        self._on_trigger_overlay_change()
        if id(self._trigger_overlay_var) in self._toggle_switch_drawers:
            self._toggle_switch_drawers[id(self._trigger_overlay_var)]()
    
    def _on_trigger_change(self, lt: float, rt: float):
        """Handle trigger value change from keyboard hook."""
        self.after(0, lambda: self._refresh_trigger_ui(lt, rt))
    
    def _refresh_trigger_ui(self, lt: float, rt: float):
        """Update trigger UI elements."""
        self._lt_var.set(int(lt * 100))
        self._rt_var.set(int(rt * 100))
        try:
            self._lt_pct_label.config(text=f"{int(lt * 100):3d}%")
            self._rt_pct_label.config(text=f"{int(rt * 100):3d}%")
        except Exception:
            pass
        self.trigger_overlay.update_values(lt, rt)
    
    def _load_profile(self):
        """Load the selected profile."""
        profile_name = self._profile_var.get()
        
        if profile_name == "Default":
            self.config = self.config_manager.load()
        else:
            profile_config = self.profile_manager.load(profile_name)
            if profile_config:
                self.config = profile_config
            else:
                self._set_status(f"Failed to load profile '{profile_name}'", ok=False)
                return
        
        self.current_profile = profile_name
        
        main_config = self.config_manager.load()
        main_config.last_profile = profile_name
        self.config_manager.save(main_config)
        
        self._update_ui_from_config()
        self._apply_all_settings()
        
        if self.config.crosshair:
            self.crosshair.show()
        else:
            self.crosshair.hide()
        
        if self.config.trigger_overlay:
            self.trigger_overlay.show()
        else:
            self.trigger_overlay.hide()
        
        self._on_show_status_change()
        
        self._set_status(f"Profile '{profile_name}' loaded", ok=True)
    
    def _update_ui_from_config(self):
        """Update all UI variables from config."""
        self._sens_var.set(self.config.sensitivity)
        self._dz_var.set(self.config.deadzone)
        self._stick_var.set(self.config.stick)
        self._trigger_intensity_var.set(self.config.trigger_intensity)
        self._crosshair_var.set(self.config.crosshair)
        self._trigger_overlay_var.set(self.config.trigger_overlay)
        self._sep_triggers_var.set(self.config.separate_triggers)
        self._reset_opposite_trigger_var.set(self.config.reset_opposite_trigger)
        self._run_minimized_var.set(self.config.run_minimized)
        self._show_status_var.set(self.config.show_status)
        self._invert_y_var.set(self.config.invert_y)
        
        self._hk_toggle_var.set(self.config.hotkey_toggle)
        self._hk_center_var.set(self.config.hotkey_center)
        self._hk_trigger_up_var.set(self.config.hotkey_trigger_up)
        self._hk_trigger_down_var.set(self.config.hotkey_trigger_down)
        self._hk_lt_up_var.set(self.config.hotkey_lt_up)
        self._hk_lt_down_var.set(self.config.hotkey_lt_down)
        self._hk_rt_up_var.set(self.config.hotkey_rt_up)
        self._hk_rt_down_var.set(self.config.hotkey_rt_down)
        self._hk_switch_stick_var.set(self.config.hotkey_switch_stick)
        self._hk_reset_triggers_var.set(self.config.hotkey_reset_triggers)
        self._hk_crosshair_var.set(self.config.hotkey_crosshair)
        self._hk_trigger_overlay_var.set(self.config.hotkey_trigger_overlay)
        
        # Redraw all toggle switches to reflect updated values
        for drawer_func in self._toggle_switch_drawers.values():
            drawer_func()
        
        # Update all slider value labels to reflect updated values
        for updater_func in self._slider_label_updaters.values():
            updater_func()
    
    def _save_profile_as(self):
        """Save current settings as a new profile."""
        dialog = tk.Toplevel(self)
        dialog.title("Save Profile As")
        dialog.configure(bg=self.theme.background)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        self._set_icon(dialog)
        
        dialog.geometry("320x120")
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(dialog, text="Profile Name:", font=self.FONT,
                bg=self.theme.background, fg=self.theme.foreground).pack(pady=(16, 4))
        
        name_var = tk.StringVar()
        entry = tk.Entry(dialog, textvariable=name_var, font=self.FONT,
                        bg=self.theme.background_secondary, fg=self.theme.foreground,
                        width=30, insertbackground=self.theme.foreground)
        entry.pack(pady=(0, 12))
        entry.focus_set()
        
        def save():
            name = name_var.get().strip()
            if not name:
                self._set_status("Profile name cannot be empty", ok=False)
                return
            
            if not all(c.isalnum() or c in (' ', '-', '_') for c in name):
                self._set_status("Invalid profile name", ok=False)
                return
            
            self._sync_config_from_ui()
            
            if self.profile_manager.save(name, self.config):
                self.current_profile = name
                self._profile_var.set(name)
                self._refresh_profile_list()
                
                main_config = self.config_manager.load()
                main_config.last_profile = name
                self.config_manager.save(main_config)
                
                self._set_status(f"Profile '{name}' saved", ok=True)
                
                # Show success feedback on Save As button
                self._show_save_as_success()
                
                dialog.destroy()
            else:
                self._set_status("Failed to save profile", ok=False)
        
        btn_frame = tk.Frame(dialog, bg=self.theme.background)
        btn_frame.pack(pady=(0, 12))
        
        tk.Button(
            btn_frame, text="Save",
            font=self.FONT,
            bg=self.theme.accent, fg="white",
            activebackground=self.theme.success, activeforeground="white",
            relief="flat", padx=20, pady=4, cursor="hand2",
            command=save
        ).pack(side="left", padx=(0, 8))
        
        tk.Button(
            btn_frame, text="Cancel",
            font=self.FONT,
            bg=self.theme.background_secondary, fg=self.theme.foreground,
            activebackground=self.theme.background_secondary,
            activeforeground=self.theme.foreground,
            relief="flat", padx=20, pady=4, cursor="hand2",
            command=dialog.destroy
        ).pack(side="left")
        
        entry.bind("<Return>", lambda e: save())
        entry.bind("<Escape>", lambda e: dialog.destroy())
    
    def _show_save_as_success(self):
        """Show success feedback on Save As button (green with 'Done' text)."""
        original_text = self._save_as_btn.cget("text")
        original_bg = self._save_as_btn.cget("bg")
        
        # Change to success state
        self._save_as_btn.config(
            text="Done",
            bg=self.theme.success
        )
        
        # Revert after 2 seconds
        def revert():
            self._save_as_btn.config(
                text=original_text,
                bg=original_bg
            )
        
        self.after(2000, revert)
    
    def _delete_profile(self):
        """Delete the selected profile."""
        profile_name = self._profile_var.get()
        
        if profile_name == "Default":
            self._set_status("Cannot delete Default profile", ok=False)
            return
        
        dialog = tk.Toplevel(self)
        dialog.title("Delete Profile")
        dialog.configure(bg=self.theme.background)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        self._set_icon(dialog)
        
        dialog.geometry("320x120")
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(dialog, text=f"Delete profile '{profile_name}'?",
                font=self.FONT, bg=self.theme.background,
                fg=self.theme.foreground).pack(pady=(20, 4))
        tk.Label(dialog, text="This action cannot be undone.",
                font=("Segoe UI", 9), bg=self.theme.background,
                fg=self.theme.foreground_dim).pack(pady=(0, 12))
        
        def confirm():
            if self.profile_manager.delete(profile_name):
                self._profile_var.set("Default")
                self._refresh_profile_list()
                self.config = self.config_manager.load()
                self.current_profile = "Default"
                self._update_ui_from_config()
                self._apply_all_settings()
                
                if self.config.crosshair:
                    self.crosshair.show()
                else:
                    self.crosshair.hide()
                
                if self.config.trigger_overlay:
                    self.trigger_overlay.show()
                else:
                    self.trigger_overlay.hide()
                
                self._on_show_status_change()
                
                if self._active_tab in ("hotkeys", "options"):
                    self._invalidate_panel("hotkeys")
                    self._update_reset_opposite_visibility()
                
                main_config = self.config_manager.load()
                main_config.last_profile = "Default"
                self.config_manager.save(main_config)
                
                self._set_status(f"Profile '{profile_name}' deleted", ok=True)
            else:
                self._set_status("Failed to delete profile", ok=False)
            dialog.destroy()
        
        btn_frame = tk.Frame(dialog, bg=self.theme.background)
        btn_frame.pack(pady=(0, 12))
        
        tk.Button(
            btn_frame, text="Delete",
            font=self.FONT,
            bg=self.theme.error, fg="white",
            activebackground=self.theme.error, activeforeground="white",
            relief="flat", padx=20, pady=4, cursor="hand2",
            command=confirm
        ).pack(side="left", padx=(0, 8))
        
        tk.Button(
            btn_frame, text="Cancel",
            font=self.FONT,
            bg=self.theme.background_secondary, fg=self.theme.foreground,
            activebackground=self.theme.background_secondary,
            activeforeground=self.theme.foreground,
            relief="flat", padx=20, pady=4, cursor="hand2",
            command=dialog.destroy
        ).pack(side="left")
    
    def _refresh_profile_list(self):
        """Refresh the profile dropdown list."""
        profiles = ["Default"] + self.profile_manager.list_profiles()
        self._profile_combo['values'] = profiles
    
    def _sync_config_from_ui(self):
        """Synchronize config object from UI variables."""
        self.config.sensitivity = self._sens_var.get()
        self.config.deadzone = self._dz_var.get()
        self.config.stick = self._stick_var.get()
        self.config.trigger_intensity = self._trigger_intensity_var.get()
        self.config.crosshair = self._crosshair_var.get()
        self.config.trigger_overlay = self._trigger_overlay_var.get()
        self.config.separate_triggers = self._sep_triggers_var.get()
        self.config.reset_opposite_trigger = self._reset_opposite_trigger_var.get()
        self.config.run_minimized = self._run_minimized_var.get()
        self.config.show_status = self._show_status_var.get()
        self.config.invert_y = self._invert_y_var.get()
        self.config.hotkey_toggle = self._hk_toggle_var.get()
        self.config.hotkey_center = self._hk_center_var.get()
        self.config.hotkey_trigger_up = self._hk_trigger_up_var.get()
        self.config.hotkey_trigger_down = self._hk_trigger_down_var.get()
        self.config.hotkey_lt_up = self._hk_lt_up_var.get()
        self.config.hotkey_lt_down = self._hk_lt_down_var.get()
        self.config.hotkey_rt_up = self._hk_rt_up_var.get()
        self.config.hotkey_rt_down = self._hk_rt_down_var.get()
        self.config.hotkey_switch_stick = self._hk_switch_stick_var.get()
        self.config.hotkey_reset_triggers = self._hk_reset_triggers_var.get()
        self.config.hotkey_crosshair = self._hk_crosshair_var.get()
        self.config.hotkey_trigger_overlay = self._hk_trigger_overlay_var.get()
    
    def _on_save_button_click(self):
        """Handle save button click."""
        self._sync_config_from_ui()
        
        if self.current_profile == "Default":
            self.config_manager.save(self.config)
        else:
            self.profile_manager.save(self.current_profile, self.config)
        
        self._set_status("Settings saved successfully", ok=True)
        
        for btn in [self._save_btn_hotkeys, self._save_btn_options]:
            try:
                btn.config(text="Settings saved", bg=self.theme.success)
            except Exception:
                pass
        
        self.after(5000, self._reset_save_buttons)
    
    def _reset_save_buttons(self):
        """Reset save buttons to default state."""
        for btn in [self._save_btn_hotkeys, self._save_btn_options]:
            try:
                btn.config(text="Save Settings", bg=self.theme.accent)
            except Exception:
                pass
    
    def _set_status(self, msg: str, ok: bool):
        """Set status message."""
        color = self.theme.success if ok else self.theme.error
        self._status_label.config(text=f"  {msg}", fg=color)
    
    def _set_icon(self, window=None):
        """Set window icon."""
        try:
            icon_path = get_resource_dir() / "icon.ico"
            if icon_path.exists():
                if window is None:
                    self.iconbitmap(str(icon_path))
                else:
                    window.iconbitmap(str(icon_path))
        except Exception:
            pass
    
    def _center_window(self):
        """Position window at top-right of screen."""
        self.update_idletasks()
        
        window_width = self.winfo_width()
        screen_width = self.winfo_screenwidth()
        
        margin = 12
        x = screen_width - window_width - margin
        y = margin
        
        self.geometry(f"+{x}+{y}")
    
    def _open_website(self):
        """Open website in default browser."""
        webbrowser.open("https://www.youtube.com/@fakhryys")
    
    def _tray_show(self):
        """Show window from tray."""
        self.deiconify()
        self.lift()
        self.focus_force()
    
    def _on_close(self):
        """Handle window close button."""
        if self.tray_icon:
            self.withdraw()
        else:
            self._actual_close()
    
    def _actual_close(self):
        """Actually close the application."""
        self.crosshair.hide()
        self.trigger_overlay.hide()
        self.profile_message.hide()
        self.mapper.stop()
        self.keyboard_hook.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        self.destroy()
