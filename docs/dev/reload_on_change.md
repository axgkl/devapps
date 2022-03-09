# Reload on Change

You can have an arbitrary set of files being monitored in the background and have a reload signal
sent on change. Your app stays in foreground, in order to debug.

This watches all python files, in and below the current dir (the last 1 is for recursive - separator is ':'):

```bash
while true; do my_devapp --dirwatch .:*.py:1; done
```


