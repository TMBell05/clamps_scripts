# System packages
import argparse
import os

from datetime import datetime, timedelta, date
from glob import glob

# Third party packages
import netCDF4
import numpy as np

FILL_VALUE = -9999.0


def hours_to_epoch_time(date, hours):

    date = datetime(date.year, date.month, date.day)
    dates_list = np.asarray([date + timedelta(hours=float(x)) for x in hours])
    epoch_list = np.asarray([dt_to_epoch(dt) for dt in dates_list])

    return epoch_list, dates_list


def dt_to_epoch(dt):
    return (dt - datetime(1970,1,1)).total_seconds()


def write_variables(nc, variables):

    for var in variables:
        try:
            nc.variables[var][:] = variables[var]
        except IndexError:
            nc.variables[var][:] = variables[var][0]

def setup_new_nc(out_file, nc):
    new_nc = netCDF4.Dataset(out_file, 'w')

    # Create the dimensions
    new_nc.createDimension('time', None)
    new_nc.createDimension('height', nc.dimensions['height'].size)

    # Set the attributes for the netcdf
    for attr in nc.ncattrs():
        tmp = nc.getncattr(attr)
        new_nc.setncattr(attr, tmp)

    # Create a dictionary to store data
    variables = {'epoch_time': []}

    # Create the variables
    for var in nc.variables:
        if 'time' not in var and 'hour' not in var:
            variables[var] = []

            tmp_var = nc.variables[var]  # Gotta grab the variable object

            # Create the variable for later
            nc_var = new_nc.createVariable(varname=tmp_var.name, datatype=tmp_var.datatype, dimensions=tmp_var.dimensions,
                                           fill_value=FILL_VALUE)

            # Set the attrs for the variable
            for attr in tmp_var.ncattrs():
                tmp = tmp_var.getncattr(attr)
                nc_var.setncattr(attr, tmp)

            del tmp_var

    # Add in new epoch time variable
    nc_var = new_nc.createVariable('epoch_time', datatype=int, dimensions=('time',), fill_value=FILL_VALUE)
    nc_var.setncattr('long_name', 'Time since 1 Jan 1970 at 00:00:00 UTC in seconds')
    nc_var.setncattr('units', 'seconds')

    return new_nc, variables


def process_files(start, end, dir, out_file):
    """
    This function does the heavy lifting. It'll do blah blah
    :param start:
    :param end:
    :param dir:
    :param out_file:
    :return:
    """

    # Do some garbage to get the right days in string format
    tmp_start = date(start.year, start.month, start.day)
    tmp_end = date(end.year, end.month, end.day)
    days = [(tmp_start + timedelta(days=x)) for x in range((tmp_end-tmp_start).days+1)]
    days.sort()
    del tmp_start, tmp_end

    first = True
    # Get the correct files
    for day in days:
        files = glob(os.path.join(dir, day.strftime("*%Y%m%d*")))
        if len(files) == 0:
            raise Exception("No files found!")

        # Process the files
        for f in files:
            # Open the netcdf
            nc = netCDF4.Dataset(f, 'r')

            # If this is the first loop, set up the new netcdf
            if first:
                new_nc, variables = setup_new_nc(out_file, nc)
                first = False

            # Get the times
            epoch_list = np.asarray([nc.variables['base_time'] + x for x in nc.variables['time_offset']])
            dt_list = np.asarray([datetime.utcfromtimestamp(x) for x in epoch_list])


            # Get the indicies that match the dates
            ind = np.logical_and(dt_list > start, dt_list < end)

            for var in variables.keys():

                if var == 'epoch_time':
                    # Since epoch time isn't in the original netcdf, this has to be done separate
                    variables[var] += list(epoch_list[ind])
                elif var == 'height':
                    variables[var] += list(nc[var][:])
                elif nc[var].shape != ():
                    variables[var] += list(nc[var][ind])
                else:
                    variables[var] += [FILL_VALUE]

        # Close the netcdf
        nc.close()

    write_variables(new_nc, variables)

    new_nc.close()


if __name__=='__main__':
    # Initialize argument parser
    parser = argparse.ArgumentParser()

    parser.add_argument('-s', dest='start_date', help='Start of IOP (YYYYmmdd-HHMM', required=True)
    parser.add_argument('-e', dest='end_date', help="End of IOP (YYYYmmdd-HHMM)", required=True)
    parser.add_argument('-d', dest='dir', help='Directory containing the netcdf files (assumes date is somewhere '
                                               'in file name in format YYYYmmdd)', required=True)
    parser.add_argument('-o', dest='out_file', help='File to write to', required=True)
    args = parser.parse_args()

    # Turn dates to datetime objects
    start_date = datetime.strptime(args.start_date, "%Y%m%d-%H%M")
    end_date = datetime.strptime(args.end_date, "%Y%m%d-%H%M")

    process_files(start_date, end_date, args.dir, args.out_file)