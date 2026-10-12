from pathlib import Path
p=str(Path(__file__).resolve().parent/'cmd'/'beacon'/'ui.go')
s=open(p).read()
# Named mappings, not credential pairs; maintain the same source transformation.
subs=dict(renderLogin='paintLogin',renderRoster='paintRoster',renderChat='paintChat',renderDirectory='paintDirectory')
for origin,replacement in subs.items():
    a='func (c *ClientState) '+origin+'('
    st=s.index(a)
    beg=s.index('{',st)
    n=0
    end=None
    for i in range(beg,len(s)):
        if s[i]=='{':n+=1
        elif s[i]=='}':
            n-=1
            if n==0:end=i+1;break
    assert end
    sig=s[st:beg]
    suffix='return c.'+replacement+'(s)' if origin!='renderChat' else 'return c.'+replacement+'(id, s)'
    s=s[:st]+sig+'{\n\t'+suffix+'\n}'+s[end:]
# Add hover field, keep input methods and click map.
s=s.replace('\tnotice           string\n}', '\tnotice           string\n\thover            string\n\tchatScroll       map[int]int\n}')
s=s.replace('chatEntries: map[int]string{}','chatEntries: map[int]string{}, chatScroll: map[int]int{}')
# chat scroll handling input click; actions
old='''	if screen == "roster" {
		if button == 4 || button == 5 {'''
# Add chat scrolling preamble
new='''	if screen == "chat" && (button == 4 || button == 5) {
        c.mu.Lock()
        messages := c.ctl.Snap().Chats[id]
        maxOffset := len(messages)-1
        if maxOffset < 0 { maxOffset = 0 }
        if button == 4 && c.chatScroll[id] < maxOffset { c.chatScroll[id]++ }
        if button == 5 && c.chatScroll[id] > 0 { c.chatScroll[id]-- }
        c.mu.Unlock()
        return uiAction{}
    }
	if screen == "roster" {
		if button == 4 || button == 5 {'''
assert old in s;s=s.replace(old,new)
# add after c.authenticated helper? do new file
open(p,'w').write(s)
