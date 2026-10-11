package main

import (
 "context"
 "fmt"
 "strings"
 "time"

 "fyne.io/fyne/v2"
 "fyne.io/fyne/v2/container"
 "fyne.io/fyne/v2/dialog"
 "fyne.io/fyne/v2/widget"
 "github.com/gigabytegrove/beacon/clients/desktop-go/internal/beacon"
)

type Chat struct{
 window fyne.Window
 peer beacon.Buddy
 client *beacon.Client
 mine int
 history *widget.Label
 typing *widget.Label
 scroll *container.Scroll
 input *widget.Entry
 stop chan struct{}
 lastID int
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
 transcript:=widget.NewLabel("Loading your conversation…")
 transcript.Wrapping=fyne.TextWrapWord
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
 header:=container.NewVBox(title,online,search)
 footer:=container.NewVBox(writing,input,widget.NewButton("Send IM",send))
 win.SetContent(container.NewBorder(header,footer,nil,nil,scroll))
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
 if err==nil&&len(items)>0{
  newest:=0
  for _,m:=range items{if m.SenderID==ch.peer.ID&&m.ID>newest{newest=m.ID}}
  if newest>0{_=ch.client.MarkRead(c,ch.peer.ID,newest)}
 }
 cancel()
 if err!=nil{fyne.Do(func(){if u.api==ch.client{ch.typing.SetText("Network error: "+err.Error())}});return}
 var output strings.Builder
 for _,m:=range items{
  who:=ch.peer.Name()
  if m.SenderID==ch.mine{who="You"}
  output.WriteString(fmt.Sprintf("%s · %s\n%s\n\n",who,time.Unix(m.CreatedAt,0).Format("Jan 2, 15:04"),m.Body))
 }
 if output.Len()==0{output.WriteString("No messages yet. Say hello!")}
 final:=output.String()
 latest:=0;if len(items)>0{latest=items[len(items)-1].ID}
 fyne.Do(func(){
  if u.api!=ch.client{return}
  if latest!=ch.lastID||ch.lastID==0 {
   ch.history.SetText(final)
   ch.lastID=latest
   ch.scroll.ScrollToBottom()
  }
  if errTyping==nil&&typing{ch.typing.SetText(ch.peer.Name()+" is typing…")}else{ch.typing.SetText("")}
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
