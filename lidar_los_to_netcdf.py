"""
Converts raw line of sight (los) tab delimited data from the Leosphere 200s Dopplar
Lidar to netcdf. A lot had to be hard coded based on column/linen due to the format it is in.
All hardcoded stuff should be noted with in line documentation

Author: Tyler Bell (Oct 2016)
"""

import argparse
import csv
import os
import StringIO

from datetime import datetime

import netCDF4
import numpy as np


def _to_epoch(dt):
    return (dt - datetime(1970, 1, 1)).total_seconds()


def process_file(in_file, out_dir, out_prefix):
    """

    :param in_file:
    :param out_dir:
    :param out_prefix:
    :return:
    """

    # Read in the data
    data = []
    with open(in_file) as f:
        for line in f:
            data.append(line)

    # Get the number of lines in the header (hopefully in the first line of the file)
    header_size = int(data[0].split('=')[-1])

    # Dictionary for netcdf attributes
    attrs = {}

    # Get the GPS coordinates (Assumes it's in the 5th line). Converts from decimal degrees to regular
    attrs['lat'] = float(data[4].split('=')[-1].split(' ')[0].replace('\r\n', '')[:-1])/100.
    attrs['lon'] = float(data[4].split('=')[-1].split(' ')[-1].replace('\r\n', '')[:-1])/100.

    # Get the compass info which may be important (Assumes lines 29-32)
    attrs['direction_offset'] = float(data[28].split('=')[-1].replace('\r\n', ''))
    attrs['compass_heading'] = float(data[29].split('=')[-1].replace('\r\n', ''))
    attrs['pitch_angle'] = float(data[30].split('=')[-1].replace('\r\n', ''))
    attrs['roll_angle'] = float(data[31].split('=')[-1].replace('\r\n', ''))

    # Get the ranges measured (Assumes line 40 in file and tab delimited)
    range = data[39].split('=')[-1].split('\t')[1:]  # Have to take [1:] b/c of an extra tab after the equals sign
    range[-1] = range[-1].replace('\r\n', '')  # Stupid formatting crap on the last value
    range = np.asarray([float(x) for x in range])

    # Go ahead and grab the full header just in case there's something useful in it
    attrs['full_header'] = "".join(data[0:header_size])

    # Initialize the data arrays
    num_times = len(data[header_size+1:])
    num_ranges = len(range)

    time = np.zeros((num_times,), dtype=np.int64)
    azimuth = np.zeros((num_times, num_ranges), dtype=np.float64)
    elevation = np.zeros((num_times, num_ranges), dtype=np.float64)
    cnr = np.zeros((num_times, num_ranges), dtype=np.float64)
    radial_wind = np.zeros((num_times, num_ranges), dtype=np.float64)
    dispersion = np.zeros((num_times,num_ranges), dtype=np.float64)

    # Fill the arrays
    for i, line in enumerate(data[header_size+1:]):
        # Split the line into columns
        col = line.split('\t')

        try:
            # The columns are hard coded to match specified products
            time[i] = _to_epoch(datetime.strptime(col[0], '%Y/%m/%d  %H:%M:%S.%f'))
            azimuth[i, :] = col[6]
            elevation[i, :] = col[7]
            radial_wind[i, :] = col[8::8]  # Grabs every 8th value
            dispersion[i, :] = col[9::8]
            cnr[i, :] = col[10::8]
        except ValueError:
            print "Value error in line {} for file {}".format(i, in_file)

    # Create the filename
    date = datetime.utcfromtimestamp(time[0])
    if 'RHI' in in_file:
        scan = '_RHI'
    elif 'PPI' in in_file:
        scan = '_PPI'
    else:
        scan = ''

    filename = "{prefix}{scan}_{date}.nc".format(prefix=out_prefix, date=date.strftime("%Y%m%d_%H%M%S"), scan=scan)
    filename = os.path.join(out_dir, filename)

    # Create the netcdf
    nc = netCDF4.Dataset(filename, 'w')

    # Add attributes
    nc.setncatts(attrs)

    # Create Dimensions
    nc.createDimension('time', size=None)
    nc.createDimension('range', size=num_ranges)

    # Create the variables
    ncvar = nc.createVariable('epoch_time', 'i8', dimensions=('time',))
    ncvar.setncattr('units', 'seconds')
    ncvar.setncattr('long_name', 'Time since 1 Jan 1970 at 00:00:00 UTC in seconds')
    ncvar[:] = time[:]

    ncvar = nc.createVariable('range', 'f8', dimensions=('range',))
    ncvar.setncattr('units', 'meters')
    ncvar.setncattr('long_name', 'Distance to range gate')
    ncvar[:] = range[:]

    ncvar = nc.createVariable('azimuth', 'f8', dimensions=('time', 'range'))
    ncvar.setncattr('units', 'degrees')
    ncvar.setncattr('long_name', 'Azimuth angle')
    ncvar[:] = azimuth[:]

    ncvar = nc.createVariable('elevation', 'f8', dimensions=('time', 'range'))
    ncvar.setncattr('units', 'degrees')
    ncvar.setncattr('long_name', 'Elevation angle')
    ncvar[:] = elevation[:]

    ncvar = nc.createVariable('radial_wind', 'f8', dimensions=('time', 'range'))
    ncvar.setncattr('units', 'm/s')
    ncvar.setncattr('long_name', 'Radial wind speed')
    ncvar[:] = radial_wind[:]

    ncvar = nc.createVariable('dispersion', 'f8', dimensions=('time', 'range'))
    ncvar.setncattr('units', 'm/s')
    ncvar.setncattr('long_name', 'Radial wind speed dispersion')
    ncvar[:] = dispersion[:]

    ncvar = nc.createVariable('cnr', 'f8', dimensions=('time', 'range'))
    ncvar.setncattr('units', 'dB')
    ncvar.setncattr('long_name', 'Carrier to noise ratio')
    ncvar[:] = cnr[:]

    # Close the netcdf
    nc.close()


if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    parser.add_argument('-i', dest='in_file')
    parser.add_argument('-O', dest='out_prefix', default='los')
    parser.add_argument('-o', dest='out_dir', default=os.getcwd())

    args = parser.parse_args()

    process_file(args.in_file, args.out_dir, args.out_prefix)



