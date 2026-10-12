from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
P=Path(__file__).resolve().parent / 'cmd' / 'beacon' / 'assets'
F='/usr/share/fonts/truetype' 
fonts={
  'regular':'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
  'medium':'/usr/share/fonts/opentype/inter/Inter-Medium.otf',
  'semibold':'/usr/share/fonts/opentype/inter/Inter-SemiBold.otf',
  'bold':'/usr/share/fonts/opentype/inter/Inter-Bold.otf',
  'display':'/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf'
}
for k,p in fonts.copy().items():
 if not Path(p).exists(): fonts[k]='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
S=3
BG='#F3F6FC'; WHITE='#FFFFFF'; NAVY='#09172D';NAVY2='#132541'; TXT='#11223F'; MUTED='#6C819E'; BLUE='#1479F7'; SKY='#17B2FA'; PALE='#ECF4FF'; BORDER='#E4EBF5';GREEN='#15B985'

def font(size,weight='regular'):return ImageFont.truetype(fonts[weight],size*S)
def xy(*vals):return tuple(round(v*S) for v in vals)
def rr(d,box,r,fill,outline=None,width=1):
 d.rounded_rectangle(xy(*box),radius=r*S,fill=fill,outline=outline,width=width*S)
def text(d,point,msg,size,fill=TXT,weight='regular'):
 d.text(xy(*point),msg,font=font(size,weight),fill=fill,stroke_width=0)
def line(d,points,fill,width=1,joint='curve'):d.line([xy(*p) for p in points],fill=fill,width=width*S,joint=joint)
def oval(d,box,fill,outline=None,width=1):d.ellipse(xy(*box),fill=fill,outline=outline,width=width*S)
def new(name,w,h):
 im=Image.new('RGB',(w*S,h*S),BG);d=ImageDraw.Draw(im)
 d.rectangle(xy(0,0,w,201 if name=='login' else 176 if name in ('roster','directory') else 155),fill=NAVY)
 return im,d

def panel(im,box,r=20,shadow=True,fill=WHITE):
 if shadow:
  over=Image.new('RGBA',im.size,(0,0,0,0)); od=ImageDraw.Draw(over)
  od.rounded_rectangle(xy(box[0],box[1]+4,box[2],box[3]+7),radius=r*S, fill=(18,49,89,34))
  over=over.filter(ImageFilter.GaussianBlur(10*S))
  im.paste(over,(0,0),over)
 d=ImageDraw.Draw(im);rr(d,box,r,fill,BORDER)
 return d

def brand(im,d,mode='full'):
 logo=Image.open(P/'logo-mark.png').convert('RGBA')
 logo=logo.resize(xy(53,72),Image.Resampling.LANCZOS)
 # resize from thumbnail preserves preexisting rgb alpha
 x=24 if mode!='chat' else 26;y=22 if mode!='chat' else 23
 im.paste(logo,xy(x,y),logo)
 d=ImageDraw.Draw(im)
 text(d,(99 if mode!='chat' else 98,24),'Beacon',27,WHITE,'display')
 text(d,(101 if mode!='chat' else 100,64),'M E S S E N G E R',9,'#82BFFF','bold')
 oval(d,(443,39,450,46),GREEN)


def decorations(d,w):
 # subtle network constellations, fewer visual distractions
 for cx,cy,r in [(376,112,52),(438,124,85),(400,131,24)]:
  oval(d,(cx-r,cy-r,cx+r,cy+r),None,'#203655',1)
 for cx,cy in [(338,118),(423,87),(452,144)]:oval(d,(cx-2,cy-2,cx+2,cy+2),'#346FBA')

def footer(d,w,h,caption='YOUR CONVERSATIONS. YOUR NETWORK.'):
 line(d,[(24,h-37),(w-24,h-37)],BORDER)
 oval(d,(27,h-24,33,h-18),GREEN)
 text(d,(42,h-28),caption,9,MUTED,'semibold')
 text(d,(w-99,h-28),'BEACON / GO',9,MUTED,'semibold')

