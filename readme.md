# HikiBridge

HikiBridge is a cross-platform desktop application that monitors a specified folder and communicates with an API endpoint. It provides a user-friendly interface to configure monitoring settings and can be set to start automatically with your system.

## Features

- Monitor a specified folder for changes
- Communicate with custom API endpoint
- Auto-start capability
- System startup integration (Windows and Linux)
- Real-time status display
- Cross-platform support (Windows and Linux)

## Installation

1. Ensure you have Python 3.6+ installed on your system
2. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/hikibridge.git
   cd hikibridge
   ```

3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Launch the application:
   ```bash
   python hiki_bridge.py
   ```

2. Configure the following settings in the application:
   - API Endpoint URL
   - API Key
   - Folder to monitor
   - Auto-start options

3. Click "Start Monitoring" to begin folder monitoring

## Configuration

The application stores its configuration in `config.json` in the application directory. This includes:

- API endpoint URL
- API key
- Monitored folder path
- Auto-start preferences
- System startup settings

## System Requirements

- Python 3.6 or higher
- PyQt6
- Windows or Linux operating system

## License

This project is licensed under the MIT License - see the LICENSE file for details.
