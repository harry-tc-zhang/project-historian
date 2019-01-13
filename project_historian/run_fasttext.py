import fasttext
import sqlite3
import os
from time import clock


def run_model(db_path, model_path, model_type, model_params):
    print('Training FastText model...')
    start_time = clock()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if not os.path.isdir(model_path):
        os.makedirs(model_path)
    temp_fpath = os.path.join(model_path, '__ft_temp.txt')

    get_text_command = 'SELECT preprocessed FROM rss_data ORDER BY cachedate DESC'
    texts = []
    results = cursor.execute(get_text_command)
    with open(temp_fpath, 'w', newline='', encoding='utf-8') as tmpfile:
        for r in results:
            tmpfile.write(r[0] + '.\n')
    conn.close()

    model_fpath = os.path.join(model_path, 'fasttext_model')
    model = None
    p_ngrams = model_params.get('ngram', 1)
    p_dim = model_params.get('dim', 100)
    p_ws = model_params.get('ws', 5)
    p_epoch = model_params.get('epoch', 5)
    p_loss = model_params.get('loss', 'ns')
    p_min_count = model_params.get('min_count', 5)
    p_silent = model_params.get('silent', 1)
    if model_type == 'cbow':
        model = fasttext.cbow(temp_fpath, model_fpath,
                            word_ngrams=p_ngrams,
                            dim=p_dim,
                            ws=p_ws,
                            epoch=p_epoch,
                            loss=p_loss,
                            silent=p_silent,
                            min_count=p_min_count)
    else:
        model = fasttext.skipgram(temp_fpath, model_fpath,
                            word_ngrams=p_ngrams,
                            dim=p_dim,
                            ws=p_ws,
                            epoch=p_epoch,
                            loss=p_loss,
                            silent=p_silent,
                            min_count=p_min_count)

    os.remove(temp_fpath)

    end_time = clock()
    print('Model trained in {} seconds.'.format(int(end_time - start_time)))

    return model


if __name__ == '__main__':
    params = {
        'ngram': 3,
        'epoch': 10,
        'min_count': 3,
        'loss': 'ns',
        'ws': 8
    }
    db_path = os.path.join('rss_data', 'rss_database.db')
    model_path = 'models'
    model_type = 'skipgram'
    run_model(db_path, model_path, model_type, params)
