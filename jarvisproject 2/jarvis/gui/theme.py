"""Colors and stylesheet for the futuristic dark interface."""

STATE_COLORS = {
    "idle": "#3b82f6",
    "wake_detected": "#22d3ee",
    "listening": "#22d3ee",
    "thinking": "#a855f7",
    "speaking": "#34d399",
    "error": "#ef4444",
}

STATE_LABELS = {
    "idle": "Idle — say “Jarvis”",
    "wake_detected": "Yes?",
    "listening": "Listening…",
    "thinking": "Thinking…",
    "speaking": "Speaking…",
    "error": "Something went wrong",
}

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0b0f1a;
    color: #e2e8f0;
    font-family: -apple-system, "SF Pro Display", "Segoe UI", sans-serif;
}
QLabel#statusLabel {
    font-size: 16px;
    letter-spacing: 1px;
    color: #94a3b8;
    padding: 8px;
}
QTextEdit#transcriptLog {
    background-color: #10182b;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 10px;
    font-size: 13px;
}
QLineEdit {
    background-color: #10182b;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 8px;
    color: #e2e8f0;
}
QPushButton {
    background-color: #22d3ee;
    color: #0b0f1a;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #67e8f9;
}
"""
