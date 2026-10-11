package main

import (
 "bytes"
 "context"
 _ "embed"
 "encoding/base64"
 "encoding/json"
 "errors"
 "reflect"
 "fmt"
 "image"
 _ "image/jpeg"
 _ "image/png"
 "os"
 "runtime"
 "sort"
 "strings"
 "sync/atomic"
 "time"

 "fyne.io/fyne/v2"
 "fyne.io/fyne/v2/app"
 "fyne.io/fyne/v2/canvas"
 "fyne.io/fyne/v2/container"
 "fyne.io/fyne/v2/dialog"
 "fyne.io/fyne/v2/driver/desktop"
 "fyne.io/fyne/v2/widget"
 "github.com/zalando/go-keyring"
 "github.com/gigabytegrove/beacon/clients/desktop-go/internal/beacon"
)

//go:embed assets/icon.svg
var iconBytes []byte

const keyringService="net.gigabytegrove.beacon"
const keyringUser="desktop-session"
type savedSession struct{ Server string `json:"server"`;Token string `json:"token"` }

func saveLogin(server,token string) error {
 payload,e:=json.Marshal(savedSession{server,token});if e!=nil{return e}
 return keyring.Set(keyringService,keyringUser,string(payload))
}
func restoreLogin()(savedSession,error){
 var s savedSession
 data,e:=keyring.Get(keyringService,keyringUser);if e!=nil{return s,e}
 e=json.Unmarshal([]byte(data),&s);return s,e
}
func clearLogin(){_ = keyring.Delete(keyringService,keyringUser)}
func ctx() (context.Context,context.CancelFunc){return context.WithTimeout(context.Background(),15*time.Second)}

