import pandas as pd
import os
import json

def save_to_csv(data, filename):
    df = pd.DataFrame(data)
    filepath = os.path.join('static', filename)
    df.to_csv(filepath, index=False)
    return filepath

def save_to_json(data, filename):
    filepath = os.path.join('static', filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return filepath 