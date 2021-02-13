import csv
import sys
import gzip
import pickle
import base64
import re
from collections import defaultdict

SPLIT_FILE = "splits.csv"
DATA_FILE_PREFIX = "2020-09-10_"

PROJECTS_LIST = ["httpd", "nginx", "libtiff", "openssl", "libav"]
D2A_V1_DATA_DIR = "/Users/sapujar/Desktop/IBM/AI4VA/data/AutoLabellerData/"
SPLIT_DATA_OUTPUT_DIR = "/Users/sapujar/Desktop/IBM/AI4VA/data/d2av1_releaseoutput/"


def get_datafile_path(data_dir, file_prefix, project):
    project_prefix = data_dir + file_prefix + project
    one = project_prefix + "_labeler_1.pickle.gz"
    zero_after_fix = project_prefix + "_after_fix_extractor_0.pickle.gz"
    zero = project_prefix + "_labeler_0.pickle.gz"
    return one, zero_after_fix, zero


def read_pickle_data_file(file_path):
    data = []
    cnt = 0
    with gzip.open(file_path, mode = 'rb') as fp:
        while True:
            try:
                item = pickle.load(fp)
                cnt += 1
                data.append(item)
                #if cnt == 1:
                #    break
            except EOFError:
                break
    print("%d issues loaded\n" % len(data))
    #print(json.dumps(data[0], indent=2))
    #print("\n\n")
    return data


# regex to remove empty lines
def remove_empty_lines(text):
    return re.sub(r'^$\n', '', text, flags=re.MULTILINE)


# regex to remove comments from a file
def remove_comments(text):
    def replacer(match):
        s = match.group(0)
        if s.startswith('/'):
            return " " # note: a space and not an empty string
        else:
            return s
    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
        re.DOTALL | re.MULTILINE
    )
    return re.sub(pattern, replacer, text)


# regex to remove space before newLine character
def remove_space_before_newline(text):
    return re.sub(r'\s+$', '', text, flags=re.M)


def decode_and_decompress_string(encoded_content):
    encoded_bytes = encoded_content.encode('ascii')
    compressed_bytes = base64.b64decode(encoded_bytes)
    b_content = gzip.decompress(compressed_bytes)
    content = b_content.decode()
    return content


def create_cbert_bug_dict_data_list(data, after_fix=0):
    bugs_list = []
    total_functions_count = 0
    no_functions_count = 0
    no_bug_function_count = 0
    func_path_bug_function_count = 0
    for bug in data:
        if after_fix == 0:
            decoded_bug_trace = decode_and_decompress_string(bug["zipped_bug_report"])
            decoded_bug_trace = decoded_bug_trace.split("\n")
            if decoded_bug_trace[0].startswith("#"):
                decoded_bug_trace = decoded_bug_trace[1:]
            decoded_bug_trace = "\n".join(decoded_bug_trace)
            bug_url = bug['bug_info']['url']
            bug_info_function_path = bug['bug_info']['file'] + ":" + bug['bug_info']['procedure']
            bug_line = str(bug["bug_info"]["line"])
        else:
            decoded_bug_trace = ""
            bug_url = ""
            bug_info_function_path = ""
            bug_line = ""

        example = {"id": bug["id"], "label": bug["label"], "bug_type": bug["bug_type"], "trace": decoded_bug_trace,
                   'bug_function': "", 'bug_url': bug_url, 'after_fix': after_fix}

        seen_functions = set()
        functions_list = []
        func_path_match_function = ""
        for func in bug['trace']:
            func_key = func['func_key']
            if bug['functions'] and func_key in bug['functions']:
                function_path = bug['functions'][func_key]['file'] + ":" + bug['functions'][func_key]["name"]
                func_line = func["loc"].split(":")[0]
                func_code = bug['functions'][func_key]['code']
                func_code = remove_empty_lines(func_code)
                func_code = remove_comments(func_code)
                func_code = remove_space_before_newline(func_code)
                if func_key not in seen_functions:
                    functions_list.append(func_code)
                    total_functions_count += 1
                    seen_functions.add(func_key)
                if bug['adjusted_bug_loc'] and func['idx'] == bug['bug_loc_trace_index']:
                    example['bug_function'] = func_code
                    example['bug_url'] = bug['adjusted_bug_loc']['url']
                elif function_path == bug_info_function_path and example['bug_function'] == "" and func_line == bug_line:
                    example['bug_function'] = func_code
                elif function_path == bug_info_function_path:
                    func_path_match_function = func_code

        if example['bug_function'] == "":
            #print(bug["id"])
            no_bug_function_count += 1
            if func_path_match_function != "":
                example['bug_function'] = func_path_match_function
                func_path_bug_function_count += 1

        example['functions'] = functions_list

        if not example['functions']:
            no_functions_count += 1
            print(bug["id"])

        bugs_list.append(example)

    print("Print total functions: " + str(total_functions_count))
    print("Avg functions count: " + str(total_functions_count / len(data)))
    print("Missing functions examples count: " + str(no_functions_count))
    print("No bug function count: " + str(no_bug_function_count))
    print("Function path match count: " + str(func_path_bug_function_count))

    return bugs_list


