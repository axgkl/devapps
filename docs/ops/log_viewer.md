# Log Viewer


`ops log_viewer` formats json logs into the colorized dev log format, with all options.

- The `--file_name` can be set to '-', to colorized streaming from a pipe.

- The `--from_journal` switch will digest std journalctl output, putting the process pid
into a `_pid` keyword.


## Example

We go via a file to show the principle (use `-f` to follow journalctl output, where you
can also combine output of many daemons):

```bash
journalctl --user -u myapp.service > journalout 
tail journal_out 
Oct 21 22:48:35 axgk client[2388688]: {"id":"d25b36e2be237ef8","event":"Subscribing","timestamp":"10-21 20:48:35","level":"info","logger":"client"}
Oct 21 22:48:35 axgk client[2388688]: {"id":"1f060dd1f96ef2b0","event":"Subscribing","timestamp":"10-21 20:48:35","level":"info","logger":"client"}
Oct 21 22:48:36 axgk client[2388688]: {"host":"127.0.0.1","port":9092,"timeout":0.5,"event":"Timeout - Kafka Sink","timestamp":"10-21 20:48:36","level":"error","logger":"client"}
Oct 21 22:48:36 axgk client[2388688]: {"event":"TALKING KAFKA OFFLINE","timestamp":"10-21 20:48:36","level":"error","logger":"client"}
Oct 21 22:48:36 axgk client[2388688]: {"id":"a9b21ce0400e09ed","event":"Subscribing","timestamp":"10-21 20:48:36","level":"info","logger":"client"}
Oct 21 22:48:36 axgk client[2388688]: {"host":"127.0.0.1","port":9092,"timeout":0.5,"event":"Timeout - Kafka Sink","timestamp":"10-21 20:48:36","level":"error","logger":"client"}
Oct 21 22:48:36 axgk client[2388688]: {"event":"TALKING KAFKA OFFLINE","timestamp":"10-21 20:48:36","level":"error","logger":"client"}
Oct 21 22:48:36 axgk client[2388688]: {"type":"register","_ids":{"sck":"ax-t333zdgj-geg6uj5q","hbn":"hub1","hub":"127.0.0.1:1881"},"payload_len":48404,"payload":"{'funcs': {'custom.u...","event":"C -> H: register","timestamp":"10-21 20:48:36","level":"debug","logger":"client"}
Oct 21 22:48:36 axgk client[2388688]: {"type": "status", "ts": 1697921316974, "_ws": "ws://127.0.0.1:1881/ws/ax-hub", "payload_len": 10, "payload": "registered", "event": "H -> C: status", "timestamp": "10-21 20:48:36", "level": "debug", "logger": "client"}
Oct 21 22:48:36 axgk client[2388688]: {"type":"status","ts":1697921316974,"payload_len":22768,"payload":"{'pipes': [{'op_ids'...","event":"C -> H: status","timestamp":"10-21 20:48:36","level":"debug","logger":"client"}
```

Now we check the log incl. debug statements, match for "KAFKA" and dimm non matching
lines:

```bash
ops lv -fn journal_out --from_journal -ll 10 --log_dev_match KAFKA --log_dev_dimm_no_match
```

![](./img/kafka.png)
