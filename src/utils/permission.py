import stat, logging
from pathlib import Path

def check_and_fix_path_permissions(target_path: Path) -> bool:
    parts = target_path.parts
    current_path = Path(parts[0])
    
    for part in parts[1:]:
        current_path = current_path / part
        current_path.mkdir(0o711, exist_ok=True)
        
        try:
            st = current_path.stat()
        except FileNotFoundError:
            logging.error(f"Path does not exist: {current_path}")
            return False
        except PermissionError:
            logging.error(f"Permission denied: {current_path}")
            return False
        
        mode = stat.S_IMODE(st.st_mode)
        
        # Check if permissions are at least 711 (rwx--x--x)
        owner_ok = (mode & stat.S_IRWXU) == stat.S_IRWXU
        group_exec = (mode & stat.S_IXGRP) != 0
        others_exec = (mode & stat.S_IXOTH) != 0
        
        if not (owner_ok and group_exec and others_exec):
            logging.info(f"Fixing permissions on {current_path} from {oct(mode)} to 0o711")
            try:
                current_path.chmod(0o711)
            except PermissionError:
                logging.error(f"Failed to chmod {current_path}: permission denied")
                return False
            
    return True