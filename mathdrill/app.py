"""Tkinter frontend for Math Drill.

Owns windows and widgets. Configuration is validated by
:class:`mathdrill.core.DrillConfig`, and analysis is delegated to
:mod:`mathdrill.insights`.
"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
import tkinter as tk

from .core import DURATION_CHOICES, OPERATIONS, ConfigError, DrillConfig
from .game_frame import GameFrame


class ConfigFrame(tk.Frame):
    """The setup screen: operations, ranges, duration, session name."""

    def __init__(self, master, on_start_callback, on_view_analysis_callback):
        super().__init__(master, bg="white", padx=20, pady=20)
        self.on_start_callback = on_start_callback
        self.on_view_analysis_callback = on_view_analysis_callback

        tk.Label(
            self,
            text="🧠 Arithmetic Game",
            font=("Helvetica", 18, "bold"),
            bg="white",
            fg="#333",
        ).grid(row=0, column=0, columnspan=8, pady=(0, 15))

        tk.Label(
            self,
            text=(
                "Welcome! This game helps sharpen your mental math.\n"
                "Select operations, configure number ranges, and begin your session."
            ),
            justify="left",
            bg="white",
            fg="#555",
        ).grid(row=1, column=0, columnspan=8, pady=(0, 15), sticky="w")

        self.var_add = tk.BooleanVar(value=True)
        self.var_sub = tk.BooleanVar(value=True)
        self.var_mul = tk.BooleanVar(value=True)
        self.var_div = tk.BooleanVar(value=True)
        self._op_vars = {
            "add": self.var_add,
            "sub": self.var_sub,
            "mul": self.var_mul,
            "div": self.var_div,
        }

        tk.Checkbutton(self, text="Addition", variable=self.var_add, bg="white").grid(
            row=2, column=0, sticky="w"
        )
        tk.Checkbutton(self, text="Subtraction", variable=self.var_sub, bg="white").grid(
            row=3, column=0, sticky="w"
        )
        tk.Checkbutton(self, text="Multiplication", variable=self.var_mul, bg="white").grid(
            row=4, column=0, sticky="w"
        )
        tk.Checkbutton(self, text="Division", variable=self.var_div, bg="white").grid(
            row=5, column=0, sticky="w"
        )

        tk.Label(self, text="Addition range:", bg="white").grid(row=2, column=1, sticky="e", padx=5)
        self.add_min1 = self._make_entry("2", 2, 2)
        self._make_label("to", 2, 3)
        self.add_max1 = self._make_entry("100", 2, 4)
        self._make_label("+", 2, 5)
        self.add_min2 = self._make_entry("2", 2, 6)
        self._make_label("to", 2, 7)
        self.add_max2 = self._make_entry("100", 2, 8)

        tk.Label(self, text="Multiplication range:", bg="white").grid(
            row=4, column=1, sticky="e", padx=5
        )
        self.mul_min1 = self._make_entry("2", 4, 2)
        self._make_label("to", 4, 3)
        self.mul_max1 = self._make_entry("12", 4, 4)
        self._make_label("×", 4, 5)
        self.mul_min2 = self._make_entry("2", 4, 6)
        self._make_label("to", 4, 7)
        self.mul_max2 = self._make_entry("100", 4, 8)

        tk.Label(self, text="Duration:", bg="white").grid(
            row=6, column=0, sticky="w", padx=5, pady=5
        )
        self.duration_var = tk.StringVar(value="120")
        tk.OptionMenu(self, self.duration_var, *[str(d) for d in DURATION_CHOICES]).grid(
            row=6, column=1, sticky="w"
        )

        self.negatives_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            self,
            text="Allow negative subtraction answers (e.g. 2 - 100)",
            variable=self.negatives_var,
            bg="white",
        ).grid(row=6, column=2, columnspan=6, sticky="w")

        tk.Label(self, text="Session Name:", bg="white").grid(
            row=7, column=0, sticky="w", padx=5, pady=5
        )
        self.session_name_var = tk.StringVar(value="Describe practice session")
        tk.Entry(self, textvariable=self.session_name_var, width=30).grid(
            row=7, column=1, columnspan=3, sticky="w"
        )

        # Errors are reported here rather than raised into the Tk callback,
        # where they used to surface as an unhandled traceback in the console
        # while the window sat there looking unresponsive.
        self.error_label = tk.Label(
            self, text="", bg="white", fg="#c62828", justify="left", wraplength=520
        )
        self.error_label.grid(row=9, column=0, columnspan=8, sticky="w", pady=(5, 0))

        tk.Button(
            self,
            text="🚀 Start Game",
            command=self.on_start,
            bg="#4CAF50",
            fg="white",
            font=("Helvetica", 12, "bold"),
        ).grid(row=8, column=0, columnspan=2, pady=10)

        tk.Button(
            self,
            text="📊 View Overall Analysis",
            command=self.on_view_analysis_callback,
            bg="#2196F3",
            fg="white",
            font=("Helvetica", 10),
        ).grid(row=8, column=2, columnspan=2, pady=10)

    def _make_entry(self, val, row, col):
        e = tk.Entry(self, width=5)
        e.insert(0, val)
        e.grid(row=row, column=col)
        return e

    def _make_label(self, text, row, col):
        tk.Label(self, text=f" {text} ", bg="white").grid(row=row, column=col)

    def _show_error(self, message: str) -> None:
        self.error_label.config(text=message)

    @staticmethod
    def _read_range(label, min_entry, max_entry):
        """Parse one range, naming the offending box if it will not parse."""
        values = []
        for bound, entry in (("minimum", min_entry), ("maximum", max_entry)):
            raw = entry.get().strip()
            if not raw:
                raise ConfigError(f"{label} {bound} is empty.")
            try:
                values.append(int(raw))
            except ValueError:
                raise ConfigError(
                    f"{label} {bound} must be a whole number (got {raw!r})."
                ) from None
        return tuple(values)

    def build_config(self) -> DrillConfig:
        """Read the form into a validated config, or raise ConfigError."""
        add_rng1 = self._read_range("Addition range 1", self.add_min1, self.add_max1)
        add_rng2 = self._read_range("Addition range 2", self.add_min2, self.add_max2)
        mul_rng1 = self._read_range("Multiplication range 1", self.mul_min1, self.mul_max1)
        mul_rng2 = self._read_range("Multiplication range 2", self.mul_min2, self.mul_max2)

        raw_duration = self.duration_var.get().strip()
        try:
            duration = int(raw_duration)
        except ValueError:
            raise ConfigError(
                f"Duration must be a whole number of seconds (got {raw_duration!r})."
            ) from None

        operations = tuple(op for op in OPERATIONS if self._op_vars[op].get())

        session_name = self.session_name_var.get().strip()
        if session_name.lower() == "describe practice session" or not session_name:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            session_name = f"{''.join(operations)}_{duration}s_{ts}"

        return DrillConfig(
            session_name=session_name,
            duration=duration,
            operations=operations,
            add_range1=add_rng1,
            add_range2=add_rng2,
            mul_range1=mul_rng1,
            mul_range2=mul_rng2,
            allow_negative_answers=self.negatives_var.get(),
        )

    def on_start(self):
        """Validate and hand a good config to the app."""
        try:
            config = self.build_config()
        except ConfigError as exc:
            # Unchecking every operation used to raise ValueError out of
            # GameFrame.__init__ with no handler at all.
            self._show_error(str(exc))
            return
        self._show_error("")
        self.on_start_callback(config)


class SpeedDrillApp(tk.Tk):
    """The main window."""

    def __init__(self):
        super().__init__()
        self.title("Arithmetic Speed Drill")
        self.configure(bg="white")
        self.config_frame = ConfigFrame(self, self.start_game, self.view_overall_analysis)
        self.config_frame.pack()
        self.game_frame = None

    def start_game(self, config):
        self.config_frame.pack_forget()
        self.game_frame = GameFrame(self, config, self.launch_insight_after_session)
        self.game_frame.pack()

    def _run_insights(self, session_name: str | None = None):
        """Open the analysis in a separate process.

        ``-m mathdrill.insights`` resolves through the installed package rather
        than a bare relative filename, so it works regardless of the working
        directory the app was launched from.
        """
        command = [sys.executable, "-m", "mathdrill.insights"]
        if session_name:
            command.append(session_name)
        subprocess.run(command, cwd=os.path.dirname(os.path.dirname(__file__)) or None)

    def launch_insight_after_session(self, session_name):
        print(f"Launching insights for session: {session_name}")
        try:
            self._run_insights(session_name)
        except Exception as exc:
            from tkinter import messagebox

            messagebox.showerror("Error", f"Could not launch session insights: {exc}")
        finally:
            self.reset_to_main()

    def view_overall_analysis(self):
        try:
            self._run_insights()
        except Exception as exc:
            from tkinter import messagebox

            messagebox.showerror("Error", f"Could not launch insights: {exc}")

    def reset_to_main(self):
        if self.game_frame:
            self.game_frame.destroy()
            self.game_frame = None
        self.config_frame = ConfigFrame(self, self.start_game, self.view_overall_analysis)
        self.config_frame.pack()


def main() -> int:
    """Console entry point."""
    SpeedDrillApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
