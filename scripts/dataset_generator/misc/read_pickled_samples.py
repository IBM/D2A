#!/usr/bin/env python3

import sys
import json
import gzip
import pickle
import base64


def decode_and_decompress_string(encoded_content):
    encoded_bytes = encoded_content.encode('ascii')
    compressed_bytes = base64.b64decode(encoded_bytes)
    b_content = gzip.decompress(compressed_bytes)
    content = b_content.decode()
    return content


def convert_2_b64encode(bug_trace):
    zipped = base64.decodebytes(bug_trace.encode('ascii'))
    encoded_content = base64.b64encode(zipped).decode('ascii')
    return encoded_content


def print_sample(file_path):
    if not file_path.endswith(".pickle.gz"):
        print("Error: expect *.pickle.gz. exit")
    else:
        data = []
        cnt = 0
        with gzip.open(file_path, mode = 'rb') as fp:
            while True:
                try:
                    item = pickle.load(fp)
                    cnt += 1
                    data.append(item)
                    if cnt == 1:
                        break
                except EOFError:
                    break
        print("%d issues loaded\n" % len(data))
        print(json.dumps(data[0], indent=2))
        print("\n\n")
        print("bug.txt in plain text:")
        print("----------------------------------------------------------")
        bug_txt_encoded = data[0]["zipped_bug_report"]
        if bug_txt_encoded is not None:
            if bug_txt_encoded.find("\n") > 0:
                bug_txt_encoded = convert_2_b64encode(bug_txt_encoded)
            decoded_bug_txt = decode_and_decompress_string(bug_txt_encoded)
            print(decoded_bug_txt)
        else:
            print("no bug.txt")



def get_sample(file_path, labler, label, bug_type, dest_file):
    with gzip.open(file_path, mode = 'rb') as fp:
        while True:
            try:
                item = pickle.load(fp)
                if item["label_source"] == labler and item["label"] == label and item["bug_type"] == bug_type:
                    with open(dest_file, "w") as fp:
                        fp.write(json.dumps(item, indent = 2))
                        print("Saved to '%s'" % dest_file)
                        return
            except EOFError:
                break
    print("Not Found")


if __name__ == '__main__':
    pkl_dest = sys.argv[1]
    print_sample(pkl_dest)
    get_sample(pkl_dest, "after_fix_extractor", 0, "NULL_DEREFERENCE", "sample_after_fix_extractor_0.json")
    
