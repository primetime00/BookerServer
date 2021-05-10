from werkzeug.wrappers import Request, Response
import json, os, hashlib, re, time
from flask import Flask, request, jsonify, send_file, abort
from mutagen.mp3 import MP3
app = Flask(__name__)


def calculateId(directory):
    dirs = [x for x in os.listdir(directory) if os.path.isfile(directory + '/' +x) and os.path.splitext(directory + '/' +x)[1].lower() == '.mp3']
    if not dirs:
        return 0
    f1 = directory + '/' + dirs[0]
    with open(f1, 'rb') as mp3File:
        # read contents of the file
        data = mp3File.read()
        # pipe contents of the file through
        hex = hashlib.md5(data).hexdigest()
        return hex

def getChapters(directory):
    dirs = [x for x in os.listdir(directory) if os.path.isfile(directory + '/' +x) and os.path.splitext(directory + '/' +x)[1].lower() == '.mp3']
    if not dirs:
        return None
    return sorted(dirs)

def formToJson(form):
    article = re.sub(r'(\w+)=>', r'"\1": ', form)
    ce = re.compile(r':\s*([\w\s]+)')
    matches = ce.finditer(article)
    corrections = []
    changes = False;
    for m in matches:
        changes = True
        val = m.group(1).strip()
        if len(val) == 0:
            continue
        try:
            float(val)
        except ValueError:
            corrections.append((m.span(1)[1],m.span(1)[0]))

    for item in reversed(corrections):
        val = article[item[1]:item[0]]
        if val == 'true':
            article[0:item[1]] + "True" + article[item[0]:]
        elif val == 'false':
            article[0:item[1]] + "False" + article[item[0]:]
        else:
            article = article[0:item[0]] + '"' + article[item[0]:]
            article = article[0:item[1]] + '"' + article[item[1]:]
    if changes:
        return json.loads(article)
    else:
        return form


def getDuration(bookDir, chapters):
    totalLen = 0
    lenList = []
    for item in chapters:
        path = bookDir + '/' + item
        audio = MP3(path)
        totalLen += audio.info.length
        lenList.append(int(audio.info.length))
    return totalLen, lenList


@app.route('/update', methods=['GET'])
def update():
    now = int(time.time() * 1000)
    directory = os.getcwd()
    updated = False
    bookDirs = []
    try:
        with open ("books/books.json", "rt") as f:
            data = json.load(f)
    except:
        data = []

    path = directory + '/books'
    bookDir = os.listdir(path)
    for item in bookDir:
        bookpath = path + '/' + item
        if not os.path.isdir(bookpath):
            continue
        bookDirs.append(bookpath)
    bookDirList = []
    for bookDir in bookDirs:
        bookName = os.path.basename(bookDir)
        bookDirList.append(bookName)
        if len(data) == 0 or bookName not in [d['directory'] for d in data]:
            id = calculateId(bookDir)
            if id == 0:
                continue
            updated = True
            chapters = getChapters(bookDir)
            totalDuration, lenList = getDuration(bookDir, chapters)
            item = {"directory":  bookName, "position":  0, "chapter": 0, "crc":  id, "title": bookName,
                    'chapters': chapters, 'type': 'mp3', 'complete': False, 'duration': int(totalDuration),
                    'chapterDurations': lenList}
            data.append(item)
            item['lastWriteDevice'] = 'PHONE'
            item['lastWriteTime'] = now
            item['lastReadDevice'] = 'PHONE'
            item['lastReadTime'] = now


    nd = []
    for item in data:
        if item['directory'] in bookDirList:
            nd.append(item)
        else:
            updated = True
    data = nd

    if updated:
        with open ("books/books.json", "wt") as f:
            json.dump(data, f, indent=4)
    return "Update {}!".format("Complete" if updated else "Not Needed")

@app.route('/list', methods=['GET', 'POST'])
def listBooks():
    data = None
    with open ("books/books.json", "rt") as f:
        data = json.load(f)
    keyData = {}
    for item in data:
        keyData[item['crc']] = item
    return jsonify(keyData)

@app.route('/book/<id>/<int:chapter>', methods=['GET'])
def book(id, chapter):
    data = None
    with open ("books/books.json", "rt") as f:
        data = json.load(f)
    res = [x for x in data if x['crc'] == id]
    if res:
        book = res[0]
    else:
        abort(404)
    if chapter >= len(book['chapters']):
        abort(404)
    path = "{}/{}/{}/{}".format(os.getcwd(), 'books', book['directory'], book['chapters'][chapter])
    return send_file(path, as_attachment=True)


