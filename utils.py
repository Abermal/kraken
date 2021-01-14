def format_time(seconds):
    if seconds < 60:
        msg = f"{int(seconds)}sec."
    elif seconds < 3600:
        s = seconds % 60
        s_str = " sec." if s > 0 else ""
        s = s if s > 0 else ""
        msg = f"{seconds // 60}min. {s}{s_str}"
    elif seconds < 24 * 3600:
        h = seconds // 3600
        m = (seconds - 3600 * h)
        m_str = " min." if m > 0 else ""
        s = (seconds - h * 3600 - m * 60)
        s_str = " sec." if s > 0 else ""
        m = m if m > 0 else ""
        s = s if s > 0 else ""
        msg = f"{h}h. {m}{m_str} {s}{s_str}"
    else:
        raise ValueError(f"time should be <= {24 * 60 * 60}.")
    return msg


def round_clip(a, clip):
    return round(float(a) / clip) * clip


def roundpr(price):
    return round(float(price), 2)

def format_interval_name(interval: str) -> str:
    try:
        return format_time(int(interval)).strip()
    except ValueError:
        return interval