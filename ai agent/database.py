import json
import os
from typing import Dict, Any, List, Optional
from uuid import uuid4
from datetime import datetime, timezone

DB_FILE = "db.json"

class SimpleDB:
    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file
        self._ensure_db()

    def _ensure_db(self):
        if not os.path.exists(self.db_file):
            with open(self.db_file, "w") as f:
                json.dump([], f)

    def _read_db(self) -> List[Dict[str, Any]]:
        try:
            with open(self.db_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_db(self, data: List[Dict[str, Any]]):
        with open(self.db_file, "w") as f:
            json.dump(data, f, indent=2)

    def save_application(self, application: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read_db()
        if "id" not in application:
            application["id"] = str(uuid4())[:8]  # Short ID for readability
        if "timestamp" not in application:
            application["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Ensure status is set
        if "status" not in application:
            application["status"] = "pending_ai"
            
        data.append(application)
        self._write_db(data)
        return application

    def get_application(self, app_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_db()
        for app in data:
            if app.get("id") == app_id:
                return app
        return None

    def get_all_applications(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        data = self._read_db()
        if status:
            return [app for app in data if app.get("status") == status]
        return data

    def update_application(self, app_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = self._read_db()
        for i, app in enumerate(data):
            if app.get("id") == app_id:
                data[i].update(updates)
                self._write_db(data)
                return data[i]
        return None
