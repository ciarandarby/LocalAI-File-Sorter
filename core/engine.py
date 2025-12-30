import os
import time
import shutil
import logging
from datetime import datetime
from typing import Optional
from box import Box
from .file_watcher import FileListener
from .ai_engine import AIHandler

class Domain:
    def __init__(self, config: dict, filepath: str) -> None:
        self.filepath = filepath
        self.data_types_json = config.get('data_types')

    def _get_data_type(self) -> str:
        try:
            return Box.from_json(filename=self.data_types_json).get(self.filepath.split('.')[-1:][0]).upper()
        except Exception as e:
            print(f'Cannot get datatype for filename {self.filepath}, fallback to "UNKNOWN". Error: {e}')
            return self.filepath.split('.')[-1:][0].upper()

class ProcessFiles:
    def __init__(self, ai_bridge: Optional[str], config: dict) -> None:
        self.ai_bridge = ai_bridge
        self.config = config
        self.dirs = config.directories
        self.ignore = config.ignore_filetypes
        self.include_date = config.include_date
        self.database = config.database
        if not os.path.exists(self.database):
            os.makedirs(self.database, exist_ok=True)
        self.file_action_delay = config.file_action_delay
        self.rename_files = config.rename_files
        self.stability_checks = getattr(config, 'file_stability_checks', 5)
        self.stability_timeout = getattr(config, 'file_stability_timeout', 300)
        self.check_interval = getattr(config, 'file_check_interval', 2.0)
        self.file_listener = FileListener(self.dirs, self._on_file_created)
        self.ai_handler = AIHandler(self.config)

    def start(self) -> None:
        self.file_listener.start()

    def _base_name(self, file_name: str) -> str:
        if '.Screenshot' in file_name:
            file_name.replace('.Screenshot', 'Screenshot')
        return f'[{datetime.now().strftime("%Y-%m-%d")}] {file_name}'

    def _save_to_db(self, path: str, domain: str, new_filename: str) -> bool:
        if '.Screenshot' in path:
            path = path.replace('.Screenshot', 'Screenshot')
            logging.info('*SCREENSHOT*')
        save_dir = os.path.join(self.database, domain)
        os.makedirs(save_dir, exist_ok=True)
        
        name, ext = os.path.splitext(new_filename)
        destination = os.path.join(save_dir, new_filename)
        
        counter = 1
        while os.path.exists(destination):
            destination = os.path.join(save_dir, f'{name} ({counter}){ext}')
            counter += 1
            
        try:
            if '.Screenshot' in path:
                path.replace('.Screenshot', 'Screenshot')
            shutil.move(path, destination)
            logging.info(f'Moved {path} -> {destination}')
            return True
        except Exception as e:
            if '.Screenshot' in path:
                return False
            logging.error(f'Move failed for {path}: {e}')
            return False

    def _on_file_created(self, file_path: str) -> None:
        if '.screenshot' in file_path.lower():
            file_path.replace('.Screenshot', 'Screenshot')
        time.sleep(self.file_action_delay)
        if not self._is_file_ready(file_path) and 'screenshot' not in file_path.lower():
            return

        ext = file_path.split('.')[-1].lower()
        if any(ignore_type.lower() == ext for ignore_type in self.ignore):
            return

        filename = os.path.basename(file_path)
        if '.Screenshot' in filename:
            filename.replace('.Screenshot', 'Screenshot')
        if filename.startswith(('~$', 'temp_', 'tmp_', '.DS_Store')) or \
           any(x in filename for x in ['~', '.tmp', '.temp', '.crdownload', '.part']):
            return
            
        new_base_name = filename
        if ext in self.ai_handler.extensions:
            ai_name = self.ai_handler.get_new_filename(file_path)
            if ai_name:
                new_base_name = f'{ai_name}.{ext}' if not ai_name.endswith(f'.{ext}') else ai_name
                logging.info(f'AI suggested name: {new_base_name}')

        domain = Domain(self.config, file_path)._get_data_type()
        new_filename = self._base_name(new_base_name) if self.include_date else new_base_name
        self._save_to_db(file_path, domain, new_filename)

    def _is_file_ready(self, file_path: str) -> bool:
        try:
            import fcntl
            with open(file_path, 'rb') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (IOError, OSError):
            return False
        except ImportError:
            pass

        start_time = time.time()
        last_size, last_mtime = -1, -1
        stable_count = 0
        
        while stable_count < self.stability_checks:
            if time.time() - start_time > self.stability_timeout:
                return False
                
            try:
                size = os.path.getsize(file_path)
                mtime = os.path.getmtime(file_path)
                
                if size == last_size and mtime == last_mtime:
                    stable_count += 1
                else:
                    stable_count = 0
                    last_size, last_mtime = size, mtime
                
                if stable_count < self.stability_checks:
                    time.sleep(self.check_interval)
            except OSError:
                return False
                
        return True
