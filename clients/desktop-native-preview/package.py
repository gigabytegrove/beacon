from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import zipfile,tarfile,hashlib,shutil,subprocess,os
ROOT=Path(__file__).resolve().parent;DEST=ROOT/'dist';DEST.mkdir(parents=True, exist_ok=True);P=ROOT/'previews'
# Product overview: screenshots of the actual Go renderer, with the live
# Linux IM screenshot used for the chat panel.
W,H=1920,1080
bg=Image.new('RGB',(W,H),'#EEF3F9');d=ImageDraw.Draw(bg)
F='/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf';F2='/usr/share/fonts/opentype/inter/Inter-Medium.otf'
if not Path(F).exists():F='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
if not Path(F2).exists():F2='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font=lambda pt,bold=False:ImageFont.truetype(F if bold else F2,pt)
d.text((84,47),'BEACON / PREMIUM DESKTOP',font=font(33,True),fill='#0B203E')
d.text((85,101),'A real Go messenger · One shared Windows + Linux interface',font=font(19),fill='#71849C')
d.rounded_rectangle((84,145,1838,150),3,fill='#1479F7')
inputs=[(P/'login.png','WELCOME BACK',84,217,1.00),(P/'roster.png','THE BUDDY LIST',591,217,1.00),(P/'live-chat-sent.png','PRIVATE CONVERSATION',1104,217,.96)]
for path,caption,x,y,scale in inputs:
 image=Image.open(path).convert('RGB')
 wi,hi=image.size;new=(int(wi*scale),int(hi*scale));image=image.resize(new,Image.Resampling.LANCZOS)
 outer=(x-7,y-7,x+new[0]+7,y+new[1]+7)
 shadow=Image.new('RGBA',bg.size);sd=ImageDraw.Draw(shadow);sd.rounded_rectangle((outer[0]+3,outer[1]+5,outer[2]+10,outer[3]+14),20,fill=(10,26,50,70))
 shadow=shadow.filter(ImageFilter.GaussianBlur(16));bg=Image.alpha_composite(bg.convert('RGBA'),shadow)
 bg.paste(image,(x,y));d=ImageDraw.Draw(bg)
 d.rounded_rectangle((outer[0],outer[1],outer[2],outer[3]),10,outline='#CEDCEC',width=2)
 d.text((x,y+new[1]+22),caption,font=font(17,True),fill='#15304D')
 d.text((x,y+new[1]+48),'Native Go · no Python runtime',font=font(13),fill='#71849C')