type UI struct{
 app fyne.App
 root fyne.Window
 api *beacon.Client
 me beacon.User
 roster *fyne.Container
 title *widget.Label
 network *widget.Label
 buddies []beacon.Buddy
 groups []beacon.Group
 chats map[int]*Chat
 status atomic.Value
 pollStop chan struct{}
 firstRoster bool
 running atomic.Bool
}
func main(){
 a:=app.NewWithID("net.gigabytegrove.beacon")
 a.SetIcon(&fyne.StaticResource{StaticName:"beacon.svg",StaticContent:iconBytes})
 ui:=&UI{app:a,root:a.NewWindow("Beacon · Buddy List"),chats:map[int]*Chat{}}
 ui.status.Store("available")
 ui.root.Resize(fyne.NewSize(375,670))
 ui.showLogin()
 ui.root.Show()
 go ui.restoreStored()
 a.Run()
}
func(u *UI) async(task func(context.Context)error,after func(error)){
 go func(){ctx,cancel:=ctx();defer cancel();err:=task(ctx);fyne.Do(func(){after(err)})}()
}
func(u *UI) alert(err error){if err!=nil{dialog.ShowError(err,u.root)}}
func(u *UI) showLogin(){
 address:=widget.NewEntry();address.SetPlaceHolder("https://beacon.example.com or http://LAN-IP:8765")
 account:=widget.NewEntry();account.SetPlaceHolder("Username")
 password:=widget.NewPasswordEntry();password.SetPlaceHolder("Password")
 host,_:=os.Hostname();device:=widget.NewEntry();device.SetText("Beacon-"+runtime.GOOS+"-"+host)
 remember:=widget.NewCheck("Remember this device securely (Windows Credential Manager / Linux Secret Service)",nil)
 remember.SetChecked(false)
 info:=widget.NewLabel("Sign in to your self-hosted Beacon messenger.")
 info.Wrapping=fyne.TextWrapWord
 submit:=widget.NewButton("Sign in",func(){
  client,err:=beacon.NewClient(address.Text);if err!=nil{u.alert(err);return}
  if account.Text==""||password.Text==""||device.Text==""{dialog.ShowInformation("Missing information","Please enter a username, password and device name.",u.root);return}
  username,pass,deviceName,save:=account.Text,password.Text,device.Text,remember.Checked
  u.async(func(c context.Context)error{
   result,e:=client.Login(c,username,pass,deviceName);if e!=nil{return e}
   if save{if e=saveLogin(client.Server(),result.Token);e!=nil{ // login still succeeds; user is informed
     fyne.Do(func(){dialog.ShowInformation("Secure storage unavailable","Signed in, but the OS credential vault is unavailable. You'll sign in again next launch.",u.root)})
   }}else{clearLogin()}
   fyne.Do(func(){u.signedIn(client,result.User)})
   return nil
  },u.alert)
 })
 u.root.SetContent(container.NewPadded(container.NewVBox(
  widget.NewLabelWithStyle("◉ BEACON",fyne.TextAlignCenter,fyne.TextStyle{Bold:true}),
  info,widget.NewForm(widget.NewFormItem("Server",address),widget.NewFormItem("Username",account),
   widget.NewFormItem("Password",password),widget.NewFormItem("Device",device)),remember,submit,
  widget.NewLabel("Use HTTPS when connecting outside a trusted LAN."),
 )))
}
func(u *UI) restoreStored(){
 s,err:=restoreLogin();if err!=nil||s.Server==""||s.Token==""{return}
 c,err:=beacon.NewClient(s.Server);if err!=nil{clearLogin();return}
 c.SetToken(s.Token)
 ctx,cancel:=ctx();me,err:=c.Me(ctx);cancel()
 fyne.Do(func(){
  if err!=nil{clearLogin();return}
  if u.api!=nil{return}
  u.signedIn(c,me)
 })
}
func(u *UI) signedIn(client *beacon.Client,me beacon.User){
 u.stopPolling()
 u.api=client;u.me=me;u.buddies=nil;u.groups=nil;u.firstRoster=false
 for _,c:=range u.chats{c.window.Close()}
 u.chats=map[int]*Chat{}
 u.showRoster()
 u.enableTray()
 u.startPolling()
}
func(u *UI) enableTray(){
 if d,ok:=u.app.(desktop.App);ok{
  d.SetSystemTrayIcon(&fyne.StaticResource{StaticName:"beacon.svg",StaticContent:iconBytes})
  d.SetSystemTrayWindow(u.root)
  d.SetSystemTrayMenu(fyne.NewMenu("Beacon",
   fyne.NewMenuItem("Open Buddy List",func(){u.root.Show();u.root.RequestFocus()}),
   fyne.NewMenuItem("Sign Out",u.logout),
   fyne.NewMenuItem("Quit",func(){u.app.Quit()})))
  u.root.SetCloseIntercept(func(){
   if u.app.Preferences().BoolWithFallback("closeToTray",runtime.GOOS=="windows"){u.root.Hide()}else{u.app.Quit()}
  })
 }
}
func(u *UI) showRoster(){
 u.title=widget.NewLabelWithStyle("◉ Beacon",fyne.TextAlignLeading,fyne.TextStyle{Bold:true})
 u.network=widget.NewLabel("Connecting to your server…")
 u.roster=container.NewVBox()
 presence:=widget.NewSelect([]string{"available","away","busy"},func(s string){
  if s==""||u.api==nil{return}
  u.status.Store(s);client:=u.api;u.async(func(c context.Context)error{return client.Presence(c,s)},u.alert)
 })
 presence.SetSelected("available")
 header:=container.NewVBox(u.title,widget.NewLabel(u.me.DisplayName+" · "+u.me.Username),u.network)
 controls:=container.NewGridWithColumns(3,
  widget.NewButton("+ Buddy",u.addBuddy),
  widget.NewButton("+ Group",u.manageGroups),
  widget.NewButton("My Profile",u.editProfile))
 extras:=container.NewGridWithColumns(2,
  widget.NewButton("Profile Photo",u.uploadPhoto),
  widget.NewButton("Change Password",u.changePassword))
 footer:=container.NewGridWithColumns(3,
  widget.NewButton("Devices",u.showSessions),
  widget.NewButton("Preferences",u.showPreferences),
  widget.NewButton("Sign Out",u.logout))
 if u.me.IsAdmin {header.Add(widget.NewButton("Create user account",u.createUser))}
 u.root.SetContent(container.NewBorder(
  container.NewVBox(header,presence,controls,extras),
  footer,nil,nil,container.NewVScroll(u.roster),
 ))
 u.root.SetTitle("Beacon · Buddy List")
}
func(u *UI) startPolling(){
 stop:=make(chan struct{});u.pollStop=stop
 client:=u.api
 go func(){
  tick:=time.NewTicker(3500*time.Millisecond);defer tick.Stop()
  for {
   select{case <-stop:return;default:}
   c,cancel:=ctx()
   status:=u.status.Load().(string)
   _=client.Presence(c,status)
   friends,err:=client.Buddies(c)
   groups,e2:=client.Groups(c)
   cancel()
   if err==nil&&e2==nil{
    fyne.Do(func(){if u.api!=client{return};u.applyRoster(friends,groups)})
   }else{
    if err==nil{err=e2}
    fyne.Do(func(){
     if u.api!=client{return}
     if errors.Is(err,beacon.ErrUnauthorized){
      u.stopPolling()
      clearLogin()
      u.api=nil
      for _,chat:=range u.chats{chat.window.Close()}
      u.chats=map[int]*Chat{}
      u.root.SetCloseIntercept(nil)
      u.showLogin()
      dialog.ShowInformation("Beacon session expired","This device was signed out or its session expired. Please sign in again.",u.root)
      return
     }
     if u.network!=nil{u.network.SetText("Connection problem: "+err.Error())}
    })
   }
   select{case <-stop:return;case <-tick.C:}
  }
 }()
}
func(u *UI) stopPolling(){if u.pollStop!=nil{close(u.pollStop);u.pollStop=nil}}
func(u *UI) applyRoster(newBuddies []beacon.Buddy,newGroups []beacon.Group){
 old:=map[int]beacon.Buddy{}
 for _,b:=range u.buddies{old[b.ID]=b}
 for _,b:=range newBuddies{
  if prev,exists:=old[b.ID];exists&&u.firstRoster&&!bool(b.Muted){
   if prev.Presence=="offline"&&b.Presence!="offline"{
    u.app.SendNotification(fyne.NewNotification("Beacon · Buddy signed on",b.Name()+" is online"))
   }
   if b.UnreadCount>prev.UnreadCount {
    u.app.SendNotification(fyne.NewNotification("Beacon · New IM",b.Name()+" sent a message"))
    if u.app.Preferences().BoolWithFallback("autoOpenIM",false){u.openChat(b)}
   }
  }
 }
 unchanged:=reflect.DeepEqual(u.buddies,newBuddies)&&reflect.DeepEqual(u.groups,newGroups)&&u.firstRoster
 u.buddies=newBuddies;u.groups=newGroups;u.firstRoster=true
 if u.network!=nil{u.network.SetText("● Connected to "+u.api.Server())}
 // Preserve scroll position and avoid allocating hundreds of widgets on every poll.
 if unchanged{return}
 u.roster.RemoveAll()
 sorted:=append([]beacon.Buddy(nil),newBuddies...)
 sort.Slice(sorted,func(i,j int)bool{
  if sorted[i].Presence=="offline"&&sorted[j].Presence!="offline"{return false}
  if sorted[j].Presence=="offline"&&sorted[i].Presence!="offline"{return true}
  return strings.ToLower(sorted[i].Name())<strings.ToLower(sorted[j].Name())
 })
 allGroups:=[]beacon.Group{{ID:0,Name:"Buddies"}}
 allGroups=append(allGroups,newGroups...)
 for _,g:=range allGroups {
  var peers []beacon.Buddy
  online:=0
  for _,b:=range sorted{
   id:=0;if b.GroupID!=nil{id=*b.GroupID}
   if id==g.ID{peers=append(peers,b);if b.Presence!="offline"{online++}}
  }
  if len(peers)==0&&g.ID==0&&len(newGroups)>0{continue}
  u.roster.Add(widget.NewLabelWithStyle(fmt.Sprintf("%s (%d online / %d)",g.Name,online,len(peers)),
   fyne.TextAlignLeading,fyne.TextStyle{Bold:true}))
  for _,b:=range peers{
   buddy:=b
   mark:="○";if b.Presence=="available"{mark="●"}else if b.Presence!="offline"{mark="◐"}
   name:=fmt.Sprintf("%s %s",mark,b.Name())
   if b.UnreadCount>0{name+=fmt.Sprintf("  [%d]",b.UnreadCount)}
   if b.Muted{name+="  🔕"}
   label:=widget.NewLabel(name+"\n"+b.StatusText)
   label.Wrapping=fyne.TextWrapWord
   row:=container.NewBorder(nil,nil,buddyAvatar(b),container.NewHBox(
    widget.NewButton("IM",func(){u.openChat(buddy)}),
    widget.NewButton("⋯",func(){u.buddySettings(buddy)})),label)
   u.roster.Add(row)
  }
 }
 u.roster.Refresh()
}
func buddyAvatar(b beacon.Buddy)fyne.CanvasObject{
 parts:=strings.SplitN(b.Avatar,",",2)
 if len(parts)==2&&strings.HasPrefix(parts[0],"data:image/"){
  raw,e:=base64.StdEncoding.DecodeString(parts[1])
  if e==nil&&len(raw)<300000{
   picture,_,e:=image.Decode(bytes.NewReader(raw))
   if e==nil{photo:=canvas.NewImageFromImage(picture);photo.FillMode=canvas.ImageFillContain;photo.SetMinSize(fyne.NewSize(42,42));return photo}
  }
 }
 initial:="?";if b.Name()!=""{initial=strings.ToUpper(string([]rune(b.Name())[0]))}
 return widget.NewLabel(initial)
}
func(u *UI) logout(){
 if u.api==nil{return}
 client:=u.api
 clearLogin()
 u.stopPolling()
 u.api=nil
 for _,c:=range u.chats{c.window.Close()}
 u.chats=map[int]*Chat{}
 u.root.SetCloseIntercept(nil)
 u.showLogin()
 go func(){c,cancel:=ctx();defer cancel();_ =client.Logout(c)}()
}
func(u *UI) action(f func(context.Context)error){
 client:=u.api;if client==nil{return}
 u.async(f,func(err error){u.alert(err)})
}

func(u *UI) showPreferences(){
 auto:=widget.NewCheck("Automatically open an IM window for new messages",nil)
 auto.SetChecked(u.app.Preferences().BoolWithFallback("autoOpenIM",false))
 closeToTray:=widget.NewCheck("Closing the buddy list hides it in the system tray",nil)
 closeToTray.SetChecked(u.app.Preferences().BoolWithFallback("closeToTray",runtime.GOOS=="windows"))
 dialog.ShowForm("Desktop Preferences","Save","Cancel",
  []*widget.FormItem{widget.NewFormItem("",auto),widget.NewFormItem("",closeToTray)},
  func(ok bool){if ok{
   u.app.Preferences().SetBool("autoOpenIM",auto.Checked)
   u.app.Preferences().SetBool("closeToTray",closeToTray.Checked)
  }},u.root)
}
