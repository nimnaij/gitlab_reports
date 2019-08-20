## Installing

Get your python env set up by running install:

```bash install.sh```

Enter your env with:

``` . ./gitlabenv/bin/activate ```

## Usage:

## Features

This tool will scrape a gitlab repository for all commit data and then generate reports based on that data. It works by querying gitlab for all projects, and then querying each project for commits. This process is somewhat time consuming and the results are stored as a json blob on disk in between data pulls.

Those commits are then thrown into a one-time-use sqlite database to streamline report generation by time interval.

Various reports are generated in as stdout data as well as CSV files, including total commmits, commits by project, commits by user by project, commits by project by user, commits by user by project over a time interval (default is 7 days).

I wrote this for an organization that provides resourcing both in a training environment (a military school) and an operational environment. Consequently, the tool provides manual lookups to identify users as internal vs. external and to map namespaces to specific internal courses or known operational projects. You can generate an internal/external dictionary with the ```generate_internal_external_dict``` method.

Using the great project at https://www.chartjs.org, I've added support to export data into charts.

## Correlating aliases to individuals

Commits are tracked by committer name, committer email, author name, and author email. Often users are inconsistent about how they submit this data across devices and methods of commit. Consequently, some effort is required to correlate the various user personas to a single user. The repo data file is designed to provide data to aid in this correlation.

```anonymous_emails``` provides a blacklist of values in the four identifying fields.

```known_aliases``` provides a dictionary of lists that ties a dictionary key value (primary alias) to a list of secondary aliases. All secondary aliases should be lower case.

The method ```unique_user_key``` will choose a unique key for a commit by checking the committer email, author email, committer name, and finally author name fields in the commit for a non-zero length string that is not in the list of blacklisted anonymous emails.

The method ```de_alias``` will iterate replace secondary aliases with the primary alias if it finds a match.

Finally, if no means of identifying a user is possible, the commit is tracked by the top-level project namespace itself. To correlate a top level project namespace to a primary alias, list the top level project namespace as a secondary alias, but add a slash at the end.

Example:
```"ben" : ["ben/", "jianmin"],```

## Usage

A quick demonstration of usage:

```
python3 -i gitlab_reports

reports = gitlab_reports(fresh=False,  base_url="GITLAB_URL",api_code="xxxxxxxxxxxxxxxxxxxx",debug=True,verbose=False)
```

Note on parameters for the class init:
* fresh - when true, will always query gitlab for the latest data. when false, will use a local on-disk copy if it exists
* api_code - can be passed as an environmental variable (GITLAB_API) or as a parameter. If no token is passed it will ask the user interactively
* base_url - the repository to connect to
* debug - enable debug output
* verbose - enable gitlab connection debugging and verbose output

```
reports.build_all_reports(from_date="2015-12-01T00:00:00.000Z",to_date="2019-08-17T00:00:00.000Z")
```

You can also build individual reports:

```
reports.query_by_user_by_project_over_time(from_date="2015-12-01T00:00:00.000Z",to_date="2019-08-17T00:00:00.000Z",interval=7)
reports.write_csv()
```

Note: interval is in days.

To refresh a the local report cache, delete the file ```.all_history``` or run:
```
reports.refresh_data()
```

A few report types also export chartjs data, which can then be viewed with the example view_in_chartjs.html file. At this time, these reports include:

* query_all_range()
* query_by_user_by_project()
* query_by_user_by_project_over_time() - showing internal vs. external contributors
* query_all_commits()
