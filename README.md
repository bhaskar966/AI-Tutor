# 🎓 AI Tutor System

> **Your personal AI-powered mentor for DSA, System Design, and Development.**

![Tutor Dashboard Placeholder](https://github.com/bhaskar966/AI-Tutor/blob/master/images/AI_Tutor_Learning_Path.png?raw=true)

## 📖 Introduction

The AI Tutor System is a sophisticated multi-agent platform designed to help students master technical subjects. It provides personalized learning paths, interactive lessons, and real-time guidance across three main domains:

*   **DSA (Data Structures & Algorithms)**: Master algorithmic thinking and problem-solving.
*   **System Design**: Learn to architect scalable and robust systems.
*   **Development**: Hands-on coding guidance for Web, Mobile, and Backend technologies.

The system uses a collaborative agent architecture where specialized agents (DSA Tutor, Code Generator, System Design Expert, etc.) work together to provide a comprehensive learning experience.

## ⚒️ Technologies Used

*   **ADK (Agent Development Kit)**: The core framework powering the collaborative multi-agent system.
*   **Gemini 2.5 Flash**: Advanced LLM for intelligent reasoning and content generation.
*   **SQLite**: Persistent storage for user profiles, sessions, and learning history.
*   **Streamlit**: Interactive and responsive web user interface.
*   **SQLAlchemy**: ORM for robust database management.

## 🙏 Acknowledgements

A special thanks to the **ADK Team** for building the powerful library that serves as the backbone of this project's agentic capabilities.

## ✨ Key Features

*   **Personalized Learning Paths**: Dynamic syllabus generation based on your goals and skill level.
*   **Multi-Agent Intelligence**: Specialized agents for different topics ensure expert-level guidance.
*   **Progress Tracking**: persistent tracking of completed modules and topics.
*   **Interactive Chat**: rich conversational interface with code rendering, diagrams, and formatting.
*   **Guest Access**: Try the platform instantly without creating an account.
*   **Web & CLI Interfaces**: Flexible access via a rich web UI or a terminal-based interface.

## 🚀 Installation & Setup

### Prerequisites

*   **Python 3.10+** must be installed on your system.
*   A **Google Gemini API Key** (for the AI models).

### 1. Clone the Repository

```bash
git clone https://github.com/bhaskar966/AI-Tutor.git
cd AI-Tutor
```

### 2. Set up Python Environment

It is recommended to use a virtual environment.

**Windows:**
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dimensions

```bash
pip install -r requirements.txt
```

### 4. Configuration (.env)

Create a file named `.env` in the `ai_tutor_agent` directory (`ai_tutor_agent/.env`).
Copy the following template and fill in your details:

```ini
# Required: Your Google Gemini API Key
GOOGLE_GENAI_USE_VERTEXTAI=FALSE
GOOGLE_API_KEY=your_actual_api_key_here
DATABASE_URI=sqlite:///ai_tutor.db
AGENT_MODEL=gemini-2.5-flash
```

> **Note**: Do not share your `GOOGLE_API_KEY` publicly.

## 🖥️ Usage

### Web Interface (Recommended)

Run the Streamlit application for the full graphical experience:

```bash
streamlit run streamlit_app.py
```

This will open the application in your default web browser (usually at `http://localhost:8501`).

*   **Login**: Use an existing ID or creates a new one.
*   **Guest Mode**: Click "Continue as Guest" to test immediately.
*   **Navigation**: Use the sidebar to switch between learning paths.

![Login Page Placeholder](https://github.com/bhaskar966/AI-Tutor/blob/master/images/AI_Tutor_Login.png?raw=true)

### CLI Interface

For a terminal-based chat experience:

```bash
python run_cli.py
```

## 🛠️ Debugging

If you encounter issues, here are some tips:

*   **Check Logs**: Errors are often printed to the terminal console where you ran the app.
*   **Database Issues**: If you see "no such column" or database errors, try deleting `ai_tutor.db` (it will be auto-recreated on next run).
*   **Agent Flow**: You can use the `adk web` command to visualize the agent orchestration and debugging flow.
*   **API Errors**: Ensure your `GOOGLE_API_KEY` is valid and has access to the Gemini models.

## 📂 Project Structure

*   `ai_tutor_agent/`: Core agent logic and definitions.
    *   `agent.py`: Root agent configuration.
    *   `utils/`: Database and helper utilities.
*   `streamlit_app.py`: The web-based user interface.
*   `run_cli.py`: The terminal-based runner.
*   `requirements.txt`: Python package dependencies.
