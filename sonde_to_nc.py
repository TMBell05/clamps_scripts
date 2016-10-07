import argparse
import csv
import os
import StringIO

from datetime import datetime

import netCDF4


def sonde_to_nc(in_file, out_dir, out_prefix):
    """

    :param in_file: File to convert to netcdf
    :param out_dir: Directory to write file to
    :param out_prefix:
    :return:
    """

    # Put lines from file into a list
    count = 0
    launches = []
    with open(in_file, 'r') as f:
        for line in f:
            if 'Data Type' not in line:
                launches[count-1].append(line)
            else:
                count += 1
                launches.append([line])

    # Loop through launches and make the netcdf
    for sonde in launches:

        # Get the data into an easier format for writing to netcdf
        data = StringIO.StringIO("".join(sonde[12:]))
        reader = csv.DictReader(data, delimiter=' ', skipinitialspace=True)
        del data

        data = {}
        first = True
        for level in reader:
            # Create the lists in the dictionary if this is the first loop
            if first:
                for key in level.keys():
                    data[key] = []
                first = False

            # Append data from each column to the data dictionary.
            # The way this is done, the zeroth index is the unit and
            # The second index is a series of dashes from the text file
            for key in level.keys():
                data[key].append(level[key])

        # Figure out netcdf attributes
        ncattrs = {}
        for i in range(11):  # Since header should always be 11 lines long; will grab release time separately
            if "/" not in sonde[i]:
                tmp = sonde[i].split(": ")
                ncattrs[tmp[0]] = tmp[1].lstrip().replace('\n', '') # Gets rid of white space and newline chars

        # Grab the release time and turn into a datetime object.
        release_time = datetime.strptime(sonde[11].replace('\n', ''),
                                         'Nominal Release Time (y,m,d,h,m,s):%Y, %m, %d, %H:%M:%S')

        # Create the netcdf
        filename = release_time.strftime("{prefix}_%Y%m%d_%H%M%S.nc".format(prefix=out_prefix))
        filename = os.path.join(out_dir, filename)
        nc = netCDF4.Dataset(filename, 'w')

        # Add the attributes
        nc.setncatts(ncattrs)

        # Create the time dimension
        nc.createDimension('time', None)

        # Add the data
        for var in data.keys():
            nc_var = nc.createVariable(var, 'f', dimensions=('time',))
            nc_var.setncattr('units', data[var][0])
            nc_var[:] = data[var][2:]

        # Close the netcdf
        nc.close()


if __name__=='__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-i', dest='in_file')
    parser.add_argument('-O', dest='out_prefix', default='sonde')
    parser.add_argument('-o', dest='out_dir', default=os.getcwd())

    args = parser.parse_args()

    sonde_to_nc(args.in_file, args.out_dir, args.out_prefix)