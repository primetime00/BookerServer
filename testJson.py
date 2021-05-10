import json
import time

pos = 942
ch = 9

with open("books/books.json", "rt") as f:
    data = json.load(f)
now = int(time.time() * 1000)
item = data[0]
item['lastWriteTime'] = now
item['lastReadTime'] = now-300000
item['lastWriteDevice'] = 'PHONE'
item['position'] = pos
item['chapter'] = ch
print(item)

with open("books/books.json", "wt") as f:
    json.dump(data, f, indent=4)

