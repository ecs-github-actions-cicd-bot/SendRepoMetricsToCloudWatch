import requests
import time
import boto3
import json
import os
from datetime import datetime, timedelta, timezone

# GitHub API details
GITHUB_API_URL = "https://api.github.com"
REPO_NAME = os.getenv('REPO_NAME')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

# AWS CLoudwatch details
AWS_REGION = os.getenv('AWS_REGION')
NAMESPACE = os.getenv('NAMESPACE')

# Initialize CloudWatch client with specified region
client = boto3.client(
  'cloudwatch',
  aws_access_key_id = AWS_ACCESS_KEY_ID,
  aws_secret_access_key = AWS_SECRET_ACCESS_KEY,
  region_name = AWS_REGION  
)

# Headers for GitHub API request
headers = {
  "Authorization":f"token {GITHUB_TOKEN}"
}

def fetch_data(url):
  print(f"URL: {url}")
  items = []
  while url:
    while True:
      response = requests.get(url, headers=headers)
      if response.status_code == 200:
        items.extend(response.json())
        url = response.links.get('next', {}).get('url')
        break
        # stats = response.json()
        # num_data = len(stats)
        # return num_data
      elif response.status_code == 202:
        print("Got 202, Wating...")
        time.sleep(30)
      else:
        print(f"Failed to fecth data: {response.status_code}")
        return None
  return items

def fetch_num_open_issues():  
  url_issues = f"{GITHUB_API_URL}/repos/aws-actions/{REPO_NAME}/issues?state=open"
  data = fetch_data(url_issues)
  return len(data)

def fetch_num_open_prs():
  url_prs = f"{GITHUB_API_URL}/repos/aws-actions/{REPO_NAME}/pulls?state=open"
  data = fetch_data(url_prs)
  return len(data)

def fetch_num_closed_issues():
  url_closed_issues = f"{GITHUB_API_URL}/repos/aws-actions/{REPO_NAME}/issues?state=closed"
  data = fetch_data(url_closed_issues)
  return len(data)

def fetch_num_closed_prs_yesterday():
  url_closed_prs_yesterday = f"{GITHUB_API_URL}/repos/aws-actions/{REPO_NAME}/pulls?state=closed&sort=updated&direction=desc"
  data = fetch_data(url_closed_prs_yesterday)
  now = datetime.now(timezone.utc)
  yesterday = now - timedelta(days=1)

  merged_count = 0
  for pr in data:
      if pr['merged_at']:
          merged_at = datetime.strptime(pr['merged_at'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

          if merged_at >= yesterday:
            merged_count += 1
          else:
            break
  return merged_count

def upload_metrics_to_cloudwatch(num_issues, num_prs_open, num_prs_closed_yesterday):

  if num_issues is not None and num_prs_open is not None:
    # put metric data to CloudWatch
    print(f"Number of PRs: {num_prs_open}")
    print(f"Number of Issues: {num_issues}")
    response = client.put_metric_data(
      Namespace = NAMESPACE,
      MetricData = [
        {
          'MetricName':f'NumberOfOpenIssues.{REPO_NAME}',
          'Value':num_issues,
          'Unit':'Count'
        },
        {
          'MetricName':f'NumberOfOpenPRs.{REPO_NAME}',
          'Value':num_prs_open,
          'Unit':'Count'
        },
        {
          'MetricName':f'NumberOfPRsClosed.{REPO_NAME}',
          'Value':num_prs_closed_yesterday,
          'Unit':'Count'
        }
      ]
    )
    print("Uploaded metrics to cloudwatch:", response)
  else:
    print("No metrics to Upload")

if __name__ == "__main__":
  num_open_issues = fetch_num_open_issues()
  num_open_prs = fetch_num_open_prs()
  num_closed_prs = fetch_num_closed_prs_yesterday()
  upload_metrics_to_cloudwatch(num_open_issues - num_open_prs, num_open_prs, num_closed_prs)
