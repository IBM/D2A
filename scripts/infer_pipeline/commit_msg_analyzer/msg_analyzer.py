#!/usr/bin/env python3

import os
import sys
import re
import csv
import pickle
import random
import subprocess
import shutil
from pathvalidate import is_valid_filepath
from datetime import datetime
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.stem import PorterStemmer



class Preprocessor:

    def __init__(self):
        nltk.download('stopwords', download_dir="nltk_data")
        nltk.download('punkt', download_dir="nltk_data")
        nltk.data.path.append("nltk_data")
        # if not os.path.exists("files"):
        #     os.mkdir("files")
        print("* init done")


    def fetch_commit_msg(self, repo_url):
        print("* download commit hashes and messages from " + repo_url)
        fresh = True
        if os.path.exists("repo"):
            print("* local 'repo' folder found. reuse [Y/n]? ", end=" ")
            user_input = input()
            if user_input == "y" or user_input == "Y" or user_input == "":
                fresh = False
        if fresh:
            print("* clone into 'repo'")
            if os.path.exists("repo"):
                shutil.rmtree("repo")
            subprocess.run(["git", "clone", repo_url, "repo"])
        else:
            print("* reuse local 'repo'")
        field_separator = "^@@@^"
        line_separator = "^&_@&_@&_@^"
        git_format = "--pretty=format:%H" + field_separator + "%s%n%b" + line_separator
        proc = subprocess.run(["git", "log", git_format], cwd='repo/', stdout=subprocess.PIPE)
        raw_data = proc.stdout.decode("iso-8859-1")
        item_list = raw_data.split(line_separator)
        # print(item_list)
        # print("")
        # json_data = []
        res = []
        for item in item_list:
            item = item.strip()
            if item.find(field_separator) > 0:
                parts = item.split(field_separator)
                commit_hash = parts[0].strip()
                msg = parts[1].strip()
                # json_data.append({
                #     "hashcode": commit_hash,
                #     "commit message": msg
                # })
                res.append([commit_hash, msg])
        print("* %d commit messages dumped" % len(res))
        # with open(os.path.join("files", "all_msg.json"), "w") as fp:
        #     fp.write(json.dumps(json_data, indent=2))
        return res


    def my_tokenizer(self, s):
        s = s.strip('\t\n\r\f\v').strip().lower() # downcase
        tokens = nltk.word_tokenize(s)
        tokens = [tok for tok in tokens if tok.isalpha()]
        stop_words = set(stopwords.words("english"))
        tokens = [w for w in tokens if not w in stop_words]
        tokens = [w for w in tokens if len(w)>2]
        return tokens


    def process_original(self, data):
        new_data = []
        for each in data:
            if len(each) >= 2:
                id = each[0].strip()
                other_sentence = " ".join(each[1:])
                other_sentence_token = self.my_tokenizer(other_sentence)
                if len(other_sentence_token) > 0:
                    new_data.append([id, other_sentence, other_sentence_token])
                else:
                    print("empty")
            else:
                print("empty")
        return new_data


    def process_original_token(self, data):
        new_data = []
        for each in data:
            id_, old, new = each
            if len(new) >= 2:
                #id = new[0].strip()
                other_sentence = " ".join(new[1:])
                other_sentence_token = self.my_tokenizer(other_sentence)
                if len(other_sentence_token) > 0:
                    new_data.append([id_, old, other_sentence_token])
        return new_data


    def filter_some_pattern(self, data):
        new_data = []
        for each_instance in data:
            id_, msg_ =  each_instance
            msg_list = msg_.split("\n")
            filtered = []
            for sent_ in msg_list:
                sent_ = sent_.strip('\t\n\r\f\v').strip()
                if re.search('-[Bb][Yy]:', sent_) or re.search('[Cc][Cc]:', sent_) or re.search('[Hh][Tt][Tt][Pp]s?:', sent_) \
                        or len(sent_) == 0:
                    pass
                else:
                    filtered.append(sent_)
            new_data.append([id_, msg_, filtered])
        return new_data

    
    def process(self, repo_url):
        all_instances = self.fetch_commit_msg(repo_url)
        filtered = self.filter_some_pattern(all_instances)  # filter sign-off-by/CC so on.
        filtered_token = self.process_original_token(filtered) # tokenize
        # print(filtered_token)
        # dest = os.path.join("files", "commit_msg_processed.p")
        # pickle.dump([filtered_token], open(dest, "wb"))
        # print("* pre-processed data saved at " + dest)
        print("* pre-processing done")
        return filtered_token





