import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import sys
import os

os.makedirs("Data", exist_ok=True)
file_path = "Data/session_insights.json"

try:
    with open(file_path, "r") as f:
        content = f.read().strip()
        if not content:
            data = []
        else: 
            data = json.loads(content)
except FileNotFoundError:
    print(f"File '{file_path}' not found.")
    exit()

selected_session = None
if len(sys.argv) > 1:
    selected_session = sys.argv[1]

flattened_data = []
for session in data:
    for i, insight in enumerate(session["insights"]):
        flattened_data.append({
            "session_name": session["session_name"],
            "duration": session["duration"],
            "index": i + 1,
            **insight
        })

df = pd.DataFrame(flattened_data)

if df.empty or "session_name" not in df.columns:
    print("No session data found. Please play a session first.")
    sys.exit(0)

if selected_session:
    df = df[df["session_name"] == selected_session].copy()
    if df.empty:
        print(f"No data found for session '{selected_session}'.")
        sys.exit(0)

# Feature Extraction
def compute_insight_flags(df):
    df = pd.DataFrame(flattened_data)

    if df.empty:
        print("No session data found. Please play a session first.")
        sys.exit(0)
    df["is_carry_addition"] = (
        (df["operation"] == "add") &
        ((df["operand_1"] % 10 + df["operand_2"] % 10) >= 10)
    )
    for d in range(1, 10):
        df[f"has_{d}"] = df["operand_1"].astype(str).str.contains(str(d)) | \
                         df["operand_2"].astype(str).str.contains(str(d))
    df["is_round_operand_1"] = df["operand_1"] % 10 == 0
    df["is_round_operand_2"] = df["operand_2"] % 10 == 0
    df["num_digits_op1"] = df["operand_1"].astype(str).str.len()
    df["num_digits_op2"] = df["operand_2"].astype(str).str.len()
    df["operand_diff"] = abs(df["operand_1"] - df["operand_2"])
    df["is_exact_division"] = (
        (df["operation"] == "div") &
        (df["operand_2"] != 0) &
        (df["operand_1"] % df["operand_2"] == 0)
    )
    df['is_decimal_division'] = (
        (df["operation"] == "div") &
        (df["operand_2"] != 0) &
        (df["operand_1"] % df["operand_2"] != 0)
    )
    return df

df = compute_insight_flags(df)

fig, axes = plt.subplots(2, 6, figsize=(22, 8))
axes = axes.flatten()
sns.set_style("whitegrid")

# 1. Avg Time by Operation with annotations
if "operation" in df.columns:
    avg_op = df.groupby("operation").agg({"time_taken_sec": "mean", "operation": "count"})
    avg_op.columns = ["Avg Time", "Count"]
    avg_op.sort_values("Avg Time", inplace=True)
    avg_op["Avg Time"].plot(kind="bar", ax=axes[0], color="skyblue")
    axes[0].set_title("Avg Time by Operation")
    axes[0].set_ylabel("Seconds")
    for i, (idx, row) in enumerate(avg_op.iterrows()):
        axes[0].text(i, row["Avg Time"] + 0.1, f"n={row['Count']}", ha='center', fontsize=8)

# 2. Digit Heatmap
stats = []
for d in range(1, 10):
    mask = df["operand_1"].astype(str).str.contains(str(d)) | df["operand_2"].astype(str).str.contains(str(d))
    subset = df[mask]
    if not subset.empty:
        stats.append({"Digit": d, "Avg Time": subset["time_taken_sec"].mean(), "Error Rate": 1 - subset["correctness"].mean()})
df_digits = pd.DataFrame(stats).set_index("Digit").sort_values("Avg Time", ascending=False)
sns.heatmap(df_digits, annot=True, fmt=".2f", cmap="YlOrRd", ax=axes[1])
axes[1].set_title("Digits That Trip You Up")

# 3. Time vs Operand Size with regression
df["max_operand"] = df[["operand_1", "operand_2"]].max(axis=1)
sns.regplot(data=df, x="max_operand", y="time_taken_sec", scatter_kws={"alpha": 0.5}, line_kws={"color": "blue"}, ax=axes[2])
axes[2].set_title("Time vs Operand Size")

# 4. Response Time Chart with rolling avg
df_sorted = df.sort_values(by="timestamp").reset_index(drop=True)
df_sorted["question_number"] = df_sorted.index + 1
df_sorted["rolling"] = df_sorted["time_taken_sec"].rolling(5, min_periods=1).mean()
sns.lineplot(data=df_sorted, x="question_number", y="time_taken_sec", ax=axes[3], label="Time", color="gray")
sns.lineplot(data=df_sorted, x="question_number", y="rolling", ax=axes[3], label="Rolling Avg", color="purple")
axes[3].set_title("Response Time (with Rolling Avg)")

# 5. Accuracy vs Time Buckets
bins = [0, 2, 4, 6, 100]
labels = ["<2s", "2-4s", "4-6s", "6s+"]
df["time_bucket"] = pd.cut(df["time_taken_sec"], bins=bins, labels=labels, include_lowest=True)
time_perf = df.groupby("time_bucket")["correctness"].mean().reindex(labels)
time_perf.plot(kind="bar", color="salmon", ax=axes[4])
axes[4].set_ylim(0, 1)
axes[4].set_title("Accuracy by Time Bucket")

# 6. Top Time-Consuming Features
smart_features = [
    "is_carry_addition", "is_round_operand_1", "is_round_operand_2",
    "is_exact_division", "num_digits_op1", "num_digits_op2", "operand_diff", "is_decimal_division"
] + [f"has_{d}" for d in range(1, 10)]

results = []
for feat in smart_features:
    if feat in df.columns and df[feat].dtype != "object":
        true_set = df[df[feat]] if df[feat].dtype == bool else df
        if len(true_set) >= 5:
            results.append({
                "Feature": feat,
                "Avg Time": true_set["time_taken_sec"].mean(),
                "Accuracy": true_set["correctness"].mean(),
                "Sample Size": len(true_set)
            })
insight_df = pd.DataFrame(results).sort_values(by="Avg Time", ascending=False)
sns.barplot(data=insight_df.head(6), x="Avg Time", y="Feature" , ax=axes[5], palette="coolwarm")
axes[5].set_title("Top Time-Consuming Features")

# 7. Session Summary Block
axes[6].axis("off")
if df["session_name"].nunique() == 1:
    session_name = df["session_name"].iloc[0]
else:
    session_name = "Multiple Sessions"

overall_text = (
    f"Session: {session_name}\n"
    f"Total: {len(df)} | Correct: {df['correctness'].sum()} | Incorrect: {(df['correctness'] == False).sum()}\n"
    f"Avg Time: {df['time_taken_sec'].mean():.2f}s | Speed: {len(df) / (df['timestamp'].max() - df['timestamp'].min()) * 60:.1f} Q/min"
)
axes[6].text(0, 0.5, overall_text, fontsize=12, verticalalignment='center')
axes[6].set_title("Session Summary")

# 8. Error Distribution by Operation
error_dist = df[df["correctness"] == False]["operation"].value_counts()
sns.barplot(x=error_dist.index, y=error_dist.values,  palette="Reds", ax=axes[7])
axes[7].set_title("Error Distribution by Operation")
axes[7].set_ylabel("Count")

# Remove unused axes (if any)
for i in range(8, len(axes)):
    axes[i].axis("off")
    axes[i].text(0, 0.5, "More insights coming soon...", fontsize=10, color="gray")

plt.tight_layout()
plt.show()