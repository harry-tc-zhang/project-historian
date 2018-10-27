from flask import Flask
import os
import fasttext
import sqlite3
import redis
from flask_kvsession import KVSessionExtension
from simplekv.memory.redisstore import RedisStore
from flask import render_template, request, jsonify, session
from pipeline import *


app = Flask(__name__)
store = RedisStore(redis.StrictRedis())
KVSessionExtension(store, app)
app.secret_key = 'PZ2HKD7WIAM1D708OE9I78KZ0'


data_path = os.path.join('..', 'project_historian')
models_path = os.path.join(data_path, 'models')
rss_path = os.path.join(data_path, 'rss_data')

model_path = os.path.join(models_path, 'fasttext_model.bin')
db_path = os.path.join(rss_path, 'rss_database.db')

model = fasttext.load_model(model_path)
print('- Model loaded successfully.')


@app.route('/')
def index():
	return render_template('index.html')


@app.route('/query', methods=['POST'])
def query():
	keywords = []
	if 'keywords' not in request.form:
		return None
	t_keywords = request.form['keywords'].split(',')
	keywords = ['_'.join(kw.strip().split()) for kw in t_keywords]
	print(keywords)
	session['keywords'] = keywords
	session['exp_keywords'] = expand_keywords(keywords, model)
	return jsonify({
				'exp_keywords': session['exp_keywords'],
			})


@app.route('/lookup', methods=['POST'])
def lookup():
	lookup_keywords = None
	if 'keywords' not in request.form:
		lookup_keywords = session['exp_keywords']
	if 'keywords' in request.form:
		session['final_keywords'] = request.form['keywords']
		print(session['final_keywords'])
		lookup_keywords = session['final_keywords']
	session['data'] = query_db(lookup_keywords, db_path)
	return jsonify({
		'num_stories': session['data']['length']
	})


@app.route('/vectorize', methods=['POST'])
def vectorize():
	if 'data' in session.keys():
		session['vectors'] = gen_doc_vecs(session['data']['texts'],  session['data']['text_tokens'], model, threshold=30)
		return jsonify({
			'num_vectors': len(session['vectors'])
		})
	return None


@app.route('/cluster', methods=['POST'])
def cluster():
	par = 1
	if 'par' in request.form:
		par = float(request.form['par'])
	session['clusters'] = iterative_cluster(session['vectors'], par)
	return jsonify(present_clusters(session['clusters'], session['data']))


if __name__ == '__main__':
	app.run(host='0.0.0.0', port=5000, debug=True)
