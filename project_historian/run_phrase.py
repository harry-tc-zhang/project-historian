from gensim.models.phrases import Phraser, Phrases
import sqlite3
import os
from time import clock
from operator import itemgetter
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize


# Cleans up a token by making it lower-case
# and removing any non-alphanumeric characters in case
# they are compound words
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


@profile
def run_phrases(db_path, models_path):
    print("Preprocessing text...")
    start_time = clock()

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
    # rawtext_dict stores each iteration of the sentence streams
    # for the next training stage/.
    rawtext_dict = {}
    execution = db_cursor.execute(get_rawtext_command)
    while True:
        row = execution.fetchone()
        if row is None:
            break
        rawtext_dict[row[0]] = {
            'raw': row[1]
        }

    # Generate the initial sentence stream for training level 1 phrases.
    # Sentences are splitted and tokenized using NLTK functions.
    sent_stream = []
    for k in rawtext_dict.keys():
        sentences = sent_tokenize(rawtext_dict[k]['raw'])
        sent_tokens = [word_tokenize(sentence) for sentence in sentences if len(sentence.split()) > 0]
        stream_tokens = [sum([clean_token(token) for token in sentence], []) for sentence in sent_tokens]
        rawtext_dict[k]['stream'] = stream_tokens
        sent_stream += stream_tokens

    # Train "level 1" phrases.
    # A relatively high threshold is set for level 1 to train on
    # "strong" phrases, mostly names, e.g. Bob Corker, Mike Pence.
    lv1_phrases = Phrases(sent_stream, common_terms=swlist, threshold=1000.0)
    lv1_phraser = Phraser(lv1_phrases)

    # Use level 1 phraser to transform the corpus so that each phrase is replaced with a token,
    # A level 2 phraser is trained on this new sentence stream.
    lv1_sent_stream = []
    for k in rawtext_dict.keys():
        rawtext_dict[k]['lv1_stream'] = list(lv1_phraser[rawtext_dict[k]['stream']])
        lv1_sent_stream += rawtext_dict[k]['lv1_stream']

    # Train "level 2" phrases.
    # A smaller threshold is chosen as a catch-all now that the stronger associations
    # have been captured.
    lv2_phrases = Phrases(lv1_sent_stream, common_terms=swlist, threshold=150)
    lv2_phraser = Phraser(lv2_phrases)

    # Use the level 2 phraser to transform the corpus from level 1 phraser
    # and then turn the transformed phrases back to the original corpus.
    for k in rawtext_dict.keys():
        lv2_stream = lv2_phraser[rawtext_dict[k]['lv1_stream']]
        lv2_sentences = [' '.join(lv2_sent) for lv2_sent in lv2_stream]
        rawtext_dict[k]['phrasedtext'] = ' '.join(lv2_sentences)

    # Update the database with preprocessed text.
    update_template = (
        'UPDATE rss_data SET preprocessed=? '
        'WHERE id=?'
    )
    for k in rawtext_dict.keys():
        db_cursor.execute(update_template, (rawtext_dict[k]['phrasedtext'], k))
    db_connection.commit()

    db_connection.close()

    # Save the trained phrase models just in case.
    lv1_phrases.save(os.path.join(models_path, 'lv1_phrases'))
    lv1_phraser.save(os.path.join(models_path, 'lv1_phraser'))
    lv2_phrases.save(os.path.join(models_path, 'lv2_phrases'))
    lv2_phraser.save(os.path.join(models_path, 'lv2_phraser'))

    end_time = clock()
    print('Preprocessing done in {} seconds.'.format(int(end_time - start_time)))

    return


if __name__ == '__main__':
    db_path = os.path.join('rss_data', 'rss_database.db')
    model_path = 'models'
    run_phrases(db_path, model_path)
