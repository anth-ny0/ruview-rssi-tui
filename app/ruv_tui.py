#!/usr/bin/env python3
import sys
import time
import statistics
from collections import deque

sys.path.insert(0, "vendor/RuView/archive")

from v1.src.sensing.rssi_collector import LinuxWifiCollector

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, ProgressBar, TabbedContent, TabPane, Markdown
from textual.reactive import reactive


INTERFACE = "wlan0"

SAMPLE_RATE = 10.0
CALIBRATION_SECONDS = 20
WINDOW_SECONDS = 5

DEFAULT_RANGE_THRESHOLD = 5.0
DEFAULT_STD_MULTIPLIER = 3.0
DEFAULT_SHIFT_THRESHOLD = 3.0

LIVE_BASELINE_ALPHA = 0.02


class StatusCard(Static):
    status_text = reactive("CALIBRATING")
    score = reactive(0)
    rssi = reactive("--")

    def render(self):
        return (
            f"[bold]{self.status_text}[/bold]\n"
            f"[dim]score[/dim] [bold]{self.score}%[/bold]    "
            f"[dim]rssi[/dim] [bold]{self.rssi}[/bold]"
        )


class TuningOption(Static):
    can_focus = True

    OPTION_MAP = {
        "range_slider_text": "range",
        "std_slider_text": "std",
        "shift_slider_text": "shift",
    }

    def on_click(self, event) -> None:
        if self.id in self.OPTION_MAP:
            self.app.selected_tuning = self.OPTION_MAP[self.id]
            self.app.update_tuning_tab()
            self.focus()


