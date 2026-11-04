import json,time,requests,websocket
t=[x for x in requests.get("http://127.0.0.1:9222/json",timeout=10).json() if x.get("type")=="page"][0]
ws=websocket.create_connection(t["webSocketDebuggerUrl"],timeout=20); i=0
def cmd(m,p=None):
 global i; i+=1; ws.send(json.dumps({"id":i,"method":m,"params":p or {}}))
 while True:
  r=json.loads(ws.recv())
  if r.get("id")==i: return r
for y in (288,322):
 cmd("Input.dispatchMouseEvent",{"type":"mousePressed","x":100,"y":y,"button":"left","clickCount":1})
 cmd("Input.dispatchMouseEvent",{"type":"mouseReleased","x":100,"y":y,"button":"left","clickCount":1})
 time.sleep(3)
 r=cmd("Runtime.evaluate",{"expression":"localStorage.getItem('dsh.sessions.current')","returnByValue":True}); print(y,r["result"]["result"]["value"])
ws.close()
