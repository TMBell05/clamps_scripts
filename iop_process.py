import csv
import os
from lidar_to_iop import process_files
from datetime import datetime

input_dir = '/Users/tylerbell/data/pecan_mp1_lidar_vad/'

with open('/Users/tylerbell/data/Copy of IOPPriorityList.csv') as csvfile:
    reader = csv.DictReader(csvfile, delimiter=',')

    for row in reader:
        try:

            start = datetime.strptime(row['Start Date'] + row['Start Time'], "%m/%d/%y%H:%M UTC")
            end = datetime.strptime(row['End Date'] + row['End Time'], "%m/%d/%y%H:%M UTC")
            new_file = 'pecan_mp1_lidar_vad_{}.nc'.format(row['Mission'])
            process_files(start, end, input_dir, os.path.join(input_dir, new_file))
        except Exception:
            print row['Start Date']