class MotionApp(App):
    TITLE = "RuView RSSI Motion Monitor"

    CSS = """
    Screen {
        background: #000000;
        color: #cceeff;
    }

    #root {
        background: #000000;
        height: 100%;
        padding: 1 2;
    }

    #topbar {
        height: 3;
        background: #030a12;
        color: #6bdcff;
        content-align: center middle;
        text-align: center;
        text-style: bold;
        border: solid #0b84b8;
        margin-bottom: 1;
    }

    TabbedContent {
        height: 1fr;
        background: #000000;
    }

    Tabs {
        background: #000000;
        color: #8ccfff;
    }

    Tab {
        background: #020812;
        color: #8ccfff;
    }

    Tab.-active {
        background: #06324a;
        color: #ffffff;
        text-style: bold;
    }

    TabPane {
        background: #000000;
        padding-top: 1;
    }

    #status {
        height: 6;
        background: #020812;
        content-align: center middle;
        text-align: center;
        border: heavy #0b84b8;
        margin-bottom: 1;
    }

    #status.calibrating {
        color: #ffd166;
        border: heavy #ffd166;
    }

    #status.still {
        color: #45ff99;
        border: heavy #20c975;
    }

    #status.possible {
        color: #ffb347;
        border: heavy #ffb347;
    }

    #status.motion {
        color: #ff4d6d;
        border: heavy #ff4d6d;
    }

    #calibration {
        height: 8;
        background: #020812;
        border: round #0b84b8;
        padding: 1 2;
        margin-bottom: 1;
    }

    #calibration_label {
        color: #6bdcff;
        text-style: bold;
    }

    #calibration_text {
        color: #d8f5ff;
        margin-top: 1;
    }

    ProgressBar {
        margin-top: 1;
    }

    #dashboard {
        height: 1fr;
    }

    .card {
        background: #020812;
        border: round #0b84b8;
        padding: 1 2;
        margin-right: 1;
        height: 100%;
    }

    #left_col {
        width: 62%;
        height: 100%;
    }

    #right_col {
        width: 38%;
        height: 100%;
    }

    .section_title {
        color: #6bdcff;
        text-style: bold;
        margin-bottom: 1;
    }

    #tuning_layout {
        height: 1fr;
    }

    #tuning_left {
        width: 60%;
        height: 100%;
        background: #020812;
        border: round #0b84b8;
        padding: 1 2;
        margin-right: 1;
    }

    #tuning_right_scroll {
        width: 40%;
        height: 100%;
        background: #020812;
        border: round #0b84b8;
        padding: 1 2;
    }

    .tuning_option {
        background: #020812;
        border: solid #020812;
        padding: 0 1;
        margin-bottom: 1;
        color: #d8f5ff;
    }

    .tuning_option:hover {
        background: #031826;
    }

    .tuning_selected {
        background: #031826;
        border: round #00e5ff;
        color: #ffffff;
    }

    #live_text,
    #logic_text,
    #baseline_text,
    #settings_text,
    #tuning_help {
        color: #d8f5ff;
    }

    #settings_text {
        width: 100%;
    }

    #explain_scroll {
        background: #020812;
        border: round #0b84b8;
        padding: 1 2;
        height: 1fr;
    }

    #explain_box {
        background: #020812;
        color: #d8f5ff;
        width: 100%;
    }

    #controls {
        height: 3;
        background: #030a12;
        border: solid #0b84b8;
        color: #8ccfff;
        content-align: center middle;
        text-align: center;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "reset_calibration", "Recalibrate"),
        ("l", "toggle_live_baseline", "Live baseline"),
        ("left", "selected_down", "Decrease"),
        ("right", "selected_up", "Increase"),
        ("up", "select_previous_tuning", "Previous"),
        ("down", "select_next_tuning", "Next"),
        ("1", "range_down", "Range -"),
        ("2", "range_up", "Range +"),
        ("3", "std_down", "Std -"),
        ("4", "std_up", "Std +"),
        ("5", "shift_down", "Shift -"),
        ("6", "shift_up", "Shift +"),
    ]

    TUNING_DESCRIPTIONS = {
        "range": {
            "title": "RSSI Range Threshold",
            "body": (
                "This controls how much the RSSI must swing inside the live window "
                "before it counts as suspicious.\n\n"
                "The app calculates:\n\n"
                "live_range = strongest RSSI - weakest RSSI\n\n"
                "Example:\n"
                "If your live RSSI moves from -25 dBm to -32 dBm, then:\n\n"
                "live_range = 7 dB\n\n"
                "If your range threshold is 5 dB, that triggers the range check.\n\n"
                "This setting is good at catching quick RSSI jumps, dips, and sharp changes."
            ),
            "effect": (
                "Higher = less sensitive to quick RSSI jumps.\n"
                "Lower = more sensitive to smaller RSSI swings."
            ),
            "raise": (
                "Raise this if the app says POSSIBLE or MOTION when nobody is moving, "
                "especially if your RSSI naturally bounces a few dB."
            ),
            "lower": "Lower this if walking near the router or adapter does not trigger anything.",
        },
        "std": {
            "title": "Std Multiplier",
            "body": (
                "This controls how much noisier the live signal must be compared "
                "to your calibrated baseline noise.\n\n"
                "The app measures baseline noise during calibration. Then it checks:\n\n"
                "live_std >= baseline_std × std_multiplier\n\n"
                "Example:\n"
                "If baseline_std is 0.80 and std_multiplier is 3.0, the live signal "
                "must reach about 2.40 std before this check triggers.\n\n"
                "This setting helps ignore normal Wi-Fi noise."
            ),
            "effect": (
                "Higher = ignores more normal Wi-Fi noise.\n"
                "Lower = reacts to smaller signal instability."
            ),
            "raise": "Raise this if normal adapter/router noise causes false positives.",
            "lower": "Lower this if real movement causes noisy RSSI but still does not trigger.",
        },
        "shift": {
            "title": "Average Shift Threshold",
            "body": (
                "This controls how far the live average RSSI must move away from "
                "the baseline average.\n\n"
                "The app calculates:\n\n"
                "avg_shift = abs(live_average - baseline_average)\n\n"
                "Example:\n"
                "If your baseline average is -24 dBm and the live average becomes -29 dBm, then:\n\n"
                "avg_shift = 5 dB\n\n"
                "If your shift threshold is 3 dB, that triggers the shift check.\n\n"
                "This catches slower changes, like a person standing between the adapter and router."
            ),
            "effect": (
                "Higher = less sensitive to slow signal drift.\n"
                "Lower = detects smaller average signal changes."
            ),
            "raise": "Raise this if the signal slowly drifts and creates false positives.",
            "lower": "Lower this if movement causes small but steady RSSI changes.",
        },
    }

    def compose(self) -> ComposeResult:
        with Container(id="root"):
            yield Static("RuView Motion Monitor  •  RSSI sensing on wlan0", id="topbar")

            with TabbedContent(initial="monitor_tab"):
                with TabPane("Monitor", id="monitor_tab"):
                    yield StatusCard(id="status", classes="calibrating")

                    with Vertical(id="calibration"):
                        yield Static("CALIBRATION", id="calibration_label")
                        yield ProgressBar(
                            total=CALIBRATION_SECONDS * SAMPLE_RATE,
                            id="calibration_bar",
                        )
                        yield Static("Stay still while the baseline is collected.", id="calibration_text")

                    with Horizontal(id="dashboard"):
                        with Vertical(id="left_col", classes="card"):
                            yield Static("LIVE SIGNAL", classes="section_title")
                            yield Static("Waiting for samples...", id="live_text")

                        with Vertical(id="right_col", classes="card"):
                            yield Static("BASELINE", classes="section_title")
                            yield Static("No baseline yet.", id="baseline_text")
                            yield Static("")
                            yield Static("DETECTION", classes="section_title")
                            yield Static("Waiting for calibration...", id="logic_text")

                with TabPane("Tuning", id="tuning_tab"):
                    with Horizontal(id="tuning_layout"):
                        with Vertical(id="tuning_left"):
                            yield Static("LIVE TUNING", classes="section_title")
                            yield TuningOption("", id="range_slider_text")
                            yield TuningOption("", id="std_slider_text")
                            yield TuningOption("", id="shift_slider_text")
                            yield Static("", id="tuning_help")

                        with VerticalScroll(id="tuning_right_scroll"):
                            yield Static("CURRENT SETTINGS", classes="section_title")
                            yield Static("", id="settings_text")

                with TabPane("How It Works", id="explain_tab"):
                    with VerticalScroll(id="explain_scroll"):
                        yield Markdown(self.explanation_text(), id="explain_box")

            yield Static(
                "q quit • r recalibrate • l live baseline • click setting • ←/→ tune • ↑/↓ select • scroll settings pane",
                id="controls",
            )

    def on_mount(self) -> None:
        self.collector = LinuxWifiCollector(interface=INTERFACE, sample_rate_hz=SAMPLE_RATE)

        self.range_threshold = DEFAULT_RANGE_THRESHOLD
        self.std_multiplier = DEFAULT_STD_MULTIPLIER
        self.shift_threshold = DEFAULT_SHIFT_THRESHOLD

        self.selected_tuning = "range"
        self.live_baseline_enabled = False

        self.calibrating = True
        self.calibration_start = time.time()
        self.baseline_samples = []

        self.baseline_mean = None
        self.baseline_std = None
        self.baseline_range = None

        self.window_size = int(SAMPLE_RATE * WINDOW_SECONDS)
        self.window = deque(maxlen=self.window_size)

        self.update_tuning_tab()

        self.set_interval(1.0 / SAMPLE_RATE, self.sample_wifi)

    def make_bar(self, value, min_value, max_value, width=28):
        ratio = (value - min_value) / (max_value - min_value)
        ratio = max(0.0, min(1.0, ratio))
        filled = int(ratio * width)
        empty = width - filled
        return f"[cyan]{'█' * filled}[/cyan][dim]{'░' * empty}[/dim]"

    def selected_description_text(self) -> str:
        desc = self.TUNING_DESCRIPTIONS[self.selected_tuning]

        return (
            f"[bold cyan]{desc['title']}[/bold cyan]\n\n"
            f"{desc['body']}\n\n"
            f"[bold]Effect:[/bold]\n"
            f"{desc['effect']}\n\n"
            f"[bold]Raise when:[/bold]\n"
            f"{desc['raise']}\n\n"
            f"[bold]Lower when:[/bold]\n"
            f"{desc['lower']}"
        )

    def update_tuning_tab(self) -> None:
        range_prefix = "▶ " if self.selected_tuning == "range" else "  "
        std_prefix = "▶ " if self.selected_tuning == "std" else "  "
        shift_prefix = "▶ " if self.selected_tuning == "shift" else "  "

        range_widget = self.query_one("#range_slider_text", TuningOption)
        std_widget = self.query_one("#std_slider_text", TuningOption)
        shift_widget = self.query_one("#shift_slider_text", TuningOption)

        range_widget.update(
            f"{range_prefix}[bold cyan]RSSI range threshold[/bold cyan]\n"
            f"{self.make_bar(self.range_threshold, 1.0, 15.0)}  "
            f"[bold]{self.range_threshold:.1f} dB[/bold]\n"
            f"[dim]click to select   ← decrease   → increase[/dim]"
        )

        std_widget.update(
            f"{std_prefix}[bold cyan]Std multiplier[/bold cyan]\n"
            f"{self.make_bar(self.std_multiplier, 1.0, 8.0)}  "
            f"[bold]{self.std_multiplier:.1f}x[/bold]\n"
            f"[dim]click to select   ← decrease   → increase[/dim]"
        )

        shift_widget.update(
            f"{shift_prefix}[bold cyan]Average shift threshold[/bold cyan]\n"
            f"{self.make_bar(self.shift_threshold, 1.0, 10.0)}  "
            f"[bold]{self.shift_threshold:.1f} dB[/bold]\n"
            f"[dim]click to select   ← decrease   → increase[/dim]"
        )

        range_widget.set_classes(
            "tuning_option tuning_selected"
            if self.selected_tuning == "range"
            else "tuning_option"
        )

        std_widget.set_classes(
            "tuning_option tuning_selected"
            if self.selected_tuning == "std"
            else "tuning_option"
        )

        shift_widget.set_classes(
            "tuning_option tuning_selected"
            if self.selected_tuning == "shift"
            else "tuning_option"
        )

        self.query_one("#tuning_help", Static).update(
            "[dim]Click a setting to select it.\n"
            "Use left/right arrows to tune the selected setting.\n"
            "Use up/down arrows to move between settings.\n"
            "Higher values reduce false positives.\n"
            "Lower values make detection more sensitive.[/dim]"
        )

        baseline_state = "ON" if self.live_baseline_enabled else "OFF"

        if self.baseline_mean is None:
            baseline_info = "No baseline yet."
        else:
            baseline_info = (
                f"Mean RSSI       [bold]{self.baseline_mean:.2f} dBm[/bold]\n"
                f"Noise std       [bold]{self.baseline_std:.2f}[/bold]\n"
                f"Noise range     [bold]{self.baseline_range:.2f} dB[/bold]"
            )

        self.query_one("#settings_text", Static).update(
            f"Selected            [bold cyan]{self.selected_tuning.upper()}[/bold cyan]\n\n"
            f"Range threshold     [bold cyan]{self.range_threshold:.1f} dB[/bold cyan]\n"
            f"Std multiplier      [bold cyan]{self.std_multiplier:.1f}x[/bold cyan]\n"
            f"Shift threshold     [bold cyan]{self.shift_threshold:.1f} dB[/bold cyan]\n\n"
            f"Live baseline       [bold]{baseline_state}[/bold]\n"
            f"Live adapt rate     [bold]{LIVE_BASELINE_ALPHA:.2f}[/bold]\n\n"
            f"{baseline_info}\n\n"
            f"[dim]Press r for a new baseline.\n"
            f"Press l to toggle live baseline tracking.[/dim]\n\n"
            f"────────────────────────────\n\n"
            f"{self.selected_description_text()}"
        )

    def action_selected_down(self) -> None:
        if self.selected_tuning == "range":
            self.action_range_down()
        elif self.selected_tuning == "std":
            self.action_std_down()
        elif self.selected_tuning == "shift":
            self.action_shift_down()

    def action_selected_up(self) -> None:
        if self.selected_tuning == "range":
            self.action_range_up()
        elif self.selected_tuning == "std":
            self.action_std_up()
        elif self.selected_tuning == "shift":
            self.action_shift_up()

    def action_select_next_tuning(self) -> None:
        order = ["range", "std", "shift"]
        index = order.index(self.selected_tuning)
        self.selected_tuning = order[(index + 1) % len(order)]
        self.update_tuning_tab()

    def action_select_previous_tuning(self) -> None:
        order = ["range", "std", "shift"]
        index = order.index(self.selected_tuning)
        self.selected_tuning = order[(index - 1) % len(order)]
        self.update_tuning_tab()

    def action_range_down(self) -> None:
        self.range_threshold = max(1.0, self.range_threshold - 0.5)
        self.update_tuning_tab()
        self.update_detection_panel_if_ready()

    def action_range_up(self) -> None:
        self.range_threshold = min(15.0, self.range_threshold + 0.5)
        self.update_tuning_tab()
        self.update_detection_panel_if_ready()

    def action_std_down(self) -> None:
        self.std_multiplier = max(1.0, self.std_multiplier - 0.5)
        self.update_tuning_tab()
        self.update_detection_panel_if_ready()

    def action_std_up(self) -> None:
        self.std_multiplier = min(8.0, self.std_multiplier + 0.5)
        self.update_tuning_tab()
        self.update_detection_panel_if_ready()

    def action_shift_down(self) -> None:
        self.shift_threshold = max(1.0, self.shift_threshold - 0.5)
        self.update_tuning_tab()
        self.update_detection_panel_if_ready()

    def action_shift_up(self) -> None:
        self.shift_threshold = min(10.0, self.shift_threshold + 0.5)
        self.update_tuning_tab()
        self.update_detection_panel_if_ready()

    def action_toggle_live_baseline(self) -> None:
        self.live_baseline_enabled = not self.live_baseline_enabled
        self.update_tuning_tab()

    def action_reset_calibration(self) -> None:
        self.calibrating = True
        self.calibration_start = time.time()
        self.baseline_samples = []
        self.window.clear()

        self.baseline_mean = None
        self.baseline_std = None
        self.baseline_range = None

        status = self.query_one("#status", StatusCard)
        status.status_text = "CALIBRATING"
        status.score = 0
        status.rssi = "--"
        status.set_classes("calibrating")

        self.query_one("#calibration_bar", ProgressBar).update(progress=0)
        self.query_one("#calibration_text", Static).update(
            "Recalibrating. Stay completely still."
        )
        self.query_one("#live_text", Static).update("Recalibrating. Stay completely still.")
        self.query_one("#baseline_text", Static).update("No baseline yet.")
        self.query_one("#logic_text", Static).update("Waiting for calibration...")
        self.update_tuning_tab()

    def sample_wifi(self) -> None:
        try:
            sample = self.collector.collect_once()
            rssi = sample.rssi_dbm

            if self.calibrating:
                self.handle_calibration(rssi)
            else:
                self.handle_live_detection(rssi)

        except Exception as e:
            self.query_one("#live_text", Static).update(f"[red]Error:[/red] {e}")

    def handle_calibration(self, rssi: float) -> None:
        self.baseline_samples.append(rssi)

        elapsed = time.time() - self.calibration_start
        remaining = max(0, CALIBRATION_SECONDS - elapsed)

        status = self.query_one("#status", StatusCard)
        status.status_text = "CALIBRATING"
        status.score = 0
        status.rssi = f"{rssi:.1f} dBm"
        status.set_classes("calibrating")

        self.query_one("#calibration_bar", ProgressBar).update(
            progress=len(self.baseline_samples)
        )

        self.query_one("#calibration_text", Static).update(
            f"Collecting baseline on [bold cyan]{INTERFACE}[/bold cyan] | "
            f"RSSI [bold]{rssi:.1f} dBm[/bold] | "
            f"samples [bold]{len(self.baseline_samples)}[/bold] | "
            f"remaining [bold]{remaining:.1f}s[/bold]"
        )

        self.query_one("#live_text", Static).update(
            f"[bold cyan]Collecting baseline[/bold cyan]\n\n"
            f"Interface      [bold]{INTERFACE}[/bold]\n"
            f"Current RSSI   [bold]{rssi:.1f} dBm[/bold]\n"
            f"Samples        [bold]{len(self.baseline_samples)}[/bold]\n"
            f"Remaining      [bold]{remaining:.1f}s[/bold]\n\n"
            f"[dim]Stay still. Motion detection starts after calibration.[/dim]"
        )

        self.query_one("#logic_text", Static).update(
            f"[yellow]Calibration active[/yellow]\n\n"
            f"Range threshold   {self.range_threshold:.1f} dB\n"
            f"Std multiplier    {self.std_multiplier:.1f}x\n"
            f"Shift threshold   {self.shift_threshold:.1f} dB"
        )

        if elapsed >= CALIBRATION_SECONDS:
            self.finish_calibration()

    def finish_calibration(self) -> None:
        self.baseline_mean = statistics.mean(self.baseline_samples)
        self.baseline_std = statistics.pstdev(self.baseline_samples)
        self.baseline_range = max(self.baseline_samples) - min(self.baseline_samples)

        self.calibrating = False
        self.window.clear()

        status = self.query_one("#status", StatusCard)
        status.status_text = "STILL"
        status.score = 0
        status.set_classes("still")

        self.query_one("#calibration_bar", ProgressBar).update(
            progress=CALIBRATION_SECONDS * SAMPLE_RATE
        )

        self.query_one("#calibration_text", Static).update(
            f"[bold green]Baseline complete[/bold green] | "
            f"mean [bold]{self.baseline_mean:.2f} dBm[/bold] | "
            f"noise std [bold]{self.baseline_std:.2f}[/bold] | "
            f"range [bold]{self.baseline_range:.2f} dB[/bold]"
        )

        self.update_baseline_panel()
        self.update_detection_panel()
        self.update_tuning_tab()

    def update_baseline_panel(self) -> None:
        if self.baseline_mean is None:
            return

        self.query_one("#baseline_text", Static).update(
            f"Interface       [bold cyan]{INTERFACE}[/bold cyan]\n"
            f"Mean RSSI       [bold]{self.baseline_mean:.2f} dBm[/bold]\n"
            f"Noise std       [bold]{self.baseline_std:.2f}[/bold]\n"
            f"Noise range     [bold]{self.baseline_range:.2f} dB[/bold]\n"
            f"Window          [bold]{WINDOW_SECONDS}s[/bold]\n"
            f"Sample rate     [bold]{SAMPLE_RATE} Hz[/bold]"
        )

    def update_detection_panel_if_ready(self) -> None:
        if not self.calibrating and self.baseline_mean is not None:
            self.update_detection_panel()

    def update_detection_panel(self) -> None:
        self.query_one("#logic_text", Static).update(
            f"Range trigger   [bold]{self.range_threshold:.1f} dB[/bold]\n"
            f"Std trigger     [bold]{self.std_multiplier:.1f}x noise[/bold]\n"
            f"Shift trigger   [bold]{self.shift_threshold:.1f} dB[/bold]\n\n"
            f"[dim]Thresholds are adjustable in the Tuning tab.[/dim]"
        )

    def handle_live_detection(self, rssi: float) -> None:
        self.window.append(rssi)

        result, score, details = self.classify_motion()

        if self.live_baseline_enabled and result == "still" and len(self.window) >= 5:
            self.adapt_baseline(details)

        status = self.query_one("#status", StatusCard)
        status.status_text = result.upper()
        status.score = score
        status.rssi = f"{rssi:.1f} dBm"

        if result == "motion":
            status.set_classes("motion")
        elif result == "possible":
            status.set_classes("possible")
        elif result == "buffering":
            status.set_classes("calibrating")
        else:
            status.set_classes("still")

        if result == "buffering":
            self.query_one("#live_text", Static).update(
                f"[bold cyan]Building live window[/bold cyan]\n\n"
                f"Samples        [bold]{len(self.window)}/{self.window_size}[/bold]\n"
                f"Current RSSI   [bold]{rssi:.1f} dBm[/bold]"
            )
            return

        self.query_one("#live_text", Static).update(
            f"Current RSSI    [bold]{rssi:.1f} dBm[/bold]\n"
            f"Live average    [bold]{details['current_mean']:.2f} dBm[/bold]\n"
            f"Live range      [bold]{details['current_range']:.2f} dB[/bold]\n"
            f"Live std        [bold]{details['current_std']:.2f}[/bold]\n"
            f"Avg shift       [bold]{details['avg_shift']:.2f} dB[/bold]\n"
            f"Score           [bold]{score}%[/bold]\n\n"
            f"{self.motion_bar(score)}"
        )

        self.query_one("#logic_text", Static).update(
            f"Triggered       [bold]{details['trigger_count']}/3[/bold]\n\n"
            f"Range check     {self.yes_no(details['range_trigger'])}\n"
            f"Std check       {self.yes_no(details['std_trigger'])}\n"
            f"Shift check     {self.yes_no(details['shift_trigger'])}\n\n"
            f"[dim]Thresholds are adjustable in the Tuning tab.[/dim]"
        )

        self.update_baseline_panel()
        self.update_tuning_tab()

    def adapt_baseline(self, details: dict) -> None:
        self.baseline_mean = (
            self.baseline_mean * (1.0 - LIVE_BASELINE_ALPHA)
            + details["current_mean"] * LIVE_BASELINE_ALPHA
        )

        self.baseline_std = (
            self.baseline_std * (1.0 - LIVE_BASELINE_ALPHA)
            + details["current_std"] * LIVE_BASELINE_ALPHA
        )

        self.baseline_range = (
            self.baseline_range * (1.0 - LIVE_BASELINE_ALPHA)
            + details["current_range"] * LIVE_BASELINE_ALPHA
        )

    def classify_motion(self):
        if len(self.window) < 5:
            return "buffering", 0, {}

        values = list(self.window)

        current_mean = statistics.mean(values)
        current_std = statistics.pstdev(values)
        current_range = max(values) - min(values)
        avg_shift = abs(current_mean - self.baseline_mean)

        safe_baseline_std = max(self.baseline_std, 0.75)

        range_trigger = current_range >= self.range_threshold
        std_trigger = current_std >= safe_baseline_std * self.std_multiplier
        shift_trigger = avg_shift >= self.shift_threshold

        trigger_count = sum([range_trigger, std_trigger, shift_trigger])

        score = 0

        if range_trigger:
            score += min(40, (current_range / self.range_threshold) * 40)

        if std_trigger:
            score += min(
                35,
                (current_std / (safe_baseline_std * self.std_multiplier)) * 35,
            )

        if shift_trigger:
            score += min(25, (avg_shift / self.shift_threshold) * 25)

        score = min(100, int(score))

        if trigger_count >= 2 and score >= 55:
            result = "motion"
        elif trigger_count == 1 and score >= 40:
            result = "possible"
        else:
            result = "still"

        details = {
            "current_mean": current_mean,
            "current_std": current_std,
            "current_range": current_range,
            "avg_shift": avg_shift,
            "range_trigger": range_trigger,
            "std_trigger": std_trigger,
            "shift_trigger": shift_trigger,
            "trigger_count": trigger_count,
        }

        return result, score, details

    def motion_bar(self, score: int) -> str:
        blocks = 24
        filled = int((score / 100) * blocks)
        empty = blocks - filled
        return f"[cyan]{'█' * filled}[/cyan][dim]{'░' * empty}[/dim]  {score}%"

    def yes_no(self, value: bool) -> str:
        if value:
            return "[bold green]YES[/bold green]"
        return "[dim]no[/dim]"

    def explanation_text(self) -> str:
        return """
