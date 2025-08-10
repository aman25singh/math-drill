import tkinter as tk
from tkinter import ttk
import time
import random
import json
import os, sys
import subprocess
import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

if len(sys.argv) > 1:
    session_name = sys.argv[1]
else:
    session_name = None

class ConfigFrame(tk.Frame):
    def __init__(self, master, on_start_callback, on_view_analysis_callback):
        super().__init__(master, bg="white", padx=20, pady=20)
        self.on_start_callback = on_start_callback
        self.on_view_analysis_callback = on_view_analysis_callback

        title_label = tk.Label(self, text="🧠 Arithmetic Game", font=("Helvetica", 18, "bold"), bg="white", fg="#333")
        title_label.grid(row=0, column=0, columnspan=8, pady=(0, 15))

        desc_text = (
            "Welcome! This game helps sharpen your mental math.\n"
            "Select operations, configure number ranges, and begin your session."
        )
        desc_label = tk.Label(self, text=desc_text, justify="left", bg="white", fg="#555")
        desc_label.grid(row=1, column=0, columnspan=8, pady=(0, 15), sticky="w")



        self.var_add = tk.BooleanVar(value=True)
        self.var_sub = tk.BooleanVar(value=True)
        self.var_mul = tk.BooleanVar(value=True)
        self.var_div = tk.BooleanVar(value=True)

        self.chk_add = tk.Checkbutton(self, text="Addition", variable=self.var_add, bg="white")
        self.chk_sub = tk.Checkbutton(self, text="Subtraction", variable=self.var_sub, bg="white")
        self.chk_mul = tk.Checkbutton(self, text="Multiplication", variable=self.var_mul, bg="white")
        self.chk_div = tk.Checkbutton(self, text="Division", variable=self.var_div, bg="white")

        self.chk_add.grid(row=2, column=0, sticky="w")
        self.chk_sub.grid(row=3, column=0, sticky="w")
        self.chk_mul.grid(row=4, column=0, sticky="w")
        self.chk_div.grid(row=5, column=0, sticky="w")

        tk.Label(self, text="Addition range:", bg="white").grid(row=2, column=1, sticky="e", padx=5)
        self.add_min1 = self._make_entry("2", 2, 2)
        self._make_label("to", 2, 3)
        self.add_max1 = self._make_entry("100", 2, 4)
        self._make_label("+", 2, 5)
        self.add_min2 = self._make_entry("2", 2, 6)
        self._make_label("to", 2, 7)
        self.add_max2 = self._make_entry("100", 2, 8)

        tk.Label(self, text="Multiplication range:", bg="white").grid(row=4, column=1, sticky="e", padx=5)
        self.mul_min1 = self._make_entry("2", 4, 2)
        self._make_label("to", 4, 3)
        self.mul_max1 = self._make_entry("12", 4, 4)
        self._make_label("\u00d7", 4, 5)
        self.mul_min2 = self._make_entry("2", 4, 6)
        self._make_label("to", 4, 7)
        self.mul_max2 = self._make_entry("100", 4, 8)

        tk.Label(self, text="Duration:", bg="white").grid(row=6, column=0, sticky="w", padx=5, pady=5)
        self.duration_var = tk.StringVar(value="120")
        duration_options = ["30", "60", "120", "180", "300"]
        self.duration_menu = tk.OptionMenu(self, self.duration_var, *duration_options)
        self.duration_menu.grid(row=6, column=1, sticky="w")
        
        tk.Label(self, text="Session Name:", bg="white").grid(row=7, column=0, sticky="w", padx=5, pady=5)
        self.session_name_var = tk.StringVar(value="Describe practice session")
        self.session_name_entry = tk.Entry(self, textvariable=self.session_name_var, width=30)
        self.session_name_entry.grid(row=7, column=1, columnspan=3, sticky="w")

        start_btn = tk.Button(self, text="🚀 Start Game", command=self.on_start, bg="#4CAF50", fg="white", font=("Helvetica", 12, "bold"))
        start_btn.grid(row=8, column=0, columnspan=2, pady=10)

        analysis_btn = tk.Button(self, text="📊 View Overall Analysis", command=self.on_view_analysis_callback, bg="#2196F3", fg="white", font=("Helvetica", 10))
        analysis_btn.grid(row=8, column=2, columnspan=2, pady=10)

    def _make_entry(self, val, row, col):
        e = tk.Entry(self, width=5)
        e.insert(0, val)
        e.grid(row=row, column=col)
        return e

    def _make_label(self, text, row, col):
        tk.Label(self, text=f" {text} ", bg="white").grid(row=row, column=col)

    def on_start(self):
        try:
            add_rng1 = (int(self.add_min1.get()), int(self.add_max1.get()))
            add_rng2 = (int(self.add_min2.get()), int(self.add_max2.get()))
            mul_rng1 = (int(self.mul_min1.get()), int(self.mul_max1.get()))
            mul_rng2 = (int(self.mul_min2.get()), int(self.mul_max2.get()))
            duration = int(self.duration_var.get())
        except ValueError:
            return

        user_session = self.session_name_var.get().strip()
        if user_session.lower() == "describe practice session" or not user_session:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            ops = "".join([x for x, v in zip(["add", "sub", "mul", "div"], [
                self.var_add.get(), self.var_sub.get(), self.var_mul.get(), self.var_div.get()]) if v])
            user_session = f"{ops}_{duration}s_{ts}"

        config = {
            "session_name": user_session,
            "use_add": self.var_add.get(),
            "use_sub": self.var_sub.get(),
            "use_mul": self.var_mul.get(),
            "use_div": self.var_div.get(),
            "add_range1": add_rng1,
            "add_range2": add_rng2,
            "mul_range1": mul_rng1,
            "mul_range2": mul_rng2,
            "duration": duration
        }

        self.on_start_callback(config)


class SpeedDrillApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Arithmetic Speed Drill")
        self.configure(bg="white")
        self.config_frame = ConfigFrame(self, self.start_game, self.view_overall_analysis)
        self.config_frame.pack()
        self.game_frame = None

    def start_game(self, config):
        self.config_frame.pack_forget()
        from game_frame import GameFrame
        self.game_frame = GameFrame(self, config, self.launch_insight_after_session)
        self.game_frame.pack()

    def launch_insight_after_session(self, session_name):
        print(f"Launching insights for session: {session_name}")
        try:
            # Construct the full path to insights.py
            insights_path = os.path.join(os.path.dirname(__file__), "insights.py")
            subprocess.run([sys.executable, insights_path, session_name])
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Could not launch session insights: {e}")
        finally:
            self.reset_to_main()

    def view_overall_analysis(self):
        try:
            subprocess.run([sys.executable, "insights.py"])
        except Exception as e:
            print("Could not launch overall insights:", e)

    def reset_to_main(self):
        if self.game_frame:
            self.game_frame.destroy()
        self.config_frame = ConfigFrame(self, self.start_game, self.view_overall_analysis)
        self.config_frame.pack()


if __name__ == "__main__":
    app = SpeedDrillApp()
    app.mainloop()

