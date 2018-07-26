# phd-report
Generate reports of messages in the AWS personal health dashboard for one or multiple accounts 

## Installation
Use `pip install requirements.txt` to install required python packages.

## Usage


```
usage: phd-report.py [-h] [-o OUTPUT] [-a] [-r ROLE] [-p PERIOD]

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        The output filename, default: phd_<date>.xlsx
  -a, --all             Use this switch to fetch events from all linked
                        accounts. Requires --role
  -r ROLE, --role ROLE  The role to be assumed to access PHD in other accounts
  -p PERIOD, --period PERIOD
                        Define the report period as <number>m|d e.g 30d for
                        last 30 days or 1m for the last 2 months
```

Make sure you have setup your AWS cli environment and user.

**Single account**

If you want to generate a report of PHD messages of your user's account make sure the user has access to the `health` api. 

As an example you can run:

`> phd-report.py`

which will save a report of PHD messages in your user's account for the default period of 30 days to a file with the default filename.

**Multi account**

If you want to generate a report of PHD messages across all accounts in an organisation you need to provide a `role` which will be assumed by your user in every account. The `role` needs to have access to the `health` api. 

As an example you can run

`> phd-report.py -a -r role`

which will save a report of PHD messages across all accounts in your organization for the default period of 30 days to a file with the default filename.