class Analyzer:

    def __init__(self):
        nltk.download('stopwords', download_dir="nltk_data")
        nltk.data.path.append("nltk_data")


    def get_all_sentences(self, data):
        all_s = []
        for each in data:
            id_, org, s = each
            all_s.append([id_, " ".join(s), org])
        return all_s


    def compute_zero(self, sentences, all_dict):
        scores = []
        all_scores = []
        all_original_msgs = []
        total = len(sentences)
        idx = 0
        for each in sentences:
            s=0
            id_, each_s, org_s = each
            classes, key_words = [], []
            for each_class in all_dict:
                cur_class = all_dict[each_class]
                for each_key in cur_class:
                    c_sc = float(cur_class[each_key])
                    if each_s.find(each_key) >= 0:
                        s += c_sc
                        classes.append(each_class)
                        key_words.append(each_key)
            scores.append([id_, s, classes, key_words, each_s, org_s])
            all_scores.append(s)
            all_original_msgs.append(org_s)
            
        zeros = []
        for e in scores:
            _, sc, _, _, sent, _ = e
            if sc == 0:
                zeros.append([sent, sc])
        # print("zeros:", len(zeros))
        Z = zip(all_scores, scores)
        Z = sorted(Z, reverse=True)
        all_scores, scores = zip(*Z)
        return scores, all_original_msgs


    def remove_repeat(self, old_list):
        list1 = []
        for element in old_list:
            if (element not in list1):
                list1.append(element)
        return list1


    def my_tokenizer(self, s):
        s = s.strip('\t\n\r\f\v').strip().lower() # downcase
        tokens = nltk.word_tokenize(s)
        tokens = [tok for tok in tokens if tok.isalpha()]
        stop_words = set(stopwords.words("english"))
        tokens = [w for w in tokens if not w in stop_words]
        tokens = [w for w in tokens if len(w)>2]
        return tokens


    def read_keyword(self):
        all_dict = dict()
        with open("keywords.csv", encoding="utf8") as csvfile:
            csv_reader = csv.reader(csvfile)
            birth_header = next(csv_reader)
            for row in csv_reader:
                class_ = row[0]
                words = row[1]
                score = row[2]
                if class_ != "":
                    cur_class = class_
                    all_dict[cur_class] = dict()
                word_list = words.split("/")
                for each in word_list:
                    all_dict[cur_class][each] = score
        return all_dict


    def check_keyword(self, tok, keyword_dict):
        ret = None
        for each_cate in keyword_dict:
            cur_dict = keyword_dict[each_cate]
            if tok in cur_dict:
                ret = each_cate
        return ret


    def process_each_msg(self, each, keyword_dict):
        new_msg = []        
        sentences = each.split("\n")
        for each_sentence in sentences:
            each_sentence = each_sentence.strip('\t\n\r\f\v').strip().lower()
            tokens = each_sentence.split(" ")
            new_tokens = []
            for tok in tokens:
                tok = tok.strip("\t\n\r\f\v.:',;")
                if tok == "":
                    continue
                # print("tok = '%s'" % tok)
                if tok.isalpha(): ### check keyword
                    category = self.check_keyword(tok, keyword_dict)
                    if category:
                        tok = "<keyword category="+ category +">"+tok+"</keyword>"
                    new_tokens.append(tok)
                else:   ### check types
                    # if "(" in tok:
                    #     if re.match('([a-z0-9]+(_?))+[a-z0-9]*\([a-z0-9, ]*\)\Z', tok):
                    #         tok = "<function>" + tok + "</function>"
                    # ----------------------
                    # TODO: argument list check, the original argument checks are problematic '[a-z0-9, ]*'
                    # it cannot match foo(int *)
                    # for now, just check if the tok is in shape of 'identifier(.*)'
                    # ----------------------
                    if "(" in tok and tok.endswith(")"):
                        parts = tok[ : -1].split("(")
                        if parts[0].isidentifier():
                            tok = "<function>" + tok + "</function>"
                            # print("  |- " + tok)
                    elif "." in tok:
                        # if re.match('([a-z0-9]+(_?)(/)?)?([a-z0-9]+(_?))+[a-z0-9]*.[ch]\Z', tok):
                        #     tok = "<file_name>" + tok + "</file_name>"
                        if is_valid_filepath(tok):
                            _, f_ext = os.path.splitext(tok)
                            if f_ext == ".c" or f_ext == ".h" or f_ext == ".cpp" or f_ext == ".hpp":
                                tok = "<file_name>" + tok + "</file_name>"
                    # elif re.match('([a-z0-9]+_)+[a-z0-9]*\Z', tok):
                    #     tok = "<variable>"+tok+"</variable>"
                    elif tok.isidentifier():
                        tok = "<variable>" + tok + "</variable>"
                    new_tokens.append(tok)
                
            new_msg.append(new_tokens)
        return new_msg


    def analysis_original_msg(self, original_msgs, keyword_dict):
        tagged_msgs = []
        total = len(original_msgs)
        idx = 0
        for each in original_msgs:
            new_msg = self.process_each_msg(each, keyword_dict)
            tagged_msgs.append(new_msg)
            idx += 1
            if idx % 10000 == 0:
                print("  - %d/%d processed" % (idx, total))
        return tagged_msgs


    def process_main(self, all_original_msgs, keyword_dict):
        tagged_all_msgs = self.analysis_original_msg(all_original_msgs, keyword_dict)
        return tagged_all_msgs


    def all_original_sentence(self, file_name):
        all_original_msgs = []
        with open(file_name, encoding="utf8") as fp:
            csv_reader = csv.reader(fp)
            header = next(csv_reader)
            for row in csv_reader:
                msg = row[5]
                list_ = msg.split('\n')
                all_original_msgs.append(list_)
        return all_original_msgs


    def save_result(self, project_name, scores, all_tagged_msgs, collected_tags, save_details = False):
        print("* score threshold [default = 0.4]? ", end="")
        threshold_str = input().strip()
        threshold = 0.4
        try:
            threshold = float(threshold_str)
        except ValueError:
            threshold = 0.4
        print("* score threshold is set to '%f'" % threshold)
        
        timestamp = datetime.now().strftime("%Y%m%d")
        commit_cnt = 0
        output_path = "result"
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        with open(os.path.join(output_path, "%s_%s_commit_only.txt" % (timestamp, project_name)), "w") as fp:
            for index, each in enumerate(scores):
                commit_hash, score, _, _, _, _ = each
                if score < threshold:
                    break
                fp.write(commit_hash + "\n")
                commit_cnt += 1
        print("* %d commits with positive scores identified" % commit_cnt)
        with open(os.path.join(output_path, "%s_%s_commit_score.csv" % (timestamp, project_name)), "w") as fp:
            writer = csv.writer(fp)
            writer.writerow(["commit_hash", "score"])
            for index, each in enumerate(scores):
                commit_hash, score, _, _, _, _ = each
                writer.writerow([commit_hash, score])
        if save_details:
            with open(os.path.join(output_path, "%s_%s_details.csv" % (timestamp, project_name)), "w") as fp:
                writer = csv.writer(fp)
                writer.writerow(["hashcode", "score", "class", "keyword", "msg", "original msg"]+["tagged", "pattern"])
                for index, each in enumerate(scores):
                    id_, sc, classes, key_words, each_s, each_o = each
                    original_writer = [id_, sc, "**".join(self.remove_repeat(classes)), "**".join(self.remove_repeat(key_words)), each_s, each_o]
                    tagged = all_tagged_msgs[index]
                    new_string_tagged = []
                    for each_sentence in tagged:
                        new_string_tagged.append(" ".join(each_sentence))
                    tagged_new = "\n".join(new_string_tagged)
                    if len(collected_tags[index]) > 0:
                        pattern_new = "\n".join(collected_tags[index])
                        writer.writerow(original_writer + [tagged_new, pattern_new])
                    else:
                        writer.writerow(original_writer + [tagged_new])


    def clean_keyword(self, tok):
        category = tok[len('<keyword category='): tok.find('>')]
        keyword = tok[tok.find('>') + 1: tok.find('</')]
        return keyword, category


    def clean_variable(self, tok):
        new_tok = tok[len('<variable>'): tok.find('</')]
        return new_tok


    def clean_function(self, tok):
        new_tok = tok[len('<function>'): tok.find('</')]
        return new_tok


    def clean_filename(self, tok):
        new_tok = tok[len('<file_name>'): tok.find('</')]
        return new_tok


    def get_nearest(self, key_index, cur_set, set_indexes):
        near = None
        if len(cur_set) == 0:
            pass
        elif len(cur_set) == 1:
            near = cur_set[0]
        else:
            val = abs(key_index - set_indexes[0])
            index = 0
            for i in range(1, len(set_indexes)):
                cur_val = abs(key_index - set_indexes[i])
                if cur_val < val:
                    index = i
            near = cur_set[index]
        return near


    def compute_pattern(self, key, key_index, variables, variable_indexes, functions, function_indexes, files, file_indexes):
        key, category = self.clean_keyword(key)
        near_var = self.get_nearest(key_index, variables, variable_indexes)
        near_fun = self.get_nearest(key_index, functions, function_indexes)
        near_file = self.get_nearest(key_index, files, file_indexes)
        if near_var is not None:
            near_var = self.clean_variable(near_var)
        if near_fun is not None:
            near_fun = self.clean_function(near_fun)
        if near_file is not None:
            near_file = self.clean_filename(near_file)
        return key, category, near_var, near_fun, near_file


    def combine_collected_tags(self, collected_tags):
        new_combined = []
        if len(collected_tags) == 0:
            pass
        elif len(collected_tags) == 1:
            key_word, category, sentence, variable, function, file = collected_tags[0]
            new_ins = [category, sentence, [key_word], [variable], [function], [file]]
            new_combined.append(new_ins)
        else:
            start = collected_tags[0]
            kw_list, variable_list, function_list, file_list = [], [], [], []
            s_key_word, s_category, s_sentence, s_variable, s_function, s_file = start
            kw_list.append(s_key_word)
            variable_list.append(s_variable)
            function_list.append(s_function)
            file_list.append(s_file)
            for index in range(1, len(collected_tags)):
                cur_instance = collected_tags[index]
                kw, cate, sent, var, fun, fil = cur_instance
                if cate == s_category and sent == s_sentence:
                    kw_list.append(kw)
                    variable_list.append(var)
                    function_list.append(fun)
                    file_list.append(fil)
                    if index == len(collected_tags)-1:
                        new_combined.append([s_category, s_sentence, kw_list, variable_list, function_list, file_list])
                else:
                    new_combined.append([s_category, s_sentence, kw_list, variable_list, function_list, file_list])
                    s_category = cate
                    s_sentence = sent
                    kw_list = [kw]
                    variable_list = [var]
                    function_list = [fun]
                    file_list = [fil]
                    if index == len(collected_tags)-1:
                        new_combined.append([s_category, s_sentence, kw_list, variable_list, function_list, file_list])
        return new_combined


    def compute_strings(self, new_combined):
        string_list = []
        if len(new_combined) == 0:
            pass
        else:
            for each in new_combined:
                category, sentence, kws, varis, funs, files = each
                kws = list(set(kws))
                varis = list(set(varis))
                funs = list(set(funs))
                files = list(set(files))
                if None in kws:
                    kws.remove(None)
                if None in varis:
                    varis.remove(None)
                if None in funs:
                    funs.remove(None)
                if None in files:
                    files.remove(None)
                cur_str = "<Category: " + category + "> " + "<Sentence: " + sentence + "> " + "<Keyword: "+ " ".join(kws) + "> "
                if len(varis) > 0:
                    cur_str += "<Variable: " + " ".join(varis) + "> "
                if len(funs) > 0:
                    cur_str += "<Function: " + " ".join(funs) + "> "
                if len(files) > 0:
                    cur_str += "<File: " + " ".join(files) + ">"
                string_list.append(cur_str)
        return string_list


    def collect_tags_combine(self, all_, all_original):
        statistics = {
            "all_none": 0,
            "nonkey_withother": 0,
            "withkey_nonother": 0,
            "withkey_withother" :0
        }
        collected_tags = []
        for msg_index, each_msg in enumerate(all_):
            cur_collected_tags = []
            for sent_index, each_sentence in enumerate(each_msg):
                keywords = []
                variables, functions, files = [], [], []
                keyword_indexes, variable_indexes, function_indexes, file_indexes = [], [], [], []
                for index, each_tok in enumerate(each_sentence):
                    if "<keyword" in each_tok:
                        keywords.append(each_tok)
                        keyword_indexes.append(index)
                    elif "<variable>" in each_tok:
                        variables.append(each_tok)
                        variable_indexes.append(index)
                    elif "<function>" in each_tok:
                        functions.append(each_tok)
                        function_indexes.append(index)
                    elif "<file_name>" in each_tok:
                        files.append(each_tok)
                        file_indexes.append(index)
                    else:
                        pass
                if len(keywords) > 0:
                    if len(keywords) == 1:
                        if len(variables) == 0 and len(functions) == 0 and len(files) == 0:
                            statistics["withkey_nonother"] += 1
                        else:
                            statistics["withkey_withother"] += 1
                            key = keywords[0]
                            key_index = keyword_indexes[0]
                            key, cate, var, fun, fil = self.compute_pattern(key, key_index, variables, variable_indexes, functions, function_indexes, files, file_indexes)
                            ori_sent = all_original[msg_index][sent_index]
                            cur_collected_tags.append((key, cate, ori_sent, var, fun, fil))
                    elif len(keywords) > 1:
                        if len(variables) == 0 and len(functions) == 0 and len(files) == 0:
                            statistics["withkey_nonother"] += 1
                        else:
                            statistics["withkey_withother"] += 1
                            for key_i in range(len(keywords)):
                                key = keywords[key_i]
                                key_index = keyword_indexes[key_i]
                                key, cate, var, fun, fil = self.compute_pattern(key, key_index, variables, variable_indexes,
                                                                        functions, function_indexes, files, file_indexes)
                                ori_sent = all_original[msg_index][sent_index]
                                cur_collected_tags.append((key, cate, ori_sent, var, fun, fil))
                else:
                    if len(variables) == 0 and len(functions) == 0 and len(files) == 0:
                        statistics["all_none"] += 1
                    elif len(variables) > 0 or len(functions) > 0 or len(files) > 0:
                        statistics["nonkey_withother"] += 1
            new_combined = self.combine_collected_tags(cur_collected_tags)
            string_represts = self.compute_strings(new_combined)
            collected_tags.append(string_represts)
        # print(statistics)
        return collected_tags


    def analyze(self, project_name, preprocessed_data):
        all = preprocessed_data # pickle.load(open("files/commit_msg_processed.p", "rb"))[0]
        print("* start scoring")
        all_sentences = self.get_all_sentences(all)
        keyword_dict = self.read_keyword()
        scores, all_original_msgs = self.compute_zero(all_sentences, keyword_dict)
        print("* start tagging")
        all_tagged = self.process_main(all_original_msgs, keyword_dict)
        collected_tags = self.collect_tags_combine(all_tagged, all_original_msgs)
        print("* save results")
        self.save_result(project_name, scores, all_tagged, collected_tags)



class Commit_Msg_Analyzer:

    def process(self, project_name, git_repo_url):
        print("pre-processing...")
        p = Preprocessor()
        pre_processed_data = p.process(git_repo_url)
        print("")
        print("analyzing...")
        a = Analyzer()
        a.analyze(project_name, pre_processed_data)



if __name__ == '__main__':
    msg_analyzer = Commit_Msg_Analyzer()
    msg_analyzer.process("libav", "https://github.com/libav/libav.git")

