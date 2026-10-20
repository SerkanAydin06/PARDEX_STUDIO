"""Project-local read-only metadata check; no 3rd-party shell execution."""
import json
import urllib.request
SOURCES=('godotengine/godot','flutter/flutter','openai/codex','google-gemini/gemini-cli','anthropics/claude-code')
for repo in SOURCES:
 try:
  req=urllib.request.Request('https://api.github.com/repos/'+repo+'/releases/latest',headers={'User-Agent':'ultra-pro-studio-project'})
  with urllib.request.urlopen(req,timeout=6) as response:data=json.load(response)
  link=str(data.get('html_url',''))
  if not link.startswith('https://github.com/'+repo+'/releases/'):
   raise ValueError('Unknown release URL')
  print(repo,'release',str(data.get('tag_name'))[:60],link)
 except Exception as e:
  print(repo,'could not check',type(e).__name__)
print('Info only; no automatic installation or tool execution.')
