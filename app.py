#!/usr/bin/env python3
import sys
import os
import subprocess
import json
import logging
import signal
import time

def ensure_venv():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(root_dir, '.venv')

    if not os.path.exists(venv_dir):
        subprocess.check_call([sys.executable, '-m', 'venv', venv_dir])

    if sys.prefix != venv_dir:
        venv_python = os.path.join(venv_dir, 'bin', 'python')
        os.execv(venv_python, [venv_python] + sys.argv)

def ensure_dependencies():
    requirements_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'requirements.txt')
    if os.path.exists(requirements_path):
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', requirements_path])
        except subprocess.CalledProcessError as e:
            sys.exit(1)

class Setup:
    def __init__(self) -> None:
        self.config_dir = os.path.join(os.getcwd(), 'config')
        self.config_path = os.path.join(self.config_dir, 'config.json')
        self.default_config_path = os.path.join(self.config_dir, 'default_config.json')
    
    def _check_config(self) -> None:
        if not os.path.exists(self.config_path):
            self._make_config()
    
    def _make_config(self) -> None:
        os.makedirs(self.config_dir, exist_ok=True)
        try:
            with open(self.default_config_path, 'r') as f:
                base_config = json.load(f)
        except FileNotFoundError:
            sys.exit(1)

        with open(self.config_path, 'w') as config_file:
            json.dump(base_config, config_file, indent=2)

    def _load_config(self) -> dict:
        from box import Box
        return Box.from_json(filename=self.config_path)

    def start(self) -> dict:
        logging.info(f'Config found: {self.config_path}')
        self._check_config()
        return self._load_config()

processor = None

def signal_handler(signum, frame):
    logging.info('Shutting Down')
    if processor:
        processor.file_listener.stop()
    sys.exit(0)

def main():
    global processor
    
    from core.engine import ProcessFiles
    
    os.makedirs('logs', exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/file_sorter.log'),
            logging.StreamHandler()
        ]
    )

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        config = Setup().start()
        processor = ProcessFiles(ai_bridge=None, config=config)
        processor.start()
        
        logging.info('File sorter running. Ctrl+C to stop')
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        signal_handler(None, None)
    except Exception as e:
        logging.error(f'Fatal error: {e}')
        sys.exit(1)

if __name__ == '__main__':
    ensure_venv()
    ensure_dependencies()
    main()