def login():
 im,d=new('login',480,760);decorations(d,480);brand(im,d)
 d=ImageDraw.Draw(im)
 text(d,(30,116),'Stay close.',28,WHITE,'display')
 text(d,(31,154),'On your own network.',16,'#BCD0EB','medium')
 line(d,[(0,199),(480,199)],BLUE,3)
 d=panel(im,(18,214,462,692),22)
 text(d,(46,236),'Welcome back',24,TXT,'display')
 text(d,(47,273),'Sign in to your private messenger.',12,MUTED,'medium')
 for label,y in [('SERVER ADDRESS',324),('USERNAME',406),('PASSWORD',488)]:
  text(d,(50,y),label,10,'#607796','bold')
 for y in [347,429,511]:rr(d,(47,y,433,y+50),12,WHITE,BORDER,1)
 rr(d,(47,584,433,638),13,BLUE)
 text(d,(188,601),'Sign in',16,WHITE,'bold')
 # arrow circle at end of button
 oval(d,(389,595,422,628),'#2E8FFF');line(d,[(402,606),(409,612),(402,618)],WHITE,2)
 rr(d,(46,648,434,677),9,'#F4F8FE')
 oval(d,(56,658,65,667),GREEN)
 footer(d,480,760,'SECURE SIGN IN   ·   SELF HOSTED')
 return im

def roster():
 im,d=new('roster',480,760);decorations(d,480);brand(im,d)
 d=ImageDraw.Draw(im)
 text(d,(28,111),'Your people',27,WHITE,'display')
 text(d,(29,151),'One network. Every conversation.',11,'#BCD0EB','medium')
 line(d,[(0,175),(480,175)],BLUE,3)
 d=panel(im,(18,167,462,263),19)
 oval(d,(39,175,110,246),'#EDF4FF')
 text(d,(119,181),'SIGNED IN AS',9,MUTED,'bold')
 # dynamic name and account below
 # tab controls
 for x,w in [(20,101),(127,101),(234,101),(341,119)]:rr(d,(x,281,x+w,325),11,PALE)
 text(d,(369,293),'Sign out',12,TXT,'semibold')
 rr(d,(21,341,322,391),13,WHITE,BORDER)
 # search icon
 oval(d,(39,358,50,369),None,MUTED,2)
 line(d,[(48,368),(55,375)],MUTED,2)
 rr(d,(331,341,459,391),13,BLUE)
 text(d,(349,355),'+ Add buddy',12,WHITE,'semibold')
 text(d,(26,405),'MY BUDDIES',10,'#1D78E8','bold')
 text(d,(372,405),'ALL CONTACTS',9,MUTED,'semibold')
 # rows dynamic, shadowless clean. no fake placeholder rows.
 footer(d,480,760,'PRIVATE MESSAGING   ·   LAN CONNECTED')
 return im

def chat():
 im,d=new('chat',700,680)
 d=ImageDraw.Draw(im)
 for cx,cy,r in [(600,105,40),(651,85,60)]:oval(d,(cx-r,cy-r,cx+r,cy+r),None,'#1F3755',1)
 brand(im,d,'chat')
 # upper right security indicator
 rr(d,(550,32,665,60),14,'#182F4B')
 oval(d,(566,41,576,51),GREEN)
 text(d,(584,36),'CONNECTED',10,'#B3D9FF','semibold')
 line(d,[(0,154),(700,154)],BLUE,3)
 d=panel(im,(18,173,682,528),20)
 text(d,(40,188),'MESSAGES',10,'#7388A6','bold')
 line(d,[(40,209),(660,209)],BORDER)
 # time divider
 text(d,(324,220),'RECENT',9,MUTED,'semibold')
 d=panel(im,(18,541,682,668),18,shadow=False)
 text(d,(39,552),'MESSAGE',10,'#7388A6','bold')
 rr(d,(39,577,531,636),13,'#F8FAFE',BORDER)
 rr(d,(542,577,665,636),13,BLUE)
 text(d,(573,592),'Send',15,WHITE,'bold')
 oval(d,(629,594,653,618),'#318BFC')
 line(d,[(636,606),(646,606),(642,601)],WHITE,2)
 text(d,(40,646),'ENTER TO SEND  ·  SCROLL FOR HISTORY',9,'#8092AD','semibold')
 return im

def directory():
 im,d=new('directory',480,600);decorations(d,480);brand(im,d)
 d=ImageDraw.Draw(im)
 text(d,(29,111),'Find your people',24,WHITE,'display')
 text(d,(30,150),'Add someone from your private server.',11,'#BCD0EB','medium')
 line(d,[(0,175),(480,175)],BLUE,3)
 d=panel(im,(18,194,462,572),20)
 text(d,(43,218),'PEOPLE ON YOUR SERVER',10,'#607796','bold')
 line(d,[(38,247),(443,247)],BORDER)
 return im

for name,fun in [('login',login),('roster',roster),('chat',chat),('directory',directory)]:
 im=fun();out=im.resize((im.width//S,im.height//S),Image.Resampling.LANCZOS)
 out.save(P/(name+'.png'),optimize=True)
 print(name,out.size,(P/(name+'.png')).stat().st_size)
