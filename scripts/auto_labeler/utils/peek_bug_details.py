#!/usr/bin/env python3

import os
import sys
import json
import gzip
import pickle
import base64


def compress_and_encode_string(content):
    if isinstance(content, str):
        b_content = content.encode()
    else:
        b_content = content
    compressed_bytes = gzip.compress(b_content)
    encoded_content = base64.b64encode(compressed_bytes).decode('ascii')
    return encoded_content


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


pkl_dest = sys.argv[1]
if not pkl_dest.endswith(".pickle.gz"):
    print("Error: expect *.pickle.gz. exit")
else:
    data = []
    with gzip.open(pkl_dest, mode = 'rb') as fp:
        while True:
            try:
                item = pickle.load(fp)
                data.append(item)
                break
            except EOFError:
                break
    print("%d issues loaded\n" % len(data))
    print(json.dumps(data[0], indent=2))
    print("\n\n")
    bug_txt_encoded = data[0]["sample_gzipped_bug_txt_file_content"]
    if bug_txt_encoded.find("\n") > 0:
        bug_txt_encoded = convert_2_b64encode(bug_txt_encoded)
    decoded_bug_txt = decode_and_decompress_string(bug_txt_encoded)
    print(decoded_bug_txt)
    

