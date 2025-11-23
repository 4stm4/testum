import uuid
import datetime


class InMemoryStorage:
    def __init__(self):
        self.reset()

    def reset(self):
        self.keys = {}
        self.platforms = {}
        self.scripts = {}
        self.automations = {}

    # SSH Keys
    def create_key(self, name: str, public_key: str):
        key_id = str(uuid.uuid4())
        record = {
            "id": key_id,
            "name": name,
            "public_key": public_key,
            "created_at": datetime.datetime.utcnow().isoformat(),
        }
        self.keys[key_id] = record
        return record

    def list_keys(self):
        return list(self.keys.values())

    def delete_key(self, key_id: str):
        return self.keys.pop(key_id, None)

    # Platforms
    def create_platform(self, data: dict):
        platform_id = str(uuid.uuid4())
        record = {
            "id": platform_id,
            **data,
            "created_at": datetime.datetime.utcnow().isoformat(),
        }
        self.platforms[platform_id] = record
        return record

    def list_platforms(self):
        return list(self.platforms.values())

    def get_platform(self, platform_id: str):
        return self.platforms.get(platform_id)

    def delete_platform(self, platform_id: str):
        return self.platforms.pop(platform_id, None)

    # Scripts
    def create_script(self, data: dict):
        script_id = str(uuid.uuid4())
        now = datetime.datetime.utcnow().isoformat()
        record = {
            "id": script_id,
            "created_at": now,
            "updated_at": now,
            **data,
        }
        self.scripts[script_id] = record
        return record

    def update_script(self, script_id: str, updates: dict):
        if script_id not in self.scripts:
            return None
        self.scripts[script_id].update(updates)
        self.scripts[script_id]["updated_at"] = datetime.datetime.utcnow().isoformat()
        return self.scripts[script_id]

    def get_script(self, script_id: str):
        return self.scripts.get(script_id)

    def list_scripts(self):
        return list(self.scripts.values())

    def delete_script(self, script_id: str):
        return self.scripts.pop(script_id, None)

    # Automations
    def create_automation(self, data: dict):
        automation_id = str(uuid.uuid4())
        now = datetime.datetime.utcnow().isoformat()
        record = {"id": automation_id, "created_at": now, "updated_at": now, **data}
        self.automations[automation_id] = record
        return record

    def update_automation(self, automation_id: str, updates: dict):
        if automation_id not in self.automations:
            return None
        self.automations[automation_id].update(updates)
        self.automations[automation_id]["updated_at"] = datetime.datetime.utcnow().isoformat()
        if self.automations[automation_id].get("run_on_all_platforms"):
            self.automations[automation_id]["target_platform_ids"] = []
        return self.automations[automation_id]

    def get_automation(self, automation_id: str):
        return self.automations.get(automation_id)

    def list_automations(self):
        return list(self.automations.values())

    def delete_automation(self, automation_id: str):
        return self.automations.pop(automation_id, None)


storage = InMemoryStorage()
