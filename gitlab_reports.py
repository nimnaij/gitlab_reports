#!/usr/bin/env python3
import gitlab
import time
import json
import sys
import os
import sqlite3
import datetime
import hashlib
import secrets
from repo_data import *

BASE_GITLAB_URL = "https://git.cybbh.space/"

FROM_DATE="2015-12-06T00:00:00.000Z"
TO_DATE="2019-08-17T00:00:00.000Z"

class gitlab_reports:

    LOCAL_HISTORY_FILE = ".all_history"
    LOCAL_HISTORY = False

    csv = {}
    chartjs = {}

    def err(self,s):
        print(s)
        sys.exit(1)
    def get_access_code(self,api_code=""):
        if "GITLAB_API" in os.environ.keys():
            self.API_CODE = os.environ["GITLAB_API"]
        elif api_code != "":
            self.API_CODE = api_code
        else:
            self.API_CODE = input("Please enter your gitlab api access code: ")

        if len(self.API_CODE) != 20:
            self.err("Bad API access code")

    def connect_by_token(self):
        gl = gitlab.Gitlab(self.BASE_URL,private_token=self.API_CODE)
        if self.DEBUG and self.VERBOSE:
            gl.enable_debug()
        self.gl = gl

    def debug(self,s):
        if self.DEBUG:
            print(s)

    def query_project(self,project,ignore_duplicates = False):

        try:
            commits = project.commits.list(all=True)
        except gitlab.exceptions.GitlabListError:
            self.debug("Error querying commits for {}".format(project.path_with_namespace))
            self.failures.append(project.path_with_namespace)
            return
        self.commit_projects[project.path_with_namespace] = []
        for commit in commits:
            current_commit = {
                "id" : commit.id,
                "created_at" : commit.created_at,
                "parent_ids" : commit.parent_ids,
                "title" : commit.title,
                "message" : commit.message,
                "author_name" : commit.author_name,
                "author_email" : commit.author_email,
                "authored_date" : commit.authored_date,
                "committer_name" : commit.committer_name,
                "committer_email" : commit.committer_email,
                "committed_date" : commit.committed_date,
                "duplicate" : False
            }
            if commit.id in self.commit_ids:
                if ignore_duplicates:
                    return
                else:
                    self.duplicates += 1
                    current_commit["duplicate"] = True
            self.commit_ids.append(commit.id)
            self.commit_projects[project.path_with_namespace].append(current_commit)


    def get_latest_data(self):

        self.connect_by_token()

        self.commit_ids = []
        self.commit_projects = {}
        self.failures = []
        self.duplicates = 0
        forked_projects = []

        for project in self.gl.projects.list(all=True):
            try:
                if project.forked_from_project:
                    forked_projects.append(project)
                    continue
            except:
                pass
            self.debug("Querying project: {}".format(project.path_with_namespace))
            self.query_project(project)
        self.debug("Dataset includes {} duplicates".format(self.duplicates))

        for project in forked_projects:
            self.debug("Querying forked project: {}".format(project.path_with_namespace))
            self.query_project(project,ignore_duplicates = True)
        self.LOCAL_HISTORY = self.commit_projects
    def save_latest_data(self):
        f = open(self.LOCAL_HISTORY_FILE,"w")
        f.write(json.dumps(self.LOCAL_HISTORY))
        f.close()

    def load_data_from_file(self):
        f = open(self.LOCAL_HISTORY_FILE,"r")
        self.LOCAL_HISTORY = json.loads(f.read())
        f.close()

    def build_db(self):
        self.db = sqlite3.connect(":memory:")
        c = self.db.cursor()
        c.execute('''CREATE TABLE committers
                     (name text PRIMARY_KEY)''')
        c.execute('''CREATE TABLE projects
                     (project_path text PRIMARY KEY)''')
        c.execute('''CREATE TABLE commits
                     (committer_name text,
                      committer_email text,
                      author_name text,
                      author_email text,
                      duplicate text,
                      name text,
                      project_path text,
                      date text,
                      FOREIGN KEY(project_path) REFERENCES projects(project_path),
                      FOREIGN KEY(name) REFERENCES committers(name)
                      )''')
        self.db.commit()

    def populate_db(self):
        data = self.LOCAL_HISTORY
        c = self.db.cursor()
        self.users = set()
        self.projects = set()
        for project in data.keys():
            c.execute("INSERT OR IGNORE INTO projects(project_path) VALUES(?)", (project,))
            commits = data[project]
            self.projects.add(project)
            for commit in commits:
                unique_name = self.unique_user_key(commit,project)
                self.users.add(unique_name)
                c.execute("INSERT OR IGNORE INTO committers(name) VALUES(?)", (unique_name,))
                c.execute("INSERT INTO commits(committer_name,committer_email, author_name, author_email, project_path, date,name,duplicate) VALUES(?,?,?,?,?,?,?,?)",(commit["committer_name"], commit["committer_email"], commit["author_name"], commit["author_email"],  project,commit["committed_date"],unique_name,str(commit["duplicate"]).lower()))

        self.db.commit()

    def lookup_name(self,n):
        c = self.db.cursor()
        c.execute("SELECT * from commits where name = ?", (n,))
        return c.fetchall()

    # This method depends on repo_data.py: internal_data
    # repo_data.py consolidates repository-specific, custom data.
    def correlate_user(self,u):
        if u in internal_external.keys():
            return internal_external[u]
        else:
            return "unknown"

    # This method depends on repo_data.py: namespace_to_course
    # repo_data.py consolidates repository-specific, custom data.
    def correlate_project(self,p):
        top_namespace = p.split("/")[0]
        if top_namespace in namespace_to_course.keys():
            return namespace_to_course[top_namespace],"schoolhouse"
        elif top_namespace in known_namespaces:
            return top_namespace, "operational"
        else:
            return top_namespace, "personal"

    # This method depends on repo_data.py: known_aliases
    # repo_data.py consolidates repository-specific, custom data.
    def de_alias(self,name):
        for k in known_aliases.keys():
            if name.lower() in known_aliases[k]:
                return k
        if name[-4:] == ".mil" or name[-4:] == ".ctr" or name[-4:] == ".civ":
            name = name[:-4]
        return name

    # This method depends on repo_data.py: anonymous_emails
    # repo_data.py consolidates repository-specific, custom data.
    def unique_user_key(self,commit,project):
        k = self.de_alias(commit["committer_email"])
        if k == "" or k in anonymous_emails:
            k = self.de_alias(commit["author_email"])
        if k == "" or k in anonymous_emails:
            k = self.de_alias(commit["committer_name"])
        if k == "" or k in anonymous_emails:
            k = self.de_alias(commit["author_name"])
        k = self.de_alias(k.split("@")[0])
        if k == "" or k in anonymous_emails:
            k = self.de_alias(project.split("/")[0] + "/")
            if k[-1:] == "/":
                k = k[:-1]
        return self.de_alias(k)

    def query_all_range(self,from_date,to_date):
        c = self.db.cursor()
        c.execute("SELECT count(*) FROM commits WHERE duplicate = 'false' and date BETWEEN datetime(?) AND datetime(?)", (from_date,to_date))
        total_commits = c.fetchall()[0][0]
        print("Total Commits: {}".format(total_commits))
        print("===================\n")
        self.csv["total_commits"] = [("total_commits",)]
        self.csv["total_commits"].append((total_commits,))
        self.chartjs["total_commits"] = total_commits;

    def query_by_user(self,from_date,to_date):
        print("Commits by user:")
        print("================")
        c = self.db.cursor()
        c.execute("SELECT name, count(*) as 'commits' FROM commits WHERE duplicate = 'false' and date BETWEEN datetime(?) AND datetime(?) group by commits.name order by commits desc", (from_date,to_date))
        self.csv["by_user"] = [("name","commit_count","user_type")]
        for row in c.fetchall():
            user = self.correlate_user(row[0])
            print("{:<30}{:<12}{}".format(row[0],row[1],user))
            self.csv["by_user"].append((self.anonymize_value(row[0]),row[1],user))

    def query_by_project(self,from_date,to_date):
        print("Commits by project:")
        print("================")
        c = self.db.cursor()
        c.execute("SELECT project_path, count(*) as 'commits' FROM commits WHERE duplicate = 'false' and date BETWEEN datetime(?) AND datetime(?) group by commits.project_path order by project_path asc", (from_date,to_date))
        self.csv["by_project"] = [("project_path", "commit_count","project_group","project_type")]
        for row in c.fetchall():
            project_group, project_type = self.correlate_project(row[0])
            if project_type == "personal":
                project_group = self.anonymize_value(project_group)
            print("{:<75}{:<12}{:<30}{}".format(row[0],row[1],project_group,project_type))
            self.csv["by_project"].append((self.anonymize_value(row[0]),row[1],project_group,project_type))

    def query_by_project_by_user(self,from_date,to_date):
        print("\nCommits by project by user:")
        print("================")
        c = self.db.cursor()
        c.execute("SELECT project_path, name, count(*) as 'commits' FROM commits WHERE duplicate = 'false' and date BETWEEN datetime(?) AND datetime(?) group by commits.name, commits.project_path order by project_path asc, commits desc", (from_date,to_date))
        path = set()
        self.csv["by_user_and_project"] = [("name","user_type","project","commit_count","project_group","project_type")]
        for row in c.fetchall():
            project_group, project_type = self.correlate_project(row[0])
            if project_type == "personal":
                project_group = self.anonymize_value(project_group)
            user_type = self.correlate_user(row[1])
            user_name = self.anonymize_value(row[1])

            if row[0] not in path:
                path.add(row[0])
                print("\n" + row[0] + " - " + project_group + " - " + project_type)
            print("\t{:<30}{:<12}{}".format(row[1], row[2],user_type))
            self.csv["by_user_and_project"].append((user_name,user_type,self.anonymize_value(row[0]),row[2],project_group, project_type))

    def query_by_user_by_project(self,from_date,to_date):
        print("\nCommits by user by project")
        print("================")
        chartjs_labels = set()
        chartjs_user_datasets = {}
        c = self.db.cursor()
        c.execute("SELECT project_path, name, count(*) as 'commits_count' FROM commits WHERE duplicate = 'false' and date BETWEEN datetime(?) AND datetime(?) group by commits.name, commits.project_path order by name asc, project_path asc", (from_date,to_date))
        user_set = set()
        for row in c.fetchall():
            project_group, project_type = self.correlate_project(row[0])
            user_name = self.anonymize_value(row[1])

            if project_type == "personal":
                project_group = self.anonymize_value(project_group)
                project_label = project_type
            else:
                project_label = project_group
            chartjs_labels.add(project_label)
            try:
                chartjs_user_datasets[user_name]["data"][project_label] = row[2]
            except:
                chartjs_user_datasets[user_name] = {
                    "data" : {
                        project_label : row[2]
                    },
                    "stack" : "0",
                    "label": user_name,
                    "backgroundColor" : "#"+self.hash_value(user_name)[-6:]
                }

            user_type = self.correlate_user(row[1])
            if row[1] not in user_set:
                user_set.add(row[1])
                print("\n" + row[1] + " - " + user_type)
            print("\t{:<75}{:<12}{:<30}{}".format(row[0], row[2],project_group, project_type))

        chartjs_labels = list(chartjs_labels)
        chartjs_datasets = []
        for user_name in chartjs_user_datasets.keys():
            new_data = []
            for project in chartjs_labels:
                try:
                    new_data.append(chartjs_user_datasets[user_name]["data"][project])
                except:
                    new_data.append(0)
            chartjs_user_datasets[user_name]["data"] = new_data
            chartjs_datasets.append(chartjs_user_datasets[user_name])
        self.chartjs["by_user_by_project"] =  {
            "labels" : chartjs_labels,
            "datasets" : chartjs_datasets
        }



    def query_by_user_by_project_over_time(self,from_date,to_date,interval=7):
        c = self.db.cursor()
        self.chartjs["internal_external"] =  {
            "labels" : [],
            "datasets" : [],
        }
        chartjs_external = {
            "label" : "External Users",
            "backgroundColor" : "#00FF00",
            "borderColor" : "#00FF00",
            "fill": False,
            "data" : []
        }
        chartjs_internal = {
            "label" : "Internal Users",
            "backgroundColor" : "#0000FF",
            "borderColor" : "#0000FF",
            "fill": False,
            "data" : []
        }

        self.csv["by_user_and_project_over_time"] = [("name","user_type","project","project_group","project_type","commit_count","interval ({} days)".format(interval))]
        start_time = datetime.datetime.strptime(from_date,"%Y-%m-%dT%H:%M:%S.%fZ")
        end_time = datetime.datetime.strptime(to_date,"%Y-%m-%dT%H:%M:%S.%fZ")
        hop = datetime.timedelta(days=interval)
        print("\nCommits by user by project over time")
        print("================")
        while start_time < end_time:
            next_time = start_time+hop
            self.chartjs["internal_external"]["labels"].append(str(start_time)[:10])
            c.execute("SELECT project_path, name, count(*) as 'commits' FROM commits WHERE duplicate = 'false' and date BETWEEN datetime(?) AND datetime(?) group by commits.name, commits.project_path order by name asc, project_path asc", (str(start_time),str(next_time)))
            print("From {} to {}".format(str(start_time),str(next_time)))
            user_set = set()
            ext_count = 0
            int_count = 0
            for row in c.fetchall():
                project_group, project_type = self.correlate_project(row[0])
                user_type = self.correlate_user(row[1])
                if project_type == "personal":
                    project_group = self.anonymize_value(project_group)
                if row[1] not in user_set:
                    user_set.add(row[1])
                    print("\n" + row[1] + " - " + user_type)
                print("\t{:<75}{:<12}{:<30}{}".format(row[0], row[2],project_group,project_type))
                self.csv["by_user_and_project_over_time"].append((self.anonymize_value(row[1]),user_type,self.anonymize_value(row[0]),project_group,project_type,row[2],str(start_time)))
                if user_type == "internal":
                    int_count += int(row[2])
                else:
                    ext_count += int(row[2])
            chartjs_external["data"].append(ext_count)
            chartjs_internal["data"].append(int_count)


            start_time = next_time
            print("")
        self.chartjs["internal_external"]["datasets"].append(chartjs_external)
        self.chartjs["internal_external"]["datasets"].append(chartjs_internal)


    def query_all_commits(self,from_date,to_date):
        self.chartjs["all_commits"] =  {
            "labels" : set(),
            "datasets" : {},
        }
        self.csv["all_commits"] = [("name", "user_type", "project", "project_group", "project_type","date" )]
        c = self.db.cursor()
        c.execute("SELECT name, project_path, date FROM commits WHERE duplicate = 'false' and date BETWEEN datetime(?) AND datetime(?) order by name asc", (from_date,to_date))
        for row in c.fetchall():
            project_group, project_type = self.correlate_project(row[1])
            user_type = self.correlate_user(row[0])
            user_name = self.anonymize_value(row[0])
            commit_date = row[2][:10]
            self.chartjs["all_commits"]["labels"].add(commit_date)
            try:
                self.chartjs["all_commits"]["datasets"][user_name]["data"][commit_date] += 1
            except:
                color = "#"+self.hash_value(user_name)[-6:]
                self.chartjs["all_commits"]["datasets"][user_name] = {
                    "data" : {
                        commit_date : 1
                    },
                    "fill" : False,
                    "label": user_name,
                    "backgroundColor" : color,
                    "borderColor" : color
                }

            if project_type == "personal":
                project_group = self.anonymize_value(project_group)
            self.csv["all_commits"].append((user_name,user_type,self.anonymize_value(row[1]),project_group,project_type,row[2]))

        new_datasets = []
        self.chartjs["all_commits"]["labels"] = sorted(list(self.chartjs["all_commits"]["labels"]), reverse=True)
        for user_name in self.chartjs["all_commits"]["datasets"].keys():
            new_data = []
            for day in self.chartjs["all_commits"]["labels"]:
                try:
                    new_data.append(self.chartjs["all_commits"]["datasets"][user_name]["data"][day])
                except:
                    new_data.append(0)
            new_dataset = self.chartjs["all_commits"]["datasets"][user_name]
            new_dataset["data"] = new_data
            new_datasets.append(new_dataset)
        self.chartjs["all_commits"]["datasets"] = new_datasets

    def hash_value(self,v):
        return hashlib.sha256(bytes(v+self.salt,"utf-8")).hexdigest()[-16:]

    def anonymize_value(self,v):
        if self.anonymize:
            return self.hash_value(v)
        else:
            return v

    def dump_reports_as_json(self):
        return json.dumps(self.csv)

    def generate_internal_external_dict(self):
        local_internal_external = {}
        for user in self.users:
            if user in internal_external.keys():
                continue # don't ask about users already known
            print("User: {}".format(user))
            print(self.lookup_name(user))
            resp = input("Press enter for internal, or x for external: ")
            if "x" in resp:
                local_internal_external[user] = "external"
            else:
                local_internal_external[user] = "internal"
        internal_external.update(local_internal_external)
        print(json.dumps(internal_external))

    def build_all_reports(self,from_date,to_date):
        self.query_all_range(from_date,to_date)
        self.query_by_project(from_date,to_date)
        self.query_by_user(from_date,to_date)
        self.query_by_project_by_user(from_date,to_date)
        self.query_by_user_by_project(from_date,to_date)
        self.query_by_user_by_project_over_time(from_date,to_date)
        self.query_all_commits(from_date,to_date)
        self.chartjs["date_range"] = "{} to {}".format(from_date,to_date)
        self.write_charts()
        self.write_csv()

    def write_csv(self):
        for key in self.csv.keys():
            f = open(key+".csv", "w")
            for row in self.csv[key]:
                f.write(",".join(str(v) for v in row))
                f.write("\n")
            f.close()
    def write_charts(self):
        f = open("chartjsdata.js", "w")
        for key in self.chartjs.keys():
            try:
                data_to_write = json.dumps({
                    "labels" : self.chartjs[key]["labels"],
                    "datasets" : self.chartjs[key]["datasets"]
                })
            except:
                data_to_write = json.dumps(self.chartjs[key])
            f.write("var {} = {};\n".format(key,data_to_write))
        f.close()
    def refresh_data(self, api_code=""):
        try:
            self.API_CODE
        except AttributeError:
            self.get_access_code(api_code)
        self.debug("Getting the data.")
        self.get_latest_data()
        self.debug("Got the data.")
        self.save_latest_data()
        self.build_db()
        self.populate_db()

    def __init__(self, base_url=BASE_GITLAB_URL, api_code="", fresh=False,debug=False,verbose=False,anonymize = False):
        self.DEBUG = debug
        self.VERBOSE = verbose
        self.BASE_URL = base_url
        self.salt = secrets.token_hex(32)
        self.anonymize = anonymize
        self.debug("Using salt {}".format(self.salt))
        try:
            self.load_data_from_file()
            self.debug("Loaded history from file")
        except:
            if not fresh:
                self.debug("Did not find history file: {}. Doing new pull.".format(self.LOCAL_HISTORY_FILE))

        if api_code != "":
            self.get_access_code(api_code)
        if fresh == True or self.LOCAL_HISTORY == False: # first run or explicitly directed to stay fresh
            self.refresh_data(api_code=api_code)
        else:
            self.build_db()
            self.populate_db()



