#!/usr/bin/env python3
import boto3
from botocore.exceptions import ClientError
import xlsxwriter
import argparse
from datetime import datetime, timedelta
import logging
import re

def get_events(health, events_list, start_date, end_date, token=None):
    #get all events for this account
    if token:
        response = health.describe_events(
            filter = {'startTimes': [{'from': start_date}, {'to': end_date}]},
            nextToken = token
        )
    else:
        response = health.describe_events(
            filter = {'startTimes': [{'from': start_date}, {'to': end_date}]}
        )
    events = response['events']
    token = response.get('nextToken')
    #make a list of all the event arns
    event_arns=[]
    for event in events:
        event_arns.append(event['arn'])
    #make a list of all event descriptions
    response = health.describe_event_details(eventArns=event_arns)
    #add each event desription to each event
    for i in range(0, len(events)):
        events[i]['description'] = response['successfulSet'][i]['eventDescription']['latestDescription']    
    #get affected resources for each event
    response = health.describe_affected_entities(filter = {'eventArns':event_arns})

    for i in range(0, len(events)):
        events[i]['affected_resources'] = response['entities'][0]['entityValue']

    events_list.extend(events)
    
    if token:
        get_events(health, events_list, start_date, end_date, token)
    
    return(events_list)

def write_events(accounts, wb, start_date, end_date, role=None):
    ws = wb.add_worksheet(name='Events')
    bold_fmt = wb.add_format({'bold': True})
    account_id_fmt = wb.add_format({'num_format': '0'})

    header = ['Account Id', 'Account Name', 'ARN', 'Service', 'Type', 'Category', 'Region', 'Start Time', 'End Time', 'Last Updated Time', 'Status', 'Description', 'Affected Resources']
    ws.write_row(0, 0, header, bold_fmt)

    sts_client = boto3.client('sts')

    r = 1 
    for accountid in accounts:
        if role:
            RoleArn="arn:aws:iam::{}:role/{}".format(accountid, role)
            SessionName="session_{}".format(accountid)
            try:
                response = sts_client.assume_role(RoleArn=RoleArn, RoleSessionName=SessionName)
                credentials = response['Credentials']

                health = boto3.client(
                    'health', 
                    aws_access_key_id=credentials['AccessKeyId'], 
                    aws_secret_access_key=credentials['SecretAccessKey'], 
                    aws_session_token=credentials['SessionToken'], 
                    region_name='us-east-1'
                )
            except ClientError as e:
                print("While assuming role {} in account {}: {}".format(role, accountid, e))
                # print(e.response)
                #Example error response {'Error': {'Type': 'Sender', 'Code': 'AccessDenied', 'Message': 'Not authorized to perform sts:AssumeRole'}, 'ResponseMetadata': {'RequestId': 'a0346e12-8fc5-11e8-ae3a-6f2c0e2d4e6d', 'HTTPStatusCode': 403, 'HTTPHeaders': {'x-amzn-requestid': 'a0346e12-8fc5-11e8-ae3a-6f2c0e2d4e6d', 'content-type': 'text/xml', 'content-length': '284', 'date': 'Wed, 25 Jul 2018 04:45:59 GMT'}, 'RetryAttempts': 0}}        
                continue
        else:
            health = boto3.client('health', region_name='us-east-1')
            organizations = boto3.client('organizations')
            response = organizations.describe_account(AccountId=accountid)
            account_name = response["Account"]["Name"]

        events = get_events(health, [], start_date, end_date)
   
        col_width = [14, 20, 0, 0, 0, 0, 0, 12, 12, 12, 0, 15, 0]
        for event in events:
            ws.write_number(r, 0, int(accountid), account_id_fmt)
            if role:
                ws.write_formula(r, 1, "=VLOOKUP(A{},AccountTable[#Data],4,FALSE)".format(r+1))
            else:
                ws.write(r, 1, account_name)
            ws.write(r, 2, event['arn'])
            col_width[2] = max(len(event['arn']), col_width[2])
            ws.write(r, 3, event['service'])
            col_width[3] = max(len(event['service']), col_width[3])
            ws.write(r, 4, event['eventTypeCode'])
            col_width[4] = max(len(event['eventTypeCode']), col_width[4])
            ws.write(r, 5, event['eventTypeCategory'])
            col_width[5] = max(len(event['eventTypeCategory']), col_width[5])
            ws.write(r, 6, event['region'])
            col_width[6] = max(len(event['region']), col_width[6])
            ws.write(r, 7, event['startTime'])
            ws.write(r, 8, event.get('endTime', ''))
            ws.write(r, 9, event['lastUpdatedTime'])
            ws.write(r, 10, event['statusCode'])
            col_width[10] = max(len(event['statusCode']), col_width[10])
            ws.write(r, 11, event['description'])
            ws.write(r, 12, event['affected_resources'])
            col_width[12] = max(len(event['affected_resources']), col_width[12])
                
            #ws.write_row(r, 1, list(event.values()))
            r += 1

        for i in range(0, len(col_width)):
            ws.set_column(i, i, col_width[i])

        
    ws.autofilter(0, 0, r+1, len(header)-1)

