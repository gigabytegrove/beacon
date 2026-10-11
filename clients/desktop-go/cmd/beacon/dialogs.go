package main

import (
 "bytes"
 "context"
 "encoding/base64"
 "fmt"
 "image"
 "image/draw"
 "image/jpeg"
 "io"
 "strings"

 "fyne.io/fyne/v2"
 "fyne.io/fyne/v2/container"
 "fyne.io/fyne/v2/dialog"
 "fyne.io/fyne/v2/widget"
 "github.com/gigabytegrove/beacon/clients/desktop-go/internal/beacon"
)

func(u *UI) addBuddy(){
 client:=u.api;if client==nil{return}
 u.async(func(c context.Context)error{
  people,err:=client.Directory(c)
  if err!=nil{return err}
  fyne.Do(func(){
   named:=map[string]int{}
   options:=[]string{}
   existing:=map[int]bool{}
   for _,b:=range u.buddies{existing[b.ID]=true}
   for _,person:=range people{
    if existing[person.ID]{continue}
    title:=person.DisplayName+" ("+person.Username+")"
    named[title]=person.ID;options=append(options,title)
   }
   if len(options)==0{dialog.ShowInformation("Buddy list","Everyone on the server is already on your buddy list.",u.root);return}
   picker:=widget.NewSelect(options,nil);picker.SetSelected(options[0])
   dialog.ShowForm("Add a buddy","Add","Cancel",
    []*widget.FormItem{widget.NewFormItem("Person",picker)},func(ok bool){
     if ok{u.action(func(c context.Context)error{return client.AddBuddy(c,named[picker.Selected])})}
    },u.root)
  })
  return nil
 },u.alert)
}
func(u *UI) buddySettings(b beacon.Buddy){
 w:=u.app.NewWindow("Beacon · Buddy Settings · "+b.Name())
 w.Resize(fyne.NewSize(430,340))
 nickname:=widget.NewEntry();nickname.SetText(b.Nickname)
 muted:=widget.NewCheck("Mute sign-on and message alerts",nil);muted.SetChecked(bool(b.Muted))
 choices:=[]string{"Buddies"};groupIDs:=map[string]any{"Buddies":nil};selected:="Buddies"
 for _,g:=range u.groups{choices=append(choices,g.Name);groupIDs[g.Name]=g.ID;if b.GroupID!=nil&&*b.GroupID==g.ID{selected=g.Name}}
 group:=widget.NewSelect(choices,nil);group.SetSelected(selected)
 form:=widget.NewForm(
  widget.NewFormItem("Local nickname",nickname),
  widget.NewFormItem("Buddy group",group))
 w.SetContent(container.NewBorder(nil,container.NewGridWithColumns(2,
  widget.NewButton("Save Settings",func(){
   change:=map[string]any{"nickname":strings.TrimSpace(nickname.Text),
    "group_id":groupIDs[group.Selected],"muted":muted.Checked}
   client:=u.api;u.async(func(c context.Context)error{return client.EditBuddy(c,b.ID,change)},
    func(err error){if err!=nil{dialog.ShowError(err,w)}else{w.Close()}})
  }),
  widget.NewButton("Remove Buddy",func(){
   dialog.ShowConfirm("Remove Buddy","Remove "+b.Name()+" from your buddy list?",func(ok bool){
    if !ok{return}
    client:=u.api;u.async(func(c context.Context)error{return client.DeleteBuddy(c,b.ID)},
     func(err error){if err!=nil{dialog.ShowError(err,w)}else{w.Close()}})
   },w)
  })),nil,nil,container.NewVBox(form,muted)))
 w.Show()
}