def get_project_split_ids_dict(splits_csv_dict_list):
    project_split_ids_dict = dict()

    for splits_csv_dict in splits_csv_dict_list:
        project = splits_csv_dict['project']
        split = splits_csv_dict['split']
        if project not in project_split_ids_dict:
            project_split_ids_dict[project] = {'train': set(), 'test':set(), 'dev': set()}
        project_split_ids_dict[project][split].add(splits_csv_dict['id'])

    return project_split_ids_dict


def read_csv_into_dict_list(csv_path):
    with open(csv_path) as f:
        dict_list = [{k: v for k, v in row.items()} for row in csv.DictReader(f, skipinitialspace=True)]
    return dict_list


def write_dict_list_to_csv(csv_dict_list, csv_file_name):
    print("Writing CSV file: " + csv_file_name)
    keys = csv_dict_list[0].keys()
    with open(csv_file_name, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(csv_dict_list)
    print("Done!")


def get_split_dict_bug_list(split_ids_dict, bug_dict_list):
    split_dict_bug_list = {"train": [], "test": [], "dev": []}

    for bug in bug_dict_list:
        for split, bug_ids in split_ids_dict.items():
            if bug['id'] in bug_ids:
                split_dict_bug_list[split].append(bug)
                break

    return split_dict_bug_list


def main():
    splits_csv_dict_list = read_csv_into_dict_list(SPLIT_FILE)

    project_split_ids_dict = get_project_split_ids_dict(splits_csv_dict_list)

    for project in PROJECTS_LIST:
        label_one_path, label_zero_after_fix_path, label_zero_path = get_datafile_path(D2A_V1_DATA_DIR,
                                                                                       DATA_FILE_PREFIX, project)

        print("Reading Label 1 file: " + label_one_path)
        label_one_data = read_pickle_data_file(label_one_path)

        print("Creating Label 1 examples.")
        label_one_data_dict_list = create_cbert_bug_dict_data_list(label_one_data)

        print("Reading Label 0 file: " + label_zero_path)
        label_zero_data = read_pickle_data_file(label_zero_path)

        print("Creating Label 0 examples.")
        label_zero_data_dict_list = create_cbert_bug_dict_data_list(label_zero_data)

        print("Reading Label 0 After fix file: " + label_zero_after_fix_path)
        zero_after_fix_data = read_pickle_data_file(label_zero_after_fix_path)

        print("Creating Label 0 after fix examples.")
        label_zero_after_fix_data_dict_list = create_cbert_bug_dict_data_list(zero_after_fix_data, 1)

        full_data_dict_list = label_one_data_dict_list + label_zero_data_dict_list + label_zero_after_fix_data_dict_list

        split_dict_bug_list = get_split_dict_bug_list(project_split_ids_dict[project], full_data_dict_list)

        for split, bug_list in split_dict_bug_list.items():
            write_dict_list_to_csv(bug_list, SPLIT_DATA_OUTPUT_DIR + DATA_FILE_PREFIX + "splitdata_" + project + "_" + split + ".csv")


if __name__ == '__main__':
    main()
