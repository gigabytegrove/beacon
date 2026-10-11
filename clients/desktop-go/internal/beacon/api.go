package beacon

import (
 "bytes"
 "context"
 "encoding/json"
 "errors"
 "fmt"
 "io"
 "net/http"
 "net/url"
 "strings"
 "sync"
 "time"
)

const Version = "0.8.0"
var ErrUnauthorized=errors.New("session expired or revoked")
type FlexibleBool bool
func(b *FlexibleBool) UnmarshalJSON(raw []byte)error{
 switch string(raw){case "true","1":*b=true;return nil;case "false","0","null":*b=false;return nil;default:return fmt.Errorf("invalid boolean %s",string(raw))}
}
type User struct { ID int `json:"id"`; Username string `json:"username"`; DisplayName string `json:"display_name"`; StatusText string `json:"status_text"`; Avatar string `json:"avatar"`; IsAdmin FlexibleBool `json:"is_admin"` }
type Buddy struct {
 User
 Nickname string `json:"nickname"`
 GroupID *int `json:"group_id"`
 GroupName string `json:"group_name"`
 Presence string `json:"presence"`
 Muted FlexibleBool `json:"muted"`
 UnreadCount int `json:"unread_count"`
}
func(b Buddy) Name() string { if b.Nickname!="" {return b.Nickname};return b.DisplayName }
type Group struct { ID int `json:"id"`; Name string `json:"name"` }
type Session struct { ID int `json:"id"`; DeviceName string `json:"device_name"`; Current bool `json:"current"` }
type Message struct { ID int `json:"id"`; SenderID int `json:"sender_id"`; RecipientID int `json:"recipient_id"`; Body string `json:"body"`; CreatedAt int64 `json:"created_at"` }
type LoginResult struct { Token string `json:"token"`; User User `json:"user"` }
type Client struct { mu sync.RWMutex; base,token string; http *http.Client }
func ValidateServer(raw string)(string,error){
 raw=strings.TrimSpace(raw)
 u,err:=url.Parse(raw)
 if err!=nil || u==nil || (u.Scheme!="http"&&u.Scheme!="https") || u.Host=="" || u.User!=nil || u.RawQuery!="" || u.Fragment!="" || (u.Path!=""&&u.Path!="/") {return "",errors.New("enter an http(s) server URL, for example http://192.168.1.10:8765")}
 return strings.TrimRight(u.String(),"/"),nil
}
func NewClient(server string)(*Client,error){
 base,err:=ValidateServer(server);if err!=nil{return nil,err}
 return &Client{base:base,http:&http.Client{Timeout:12*time.Second,CheckRedirect:func(req *http.Request,prev []*http.Request)error{
  if len(prev)>3 {return errors.New("redirect limit exceeded")}
  if len(prev)>0 && req.URL.Scheme+"://"+req.URL.Host!=prev[0].URL.Scheme+"://"+prev[0].URL.Host {return errors.New("cross-origin redirect refused")}
  return nil
 }}},nil
}
func(c *Client) SetToken(s string){c.mu.Lock();c.token=s;c.mu.Unlock()}
func(c *Client) Token()string{c.mu.RLock();defer c.mu.RUnlock();return c.token}
func(c *Client) Server()string{return c.base}
func(c *Client) Request(ctx context.Context,method,path string,body any,out any)error{
 if !strings.HasPrefix(path,"/")||strings.HasPrefix(path,"//"){return errors.New("invalid API path")}
 var reader io.Reader
 if body!=nil{data,e:=json.Marshal(body);if e!=nil{return e};reader=bytes.NewReader(data)}
 req,err:=http.NewRequestWithContext(ctx,method,c.base+"/api"+path,reader);if err!=nil{return err}
 req.Header.Set("Accept","application/json")
 if body!=nil{req.Header.Set("Content-Type","application/json")}
 if token:=c.Token();token!=""{req.Header.Set("Authorization","Bearer "+token)}
 r,e:=c.http.Do(req);if e!=nil{return e};defer r.Body.Close()
 data,e:=io.ReadAll(io.LimitReader(r.Body,8<<20));if e!=nil{return e}
 if r.StatusCode==401 {return ErrUnauthorized}
 if r.StatusCode<200||r.StatusCode>=300{
  var failure struct{Detail string `json:"detail"`}
  if json.Unmarshal(data,&failure)==nil&&failure.Detail!=""{return errors.New(failure.Detail)}
  return fmt.Errorf("HTTP %d",r.StatusCode)
 }
 if out!=nil{if e:=json.Unmarshal(data,out);e!=nil{return fmt.Errorf("invalid server response: %w",e)}}
 return nil
}
func(c *Client) Get(ctx context.Context,path string,out any)error{return c.Request(ctx,"GET",path,nil,out)}
func(c *Client) Post(ctx context.Context,path string,data,out any)error{return c.Request(ctx,"POST",path,data,out)}
func(c *Client) Patch(ctx context.Context,path string,data any)error{return c.Request(ctx,"PATCH",path,data,nil)}
func(c *Client) Login(ctx context.Context,user,password,device string)(LoginResult,error){
 var result LoginResult
 err:=c.Post(ctx,"/login",map[string]string{"username":user,"password":password,"device_name":device},&result)
 if err==nil{if result.Token==""{return result,errors.New("empty login token")};c.SetToken(result.Token)}
 return result,err
}
func(c *Client) Me(ctx context.Context)(User,error){var v User;err:=c.Get(ctx,"/me",&v);return v,err}
func(c *Client) Logout(ctx context.Context)error{err:=c.Post(ctx,"/logout",map[string]any{},nil);c.SetToken("");return err}
func(c *Client) Buddies(ctx context.Context)([]Buddy,error){var v []Buddy;err:=c.Get(ctx,"/buddies",&v);return v,err}
func(c *Client) Directory(ctx context.Context)([]User,error){var v []User;err:=c.Get(ctx,"/directory",&v);return v,err}
func(c *Client) Groups(ctx context.Context)([]Group,error){var v []Group;err:=c.Get(ctx,"/groups",&v);return v,err}
func(c *Client) History(ctx context.Context,peer int)([]Message,error){var v []Message;err:=c.Get(ctx,fmt.Sprintf("/messages/%d",peer),&v);return v,err}
func(c *Client) Send(ctx context.Context,peer int,text string)(Message,error){
 var v Message;err:=c.Post(ctx,"/messages",map[string]any{"recipient_id":peer,"body":text},&v);return v,err
}
func(c *Client) Search(ctx context.Context,peer int,q string)([]Message,error){
 var out []Message;query:=url.Values{"q":{q},"limit":{"100"}};if peer>0{query.Set("peer_id",fmt.Sprint(peer))}
 err:=c.Get(ctx,"/messages/search?"+query.Encode(),&out);return out,err
}
func(c *Client) Presence(ctx context.Context,status string)error{return c.Post(ctx,"/presence",map[string]string{"status":status},nil)}
func(c *Client) Typing(ctx context.Context,peer int)(bool,error){
 var v struct{Active bool `json:"active"`};err:=c.Get(ctx,fmt.Sprintf("/typing/%d",peer),&v);return v.Active,err
}
func(c *Client) SendTyping(ctx context.Context,peer int,active bool)error{return c.Post(ctx,fmt.Sprintf("/typing/%d",peer),map[string]bool{"active":active},nil)}
func(c *Client) MarkRead(ctx context.Context,peer,id int)error{return c.Post(ctx,fmt.Sprintf("/conversations/%d/read",peer),map[string]int{"through_id":id},nil)}
func(c *Client) Sessions(ctx context.Context)([]Session,error){var v []Session;err:=c.Get(ctx,"/sessions",&v);return v,err}
func(c *Client) Revoke(ctx context.Context,id int)error{return c.Request(ctx,"DELETE",fmt.Sprintf("/sessions/%d",id),nil,nil)}
func(c *Client) Profile(ctx context.Context,name,status string)error{return c.Request(ctx,"PUT","/me/profile",map[string]string{"display_name":name,"status_text":status},nil)}
func(c *Client) Password(ctx context.Context,old,newPass string)error{return c.Post(ctx,"/me/password",map[string]string{"current_password":old,"new_password":newPass},nil)}
func(c *Client) Avatar(ctx context.Context,encoded string)error{return c.Post(ctx,"/me/avatar",map[string]string{"mime_type":"image/jpeg","image_base64":encoded},nil)}
func(c *Client) AddBuddy(ctx context.Context,id int)error{return c.Post(ctx,fmt.Sprintf("/buddies/%d",id),map[string]any{},nil)}
func(c *Client) DeleteBuddy(ctx context.Context,id int)error{return c.Request(ctx,"DELETE",fmt.Sprintf("/buddies/%d",id),nil,nil)}
func(c *Client) EditBuddy(ctx context.Context,id int,change map[string]any)error{return c.Patch(ctx,fmt.Sprintf("/buddies/%d",id),change)}
func(c *Client) CreateGroup(ctx context.Context,name string)error{return c.Post(ctx,"/groups",map[string]string{"name":name},nil)}
func(c *Client) RenameGroup(ctx context.Context,id int,name string)error{return c.Patch(ctx,fmt.Sprintf("/groups/%d",id),map[string]string{"name":name})}
func(c *Client) DeleteGroup(ctx context.Context,id int)error{return c.Request(ctx,"DELETE",fmt.Sprintf("/groups/%d",id),nil,nil)}
