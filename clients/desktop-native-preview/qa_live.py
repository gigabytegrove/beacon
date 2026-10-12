import os, time, subprocess, threading, json, socket, urllib.parse, sys, shutil
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parent
LOG=[]
MESSAGES=[dict(id=1,sender_id=2,recipient_id=1,body='Hey! Are you around this evening?',created_at=1791764200),dict(id=2,sender_id=1,recipient_id=2,body='Absolutely. Everything is looking great!',created_at=1791764300)]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,status,obj):
  raw=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  path=urllib.parse.urlparse(self.path).path;LOG.append(('GET',path))
  if path=='/api/buddies': self.send(200,[{'id':2,'username':'alex','display_name':'Alex Morgan','status_text':'Online and available','presence':'available','unread_count':1,'group_name':'Friends','muted':0},{'id':3,'username':'sarah','display_name':'Sarah Chen','status_text':'Away for a bit','presence':'away','unread_count':0,'group_name':'Family','muted':0}])
  elif path=='/api/groups':self.send(200,[])
  elif path=='/api/messages/2':self.send(200,MESSAGES)
  elif path=='/api/typing/2':self.send(200,{'active':False})
  elif path=='/api/directory':self.send(200,[{'id':3,'username':'sarah','display_name':'Sarah Chen'}])
  else:self.send(404,{'detail':'No such route'})
 def do_POST(self):
  path=urllib.parse.urlparse(self.path).path
  data=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}');LOG.append(('POST',path,data))
  if path=='/api/login':self.send(200,{'token':'test-only-token','user':{'id':1,'username':'tester','display_name':'Jordan Taylor','status_text':'','is_admin':True}})
  elif path=='/api/presence':self.send(200,{'ok':True})
  elif path=='/api/messages':
   msg={'id':len(MESSAGES)+1,'sender_id':1,'recipient_id':2,'body':data.get('body',''),'created_at':1791764500};MESSAGES.append(msg);self.send(201,msg)
  elif path=='/api/typing/2':self.send(200,{'ok':True})
  elif path=='/api/conversations/2/read':self.send(200,{'ok':True})
  else:self.send(404,{'detail':'No such route'})
http=ThreadingHTTPServer(('127.0.0.1',8765),Handler)
threading.Thread(target=http.serve_forever,daemon=True).start()
if 'DISPLAY' not in os.environ:os.environ['DISPLAY']=':99'
os.environ['XAUTHORITY']=str(ROOT/'qa-xauthority')
open(os.environ['XAUTHORITY'],'ab').close()
xvfb=subprocess.Popen(['Xvfb',os.environ['DISPLAY'],'-screen','0','1600x960x24','-nolisten','tcp'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
try:
 time.sleep(.8)
 import pyautogui
 from pyautogui import click,write,press
 shutil.rmtree(ROOT/'qa-config',ignore_errors=True)
 app=subprocess.Popen([str(ROOT/'Beacon-Messenger-Linux-x64')],env={**os.environ,'XDG_CONFIG_HOME':str(ROOT/'qa-config')},stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 time.sleep(1.2)
 def snap(stage,x,y,w,h):
  path=ROOT/'previews'/('live-'+stage+'.png');(ROOT/'previews'/'desktop.png').unlink(missing_ok=True);scrot=subprocess.run(['scrot','-z',str(ROOT/'previews'/'desktop.png')],env=os.environ,capture_output=True)
  if scrot.returncode:raise RuntimeError(scrot.stderr.decode())
  im=Image.open(ROOT/'previews'/'desktop.png');im.crop((x,y,x+w,y+h)).save(path);print('SCREEN',path,flush=True)
 snap('login',130,75,480,760)
 click(130+100,75+371);write('http://127.0.0.1:8765',0.005)
 click(130+100,75+450);write('tester',.03)
 click(130+100,75+533);write('testing-password',.015)
 click(130+220,75+609)
 time.sleep(2.6)
 snap('roster',130,75,480,760)
 print('wmctrl:',subprocess.run(['wmctrl','-lG'],text=True,capture_output=True).stdout,flush=True)
 # buddy row, opens separate native chat window at x200 y105
 click(130+175,75+454)
 time.sleep(2.1)
 snap('chat',200,105,700,680)
 click(200+160,105+606);write('Nice to see the updated design!',.008);press('enter')
 time.sleep(1.5)
 snap('chat-sent',200,105,700,680)
 sent=[x for x in LOG if x[0]=='POST' and x[1]=='/api/messages']
 print('SENDS',sent,'GETS',len(LOG),flush=True)
 if not sent or sent[-1][2].get('body')!='Nice to see the updated design!': raise RuntimeError('Failed to send through live UI')
 assert app.poll() is None,app.poll()
 print('PASS: Linux GUI live sign-in, buddy list, pop-up IM, and send over simulated HTTP server',flush=True)
 app.terminate();app.wait(timeout=5)
except Exception as e:
 print('ERROR',repr(e),flush=True)
 raise
finally:
 http.shutdown();xvfb.terminate();xvfb.wait(timeout=5)
