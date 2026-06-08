# Dar Tasks - Task Management Application

Dar Tasks is a lightweight, cross-platform desktop application designed for efficient task and project management. Built with Python and wxPython, it provides a clean, dark-themed interface with support for both English and Arabic.

## Features

- **Project Management**: Organize your work into different projects with a dedicated manager.
- **Daily Tasks**: Track your routine and daily goals effectively.
- **Global Search**: Quickly find tasks across all your projects.
- **Today's Harvest**: Visualize and track your daily achievements.
- **Archiving System**: Automatically archive completed tasks to maintain a clean workspace.
- **Tip of the Day**: Get daily productivity tips to enhance your workflow.
- **Multi-language Support**: Fully localized in English and Arabic.
- **Dark Mode**: Optimized for a comfortable visual experience with a modern dark theme.
- **Single Instance Enforcement**: Ensures only one instance of the app runs at a time.

## Project Structure

- `tasks_app.py`: Main entry point of the application.
- `dar_tasks/`: Core package containing UI components, managers, and utilities.
- `tests/`: Unit tests for ensuring application logic and model integrity.
- `dist/`: Directory for logs, backups, and project data.

## Installation & Running

### Prerequisites

- Python 3.x
- wxPython

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd tasks_app
   ```

2. Install dependencies:
   ```bash
   pip install wxPython
   ```

3. Run the application:
   ```bash
   python tasks_app.py
   ```

## Development

- **Build**: The application can be packaged into an executable using the provided `tasks_app.spec` file with PyInstaller.
- **Tests**: Run the test suite located in the `tests/` directory to verify core functionality.

## License

This project is licensed under the terms of the MIT license.
