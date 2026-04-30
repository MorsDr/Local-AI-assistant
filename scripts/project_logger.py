import logging
import sys
import glob
from datetime import datetime
from utils import dir_existing
class Logger_Manager:
    def __init__(self, log_dir=dir_existing("Logs"), max_logs=5):
        self.log_dir=log_dir
        self.max_logs=max_logs
        self.start_time=datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.it_crash=False

    def _get_log_path(self, is_crash=False):
        prefix="crash_log" if is_crash else "log"
        filename=f"{prefix}_{self.start_time}.txt"
        return os.path.join(self.log_dir, filename)

    def setup_logging(self):
        log_path=self._get_log_path(is_crash=False)
        logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s", handlers=[logging.FileHandler(log_path, encodinf='utf-8'), logging.StreamHandler(sys.stdout)])
        self._rotate_logs()
        
    def mark_as_crash(self):
        if is_crash:
            return
        self.is_crash=True
        old_path=self._get_log_path(is_crash=False)
        new_path=self._get_log_path(is_crash=True)
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)

        if os.path.exists(old_path):
            with open(old_path, "r", encoding='utf-8') as f:
                content=f.read()
            with open(new_path, "w", encoding='utf-8') as f:
                f.write("----------------CRASH LOG - SYSTEM FALURE----------------\n")
                f.write(content)
            os.remove(old_path)
        logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s", handler=[logging.FileHandler(new_path, encoding='utf-8'), logging.StreamHandler(sys.stdout)])

    def _rotate_logs(self):
        pattern=os.path.join(self.log_dir, "log_*.txt")
        existing_logs=sorted(glob.glob(pattern), key=os.path.getmtime)
        while len(existing_logs) >= self.max_logs:
            os.remove(existing_logs.pop(0))

logger=Logger_Manager()
def init_logging():
    logger.setup_logging
