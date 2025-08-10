import os
import tkinter as tk
from tkinter import ttk
import time
import random
import json  

class GameFrame(tk.Frame):
    def __init__(self, master, game_config, on_complete_callback):
        super().__init__(master)
        self.game_config = game_config  # Renamed from self.config
        self.on_complete_callback = on_complete_callback
        self.session_name = game_config["session_name"]
        self.remaining_time = game_config["duration"]  # Timer starts with the duration in seconds
        self.score = 0
        self.question_count = 0
        self.insights = []
        self.question_start_time = None

        # Define the operations based on the game_config
        self.ops = []
        if game_config.get("use_add", False):
            self.ops.append("add")
        if game_config.get("use_sub", False):
            self.ops.append("sub")
        if game_config.get("use_mul", False):
            self.ops.append("mul")
        if game_config.get("use_div", False):
            self.ops.append("div")
        if not self.ops:
            raise ValueError("No operations enabled in the configuration.")

        # Give the main app window a light background, consistent with our frame
        master.geometry("600x400")  # Width x Height
        master.title("Speed Drill")
        master.config(bg="#f0f0f0")

        # Ensure this frame also has a background color
        self.config(bg="#f0f0f0")

        # Title Label
        title_label = tk.Label(
            self,
            text="Speed Drill In Progress",
            font=("Helvetica", 16, "bold"),
            bg="#f0f0f0",
            fg="#333"
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(10, 5))

        # Timer and Score on the same row
        self.timer_label = tk.Label(
            self,
            text=f"Time Remaining: {self.remaining_time}s",
            font=("Helvetica", 12),
            bg="#f0f0f0",
            fg="#555"
        )
        self.timer_label.grid(row=1, column=0, sticky="w", padx=10)

        self.score_label = tk.Label(
            self,
            text=f"Score: {self.score}",
            font=("Helvetica", 12),
            bg="#f0f0f0",
            fg="#555"
        )
        self.score_label.grid(row=1, column=1, sticky="e", padx=10)

        # Question Label
        self.question_label = tk.Label(
            self,
            text="",
            font=("Helvetica", 16),
            bg="#f0f0f0",
            fg="#111"
        )
        self.question_label.grid(row=2, column=0, columnspan=2, pady=10)

        # Answer Entry
        self.answer_var = tk.StringVar()
        self.answer_entry = tk.Entry(
            self,
            textvariable=self.answer_var,
            font=("Helvetica", 14),
            width=20
        )
        self.answer_entry.grid(row=3, column=0, columnspan=2, pady=10)
        self.answer_entry.bind("<Return>", self.check_answer)

        # Stats Label (hidden initially)
        self.stats_label = tk.Label(
            self,
            text="",
            font=("Helvetica", 12),
            justify="left",
            bg="#f0f0f0",
            fg="#333"
        )
        self.stats_label.grid(row=4, column=0, columnspan=2, pady=10)

        # Close Button (hidden initially)
        self.close_btn = tk.Button(
            self,
            text="Close & View Insights",
            font=("Helvetica", 12, "bold"),
            bg="#2196F3",
            fg="white",
            relief="raised",
            command=self.complete_session
        )
        self.close_btn.grid(row=5, column=0, columnspan=2, pady=10)
        self.close_btn.grid_remove()  # Hide until session ends

        # Start the game
        self.next_question()
        self.update_timer()  # Start the countdown timer
        self.after(game_config["duration"] * 1000, self.end_game)

    def update_timer(self):
        """Update the countdown timer every second."""
        if self.remaining_time > 0:
            self.remaining_time -= 1
            self.timer_label.config(text=f"Time Remaining: {self.remaining_time}s")
            self.after(1000, self.update_timer)  # Schedule the next update
        else:
            self.timer_label.config(text="Time's up!")  # Display when time is up

    def generate_question(self):
        op = random.choice(self.ops)
        if op == "add":
            a = random.randint(*self.game_config["add_range1"])
            b = random.randint(*self.game_config["add_range2"])
            if random.choice([True, False]):
                a, b = b, a
            return self._build_question(f"{a} + {b}", a + b, op, a, b)
        elif op == "sub":
            a = random.randint(*self.game_config["add_range1"])
            b = random.randint(*self.game_config["add_range2"])
            if random.choice([True, False]):
                a, b = b, a
            return self._build_question(f"{a} - {b}", a - b, op, a, b)
        elif op == "div":
            b = random.randint(*self.game_config["mul_range2"] or [1, 1])
            b = b if b != 0 else 1  # Ensure b is not zero
            a = b * random.randint(*self.game_config["mul_range1"])  # Make a divisible by b
            return self._build_question(f"{a} ÷ {b}", a // b, op, a, b)  # Use integer division (//)
        else:
            a = random.randint(*self.game_config["mul_range1"])
            b = random.randint(*self.game_config["mul_range2"])
            if random.choice([True, False]):
                a, b = b, a
            return self._build_question(f"{a} × {b}", a * b, op, a, b)

    def _build_question(self, text, answer, op, a, b):
        return {
            "question_text": text,
            "answer": answer,
            "question_type": op,
            "operation": op,
            "operand_1": a,
            "operand_2": b
        }

    def next_question(self):
        q_meta = self.generate_question()
        self.current_question = q_meta["question_text"]
        self.correct_answer = q_meta["answer"]
        self.current_question_type = q_meta["question_type"]
        self.current_operands = (q_meta["operand_1"], q_meta["operand_2"])
        self.current_operation = q_meta["operation"]
        self.question_label.config(text=self.current_question)
        self.answer_var.set("")
        self.answer_entry.config(state="normal")
        self.answer_entry.focus_set()
        self.question_count += 1
        self.question_start_time = time.time()

    def check_answer(self, event=None):
        user_ans_str = self.answer_var.get()
        try:
            user_ans = float(user_ans_str)
        except ValueError:
            user_ans = None

        time_taken = time.time() - self.question_start_time
        correctness = user_ans == self.correct_answer

        self.insights.append({
            "timestamp": time.time(),
            "question": self.current_question,
            "question_type": self.current_question_type,
            "operation": self.current_operation,
            "operand_1": self.current_operands[0],
            "operand_2": self.current_operands[1],
            "correct_answer": self.correct_answer,
            "user_answer": user_ans,
            "time_taken_sec": time_taken,
            "correctness": correctness
        })

        if correctness:
            self.score += 1
        else:
            self.score -= 1
            print(f" Q: {self.current_question}| your answer: {user_ans_str} | correct answer: {self.correct_answer}.")
         # Update the score label
        self.score_label.config(text=f"Score: {self.score}")
        
        self.after(10, self.next_question)

    def end_game(self):
        total_questions = len(self.insights)
        correct_answers = sum(1 for i in self.insights if i["correctness"])
        incorrect_answers = total_questions - correct_answers
        if total_questions == 0:
            avg_time = 0
            speed = 0
        else:
            avg_time = sum(i["time_taken_sec"] for i in self.insights) / total_questions
            speed = total_questions / (self.game_config["duration"] / 60)

        stats_message = (
            f"Session Complete!\n\nSession: {self.session_name}\n"
            f"Questions: {total_questions}\nCorrect: {correct_answers} | Incorrect: {incorrect_answers}\n"
            f"Avg Time: {avg_time:.2f}s\nSpeed: {speed:.2f} Q/min"
        )

            # Print the most time-consuming answers
        print("\nMost Time-Consuming Questions:")
        most_time_taken = sorted(self.insights, key=lambda x: x["time_taken_sec"], reverse=True)[:5]
        for i, question in enumerate(most_time_taken, start=1):
            print(
                f"{i}. Q: {question['question']} | Time Taken: {question['time_taken_sec']:.2f}s | "
                f"Correct: {question['correctness']} | Your Answer: {question['user_answer']} | "
                f"Correct Answer: {question['correct_answer']}"
            )
        
        self.question_label.config(text="")
        self.answer_entry.pack_forget()
        self.stats_label.config(text=stats_message)
        self.stats_label.grid(row=4, column=0, columnspan=2, pady=10)
        self.close_btn.grid(row=5, column=0, columnspan=2, pady=10)

        # Save session data
        file_path = "Data/session_insights.json"
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                json.dump([], f)
        with open(file_path, "r+") as f:
            try:
                content = f.read().strip()
                if not content:
                    data = []
                else:
                    data = json.loads(content)
            except json.JSONDecodeError:
                data = []
            data.append({
                "session_name": self.session_name,
                "duration": self.game_config["duration"],
                "insights": self.insights
            })
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()

    def complete_session(self):
        if self.on_complete_callback:
            self.on_complete_callback(self.session_name)
