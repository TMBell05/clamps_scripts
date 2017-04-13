import argparse
import os

import netCDF4
import numpy as np

from utils import concat_files
from datetime import datetime
from numpy import sin, cos


def find_nearest(value, array):
    """
    Returns the index of the closest values in array to value
    :return:
    """
    return np.abs((array - value)).argmin(axis=0)


def rotate(u, v, w, yaw, pitch, roll):

    rot_matrix = np.asarray(
        [[cos(yaw)*cos(pitch), cos(yaw)*sin(pitch)*sin(roll)-sin(yaw)*cos(roll), cos(yaw)*sin(pitch)*cos(roll)+sin(yaw)*sin(roll)],
        [sin(yaw)*cos(pitch) , sin(yaw)*sin(pitch)*sin(roll)+cos(yaw)*cos(roll), sin(yaw)*sin(pitch)*cos(roll)-cos(yaw)*sin(roll)],
        [-sin(pitch)         , cos(pitch)*sin(roll)                             , cos(pitch)*cos(roll)]])

    vel_matrix = np.asarray([[u], [v], [w]]).transpose()

    result = np.dot(vel_matrix, rot_matrix)

    return result[0, 0], result[0, 1], result[0, 2]


def process_files(vert_files, horiz_files, out_dir, prefix):

    # Get all the data
    vert_data = concat_files(vert_files)
    horiz_data = concat_files(horiz_files)

    # Convert the datetime64 things to python datetime objects and put them back in the dictionary
    vert_times = np.asarray([datetime.utcfromtimestamp(vert_data['epoch'][i])
                             for i in range(vert_data['epoch'].size)])
    horiz_times = np.asarray([datetime.utcfromtimestamp(horiz_data['time'][i])
                             for i in range(horiz_data['time'].size)])

    vert_data['time'] = vert_times
    horiz_data['time'] = horiz_times

    del vert_times, horiz_times

    # Go through each vertical stare and correct it
    new_data = np.zeros_like(vert_data['velocity'])
    for i in range(vert_data['time'].size):
        time_ind = find_nearest(vert_data['time'][i], horiz_data['time'])

        # TODO - Match Heights. Right now assume they are the same gate ranges

        for j, h in enumerate(vert_data['range']):
            u, v, w = rotate(horiz_data['u'][time_ind, j], horiz_data['v'][time_ind, j], vert_data['velocity'][i, j],
                   0, -np.deg2rad(vert_data['pitch'][i, j]), -np.deg2rad(vert_data['roll'][i, j]))
            new_data[i, j] = w

    # Write out the corrected data to netcdf along with the original stuff
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    filename = vert_data['time'][0].strftime("{prefix}_fp_corr_%Y%m%d_%H%M%S.nc".format(prefix=prefix))
    filename = os.path.join(out_dir, filename)

    print filename

    nc = netCDF4.Dataset(filename, 'w', format='NETCDF4')

    nc.createDimension('time', size=None)
    nc.createDimension('range', size=len(vert_data['range']))

    print vert_data['base_time']
    var = nc.createVariable('base_time', 'i8', dimensions=('time',))
    var.setncattr('long_name', 'Time')
    var.setncattr('units', 'seconds since 1970-01-01 00:00:00 UTC')
    var[:] = vert_data['base_time']

    var = nc.createVariable('time_offset', 'i8', dimensions=('time',))
    var.setncattr('long_name', 'Time offset')
    var.setncattr('unis', 'seconds since base_time')
    var[:] = vert_data['time_offset']

    var = nc.createVariable('epoch', 'i8', dimensions=('time',))
    var.setncattr('long_name', 'Epoch Time')
    var.setncattr('units', 'seconds since 1970-01-01 00:00:00 UTC')
    var[:] = vert_data['epoch']

    var = nc.createVariable('hour', 'f8', dimensions=('time',))
    var.setncattr('long_name', 'Hour of Day')
    var.setncattr('units', 'UTC')
    var[:] = vert_data['hour']

    var = nc.createVariable('range', 'f8', dimensions=('range',))
    var.setncattr('long_name', 'height')
    var.setncattr('units', 'km AGL')
    var[:] = vert_data['range']

    var = nc.createVariable('azimuth', 'f8', dimensions=('time', 'range'))
    var.setncattr('long_name', 'Azimuth Angle')
    var.setncattr('units', 'degrees')
    var[:] = vert_data['azimuth']

    var = nc.createVariable('elevation', 'f8', dimensions=('time', 'range'))
    var.setncattr('long_name', 'Elevation angle')
    var.setncattr('units', 'degrees above the horizon')
    var[:] = vert_data['elevation']

    var = nc.createVariable('pitch', 'f8', dimensions=('time', 'range'))
    var.setncattr('long_name', 'Instrument Pitch')
    var.setncattr('units', 'degrees')
    var[:] = vert_data['pitch']

    var = nc.createVariable('roll', 'f8', dimensions=('time', 'range'))
    var.setncattr('long_name', 'Instrument Roll')
    var.setncattr('units', 'degrees')
    var[:] = vert_data['roll']

    var = nc.createVariable('velocity', 'f8', dimensions=('time', 'range'))
    var.setncattr('long_name', 'Doppler velocity')
    var.setncattr('units', 'm/s')
    var.setncattr('comment', 'Positive values are toward the radar')
    var[:] = new_data

    var = nc.createVariable('intensity', 'f8', dimensions=('time', 'range'))
    var.setncattr('long_name', 'Intensity')
    var.setncattr('units', 'Unitless')
    var.setncattr('comment', 'This is computed as (SNR+1)')
    var[:] = vert_data['intensity']

    var = nc.createVariable('backscatter', 'f8', dimensions=('time', 'range'))
    var.setncattr('long_name', 'Attenuated backscatter')
    var.setncattr('units', 'km^(-1) sr^(-1)')
    var[:] = vert_data['backscatter']

    nc.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', action='store', dest='vert_files', nargs='*')
    parser.add_argument('-i', action='store', dest='horiz_files', nargs='*')
    parser.add_argument('-o', action='store', dest='out_dir')
    parser.add_argument('-p', action='store', dest='prefix')
    args = parser.parse_args()

    process_files(args.vert_files, args.horiz_files, args.out_dir, args.prefix)

    pass