
def simple_filter(msg: str) -> float:
    if "optimi" in msg:
        return 90
    elif "improv" in msg:
        return 80
    return 0

