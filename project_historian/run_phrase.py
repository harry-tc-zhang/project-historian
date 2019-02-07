from gensim.models.phrases import Phraser, Phrases
import sqlite3
import os
from time import clock
from operator import itemgetter
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize


# Cleans up a token by making it lower-case
# and removing any non-alphanumeric characters in case
# they are compound words.
def clean_token(t):
    if t.isalpha():
        return [t.lower()]
    if t.isdigit():
        return [t]
    if len(t) == 1:
        return [t]
    current_segment = ''
    cleaned_segments = []
    for c in t:
        if c.isdigit() or c.isalpha():
            current_segment += c.lower()
        else:
            cleaned_segments.append(current_segment)
            current_segment = ''
    if current_segment.isdigit() or current_segment.isalpha():
        cleaned_segments.append(current_segment)
    if len(cleaned_segments) > 0:
        isnumber = True
        for segment in cleaned_segments:
            isnumber = (isnumber and segment.isdigit())
        if isnumber:
            return [''.join(cleaned_segments)]
        else:
            return cleaned_segments
    return []


# Function for tokenizing an article using NLTK functions. Tokenizes an article (string) into
# a list of list of strings, where each list of strings is a sentence.
def tokenize_article(article):
    sentences = sent_tokenize(article)
    sent_tokens = [word_tokenize(sentence) for sentence in sentences if len(sentence.split()) > 0]
    stream_tokens = [sum([clean_token(token) for token in sentence], []) for sentence in sent_tokens]
    return stream_tokens


def article_token_generator(db_execution):
    while True:
        row = db_execution.fetchone()
        if row is None:
            break
        # Results are in the format of (id, text)
        tokens = tokenize_article(row[1])
        for token_list in tokens:
            yield token_list


def run_phrases(db_path, models_path):
    print("Preprocessing text...")
    start_time = clock()

    # Create a temporary database to store intermediate results.
    temp_db_path = "temp.db"
    temp_db_connection = sqlite3.connect(temp_db_path)
    temp_db_cursor = temp_db_connection.cursor()
    create_temp_table_cmd = (
        'CREATE TABLE IF NOT EXISTS rss_data('
        'id TEXT, '
        'preprocessed TEXT, '
        'PRIMARY KEY(id)'
        ')'
    )
    temp_db_cursor.execute(create_temp_table_cmd)
    temp_db_connection.commit()

    # Create model directory if it doesn't exist.
    if not os.path.isdir(models_path):
        os.makedirs(models_path)

    # List of stopwords.
    # Single letters are added to detect cases such as "donald j trump".
    swlist = list(stopwords.words('english')) + [chr(i) for i in range(97, 123)]

    # Get all trainable text from the database.
    db_connection = sqlite3.connect(db_path)
    db_cursor = db_connection.cursor()
    full_text_snippet = (
        '('
        'COALESCE(title, " ") '
        '|| ". " || '
        'COALESCE(summary, " ") '
        '|| " " || '
        'COALESCE(content, " ")'
        ')'
    )
    get_rawtext_command = 'SELECT id, {} FROM rss_data ORDER BY cachedate DESC'.format(full_text_snippet)
    execution = db_cursor.execute(get_rawtext_command)
    raw_stream = article_token_generator(execution)

    # Train "level 1" phrases.
    # A relatively high threshold is set for level 1 to train on
    # "strong" phrases, mostly names, e.g. Bob Corker, Mike Pence.
    print("Training level 1 phraser...")
    lv1_phrases = Phrases(raw_stream, common_terms=swlist, threshold=1000.0)
    lv1_phraser = Phraser(lv1_phrases)

    # Command to update the "preprocessed" column of the database.
    insert_template = (
        'INSERT OR REPLACE INTO rss_data (id, preprocessed) '
        'VALUES (?, ?)'
    )
    update_template = (
        'UPDATE rss_data SET preprocessed=? '
        'WHERE id=?'
    )

    # Use level 1 phraser to transform the corpus so that each phrase is replaced with a token, and temporarily store the results in the "preprocessed" column
    print("Updating database with level 1 processing results...")
    lv1_articles_execution = db_cursor.execute(get_rawtext_command)
    update_cursor = db_connection.cursor()
    while True:
        row = lv1_articles_execution.fetchone()
        if row is None:
            break
        temp_db_cursor.execute(insert_template, (row[0], ' '.join(lv1_phraser[sum(tokenize_article(row[1]), [])])))
    temp_db_connection.commit()

    # Command for getting id and initial preprocessed text after level 1 phraser.
    get_preprocessed_command = 'SELECT id, preprocessed FROM rss_data'

    # A level 2 phraser is trained on this new sentence stream.
    lv1_preprocessed_execution = temp_db_cursor.execute(get_preprocessed_command)
    lv1_sent_stream = article_token_generator(lv1_preprocessed_execution)

    # Train "level 2" phrases.
    # A smaller threshold is chosen as a catch-all now that the stronger associations
    # have been captured.
    print("Training level 2 phraser...")
    lv2_phrases = Phrases(lv1_sent_stream, common_terms=swlist, threshold=150)
    lv2_phraser = Phraser(lv2_phrases)

    # Use the level 2 phraser to transform the corpus from level 1 phraser
    # and then turn the transformed phrases back to the original corpus.
    print("Saving level 2 results...")
    lv2_articles_execution = temp_db_cursor.execute(get_preprocessed_command)
    while True:
        row = lv2_articles_execution.fetchone()
        if row is None:
            break
        db_cursor.execute(update_template, (' '.join(lv2_phraser[sum(tokenize_article(row[1]), [])]), row[0]))
    db_connection.commit()

    db_connection.close()
    temp_db_connection.close()

    # Save the trained phrase models just in case.
    # lv1_phrases.save(os.path.join(models_path, 'lv1_phrases'))
    # lv1_phraser.save(os.path.join(models_path, 'lv1_phraser'))
    # lv2_phrases.save(os.path.join(models_path, 'lv2_phrases'))
    # lv2_phraser.save(os.path.join(models_path, 'lv2_phraser'))

    # Delete the temporary database.
    os.remove(temp_db_path)

    end_time = clock()

    print('Preprocessing done in {} seconds.'.format(int(end_time - start_time)))

    return


if __name__ == '__main__':
    db_path = os.path.join('rss_data', 'rss_database.db')
    model_path = 'models'
    run_phrases(db_path, model_path)
