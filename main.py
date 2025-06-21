from werkzeug.wrappers import Request, Response
import json, os, hashlib, re, time
from flask import Flask, request, jsonify, send_file, abort
from mutagen.mp3 import MP3
from tinytag import TinyTag
app = Flask(__name__)


def calculateId(directory):
    dirs = [x for x in os.listdir(directory) if os.path.isfile(directory + '/' +x) and (os.path.splitext(directory + '/' +x)[1].lower() == '.mp3' or os.path.splitext(directory + '/' +x)[1].lower() == '.m4b')]
    if not dirs:
        return 0
    f1 = directory + '/' + dirs[0]
    with open(f1, 'rb') as audioFile:
        # read contents of the file
        data = audioFile.read()
        # pipe contents of the file through
        hex = hashlib.md5(data).hexdigest()
        return hex

def getChapters(directory):
    dirs = [x for x in os.listdir(directory) if os.path.isfile(directory + '/' +x) and (os.path.splitext(directory + '/' +x)[1].lower() == '.mp3' or os.path.splitext(directory + '/' +x)[1].lower() == '.m4b')]
    if not dirs:
        return None
    return sorted(dirs)

def formToJson2(form):
    form = form.replace(", Book 2", "")
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

def formToJson(form):
    article = form[1:-1]
    keys = re.findall("\w+=>", article)
    if not keys:
        if not str(form).startswith('{'):
            return form
        return json.loads(form)
    vals = re.split('\w+=>', article.strip())[1:]
    for i in range(0, len(vals)):
        vals[i] = vals[i].rstrip()
        if vals[i].endswith(','):
            vals[i] = vals[i][0:-1]
        if vals[i].startswith('['):
            values = vals[i][1:-1].split(',')
            vArray = []
            for v in values:
                try:
                    float(v)
                    vArray.append(int(v))
                except:
                    vArray.append('"'+v+'"')
            vals[i] = vArray #'['+','.join(vArray)+']'
        elif vals[i] == 'true':
            vals[i] = '"True"'
        elif vals[i] == 'false':
            vals[i] = '"False"'
        else:
            try:
                float(vals[i])
                vals[i] = int(vals[i])
            except ValueError:
                vals[i] = '"'+vals[i]+'"'



    for i in range(0, len(keys)):
        keys[i] = keys[i].rstrip()
        if keys[i].endswith('=>'):
            keys[i] = keys[i][0:-2]

    m = {}
    for i in range(0, len(keys)):
        m[keys[i]] = vals[i]
    return m

def getDuration(bookDir, chapters):
    totalLen = 0
    lenList = []
    for item in chapters:
        path = bookDir + '/' + item
        audio = TinyTag.get(path)
        totalLen += audio.duration
        lenList.append(int(audio.duration))
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
                    'chapters': chapters, 'type': 'm4a', 'complete': False, 'duration': int(totalDuration),
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

@app.route('/restore', methods=['POST'])
def restore():
    content = request.get_json()
    if not content or 'crcs' not in content or not isinstance(content['crcs'], list):
        return jsonify({'error': 'Missing or invalid crcs'}), 400

    crcs = content['crcs']
    with open("books/books.json", "rt") as f:
        books = json.load(f)

    result = []
    for crc in crcs:
        book = next((b for b in books if b.get('crc') == crc), None)
        if book:
            position = book.get('position', 0)
            chapter = book.get('chapter', 0)
        else:
            position = 0
            chapter = 0
        result.append({'crc': crc, 'position': position, 'chapter': chapter})

    return jsonify({'data': result})

@app.route('/backup', methods=['POST'])
def backup():
    # Parse JSON array from request
    content = request.get_json()
    if not content or 'data' not in content:
        return jsonify({'error': 'Missing data'}), 400

    updates = content['data']

    # Load existing books data
    with open("books/books.json", "rt") as f:
        books = json.load(f)

    # Update books with incoming backup data
    for update in updates:
        for book in books:
            if book['crc'] == update.get('crc'):
                book['position'] = update.get('position', book['position'])
                book['chapter'] = update.get('chapter', book['chapter'])
                break

    # Save updated books data
    with open("books/books.json", "wt") as f:
        json.dump(books, f, indent=4)

    return jsonify({'status': 'backup complete'})

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
                print("No changes detected")
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


#form = "{chapters=>[-2030043135, -2030043134, -2030043133, -2030043132, -2030043131, -2030043130, -2030043129, -2030043128, -2030043127, -2030043126, -2030043125, -2030043124, -2030043123, -2030043122, -2030043121, -2030043120, -2030043119, -2030043118, -2030043117, -2030043116, -2030043115, -2030043114, -2030043113, -2030043112, -2030043111, -2030043110, -2030043109, -2030043108, -2030043107, -2030043106, -2030043105, -2030043104, -2030043103, -2030043102], title=>Galactic Breach Ruins of the Galaxy, Book 2, chapterDurations=>[1449, 1414, 1608, 1453, 1371, 1388, 1869, 568, 914, 1097, 976, 840, 880, 945, 759, 1221, 960, 1120, 819, 876, 878, 775, 826, 861, 1371, 1406, 990, 1104, 1416, 905, 1031, 66, 393, 1409], position=>20, chapter=>0}"
#g = formToJson2(form)
#g = 5

if __name__ == '__main__':
    from werkzeug.serving import run_simple
    run_simple('0.0.0.0', 8080 , app)