func(u *UI) manageGroups(){
 w:=u.app.NewWindow("Beacon · Buddy Groups")
 w.Resize(fyne.NewSize(415,340))
 options:=[]string{};ids:=map[string]int{}
 for _,g:=range u.groups{options=append(options,g.Name);ids[g.Name]=g.ID}
 existing:=widget.NewSelect(options,nil)
 renamed:=widget.NewEntry();renamed.SetPlaceHolder("Group name")
 if len(options)>0{existing.SetSelected(options[0]);renamed.SetText(options[0])}
 existing.OnChanged=func(s string){renamed.SetText(s)}
 create:=widget.NewEntry();create.SetPlaceHolder("New group name")
 body:=container.NewVBox(
  widget.NewLabelWithStyle("Create a group",fyne.TextAlignLeading,fyne.TextStyle{Bold:true}),
  create,widget.NewButton("Create Group",func(){
   name:=strings.TrimSpace(create.Text);if name==""{return}
   client:=u.api;u.async(func(c context.Context)error{return client.CreateGroup(c,name)},
    func(err error){if err!=nil{dialog.ShowError(err,w)}else{w.Close()}})
  }),
  widget.NewSeparator(),
  widget.NewLabelWithStyle("Edit an existing group",fyne.TextAlignLeading,fyne.TextStyle{Bold:true}),
  existing,renamed,
  container.NewGridWithColumns(2,
   widget.NewButton("Rename",func(){
    id:=ids[existing.Selected]
    if id==0||strings.TrimSpace(renamed.Text)==""{return}
    client:=u.api;u.async(func(c context.Context)error{return client.RenameGroup(c,id,renamed.Text)},
     func(err error){if err!=nil{dialog.ShowError(err,w)}else{w.Close()}})
   }),
   widget.NewButton("Delete",func(){
    id:=ids[existing.Selected];if id==0{return}
    dialog.ShowConfirm("Delete Group","Contacts move to Buddies; their messages remain.",func(ok bool){
     if !ok{return}
     client:=u.api;u.async(func(c context.Context)error{return client.DeleteGroup(c,id)},
      func(err error){if err!=nil{dialog.ShowError(err,w)}else{w.Close()}})
    },w)
   }),
  ),
 )
 w.SetContent(container.NewPadded(body));w.Show()
}
func(u *UI) editProfile(){
 client:=u.api;if client==nil{return}
 u.async(func(c context.Context)error{
  var people []beacon.User
  err:=client.Get(c,"/users",&people);if err!=nil{return err}
  var self beacon.User
  found:=false
  for _,p:=range people{if p.ID==u.me.ID{self=p;found=true;break}}
  if !found{return fmt.Errorf("your profile was not returned by the server")}
  fyne.Do(func(){
   name:=widget.NewEntry();name.SetText(self.DisplayName)
   status:=widget.NewEntry();status.SetText(self.StatusText)
   dialog.ShowForm("My Beacon Profile","Save","Cancel",
    []*widget.FormItem{widget.NewFormItem("Display name",name),
     widget.NewFormItem("Status / away message",status)},
    func(ok bool){if ok{
     u.async(func(c context.Context)error{return client.Profile(c,name.Text,status.Text)},func(err error){
      if err!=nil{u.alert(err)}else{u.me.DisplayName=name.Text;u.showRoster()}
     })
    }},u.root)
  })
  return nil
 },u.alert)
}
func(u *UI) uploadPhoto(){
 client:=u.api;if client==nil{return}
 dialog.ShowFileOpen(func(file fyne.URIReadCloser,err error){
  if err!=nil{u.alert(err);return}
  if file==nil{return}
  go func(){
   defer file.Close()
   raw,e:=io.ReadAll(io.LimitReader(file,16<<20));if e!=nil{fyne.Do(func(){u.alert(e)});return}
   img,_,e:=image.Decode(bytes.NewReader(raw));if e!=nil{fyne.Do(func(){u.alert(e)});return}
   bounds:=img.Bounds()
   if bounds.Dx()<=0||bounds.Dy()<=0||int64(bounds.Dx())*int64(bounds.Dy())>16_000_000{
    fyne.Do(func(){u.alert(fmt.Errorf("photo resolution exceeds 16 megapixels"))});return
   }
   dest:=image.NewRGBA(image.Rect(0,0,256,256))
   // Standard-library nearest-neighbour scaling avoids requiring another imaging runtime.
   for y:=0;y<256;y++{for x:=0;x<256;x++{
    px:=bounds.Min.X+x*bounds.Dx()/256;py:=bounds.Min.Y+y*bounds.Dy()/256
    dest.Set(x,y,img.At(px,py))
   }}
   // Ensure opaque JPG: no user-supplied metadata is transmitted.
   opaque:=image.NewRGBA(dest.Bounds());draw.Draw(opaque,opaque.Bounds(),dest,image.Point{},draw.Src)
   var output bytes.Buffer
   e=jpeg.Encode(&output,opaque,&jpeg.Options{Quality:75})
   if e!=nil{fyne.Do(func(){u.alert(e)});return}
   if output.Len()>192*1024{fyne.Do(func(){u.alert(fmt.Errorf("processed photo is too large"))});return}
   encoded:=base64.StdEncoding.EncodeToString(output.Bytes())
   c,cancel:=ctx();defer cancel();e=client.Avatar(c,encoded)
   fyne.Do(func(){if e!=nil{u.alert(e)}else{dialog.ShowInformation("Beacon","Profile photo updated",u.root)}})
  }()
 },u.root)
}
func(u *UI) showSessions(){
 client:=u.api;if client==nil{return}
 u.async(func(c context.Context)error{
  items,err:=client.Sessions(c);if err!=nil{return err}
  fyne.Do(func(){
   list:=container.NewVBox()
   window:=u.app.NewWindow("Beacon · Signed-in Devices")
   window.Resize(fyne.NewSize(480,380))
   for _,session:=range items{
    s:=session
    label:=s.DeviceName;if s.Current{label+=" · this device"}
    list.Add(container.NewBorder(nil,nil,nil,
     widget.NewButton("Revoke",func(){
      dialog.ShowConfirm("Revoke session","Sign out "+s.DeviceName+"?",func(ok bool){
       if !ok{return}
       u.async(func(c context.Context)error{return client.Revoke(c,s.ID)},func(err error){
        if err!=nil{u.alert(err);return}
        window.Close()
        if s.Current{clearLogin();u.stopPolling();u.api=nil;u.showLogin()}else{u.showSessions()}
       })
      },window)
     }),widget.NewLabel(label)))
   }
   list.Add(widget.NewButton("Sign out other devices",func(){
    dialog.ShowConfirm("Revoke other devices","All other sessions will be signed out.",func(ok bool){
     if ok{u.action(func(c context.Context)error{return client.Post(c,"/sessions/revoke-others",map[string]any{},nil)})}
     window.Close()
    },window)
   }))
   window.SetContent(container.NewVScroll(list));window.Show()
  })
  return nil
 },u.alert)
}
func(u *UI) changePassword(){
 client:=u.api;if client==nil{return}
 old:=widget.NewPasswordEntry();next:=widget.NewPasswordEntry()
 dialog.ShowForm("Change Account Password","Change","Cancel",
  []*widget.FormItem{widget.NewFormItem("Current",old),widget.NewFormItem("New (12+)",next)},
  func(ok bool){if !ok{return};if len(next.Text)<12{dialog.ShowInformation("Password","New password must be at least 12 characters.",u.root);return}
   u.action(func(c context.Context)error{return client.Password(c,old.Text,next.Text)})
  },u.root)
}
func(u *UI) createUser(){
 if !u.me.IsAdmin{return}
 username:=widget.NewEntry();name:=widget.NewEntry();pass:=widget.NewPasswordEntry()
 dialog.ShowForm("Create Beacon User","Create","Cancel",
  []*widget.FormItem{widget.NewFormItem("Username",username),widget.NewFormItem("Display name",name),widget.NewFormItem("Temporary password",pass)},
  func(ok bool){if !ok{return}
   client:=u.api
   u.action(func(c context.Context)error{return client.Post(c,"/admin/users",map[string]string{
    "username":username.Text,"display_name":name.Text,"password":pass.Text},nil)})
  },u.root)
}
