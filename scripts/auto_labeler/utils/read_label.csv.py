#!/usr/bin/env python3

import os
import csv
import sys
import gzip
import base64

def read_csv(file_path):
    if not os.path.exists(file_path):
        print("no file found. exit")
        return
    with open(file_path, newline='') as f:
        reader = csv.DictReader(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
        for row in reader:
            for field in row:
                if field != "encoded_bug_txt":
                    print("* %s = %s" % (field, row[field]))
            print("----------------------------------------------------")
            encoded = row['encoded_bug_txt']
            zipped = base64.decodebytes(encoded.encode('ascii'))
            content = gzip.decompress(zipped).decode()
            print(content)
            break
            

if __name__ == "__main__":
    read_csv(sys.argv[1])