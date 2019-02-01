from run_phrase import run_phrases
from run_fasttext import run_model
import os
from time import sleep


# Convenience script to run the phrase detection and FastText training.
if __name__ == '__main__':
    db_path = os.path.join('rss_data', 'rss_database.db')
    model_path = 'models'
    run_phrases(db_path, model_path)
    sleep(60)
    fasttext_params = params = {
        'ngram': 3,
        'epoch': 10,
        'min_count': 3,
        'loss': 'ns',
        'ws': 8
    }
    model_type = 'skipgram'
    run_model(db_path, model_path, model_type, fasttext_params)