def write_accounts(wb, accounts):
    bold_fmt = wb.add_format({'bold': True})
    account_id_fmt = wb.add_format({'num_format': '0'})

    ws = wb.add_worksheet(name='Accounts')

    header = list(accounts[0])
    ws.add_table(0, 0, len(accounts), len(header)-1, {'name': 'AccountTable'})    
    ws.write_row(0, 0, header, bold_fmt)
    # ws.autofilter(0, 0, len(accounts)+1, len(header)-1)

    r = 1
    for account in accounts:
        ws.write_row(r, 0, list(account.values()))
        ws.write_number(r, 0, int(account['Id']), account_id_fmt)
        r += 1
    
    ws.set_column(0, 0, 14)
    ws.set_column(6, 6, 14)

def main():
    today = datetime.now()
    default_output_file = "phd_{}.xlsx".format(today.strftime("%d%m%Y"))

    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", 
      help='The output filename, default: phd_<date>.xlsx', 
      default=default_output_file
    )
    parser.add_argument(
        "-a", "--all", action='store_true',
        help="Use this switch to fetch events from all linked accounts. Requires --role"
    )
    parser.add_argument(
        "-r", "--role",
        help="The role to be assumed to access PHD in other accounts"
    )
    parser.add_argument(
        "-p", "--period",
        help="Define the report period as <number>m|d e.g 30d for last 30 days or 1m for the last 2 months",
        default="30d"
    )
    
    args = parser.parse_args()

    dest_filename = args.output

    wb = xlsxwriter.Workbook(
        dest_filename, 
        {'strings_to_numbers':  True,
        'remove_timezone': True,
        'default_date_format': 'dd/mm/yy hh:mm',}
    )
    
    time = re.match("(\d+)([md])", args.period)
    if not time:
        logging.error("Wrong report period specified. Period must be in the form <number>m|d e.g 30d for last 30 days or 1m for the last 2 months")
        quit(-1)

    if time.group(2) == 'd':
        days = int(time.group(1))
        start_date = today - timedelta(days=days)
        end_date = today
    elif time.group(2) == 'm':
        months = int(time.group(1))
        start_date = datetime(today.year, today.month - months, 1)
        end_date = datetime(today.year, today.month, 1)
    else:
        #default period is last 30 days
        logging.error("Unknown format {}".format(args.period))

    if args.all:
        if not args.role:
            print("ERROR: --all requires --role")
            quit(-1)
        else:
            role = args.role

            org = boto3.client('organizations', region_name='us-east-1')
            response = org.list_accounts()    
            accounts = response['Accounts']
            #create a list of account IDs for all th accounts we need to get events 
            account_IDs = []
            for account in accounts:
                account_IDs.append(account['Id'])

            write_events(account_IDs, wb, start_date, end_date, role)

            write_accounts(wb, accounts)
    else:
        if args.role:
            print("ERROR: --role makes sense only in combination with --all")
            quit(-1)
        else:
            iam = boto3.client('iam')
            response = iam.get_user()
            accountid = response['User']['Arn'].split(':')[4]
            account_IDs = [accountid]

            write_events(account_IDs, wb, start_date, end_date)

    wb.close()

    quit(0)

if __name__ == '__main__':
    main()
