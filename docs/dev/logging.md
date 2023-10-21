# Logging


You have a rich structured logging system, backed by [structlog][sl]:

The features we show by matching the help full (-hf) output of an arbitrary app (here `ops
project`) on the match string "log": 

```bash lp fmt=xt_flat
ops project -hf log
```

## Theming

You can pick a theme for the dev console log output (`--log_fmt=2`), i.e. the default output format
when run in foreground. 

`dev logging_style` is the tool to do that - say `dev ls s` to get a theme previewer
(using [fzf](https://github.com/junegunn/fzf)).

![](./img/themesel.png)

Note: True color themes are not slower than 256 themes - but some terminals do not support
them - pick a non true color one then.

If you want your terminal base16 styles, pick 'dark'

## Watching Json Logs

The `ops log_viewer` command allows to ingest json logs, including systemd's journal logs,
containing them.





[sl]: https://www.structlog.org/en/stable/
