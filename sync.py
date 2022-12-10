#!/usr/bin/env python3

import configparser
import dateutil.parser
import datetime
import json
import requests
import subprocess
import sys

config = configparser.ConfigParser()
config.read('config.ini')

export_process = subprocess.run(['timew', 'export', config['timew'].get('export_interval', '5w')], capture_output=True)

tasks = json.loads(export_process.stdout)

is_logged_tag = config['timew'].get('loggedTag', 'timew2jira:logged')
project_filter = 'project:{}'.format(config['timew'].get('project'))

minimal_time_delta = datetime.timedelta(minutes=1)

jira_headers = {'Content-Type': 'application/json'}
jira_rest_url_template = '{}/rest/api/2/issue/{}/worklog'.format(config['jira'].get('base_url'), '{}')
jira_username = config['jira'].get('username')
jira_password = config['jira'].get('password')

for task in tasks:
    # Start by computing the task length. If it's less than a minute we won't push it to simplify the time report
    start_date = dateutil.parser.isoparse(task['start'])
    if 'end' in task:
        end_date = dateutil.parser.isoparse(task['end'])
        delta = end_date - start_date

    if end_date is not None and delta >= minimal_time_delta:
        # Check if the task is in a project that should be logged
        should_be_logged = False
        is_already_logged = False
        issue_id = None
        description = None

        if 'tags' in task:
            for tag in task['tags']:
                if tag == is_logged_tag:
                    is_already_logged = True
                if tag.startswith(project_filter):
                    should_be_logged = True
                if tag.startswith('issue:'):
                    issue_id = tag[6:]
                if tag.startswith('description:'):
                    description = tag[12:]

        if should_be_logged and not is_already_logged:
            if issue_id is None:
                issue_id = input('Time entry for "{}" is missing an issue ID. Enter ID or hit enter to skip : '.format(description))

            if issue_id is not None:
                print('Uploading time log of {} on issue {} ...'.format(delta, issue_id))

                url = jira_rest_url_template.format(issue_id)
                payload = json.dumps({
                    'started': start_date.strftime('%Y-%m-%dT%H:%M:%S.000%Z'),
                    'timeSpent': str(round(delta.seconds / 60)) + 'm',
                    'comment': description
                })

                response = requests.post(url, auth=(jira_username, jira_password), data=payload, headers=jira_headers)
                print(response)

                if response.status_code == 201:
                    subprocess.call(['timew', 'tag', '@{}'.format(task['id']), is_logged_tag, ':yes'])
                    print('Success uploading time log for issue {}'.format(issue_id))
                else:
                    print('Error sending time log to issue {}.'.format(issue_id))
                    print(response.text)
                    print(response.request.headers)
                    print(response.request.body)
                    print(response.request.method)
                    print(response.request.url)
