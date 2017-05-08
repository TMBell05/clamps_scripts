import argparse
import os
import sys

from datetime import datetime
from os.path import *
from time import sleep
from utils import send_mail

# Email Configuration
FROM_EMAIL = 'oubliss@icloud.com'
TO_EMAILS = ['tyler.bell@ou.edu']
PASSWORD = 'Perdigao2017'

text = "It looks like there is a problem with {process}. \n" \
       "No files in {dir} have been updated since {mtime} UTC. \n"

# Parse the command line arguments
parser = argparse.ArgumentParser()
parser.add_argument('-d', action='store', dest='dir', help='Directory to watch', required=True)
parser.add_argument('-t', action='store', dest='time', help='Alert time in seconds', required=True)
parser.add_argument('-s', action='store', dest='sleep', help='Sleep time between check in seconds', default=60)
parser.add_argument('-f', action='store', dest='flag', help='Directory to store flag', default=os.getcwd())
parser.add_argument('-i', action='store', dest='process', help='Process name', required=True)
args = parser.parse_args()

watch_dir = args.dir
time = int(args.time)
sleep_time = int(args.sleep)
flag_dir = args.flag
process = args.process

# Stuff to keep emails to a minimum
mail_buffer = 1800
last_email = datetime(2000, 01, 01)

# Check for flag, if present then exit. Otherwise create the flag
flag = join(flag_dir, "{}_CHECK".format(process))
if isfile(flag):
    sys.exit()
else:
    os.system('touch {}'.format(flag))

try:
    # Start loop
    while True:
        # Recursively get the files
        files = [os.path.join(dp, f) for dp, dn, fn in os.walk(watch_dir) for f in fn]

        # Find the latest touched file
        files.sort(key=lambda x: getmtime(x))
        last_file = files[-1]

        # Find when that file is touched
        mod_time = datetime.utcfromtimestamp(getmtime(last_file))

        # Get the time now
        now = datetime.utcnow()

        # Find the difference and alert if it's too large
        diff = (now - mod_time).total_seconds()
        if diff > time and (now-last_email).total_seconds() > mail_buffer:
            message = text.format(process=process, mtime=mod_time.isoformat(), dir=watch_dir)
            subject = "{} Process Error".format(process)
            send_mail(FROM_EMAIL, TO_EMAILS, subject, message, username=FROM_EMAIL, password=PASSWORD)
            last_email = now

        sleep(sleep_time)

except Exception as e:
    os.remove(flag)
    sys.exit()