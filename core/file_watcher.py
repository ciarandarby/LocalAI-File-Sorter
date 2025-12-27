from watchdog.events import FileSystemEvent, FileSystemEventHandler, FileCreatedEvent
from watchdog.observers import Observer
from typing import Callable, List

class CallbackModel(FileSystemEventHandler):
    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self.callback = callback

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        self.callback(event.src_path)


class FileListener:
    def __init__(self, directories: List[str], callback: Callable[[str], None]):
        self.directories = directories
        self.observer = Observer()
        self.handler = CallbackModel(callback)

    def start(self):
        for directory in self.directories:
            self.observer.schedule(self.handler, directory, recursive=True)
        self.observer.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()
