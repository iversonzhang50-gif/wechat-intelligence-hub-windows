# Windows compatibility modifications: 2026-09-06. AGPL-3.0-only; see WINDOWS-CHANGES.md.
"""Windows ACL support for private local Reader material; no secret values logged."""
from pathlib import Path
import os

def _security():
    import win32api, win32con, win32security
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    finally:
        token.Close()
    return win32security, sid

def restrict(path):
    ws, sid = _security()
    path = Path(path)
    acl = ws.ACL()
    flags = 3 if path.is_dir() else 0
    for principal in (sid, ws.ConvertStringSidToSid('S-1-5-18'), ws.ConvertStringSidToSid('S-1-5-32-544')):
        acl.AddAccessAllowedAceEx(ws.ACL_REVISION, flags, 0x1F01FF, principal)
    ws.SetNamedSecurityInfo(str(path), ws.SE_FILE_OBJECT,
        ws.DACL_SECURITY_INFORMATION | ws.PROTECTED_DACL_SECURITY_INFORMATION,
        None, None, acl, None)

def safe(path):
    if not Path(path).exists():
        return True
    try:
        ws, sid = _security()
        allowed = {ws.ConvertSidToStringSid(sid), 'S-1-5-18', 'S-1-5-32-544'}
        sd = ws.GetNamedSecurityInfo(str(path), ws.SE_FILE_OBJECT, ws.DACL_SECURITY_INFORMATION)
        acl = sd.GetSecurityDescriptorDacl()
        if acl is None:
            return False
        for index in range(acl.GetAceCount()):
            ace = acl.GetAce(index)
            if ace[0][0] == ws.ACCESS_ALLOWED_ACE_TYPE and not (ace[0][1] & 8):
                if ws.ConvertSidToStringSid(ace[-1]) not in allowed and ace[1] & 0xF01FF:
                    return False
            elif ace[0][0] not in (ws.ACCESS_ALLOWED_ACE_TYPE, ws.ACCESS_DENIED_ACE_TYPE):
                return False
        return True
    except Exception:
        return False