def calculatePosition(currentChapter, currentPosition, allDurations):
    pos = 0
    for i in range(0, currentChapter):
        pos += allDurations[i]
    pos += currentPosition
    return pos


@app.route('/progress', methods=['POST'])
def progress():
    progress = request.form.to_dict()
    for key in progress.keys():
        progress[key] = formToJson(progress[key])
    now = int(time.time() * 1000)
    with open ("books/books.json", "rt") as f:
        data = json.load(f)
    deviceNeedsUpdate = False
    serverNeedsUpdate = False

    for item in data:
        if not item["crc"] in progress:
            continue

        progressItem = progress[item["crc"]]
        receivedPos = calculatePosition(progressItem["chapter"], progressItem["position"], progressItem['chapterDurations'])
        recordedPos = calculatePosition(item["chapter"], item["position"], item['chapterDurations'])

        lastWriteDevice = item['lastWriteDevice']
        lastWriteTime = item['lastWriteTime']
        lastReadDevice = item['lastReadDevice']
        lastReadTime = item['lastReadTime']

        currentDevice = progress['DEVICE']

        if currentDevice == 'PHONE':
            progressItem["chapter"] = item["chapter"]
            progressItem["position"] = item["position"]
            progressItem['update'] = True
            item['lastReadDevice'] = currentDevice
            item['lastReadTime'] = now
        else: #device is a watch
            if progressItem["chapter"] == item["chapter"] and progressItem["position"] == item["position"]: #nothing has changed at all
                print("No change detected")
                progressItem['update'] = False
            else:
                if lastWriteTime > lastReadTime and lastWriteDevice == 'PHONE':
                    print("last Write device was a phone, and the last write time was {} sec after the read time.  Updating Watch".format((lastWriteTime - lastReadTime)/1000))
                    progressItem["chapter"] = item["chapter"]
                    progressItem["position"] = item["position"]
                    item['lastReadDevice'] = currentDevice
                    item['lastReadTime'] = now
                    progressItem['update'] = True
                elif lastReadDevice == 'PHONE' and lastWriteDevice == 'PHONE':
                    print("last Read/Write device was a phone, updating watch")
                    progressItem["chapter"] = item["chapter"]
                    progressItem["position"] = item["position"]
                    item['lastReadDevice'] = currentDevice
                    item['lastReadTime'] = now
                    progressItem['update'] = True
                elif lastWriteDevice == 'WATCH' and lastReadDevice == 'WATCH' and lastReadTime >= lastWriteTime:
                    print("last Read/Write device was a watch, and the last read time was {} sec after the write time.  Updating Watch".format((lastReadTime - lastWriteTime)/1000))
                    progressItem["chapter"] = item["chapter"]
                    progressItem["position"] = item["position"]
                    item['lastReadDevice'] = currentDevice
                    item['lastReadTime'] = now
                    progressItem['update'] = True
                else:
                    if receivedPos > recordedPos:
                        print("Time on watch is later than db.  Updating DB")
                        item["chapter"] = progressItem["chapter"]
                        item["position"] = progressItem["position"]
                        item['lastWriteDevice'] = currentDevice
                        item['lastWriteTime'] = now
                        item['lastUpdate'] = currentDevice
                        progressItem['update'] = False
                    else:
                        print("Time on watch is earlier than db.  Updating Watch")
                        progressItem["chapter"] = item["chapter"]
                        progressItem["position"] = item["position"]
                        item['lastReadDevice'] = currentDevice
                        item['lastReadTime'] = now
                        progressItem['update'] = True


    with open ("books/books.json", "wt") as f:
        json.dump(data, f, indent=4)

    print(progress)
    return jsonify(progress)

@app.route('/checkin', methods=['POST'])
def checkin(): #done from the phone
    now = int(time.time() * 1000)
    progress = request.form.to_dict()
    for key in progress.keys():
        progress[key] = formToJson(progress[key])
    with open("books/books.json", "rt") as f:
        data = json.load(f)

    for item in data:
        if not item["crc"] in progress:
            continue
        progressItem = progress[item["crc"]]
        if progressItem['complete'] != item['complete']:
            item["complete"] = progressItem["complete"]

        item["chapter"] = progressItem["chapter"]
        item["position"] = progressItem["position"]
        item['lastWriteDevice'] = progress['DEVICE']
        item['lastWriteTime'] = now

    with open ("books/books.json", "wt") as f:
        json.dump(data, f, indent=4)

    return jsonify({'time': str(now)})



if __name__ == '__main__':
    from werkzeug.serving import run_simple
    run_simple('0.0.0.0', 8080, app)