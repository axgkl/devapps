# FZF Mode of Operation

## No Preview

```bash
echo -e 'hello\nworld' | fzf 
```

We call the echo command "**Items Process**", subsequently - it produces (by default) line separated
data chunks:

```bash lp:kroki fn=img/k0

actor "User TTY" as u
participant "Items Process (IP)" as ip
participant "FZF.STDIN" as si
participant FZF as f
participant "FZF.STDOUT" as soi
note over f: FZF starts up\nreads from\n- TTY \n- IP.STDOUT
ip->si: items\n"hello\nworld"
si->f: items
note over f: rendering
f->soi: rendered items
note over soi: hello\nworld
u->si: filter (e.g. 'he')
si->f: filter
f->soi: filtered items
note over soi: hello
u->si: select
si->f: select
f->soi: 'hello'
```

Not shown are non filter/select interactions of the user via the TTY, where the user can

- mark one ore more items (using up/down keys by default)
- change the rendering behaviour while fzf is running
- complete fzf (i.e. have it exit early), with information about what the user entered

!!! note

    Subsequently we connect user and items process directly to fzf.
  
## Streaming Items Process

fzf does not wait until items process is exitting but renders as items arrive:


```bash
( echo hello; sleep 1; echo world) | fzf

```


```bash lp:kroki fn=img/k0.1

actor "User TTY" as u
participant "Items Process (IP)" as ip
participant FZF as f
participant "FZF.STDOUT" as soi
note over f: FZF starts up\nreads from\n- TTY \n- IP.STDOUT
ip->f: "hello"
f->soi: rendered "hello"
note over soi: hello
note over u, soi: 1 second
ip->f: "world"
f->soi: add rendered "world"
note over soi: hello\nworld

```




## With Preview

- fzf can start a preview process (PP) at item mark or filter time
- fzf displays what the process produces on its stdout, within its preview pane



```bash lp:kroki fn=img/k1
participant "Items Process (IP)" as ip
participant FZF as f
participant "STDOUT" as soi
ip->f: items
f->soi: items
f->p: start\nstart args may contain selected item
p->f: output preview (e.g. item details)
f->soi: display preview output within preview pane
```

## With Streaming Preview

As for items process, fzf does also not wait for the preview process to exit - but starts outputting
as soon as data is arriving:



```bash lp:kroki fn=img/k2
participant "Items Process (IP)" as ip
participant FZF as f
participant "STDOUT\nitems\npane" as soi
participant "PreviewProc(PP)" as p
participant "STDOUT\npreview\npane" as sop
participant "STDOUT\npreview status\nindicator" as sos
ip->f: first items
f->soi: items
f->p: start\nstart args may contain selected item
f->sos: "Loading..."
note over f, p: pause (PP produces first data chunk
p->f: pp data chunk 1 (via PP.stdout)
f->sos: "Data..."
f->sop: pp data chunk 1
note over f, p: pause (PP produces second data chunk)
p->f: pp data chunk 2 (via PP.stdout)
f->sop: pp data chunk 2
```


!!! important "Max One Preview Process At A Time"

    If the user marks/filters a different item then fzf kills any possibly running preview process - and
    starts a new one.
