"""Time formatting utilities for displaying audio durations."""


def format_seconds(seconds: float) -> str:
    """Format seconds to mm:ss string.
    
    Args:
        seconds: Time in seconds (float).
        
    Returns:
        Formatted string like "3:45" or "12:04".
    """
    if seconds < 0:
        seconds = 0
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def parse_time_str(time_str: str) -> float:
    """Parse a mm:ss string back to seconds.
    
    Args:
        time_str: String in format "m:ss" or "mm:ss".
        
    Returns:
        Total seconds as float.
    """
    if ":" not in time_str:
        try:
            return float(time_str)
        except ValueError:
            return 0.0
    parts = time_str.strip().split(":")
    try:
        minutes = int(parts[0])
        seconds = float(parts[1]) if len(parts) > 1 else 0.0
        return minutes * 60 + seconds
    except (ValueError, IndexError):
        return 0.0
