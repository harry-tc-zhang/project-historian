from operator import itemgetter
import sqlite3
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity, pairwise_distances
from operator import itemgetter
from nltk.corpus import stopwords
from datetime import datetime
from nltk import word_tokenize, sent_tokenize
import numpy as np
import re


def expand_keywords(keywords, model):
    exp_keywords = []
    for kw in keywords:
        exp_kw_candidates = []
        for word in model.words:
            sim = model.cosine_similarity(kw, word)
            if sim > 0.65:
                if kw not in word:
                    exp_kw_candidates.append((word, sim))
        exp_kw_candidates.sort(key=itemgetter(1))
        exp_kw_candidates.reverse()
        exp_kw = [kw] + [ekw[0] for ekw in exp_kw_candidates[:5]]
        exp_keywords.append(exp_kw)
    return exp_keywords


def query_db(exp_keywords, db_path):
    # - main structure of the query
    query_template = (
        'SELECT '
        'id, title, published, canonical, feedname, preprocessed '
        'FROM rss_data '
        'WHERE {}'
    )
    # - subclauses matching expanded keywords
    subclauses = [['preprocessed LIKE "%{}%"'.format(ekw) for ekw in exp_kw] for exp_kw in exp_keywords]
    # - compile the WHERE part of the clause
    whereclause = ' AND '.join(['({})'.format(' OR '.join(sc)) for sc in subclauses])
    # - full query
    query = query_template.format(whereclause)
    # - execute the query in database
    db_connection = sqlite3.connect(db_path)
    db_cursor = db_connection.cursor()
    query_results = db_cursor.execute(query)
    # - get a list of english stopwords
    stop_words = list(stopwords.words('english'))
    # - store results separately (the indices should match)
    ids = []
    titles = []
    timestamps = []
    links = []
    feednames = []
    texts = []
    text_tokens = []
    num_records = 0
    for result in query_results:
        # - an additional pass to make sure match is found in complete words rather than partial
        # - e.g. 'msu' (Michigan State University) matching 'samsung'
        rtext_tokens = [word for word in word_tokenize(result[5].lower())
                        if re.match('[0-9a-zA-Z_\-]{3,}', word) and word not in stop_words]
        qfound = True
        for kw_group in exp_keywords:
            kwfound = False
            for kw in kw_group:
                if kw in rtext_tokens:
                    kwfound = True
                    break
            qfound = (qfound and kwfound)
            if not qfound:
                break
        if not qfound:
            continue
        ids.append(result[0])
        titles.append(result[1])
        timestamps.append(result[2])
        links.append(result[3])
        feednames.append(result[4])
        texts.append(' '.join(rtext_tokens))
        text_tokens.append(rtext_tokens)
        num_records += 1
    # - close the db connection
    db_connection.close()
    # - return results as dictionary
    return {
        'ids': ids,
        'titles': titles,
        'timestamps': timestamps,
        'links': links,
        'feednames': feednames,
        'texts': texts,
        'text_tokens': text_tokens,
        'length': num_records
    }


def gen_doc_vecs(texts, text_tokens, model, threshold=70):
    # Run TF-IDF on the resulting text
    tfidfvec = TfidfVectorizer()
    tfidf_data = tfidfvec.fit_transform(texts)
    tfidf_vocab = tfidfvec.vocabulary_
    # Tokenize the returned text
    #raw_text_tokens = [word_tokenize(text) for text in texts]
    # Obtain a list of stopwords
    #stop_words = list(stopwords.words('english'))
    # Clean the tokens, removing stopwords and punctuations
    #text_tokens = [[token for token in text
    #                if (token not in stop_words) and len(token) > 1] for text in raw_text_tokens]
    # Retrieve word vectors from the FastText model
    text_vecs = [[model[token] for token in text] for text in  text_tokens]
    # Retrieve TF-IDF values for each token as weights
    text_weights = []
    for i in range(len(text_tokens)):
        tweights = []
        for token in text_tokens[i]:
            if token in tfidf_vocab.keys():
                tweights.append(tfidf_data[i, tfidf_vocab[token]])
            else:
                tweights.append(0)
        wthreshold = np.percentile(tweights, threshold)
        text_weights.append([w if w >= wthreshold else 0 for w in tweights])
    # Use weighted average of word vectors as a vector presentation of a story
    doc_vecs = []
    for i in range(len(text_vecs)):
        if sum(text_weights[i]) == 0:
            doc_vecs.append(np.multiply(text_vecs[i][0], 0))
        else:
            newvec = np.average(text_vecs[i], weights=text_weights[i], axis=0)
            vecnorm = np.linalg.norm(newvec)
            doc_vecs.append(newvec / vecnorm)
            #doc_vecs.append(newvec)
    return doc_vecs


def eval_cluster(cluster):
    distances = [c[1] for c in cluster]
    return np.mean(distances)


def iterative_cluster(data, clean_threshold=2, split=2):
    cdata = data
    next_cid = 0
    next_sid = 0
    clusters = {}
    # In each cluster: (center, [(index, distance)...], quality)
    clusters[0] = [None, [(i, 0) for i in range(len(data))], None]
    next_cid += 1
    while True:
        clusterer = KMeans(split, n_init=20)
        cdata = [data[i[0]] for i in clusters[next_sid][1]]
        cresults = clusterer.fit_predict(cdata)
        new_clusters = [[clusterer.cluster_centers_[i], []] for i in range(split)]
        for i in range(len(cresults)):
            item_index = clusters[next_sid][1][i][0]
            item_data = data[item_index]
            item_dist = pairwise_distances([item_data], [new_clusters[cresults[i]][0]])[0][0]
            new_clusters[cresults[i]][1].append((item_index, item_dist))
        for nc in new_clusters:
            clusters[next_cid] = nc + [eval_cluster(nc[1])]
            next_cid += 1
        del clusters[next_sid]
        next_sid += 1
        while clusters[next_sid][2] < clean_threshold:
            next_sid += 1
            if next_sid == next_cid:
                break
        if next_sid == next_cid:
            break
    rclusters = [clusters[k] for k in clusters.keys()]
    return rclusters


def present_clusters(clusters, data_dict, max_items=10):
    rclusters = []
    for cluster in clusters:
        rcluster = []
        for ci in cluster[1]:
            rcluster.append({
                'title': data_dict['titles'][ci[0]],
                'timestamp': data_dict['timestamps'][ci[0]],
                'feedname': data_dict['feednames'][ci[0]],
                'link': data_dict['links'][ci[0]],
                'distance': ci[1]
            })
        rcluster.sort(key=itemgetter('distance'))
        frcluster = rcluster[:max_items]
        frcluster.sort(key=itemgetter('timestamp'))
        rclusters.append((frcluster[0]['timestamp'], frcluster))
    rclusters.sort(key=itemgetter(0))
    return rclusters
