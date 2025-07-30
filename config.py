import yaml

def load_config(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def save_config(path, config):
    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