# How RuView Motion Detection Works

This app watches Wi-Fi RSSI values and looks for changes that suggest motion.

RSSI is signal strength in dBm.

Strong signal example:

`-25 dBm`

Weak signal example:

`-70 dBm`

When something moves near the signal path, RSSI can bounce, dip, or become noisier.

---

# Calibration

At startup, the app collects a still-room baseline.

It calculates:

- baseline mean
- baseline standard deviation
- baseline range

Press `r` to collect a new baseline.

---

# Live Window

After calibration, the app keeps a rolling window of recent RSSI samples.

The live window is compared against the baseline.

---

# The Three Motion Checks

## Range check

Checks how far RSSI swings inside the live window.

Formula:

`live_range >= range_threshold`

## Std check

Checks how noisy the signal is compared to the baseline.

Formula:

`live_std >= baseline_std * std_multiplier`

## Shift check

Checks how far the live average moved from the baseline average.

Formula:

`avg_shift >= shift_threshold`

---

# Score

The detector builds a score from 0 to 100.

- Range can add up to 40 points.
- Std can add up to 35 points.
- Shift can add up to 25 points.

---

# Results

`STILL`

Signal looks close to baseline.

`POSSIBLE`

One check looks suspicious.

`MOTION`

Multiple checks agree and score is high enough.

---

# Tuning

The Tuning tab lets you adjust the detector live.

Click a setting to select it.

Use left and right arrows to decrease or increase the selected setting.

Use up and down arrows to move between settings.

The selected setting description appears in the Current Settings panel.

Raise thresholds to reduce false positives.

Lower thresholds to make it more sensitive.

---

# Live Baseline

Press `l` to toggle live baseline tracking.

When live baseline is ON, the baseline slowly adapts while the result is STILL.
"""


if __name__ == "__main__":
    app = MotionApp()
    app.run()
