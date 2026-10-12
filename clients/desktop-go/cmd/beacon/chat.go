package main

import (
 "context"
 "fmt"
 "strings"
 "time"

 "fyne.io/fyne/v2"
 "fyne.io/fyne/v2/container"
 "fyne.io/fyne/v2/dialog"
 "fyne.io/fyne/v2/layout"
 "fyne.io/fyne/v2/widget"
 "github.com/gigabytegrove/beacon/clients/desktop-go/internal/beacon"
)

type Chat struct{
 window fyne.Window
 peer beacon.Buddy
 client *beacon.Client
 mine int
 history *fyne.Container
 typing *widget.Label
 scroll *container.Scroll
 input *widget.Entry
 stop chan struct{}
 lastID int
 lastRead int
 lastTyping time.Time
}

func(u *UI) openChat(peer beacon.Buddy){
 if u.api==nil{return}
 if current,ok:=u.chats[peer.ID];ok{current.window.Show();return}
 client:=u.api
 win:=u.app.NewWindow("Beacon IM · "+peer.Name())
 win.Resize(fyne.NewSize(540,610))
 title:=widget.NewLabelWithStyle(peer.Name(),fyne.TextAlignLeading,fyne.TextStyle{Bold:true})
 online:=widget.NewLabel(peer.Presence+" · "+peer.StatusText)
 transcript:=container.NewVBox(widget.NewLabel("Loading your conversation…"))
 scroll:=container.NewVScroll(transcript)
 writing:=widget.NewLabel("")
 input:=widget.NewMultiLineEntry();input.SetPlaceHolder("Type your message…")
 input.SetMinRowsVisible(3)
 chat:=&Chat{window:win,peer:peer,client:client,mine:u.me.ID,history:transcript,typing:writing,scroll:scroll,input:input,stop:make(chan struct{})}
 input.OnChanged=func(text string){
  if text==""||time.Since(chat.lastTyping)<1800*time.Millisecond{return}
  chat.lastTyping=time.Now()
  go func(){c,cancel:=ctx();defer cancel();_=client.SendTyping(c,peer.ID,true)}()
 }
 send:=func(){
  body:=strings.TrimSpace(input.Text)
  if body==""{return}
  input.Disable()
  u.async(func(c context.Context)error{
   _,err:=client.Send(c,peer.ID,body)
   if err==nil{_=client.SendTyping(c,peer.ID,false)}
   return err
  },func(err error){
   input.Enable()
   if err!=nil{dialog.ShowError(err,win);return}
   input.SetText("")
   go chat.load(u)
  })
 }
 search:=widget.NewButton("Search history",func(){u.searchChat(chat)})
 heading:=container.NewBorder(nil,nil,buddyAvatar(peer),nil,container.NewVBox(title,online))
 header:=container.NewVBox(heading,widget.NewSeparator(),search)
 submit:=widget.NewButton("Send message",send)
 submit.Importance=widget.HighImportance
 footer:=container.NewVBox(writing,input,submit)
 win.SetContent(container.NewPadded(container.NewBorder(header,footer,nil,nil,scroll)))
 win.SetOnClosed(func(){close(chat.stop);delete(u.chats,peer.ID)})
 u.chats[peer.ID]=chat
 win.Show()
 go chat.poll(u)
}

func(ch *Chat) poll(u *UI){
 ticker:=time.NewTicker(3*time.Second);defer ticker.Stop()
 for {
  select {case <-ch.stop:return;default:}
  ch.load(u)
  select {case <-ch.stop:return;case <-ticker.C:}
 }
}
func(ch *Chat) load(u *UI){
 c,cancel:=ctx()
 items,err:=ch.client.History(c,ch.peer.ID)
 typing,errTyping:=ch.client.Typing(c,ch.peer.ID)
 // Read state is only updated after displaying the conversation
 // on the UI thread, never while a network request is still in flight.
 cancel()
 if err!=nil{fyne.Do(func(){if u.api==ch.client{ch.typing.SetText("Network error: "+err.Error())}});return}
 latest:=0
 if len(items)>0{latest=items[len(items)-1].ID}
 latestIncoming:=0
 for _,m:=range items {
  if m.SenderID==ch.peer.ID && m.ID>latestIncoming {latestIncoming=m.ID}
 }
 fyne.Do(func(){
  if u.api!=ch.client || u.chats[ch.peer.ID]!=ch{return}
  if latest!=ch.lastID||ch.lastID==0 {
   ch.history.RemoveAll()
   if len(items)==0{
    ch.history.Add(widget.NewCard("No messages yet","Say hello and start the conversation.",widget.NewLabel("Your private messages appear here.")))
   }
   for _,message:=range items{
    who:=ch.peer.Name()
    mine:=message.SenderID==ch.mine
    if mine{who="You"}
    timestamp:=time.Unix(message.CreatedAt,0).Format("Jan 2, 15:04")
    text:=widget.NewLabel(message.Body)
    text.Wrapping=fyne.TextWrapWord
    bubble:=widget.NewCard(who+"  ·  "+timestamp,"",text)
    if mine{
     ch.history.Add(container.NewHBox(layout.NewSpacer(),bubble))
    }else{
     ch.history.Add(container.NewHBox(bubble,layout.NewSpacer()))
    }
   }
   ch.history.Refresh()
   ch.lastID=latest
   ch.scroll.ScrollToBottom()
  }
  if errTyping==nil&&typing{ch.typing.SetText(ch.peer.Name()+" is typing…")}else{ch.typing.SetText("")}
  if latestIncoming>ch.lastRead {
   id:=latestIncoming
   ch.lastRead=id
   go func(){
    requestCtx,cancelRequest:=ctx()
    defer cancelRequest()
    if e:=ch.client.MarkRead(requestCtx,ch.peer.ID,id);e!=nil {
     fyne.Do(func(){
      // Restore last-read state for a later retry, but do not rewind
      // if the user has already viewed newer messages in this window.
      if ch.lastRead==id {ch.lastRead=0}
     })
    }
   }()
  }
 })
}
func(u *UI) searchChat(chat *Chat){
 query:=widget.NewEntry();query.SetPlaceHolder("Enter 2 or more characters")
 dialog.ShowForm("Search IM history","Search","Cancel",[]*widget.FormItem{widget.NewFormItem("Text",query)},func(ok bool){
  if !ok{return}
  phrase:=strings.TrimSpace(query.Text)
  if len(phrase)<2||len(phrase)>100{dialog.ShowInformation("Search","Enter between 2 and 100 characters.",chat.window);return}
  u.async(func(c context.Context)error{
   matches,e:=chat.client.Search(c,chat.peer.ID,phrase)
   if e!=nil{return e}
   fyne.Do(func(){
    win:=u.app.NewWindow("Beacon · Search · "+chat.peer.Name())
    win.Resize(fyne.NewSize(530,460))
    var builder strings.Builder
    for i:=len(matches)-1;i>=0;i--{
     m:=matches[i];who:=chat.peer.Name();if m.SenderID==chat.mine{who="You"}
     builder.WriteString(fmt.Sprintf("%s · %s\n%s\n\n",who,time.Unix(m.CreatedAt,0).Format("2006-01-02 15:04"),m.Body))
    }
    if builder.Len()==0{builder.WriteString("No matching messages.")}
    results:=widget.NewLabel(builder.String());results.Wrapping=fyne.TextWrapWord
    win.SetContent(container.NewVScroll(results));win.Show()
   })
   return nil
  },func(e error){if e!=nil{dialog.ShowError(e,chat.window)}})
 },chat.window)
}
