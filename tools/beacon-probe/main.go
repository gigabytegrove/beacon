// Beacon Probe is a dependency-free connectivity and authenticated API preflight.
// It is NOT the Beacon graphical instant messaging client.
package main

import (
 "bytes"
 "context"
 "encoding/json"
 "errors"
 "flag"
 "fmt"
 "io"
 "net/http"
 "net/url"
 "os"
 "strings"
 "time"
)
const version="0.8.1"
func fail(msg string,args ...any){fmt.Fprintf(os.Stderr,"FAIL: "+msg+"\n",args...);os.Exit(1)}
func main(){
 raw:=flag.String("server","","Beacon server URL, e.g. http://192.168.0.25:8765")
 username:=flag.String("username","","Optional username for authenticated API checks")
 timeout:=flag.Duration("timeout",10*time.Second,"Request timeout")
 flag.Parse()
 base,err:=url.Parse(strings.TrimSpace(*raw))
 if err!=nil||base==nil||base.Host==""||(base.Scheme!="http"&&base.Scheme!="https")||base.User!=nil||base.RawQuery!=""||base.Fragment!=""||(base.Path!=""&&base.Path!="/"){fail("provide -server with a valid http:// or https:// Beacon address")}
 origin:=strings.TrimRight(base.String(),"/")
 c:=&http.Client{Timeout:*timeout,CheckRedirect:func(req *http.Request,via []*http.Request)error{
  if len(via)>0&&(req.URL.Scheme!=base.Scheme||req.URL.Host!=base.Host){return errors.New("cross-origin redirects refused")}
  if len(via)>3{return errors.New("too many redirects")};return nil
 }}
 ctx,cancel:=context.WithTimeout(context.Background(),45*time.Second);defer cancel()
 request:=func(method,path,token string,payload any)([]byte,error){
  var data io.Reader
  if payload!=nil{b,e:=json.Marshal(payload);if e!=nil{return nil,e};data=bytes.NewReader(b)}
  req,e:=http.NewRequestWithContext(ctx,method,origin+path,data);if e!=nil{return nil,e}
  req.Header.Set("Accept","application/json")
  if payload!=nil{req.Header.Set("Content-Type","application/json")}
  if token!=""{req.Header.Set("Authorization","Bearer "+token)}
  started:=time.Now()
  r,e:=c.Do(req);if e!=nil{return nil,e};defer r.Body.Close()
  b,e:=io.ReadAll(io.LimitReader(r.Body,1<<20));if e!=nil{return nil,e}
  fmt.Printf("%-25s HTTP %-3d  (%s)\n",path,r.StatusCode,time.Since(started).Round(time.Millisecond))
  if r.StatusCode<200||r.StatusCode>=300{return nil,fmt.Errorf("HTTP %d: %s",r.StatusCode,safeDetail(b))}
  return b,nil
 }
 fmt.Println("Beacon Probe",version,"— read-only connectivity checks with disposable login/logout")
 fmt.Println("Target:",origin)
 if base.Scheme=="http"{fmt.Println("NOTE: HTTP is unencrypted; only use it on a trusted LAN.")}
 health,e:=request("GET","/health","",nil);if e!=nil{fail("health endpoint unreachable: %v",e)}
 var healthData map[string]any
 if json.Unmarshal(health,&healthData)!=nil||healthData["status"]!="ok"{fail("unexpected health response")}
 if *username==""{fmt.Println("PASS: server health only; use -username and BEACON_PASSWORD for authenticated tests.");return}
 pass:=os.Getenv("BEACON_PASSWORD");if pass==""{fail("BEACON_PASSWORD environment variable is required for authenticated checks; password is never printed")}
 login,e:=request("POST","/api/login","",map[string]string{"username":*username,"password":pass,"device_name":"Beacon-Probe-Temporary"});if e!=nil{fail("login: %v",e)}
 var identity struct{Token string `json:"token"`;User struct{ID int `json:"id"`;Username string `json:"username"`} `json:"user"`}
 if json.Unmarshal(login,&identity)!=nil||identity.Token==""||identity.User.ID<=0{fail("login response missing token/user")}
 defer func(){_,e:=request("POST","/api/logout",identity.Token,map[string]any{});if e!=nil{fmt.Fprintln(os.Stderr,"WARNING: could not revoke temporary probe session:",e)}}()
 me,e:=request("GET","/api/me",identity.Token,nil);if e!=nil{fail("identity: %v",e)}
 var current struct{ID int `json:"id"`}
 if json.Unmarshal(me,&current)!=nil||current.ID!=identity.User.ID{fail("authenticated identity mismatched")}
 paths:=[]string{"/api/users","/api/buddies","/api/groups","/api/sessions","/api/conversations","/api/events/latest"}
 for _,p:=range paths{data,e:=request("GET",p,identity.Token,nil);if e!=nil{fail("%s: %v",p,e)};if !json.Valid(data){fail("invalid JSON from %s",p)}}
 fmt.Printf("PASS: server and authenticated APIs work for %s. Temporary session will be revoked.
",identity.User.Username)
}
func safeDetail(b []byte)string{
 var x struct{Detail string `json:"detail"`}
 if json.Unmarshal(b,&x)==nil&&x.Detail!=""{return x.Detail}
 return "server returned an error (response omitted)"
}