d=ImageDraw.Draw(bg)
d.text((84,1043),'Visual snapshots from the shared Go renderer; chat flow smoke-tested on Linux/X11.',font=font(15),fill='#6B809A')
preview_path=DEST/'Beacon-Messenger-Premium-Desktop-Overview-20261011.png'
bg.convert('RGB').save(preview_path,optimize=True)
# Android kit docs
kit=ROOT/'android-kit'
(kit/'README-PREMIUM.md').write_text('''# Beacon Messenger / Premium Android UI resources

This directory is a *native Android XML resource kit*, not a compiled APK and not
an independently functioning Android client. It is intended for integration into
the existing native Java Beacon app.

Improvements from the previous UI kit: exact navy/blue/surface tokens shared
with Windows/Linux, card and field styles, selectable filled presence chips,
press-state buddy rows, presence dots and an explicit reusable buddy-row layout.
All 13 XML documents were checked for well-formedness. No Android SDK or Java
app build exists in this offline environment, so no runtime compatibility
claim is made.

Copy the app/src/main/res/ resources into the Android app, wire the supplied
layout IDs into its activity/adapters, then compile/test with Android Studio.
Do not replace an existing resource that was customized for other purposes
without reviewing it first.
''')
android_zip=DEST/'Beacon-Messenger-Android-Premium-UI-Kit-20261011.zip'
with zipfile.ZipFile(android_zip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
 for file in sorted(kit.rglob('*')):
  if file.is_file():z.write(file,file.relative_to(kit))
# distro readme
(ROOT/'RELEASE-NOTES.md').write_text('''# Beacon Messenger — Premium Native Desktop Test Build

**Build date:** 2026-10-11 · Go / Win32 Windows x64 · Go / X11 Linux x64

## Substantial user-interface changes

- Replaced all four screen backgrounds with a new premium navy/blue brand system,
  Inter-based high-resolution raster typography, elevated white surfaces,
  generous spacing, and unified connection/status language.
- Stronger login hero, structured form and focus ring, inline friendly network
  error handling, clear primary action and no localhost hard-coded default.
- Rebuilt AIM buddy list: personal profile, grouped buddy/status context,
  active state chips, real searchable roster, unread badges, colored presence,
  empty/onboarding states (no dummy contact rows), contextual hover states.
- Rebuilt private IM: header with buddy name/presence, incoming/outgoing
  messages with timestamps, multi-line wrapping, scrolling to earlier history,
  composer, typing state and hover response on send.
- Redesigned directory rows, plus real hover/focus states wired on Windows
  WM_MOUSEMOVE and Linux X11 MotionNotify.
- Included an improved Android **UI resource kit only**, not an APK.

## Technical implementation

All desktop rendering and input management are written in Go and shared by
Windows and Linux; platform windows use native Win32 and X11 bindings.
No Go, Python, Fyne, Node or Java runtime is required by a recipient of
these compiled desktop binaries. The Linux application needs the host's
libX11 runtime and a working X11-compatible graphical display.

This is a **test build**. It is not the complete earlier Fyne/Java
feature-parity roadmap: OS notifications, secure saved tokens, system tray,
rich profile/device managers and signed installers remain outstanding.
The Go client only saves a nonsecret server URL preference.

## Verification

- Go test suite `go test -race -count=1 ./...`: **passed**
- `go vet ./...`: **passed**
- Windows x64 Win32 GUI: **cross-compiled**, PE32+ format verified;
  **not launched on a Windows computer** in this session.
- Linux x64 X11 GUI: **built and smoke-tested under Xvfb** with a
  simulated API, including signing in, opening a buddy IM, and sending
  `Nice to see the updated design!` (recorded as POST /api/messages).
- Android: XML checked for well-formedness, **no APK built**.
- No GitHub operations performed in this pass.

## Configuration

The server URL must point to a real Dokploy Beacon host, e.g.
`http://192.168.1.50:8765` (replace with your own address). The
address `127.0.0.1` refers to the computer running the desktop client.
Use HTTPS via a proper reverse proxy for networks you don't fully trust.

Source is included with the binaries for verification/reproducibility.
Compiler/font-atlas generation requires Go 1.23 and Linux X11 build headers
when building from source. Installed users do not need source build tools.
''')
# stage tarball with current binary
stage=ROOT/'linux-dist';shutil.copy2(ROOT/'Beacon-Messenger-Linux-x64',stage/'Beacon-Messenger-Linux-x64');shutil.copy2(ROOT/'cmd/beacon/assets/logo-mark.png',stage/'beacon-icon.png');shutil.copy2(ROOT/'RELEASE-NOTES.md',stage/'README.md')
linux_tar=DEST/'Beacon-Messenger-Linux-x64-Premium-20261011.tar.gz'
with tarfile.open(linux_tar,'w:gz') as tar:
 for file in sorted(stage.iterdir()):tar.add(file,arcname='Beacon-Messenger-Linux/'+file.name)
# source zip, no proprietary or raw font files
src_zip=DEST/'Beacon-Messenger-Go-Premium-Source-20261011.zip'
with zipfile.ZipFile(src_zip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
 for base in ['cmd/beacon','internal/beacon']:
  for f in sorted((ROOT/base).rglob('*')):
   if f.is_file():z.write(f,f.relative_to(ROOT))
 for name in ['go.mod','RELEASE-NOTES.md','create_skin.py','qa_live.py']:
  z.write(ROOT/name,name)
 for f in sorted(P.glob('*.png')):
  if f.name!='desktop.png':z.write(f,'previews/'+f.name)
# verification log
report=DEST/'Beacon-Messenger-Premium-Build-Report-20261011.txt'
report.write_text((ROOT/'RELEASE-NOTES.md').read_text()+'\nEXPECTED ARTIFACTS AND HASHES (SHA256)\n')
files=[DEST/'Beacon-Messenger-Windows-x64-Premium-20261011.exe',linux_tar,src_zip,android_zip,preview_path]
for f in files:
 h=hashlib.sha256(f.read_bytes()).hexdigest()
 with report.open('a') as out:out.write(f'{h}  {f.name}  {f.stat().st_size} bytes\n')
checksums=DEST/'Beacon-Messenger-Premium-SHA256-20261011.txt'
checksums.write_text(''.join(f'{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}\n' for f in files))
# full deliverable, filenames and docs included
complete=DEST/'Beacon-Messenger-Premium-Complete-Test-Package-20261011.zip'
with zipfile.ZipFile(complete,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for f in [*files,checksums,report]:z.write(f,f.name)
 for f in [P/'live-login.png',P/'live-roster.png',P/'live-chat-sent.png']:
  z.write(f,'Test-Screenshots/'+f.name)
print('\n'.join(f'{f.name}: {f.stat().st_size/1024/1024:.2f} MiB' for f in [*files,checksums,report,complete]))
