"""Tkinter frame that runs a drill.

Deliberately thin. Every rule about what a question is, what counts as an
answer, and how the session is scored lives in :mod:`mathdrill.core`; this
file owns widgets, the countdown, and nothing else.
"""

from __future__ import annotations

import tkinter as tk

from .core import DrillConfig, DrillSession
from .storage import append_session

BG = "#f0f0f0"


class GameFrame(tk.Frame):
    """Presents questions, collects answers, and saves the session."""

    def __init__(self, master, game_config, on_complete_callback=None):
        super().__init__(master)

        if isinstance(game_config, DrillConfig):
            self.drill_config = game_config
        else:
            # Raises core.ConfigError for an unusable configuration; the
            # caller validates before constructing us.
            self.drill_config = DrillConfig.from_mapping(game_config)

        self.session = DrillSession(self.drill_config)
        self.on_complete_callback = on_complete_callback
        self.session_name = self.drill_config.session_name
        self.remaining_time = self.drill_config.duration
        self.saved_path = None

        # Handles for scheduled callbacks so end_game can cancel them. Without
        # this the pending next_question fired after the timer expired and kept
        # the drill running past "Time's up".
        self._timer_job = None
        self._next_question_job = None
        self._end_job = None

        master.geometry("600x400")
        master.title("Speed Drill")
        master.config(bg=BG)
        self.config(bg=BG)

        tk.Label(
            self,
            text="Speed Drill In Progress",
            font=("Helvetica", 16, "bold"),
            bg=BG,
            fg="#333",
        ).grid(row=0, column=0, columnspan=2, pady=(10, 5))

        self.timer_label = tk.Label(
            self,
            text=f"Time Remaining: {self.remaining_time}s",
            font=("Helvetica", 12),
            bg=BG,
            fg="#555",
        )
        self.timer_label.grid(row=1, column=0, sticky="w", padx=10)

        self.score_label = tk.Label(
            self,
            text="Score: 0",
            font=("Helvetica", 12),
            bg=BG,
            fg="#555",
        )
        self.score_label.grid(row=1, column=1, sticky="e", padx=10)

        self.question_label = tk.Label(self, text="", font=("Helvetica", 16), bg=BG, fg="#111")
        self.question_label.grid(row=2, column=0, columnspan=2, pady=10)

        self.answer_var = tk.StringVar()
        self.answer_entry = tk.Entry(
            self, textvariable=self.answer_var, font=("Helvetica", 14), width=20
        )
        self.answer_entry.grid(row=3, column=0, columnspan=2, pady=10)
        self.answer_entry.bind("<Return>", self.check_answer)

        self.stats_label = tk.Label(
            self,
            text="",
            font=("Helvetica", 12),
            justify="left",
            bg=BG,
            fg="#333",
        )
        self.stats_label.grid(row=4, column=0, columnspan=2, pady=10)

        self.close_btn = tk.Button(
            self,
            text="Close & View Insights",
            font=("Helvetica", 12, "bold"),
            bg="#2196F3",
            fg="white",
            relief="raised",
            command=self.complete_session,
        )
        self.close_btn.grid(row=5, column=0, columnspan=2, pady=10)
        self.close_btn.grid_remove()

        self.next_question()
        self.update_timer()
        self._end_job = self.after(self.drill_config.duration * 1000, self.end_game)

    # ------------------------------------------------------------------ timer

    def update_timer(self):
        """Tick the countdown once per second."""
        if self.remaining_time > 0:
            self.remaining_time -= 1
            self.timer_label.config(text=f"Time Remaining: {self.remaining_time}s")
            self._timer_job = self.after(1000, self.update_timer)
        else:
            self._timer_job = None
            self.timer_label.config(text="Time's up!")

    # ----------------------------------------------------------------- drill

    def next_question(self):
        """Show the next question."""
        self._next_question_job = None
        question = self.session.next_question()
        if question is None:
            return
        self.question_label.config(text=question.text)
        self.answer_var.set("")
        self.answer_entry.config(state="normal")
        self.answer_entry.focus_set()

    def check_answer(self, event=None):
        """Handle Return in the answer box."""
        result = self.session.submit(self.answer_var.get())
        if not result.accepted:
            # Blank entry, or the session already ended. Do nothing at all --
            # no record, no score change, and the current question stands.
            return

        if not result.correct and result.record is not None:
            print(
                f" Q: {result.record['question']} | "
                f"your answer: {result.record['user_answer']} | "
                f"correct answer: {result.record['correct_answer']}."
            )

        self.score_label.config(text=f"Score: {self.session.score}")
        self._next_question_job = self.after(10, self.next_question)

    # ------------------------------------------------------------------- end

    def _cancel_pending(self):
        """Cancel every scheduled callback."""
        for attr in ("_timer_job", "_next_question_job", "_end_job"):
            job = getattr(self, attr, None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except (ValueError, tk.TclError):
                    pass
                setattr(self, attr, None)

    def end_game(self):
        """Stop the drill, show the summary, and save the session."""
        self._end_job = None
        self._cancel_pending()
        self.session.finish()

        summary = self.session.summary()

        print("\nMost Time-Consuming Questions:")
        for i, record in enumerate(self.session.slowest(), start=1):
            print(
                f"{i}. Q: {record['question']} | "
                f"Time Taken: {record['time_taken_sec']:.2f}s | "
                f"Correct: {record['correctness']} | "
                f"Your Answer: {record['user_answer']} | "
                f"Correct Answer: {record['correct_answer']}"
            )

        self.question_label.config(text="")
        # The entry was placed with .grid(); the old code called .pack_forget()
        # on it, which silently did nothing and left the box accepting input.
        self.answer_entry.config(state="disabled")
        self.answer_entry.grid_remove()
        self.timer_label.config(text="Time's up!")

        save_note = ""
        try:
            self.saved_path = append_session(self.session.to_record())
        except Exception as exc:  # surfaced to the user, not swallowed
            save_note = f"\n\nCould not save this session: {exc}"

        self.stats_label.config(
            text=(
                f"Session Complete!\n\n"
                f"Session: {summary['session_name']}\n"
                f"Questions: {summary['total']}\n"
                f"Correct: {summary['correct']} | Incorrect: {summary['incorrect']}\n"
                f"Score: {summary['score']}\n"
                f"Avg Time: {summary['avg_time_sec']:.2f}s\n"
                f"Speed: {summary['questions_per_min']:.2f} Q/min"
                f"{save_note}"
            )
        )
        self.stats_label.grid(row=4, column=0, columnspan=2, pady=10)
        self.close_btn.grid(row=5, column=0, columnspan=2, pady=10)

    def destroy(self):
        """Make sure no scheduled callback outlives the widget."""
        self._cancel_pending()
        super().destroy()

    def complete_session(self):
        if self.on_complete_callback:
            self.on_complete_callback(self.session_name)
