class classproperty:
    def __init__(self, func):
        self.func = func
    def __get__(self, instance, owner):
        return self.func(owner)

def log_msg(msg: str, prefix: str = '') -> str:
    return f'[{prefix}] {msg}'