import tensorflow as tf
import iteratortools as it
import model_maker
import argparse
import programtokenizer
import json
import train
import os
import sys
import tempfile
import subprocess
import uuid
#tf.enable_eager_execution()

# ARGPARSE #


parser = argparse.ArgumentParser(description='Automatically Generate Code', prog='CBT')
parser.add_argument('checkpoint_dir', help='The directory of the most recent training checkpoint')
parser.add_argument('language', help='The language being generated')
parser.add_argument('--Cin', help='Provide input via the console')
parser.add_argument('--Fin', help='Specify a python file to take as input')
parser.add_argument('--Fout', help='Specify a file to output to')
parser.add_argument('--lines', help='The number of lines to generate, the default is 1', type=int, choices=range(1,21), default=1)


# FUNCTIONS #


def newline_token(lang):
    if lang.lower() == 'c':
        return ';'
    elif lang.lower() in 'python':
        return programtokenizer.word_to_token['\n']


def generate_text(model, language, start_string, num_lines, index_to_token, var_char_index):
    if language.lower() == 'c':
        start_string, variable_to_token = programtokenizer.tokenize_c(start_string, var_char_index)
    elif language.lower() in 'python':
        # Evaluation step (generating text using the learned model)
        name_tokenizer = programtokenizer.NameTokenizer(var_char_index)
        start_string, variable_to_token = name_tokenizer.tokenize(start_string)
        start_string = programtokenizer.SyntaxTokenizer(programtokenizer.word_to_token).tokenize(start_string)
    else:
        sys.exit(1)

    # Converting our start string to numbers (vectorizing)
    token_to_index = {t: i for i, t in index_to_token.items()}

    input_eval = [index_to_token[s] for s in start_string]
    input_eval = tf.expand_dims(input_eval, 0)

    # Empty string to store our results
    text_generated = []

    # Low temperatures results in more predictable text.
    # Higher temperatures results in more surprising text.
    # Experiment to find the best setting.
    temperature = 1.0

    # Here batch size == 1
    model.reset_states()

    new_lines = 0

    generated_line = ''
    while new_lines != num_lines:
        predictions = model(input_eval)
        # remove the batch dimension
        predictions = tf.squeeze(predictions, 0)

        # using a categorical distribution to predict the word returned by the model
        predictions = predictions / temperature
        predicted_id = tf.random.categorical(predictions, num_samples=1)[-1, 0].numpy()

        # We pass the predicted word as the next input to the model
        # along with the previous hidden state
        input_eval = tf.expand_dims([predicted_id], 0)

        generated_character = token_to_index[predicted_id]
        generated_line += generated_character

        if generated_character == newline_token(language) or len(generated_line) > 100:
            if generated_line.strip() != '':
                new_lines += 1
                text_generated.append(generated_line)
            generated_line = ''


    if language.lower() == 'c':
        whole_output = programtokenizer.untokenize_c(start_string + ''.join(text_generated), {v: k for k, v in variable_to_token.items()})
        tempid = str(uuid.uuid4())
        with open(os.path.join(it.REPO_ROOT_PATH, 'temp{}.c'.format(tempid)), mode='w+') as f:
            f.write(whole_output)
            f.flush()
            subprocess.call([os.path.join(it.REPO_ROOT_PATH, 'lib', 'C-Code-Beautifier'), f.name, os.path.join(it.REPO_ROOT_PATH, 'formattedtemp{}.c'.format(tempid))])
        with open(os.path.join(it.REPO_ROOT_PATH, 'formattedtemp{}.c'.format(tempid)), mode='r') as f:
            whole_output = f.read()
        just_generated_lines = programtokenizer.untokenize_c('\n'.join(text_generated), {v: k for k, v in variable_to_token.items()})
        os.remove(os.path.join(it.REPO_ROOT_PATH, 'temp{}.c'.format(tempid)))
        os.remove(os.path.join(it.REPO_ROOT_PATH, 'formattedtemp{}.c'.format(tempid)))
    elif language.lower() in 'python':
        whole_output = programtokenizer.untokenize_python(start_string + ''.join(text_generated), {v: k for k, v in variable_to_token.items()})
        text_generated_newline_removed = []
        for i, line in enumerate(text_generated):
            if line.endswith(programtokenizer.word_to_token['\n']):
                text_generated_newline_removed.append(line[:-1])
        just_generated_lines = programtokenizer.untokenize_python('\n'.join(text_generated_newline_removed), {v: k for k, v in variable_to_token.items()})

    return whole_output, just_generated_lines.split('\n') + ['','','','']


# MAIN #


if __name__ == '__main__':
    # Parse arguments
    args = parser.parse_args()
    checkpoint_dir = args.checkpoint_dir
    language = args.language
    input_dir = args.Fin
    output_dir = args.Fout
    console_input = args.Cin
    num_lines = args.lines
    gen_start_string = ''

    # Build the model
    with open(os.path.join(checkpoint_dir, train.WORD_TO_INDEX_FILE)) as json_file:
        state = json.load(json_file)

        model = model_maker.build_model(int(state['vocab_size']), model_maker.EMBEDDING_DIMENSION, model_maker.RNN_UNITS, batch_size=1)
        model.load_weights(tf.train.latest_checkpoint(checkpoint_dir))
        model.build(tf.TensorShape([1, None]))

        # Read input
        if input_dir and console_input:
            parser.error('Please specify either --Fin or --Cin, not both')

        if input_dir:
            print('Taking input from file {}'.format(input_dir))
            with open(input_dir, 'r') as f:
                gen_start_string = f.read()
        elif console_input:
            gen_start_string = console_input
        else:
            parser.error('No input method specified')

        # Generate output
        generated_text = generate_text(model, language, gen_start_string, num_lines, state['index_to_token'], state['variable_char_start'])

        if output_dir:
            print("Outputting to file {}".format(output_dir))
            with open(output_dir, 'w') as f:
                f.write(generated_text)
        else:
            print(generated_text)
