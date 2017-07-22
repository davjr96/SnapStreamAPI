from flask import Flask, jsonify, request, redirect, url_for
from pymongo import MongoClient
from flask import request
from geopy.distance import vincenty
import os
from werkzeug.utils import secure_filename
import subprocess
from datetime import datetime
import tinys3

UPLOAD_FOLDER = './static'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

client = MongoClient("")
db = client.memories
collection = db.events

conn = tinys3.Connection("","",'')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return 'Server for Hack UVA Snap Stream Project'


@app.route('/event', methods=['GET'])
def event():
    if request.method == 'GET':
        id = int(request.args.get('id'))
        obj = collection.find_one({'id': id})
        obj.pop("_id")
        return jsonify(obj)


@app.route('/events', methods=['GET'])
def events():
    if request.method == 'GET':
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        user = (lat, lon)
        cursor = collection.find({})
        documents = []
        for document in cursor:
            doc_local = (document["lat"], document["lon"])
            if(vincenty(doc_local, user).miles < 5.0):
                document.pop("_id")
                documents.append(document)
        documents.sort(key=lambda x: x['id'], reverse=False)
        return jsonify(documents)
    return "Use location as parameters"


@app.route('/createevent', methods=['GET', 'POST'])
def newevent():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename("Event" + str(hash(request.args.get('name')+str(datetime.now()))) + unicode(
                datetime.now()) + request.args.get('name') + "." + file.filename.split(".")[1])
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            cmd = '/usr/bin/convert  -resize 100x100 static/' + \
                filename + " static/thumb." + filename
            p = subprocess.Popen(cmd, shell=True)
            p.communicate()

            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            filename =  "thumb." + filename
            f = open(os.path.join(app.config['UPLOAD_FOLDER'], filename),'rb')
            conn.upload(filename,f)
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            newEvent = {}
            newEvent['id'] = hash(request.args.get('name')+str(datetime.now()))
            newEvent['name'] = str(request.args.get('name'))
            newEvent['lat'] = float(request.args.get('lat'))
            newEvent['lon'] = float(request.args.get('lon'))
            newEvent['date'] = datetime.now()
            newEvent['pictures'] = []
            newEvent['thumbnail'] = "https://s3.amazonaws.com/snapstreamapi/"+filename
            collection.insert_one(newEvent)

            return "Recieved"
    return "Server for Hack UVA Snap Stream Project"


@app.route('/addpicture', methods=['GET', 'POST'])
def picture():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename("Event" + request.args.get('event') + unicode(
                datetime.now()) + request.args.get('user') + "." + file.filename.split(".")[1])
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            cmd = '/usr/bin/convert -resize 100x100 static/' + \
                filename + " static/thumb." + filename
            p = subprocess.Popen(cmd, shell=True)
            p.communicate()

            f = open(os.path.join(app.config['UPLOAD_FOLDER'], filename),'rb')
            conn.upload(filename,f)
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            thumbname = 'thumb.' + filename
            f = open(os.path.join(app.config['UPLOAD_FOLDER'], thumbname),'rb')
            conn.upload(thumbname,f)
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], thumbname))

            user = request.args.get('user')
            content = request.get_json()
            newPicture = {}
            newPicture['id'] = hash(filename)
            newPicture['date'] = datetime.now()
            newPicture['vote'] = 0
            newPicture['reported'] = False
            newPicture['uploadedby'] = user
            newPicture['link'] = "https://s3.amazonaws.com/snapstreamapi/" + filename
            newPicture['thumbnail'] = "https://s3.amazonaws.com/snapstreamapi/"+thumbname
            collection.update({'id': int(request.args.get('event'))}, {
                              '$push': {'pictures': newPicture}}, upsert=False)

            return redirect('static/' + filename)
    return '''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <form method=post enctype=multipart/form-data>
      <p><input type=file name=file>
         <input type=submit value=Upload>
    </form>
    '''
@app.route('/upvote',methods = ['GET'])
def upvote():
    eventID = long(request.args.get("event"))
    id = long(request.args.get("id"))
    collection.update({'id': eventID, "pictures.id" : id}, {
                      '$inc': {'pictures.$.vote': 1 }},False, True)
    return "Success"

@app.route('/downvote',methods = ['GET'])
def downvote():
    eventID = long(request.args.get("event"))
    id = long(request.args.get("id"))
    collection.update({'id': eventID, "pictures.id" : id}, {
                      '$inc': {'pictures.$.vote': -1 }},False, True)
    return "Success"

if __name__ == '__main__':
    app.run()
