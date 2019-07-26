import os
from flask import request, Flask, send_file, jsonify
from werkzeug import secure_filename
from flask_jwt_extended import jwt_required, JWTManager, create_access_token, get_jwt_identity
from pymongo import MongoClient
from flask_cors import CORS, cross_origin
import datetime
import flask_bcrypt


app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'keyboardCat'    # os.environ.get('SECRET')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(days=1)
app.config['SECRET_KEY'] = 'the quick brown fox jumps over the lazy dog'
app.config['CORS_HEADERS'] = 'Content-Type'
jwt = JWTManager(app)

CORS(app)
client = MongoClient('localhost', 27017)
db = client.music_app
users = db.users
music = db.music

# Create a directory in a known location to save files to.
uploads_dir = os.path.join(app.instance_path, 'uploads')
if not os.path.exists('../var/flask_task-instance/uploads'):
    os.makedirs(uploads_dir)


@app.after_request
def after_request(response):
    header = response.headers
    header['Access-Control-Allow-Origin'] = '*'
    return response


def validate_users(user):
    if len(user['username']) == 0:
        return 'invalid username'

    if len(user['password']) < 8 or len(user['password']) > 16:
        return 'password should be from 8 to 16 chars'

    if users.find_one({'username': user['username']}):
        return 'username already taken'

    return True


def validate_login(user):
    if len(user['username']) == 0:
        return 'invalid username'

    if len(user['password']) < 8 or len(user['password']) > 16:
        return 'password should be from 8 to 16 chars'

    return True


@app.route('/register', methods=['POST'])
@cross_origin(supports_credentials=True)
def register():
    """"" register auth endpoint """""
    data = request.get_json()
    data_is_valid = validate_users(data)
    if data_is_valid is True:
        data['password'] = flask_bcrypt.generate_password_hash(
                            data['password'])
        users.insert_one(data)
        print(list(users.find({})))
        return jsonify({'ok': True, 'message': 'User created successfully!'}), 200
    else:
        return jsonify({'ok': False, 'message': data_is_valid}), 400


@app.route('/auth', methods=['POST'])
@cross_origin(supports_credentials=True)
def auth_user():
    """"" auth endpoint """""
    data = request.get_json()
    data_is_valid = validate_login(data)
    if data_is_valid is True:
        user = users.find_one({'username': data['username']})
        if user and flask_bcrypt.check_password_hash(user['password'], data['password']):
            del user['password']
            del user['_id']
            access_token = create_access_token(identity=data)
            # refresh_token = create_refresh_token(identity=data)
            user['token'] = access_token
            print(user)
            # user['refresh'] = refresh_token
            return jsonify({'ok': True, 'data': user}), 200
    else:
        return jsonify({'ok': False, 'message': data_is_valid}), 400


@app.route('/upload', methods=['POST'])
@cross_origin(supports_credentials=True)
@jwt_required
def upload():
    if request.method == 'POST':
        current_user = get_jwt_identity()
        # save the single "profile" file
        profile = request.files['profile']
        desc = request.form.get('description')
        post_name = request.form.get('name').replace(' ', '_')
        if profile.filename.split('.')[1] != 'mp3':
            return jsonify({'message': 'wrong file format'}), 500
        profile.save(os.path.join(uploads_dir, secure_filename(profile.filename)))
        name = str(datetime.datetime.now())
        os.rename(f'{uploads_dir}/{profile.filename}', f'{uploads_dir}/{name}.mp3')
        post = {
            'by': current_user['username'],
            'filePath': f'{uploads_dir}/{name}.mp3',
            'postName': post_name,
            'description': desc
        }
        music.insert_one(post)
        return jsonify({'message': 'done'}), 200


# @app.route('/refresh', methods=['POST'])
# @jwt_refresh_token_required
# def refresh():
#     ''' refresh token endpoint '''
#     current_user = get_jwt_identity()
#     ret = {
#             'token': create_access_token(identity=current_user)
#     }
#     return jsonify({'ok': True, 'data': ret}), 200


@app.route('/posts/<song>', methods=['DELETE'])
@cross_origin(supports_credentials=True)
@jwt_required
def del_posts(song):
    current_user = get_jwt_identity()
    if request.method == 'DELETE':
        post = music.find_one({'postName': str(song),
                               'by': current_user['username']})
        if post:
            music.delete_one({'postName': str(song),
                             'by': current_user['username']})
            os.remove(post['filePath'])
            return jsonify({
                'ok': True,
                'message': 'deleted'}), 200
        return jsonify({
            'ok': False,
            'message': 'not found'}), 404


@app.route('/posts/<song>', methods=['PATCH'])
@cross_origin(supports_credentials=True)
@jwt_required
def update_posts(song):
    current_user = get_jwt_identity()
    changes = request.get_json()
    name_change = {'postName': changes['postName'].replace(' ', '_')}
    if request.method == 'PATCH':
        post = music.find_one({'postName': str(song),
                               'by': current_user['username']})
        if post:
            music.update_one({'postName': str(song),
                             'by': current_user['username']}, {"$set": name_change}, upsert=False)
            # os.remove(post['filePath'])
            return jsonify({
                'ok': True,
                'message': 'updated'}), 200
        return jsonify({
            'ok': False,
            'message': 'not found'}), 404


@app.route('/song/<song>', methods=['GET'])
@cross_origin(supports_credentials=True)
def find_song(song):
    if request.method == 'GET':
        post = music.find_one({'postName': str(song)})
        if post:
            return send_file(post['filePath'], as_attachment=True), 200
        return jsonify({
            'ok': False,
            'message': 'not found'}), 404


@app.route('/posts/<song>', methods=['GET'])
@cross_origin(supports_credentials=True)
@jwt_required
def find_posts(song):
    if request.method == 'GET':
        post = music.find_one({'postName': str(song)})
        if post:
            del post['_id']
            return jsonify({'message': post}), 200
        return jsonify({
            'ok': False,
            'message': 'not found'}), 404


@app.route('/users/', methods=['GET'])
@cross_origin(supports_credentials=True)
@jwt_required
def get_users_posts():
    if request.method == 'GET':
        query = list(music.find({}))
        print(query)
        for q in range(len(query)):
            query[q]['_id'] = str(query[q]['_id'])
        return jsonify({
            'ok': True,
            'message': query}), 200


@app.route('/users/<user>', methods=['GET'])
@cross_origin(supports_credentials=True)
@jwt_required
def get_user_posts(user):
    if request.method == 'GET':
        query = list(music.find({'by': user}))
        print(query)
        for q in range(len(query)):
            query[q]['_id'] = str(query[q]['_id'])
        return jsonify({
            'ok': True,
            'message': query}), 200


@jwt.unauthorized_loader
@cross_origin(supports_credentials=True)
def unauthorized_response():
    return jsonify({
        'ok': False,
        'message': 'Missing Authorization Header'}), 401
