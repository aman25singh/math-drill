# Math Drill

A desktop app for practicing arithmetic speed drills, built with Python and Tkinter.  
It tracks your performance, provides insights, and visualizes your progress.

# Why I Built this
As someone preparing for quantitative finance and data-intensive roles, I wanted a tool that not only drills arithmetic speed but also tracks and analyzes improvement over time.

This project combines my interests in Python development, data visualization, and performance optimization into a practical, interactive tool.

It’s designed to:
- Simulate high-pressure, time-bound calculations common in finance, analytics, and tech assessments
- Provide data-backed insights to identify strengths and weaknesses
- Demonstrate my ability to build complete, user-friendly applications with analytics capability

## Features

- Practice addition, subtraction, multiplication, and division
- Fully customizable number ranges and session durations
- Real-time scoring and timer to simulate competitive conditions
- Session analytics & insights using matplotlib/seaborn
- Automatic logging of session history in Data/session_insights.json for progress tracking
## Getting Started

### Prerequisites

- Python 3.8 or higher

### Installation

1. Clone the repository or download the source code.
2. Install dependencies:

    ```sh
    pip install -r requirements.txt
    ```

### Running the App

```sh
python math_game_gui.py
```

### Viewing Insights

After playing at least one session, run:

```sh
python insights.py
```

You can also view insights for a specific session:

```sh
python insights.py <session_name>
```

## Project Structure

- `math_game_gui.py` - Main GUI application
- `game_frame.py` - Core game logic and session handling
- `insights.py` - Analytics and visualization
- `Data/session_insights.json` - Session data (auto-created)
- `requirements.txt` - Python dependencies

## Screenshots

![alt text](image.png)
![alt text](image-1.png)


## License

MIT License