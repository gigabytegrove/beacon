package beacon

import (
 "context"
 "encoding/json"
 "errors"
 "net/http"
 "net/http/httptest"
 "strings"
 "testing"
)

func TestValidateServer(t *testing.T){
 for _,v:=range []string{"ftp://host","http://","https://user:pass@host","http://host/path","http://host/?token=123"}{
  if _,err:=ValidateServer(v);err==nil{t.Errorf("accepted invalid URL: %q",v)}
 }
 good,e:=ValidateServer("https://beacon.example/");if e!=nil||good!="https://beacon.example"{t.Fatalf("%s %v",good,e)}
}
func TestLoginAndAuthenticatedConversation(t *testing.T){
 t.Parallel()
 var requests []string
 server:=httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){
  requests=append(requests,r.Method+" "+r.URL.RequestURI())
  w.Header().Set("Content-Type","application/json")
  switch r.URL.Path {
  case "/api/login":
   if r.Header.Get("Authorization")!=""{t.Error("login sent authorization header")}
   w.Write([]byte(`{"token":"private-key","user":{"id":1,"display_name":"Admin","is_admin":true}}`))
  case "/api/buddies":
   if r.Header.Get("Authorization")!="Bearer private-key"{t.Error("missing bearer authorization")}
   w.Write([]byte(`[{"id":2,"display_name":"Alice","nickname":"Allie","muted":0,"presence":"available","unread_count":1}]`))
  case "/api/messages/search":
   if r.URL.Query().Get("q")!="100%_"{t.Error("search query not URL encoded")}
   if r.URL.Query().Get("peer_id")!="2"{t.Error("peer ID missing")}
   w.Write([]byte(`[{"id":7,"sender_id":2,"recipient_id":1,"body":"100%_"}]`))
  case "/api/logout":
   w.Write([]byte(`{"ok":true}`))
  case "/api/me":
   w.WriteHeader(401);w.Write([]byte(`{"detail":"revoked"}`))
  default: w.WriteHeader(404);w.Write([]byte(`{"detail":"missing"}`))
  }
 }))
 defer server.Close()
 c,err:=NewClient(server.URL);if err!=nil{t.Fatal(err)}
 result,err:=c.Login(context.Background(),"admin","secret","desktop")
 if err!=nil||result.User.ID!=1||!bool(result.User.IsAdmin){t.Fatalf("%+v %v",result,err)}
 buddies,err:=c.Buddies(context.Background());if err!=nil||len(buddies)!=1||buddies[0].Name()!="Allie"{t.Fatalf("%+v %v",buddies,err)}
 matches,err:=c.Search(context.Background(),2,"100%_")
 if err!=nil||len(matches)!=1{t.Fatalf("%+v %v",matches,err)}
 _,err=c.Me(context.Background());if !errors.Is(err,ErrUnauthorized){t.Fatalf("expected unauthorized: %v",err)}
 if err=c.Logout(context.Background());err!=nil||c.Token()!=""{t.Fatalf("logout: %v",err)}
 if !strings.Contains(strings.Join(requests,"|"),"/api/messages/search?"){t.Fatal("search not sent")}
}
func TestCrossOriginRedirectNeverForwardsToken(t *testing.T){
 other:=httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){
  if r.Header.Get("Authorization")!=""{t.Error("leaked bearer token across origins")}
  w.Write([]byte("{}"))
 }))
 defer other.Close()
 first:=httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){
  http.Redirect(w,r,other.URL+"/api/me",302)
 }))
 defer first.Close()
 c,_:=NewClient(first.URL);c.SetToken("very secret")
 if err:=c.Get(context.Background(),"/me",&map[string]any{});err==nil{t.Fatal("expected redirect rejection")}
}

func TestFlexibleBooleans(t *testing.T){
 for _,raw:=range []string{"true","false","1","0","null"}{
  var b FlexibleBool
  if err:=json.Unmarshal([]byte(raw),&b);err!=nil{t.Fatal(raw,err)}
 }
 var b FlexibleBool
 if err:=json.Unmarshal([]byte("123"),&b);err==nil{t.Fatal("unexpected numeric boolean accepted")}
}
