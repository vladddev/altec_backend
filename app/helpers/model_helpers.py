import json
from datetime import datetime


def add_history_action_to_model(model, action_str):
    if hasattr(model, 'actions_json'):
        actions_json = model.actions_json
        if actions_json == "":
            json_log = list()
        else:
            json_log = json.loads(actions_json)
        
        timestamp = round(datetime.now().timestamp())
        
        json_log.append({
            'timestamp': timestamp,
            'action': action_str
        })
        
        new_log = json.dumps(json_log)

        model.actions_json = new_log
        model.save(update_fields=['actions_json'])








