from pathlib import Path
import re
p=Path('/voice/FunASR/runtime/websocket/bin/funasr-wss-server.cpp')
s=p.read_text()
s,n=re.subn(r'int ret = system\((python_cmd_\w+\.c_str\(\))\);',r'int ret = std::getenv("DUIX_ASR_OFFLINE") ? 0 : system(\1);',s)
assert n in (0,5),n
if n:
 s='#include <cstdlib>\n'+s;p.write_text(s)
print({'download_commands_guarded':n,'behavior':'local model existence checks unchanged'})
