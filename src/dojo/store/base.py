from .engine import StorageEngine

class BaseRepository:
    def __init__(self, engine: StorageEngine):
        self.engine = engine
