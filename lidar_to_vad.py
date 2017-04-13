"""
Calculates VADs based on a sin fit of the data. Can specify different keynames in 'var_lookup'
to account for different qc thresholds and variable names.

TODO-Make plotting more elegant than uncommenting stuff

Author: Tyler Bell (March 2017)
"""

import argparse
import os
from datetime import datetime

import matplotlib.pyplot as plt
import netCDF4
import numpy as np

from numpy import sin, cos


# Global Values
FILL_VALUE = -9999.
VEL_LIM = (-30, 30)
HGT_LIM = (0, 1000)
PROFILES_PER_PLOT = 2
Re = 6371000
R43 = Re * 4.0 / 3.0

var_lookup = {'leo':
                  {
                      'vel': 'radial_wind',
                      'thresh_var': 'cnr',
                      'thresh_value': -27.,
                      'az': 'azimuth',
                      'elev': 'elevaton',
                      'range': 'range',
                  },
              'mp1':
                  {
                      'vel': 'velocity',
                      'thresh_var': 'intensity',
                      'thresh_value': 1.015,
                      'az': 'azimuth',
                      'elev': 'elevation',
                      'range': 'range',
                  },
              'mp3':
                  {
                      'vel': 'velocity',
                      'thresh_var': 'intensity',
                      'thresh_value': 1.005,
                      'az': 'azimuth',
                      'elev': 'elevation',
                      'range': 'range',
                  },
             }


def _ray_height(rng, elev, H0=0, R1=R43):
    """
    Center of radar beam height calculation.
    Rinehart (1997), Eqn 3.12, Bech et al. (2003) Eqn 3
    INPUT::
    -----
    r : float
        Range from radar to point of interest [m]
    elev : float
        Elevation angle of radar beam [deg]
    H0 : float
        Height of radar antenna [m]
    R1 : float
        Effective radius
    OUTPUT::
    -----
    H : float
        Radar beam height [m]
    USAGE::
    -----
    H = ray_height(r,elev,H0,[R1=6374000.*4/3])
    NOTES::
    -----
    If no Effective radius is given a "standard atmosphere" is assumed,
       the 4/3 approximation.
    Bech et al. (2003) use a factor ke that is the ratio of earth's radius
       to the effective radius (see r_effective function) and Eqn 4 in B03
    """

    # Convert earth's radius to km for common dN/dH values and then
    # multiply by 1000 to return radius in meters
    hgt = np.sqrt(rng ** 2 + R1 ** 2 + 2 * rng * R1 * np.sin(np.deg2rad(elev)))
    hgt = hgt - R1 + H0

    return hgt


def _list_to_masked_array(in_list, mask_value):
    a = np.array(in_list)
    return np.ma.masked_where(a == mask_value, a)


def calc_vad_3d(az, elev, vel):
    """
    IN DEVELOPMENT DO NOT USE
    :param az:
    :param elev:
    :param vel:
    :return:
    """
    elev = np.deg2rad(elev)
    az = np.deg2rad(az)

    if vel.size > 1:  # If there could be sufficient data points...
        A = sum(vel * sin(az))
        B = sum(sin(az) ** 2 * cos(elev))
        C = sum(cos(az) * sin(az) * cos(elev))
        G = sum(sin(az) * sin(elev))

        D = sum(vel * cos(az))
        E = sum(sin(az) * cos(az) * cos(elev))
        F = sum(cos(az) ** 2 * cos(elev))
        H = sum(cos(az) * sin(elev))

        W = sum(vel)
        X = sum(sin(az)*cos(elev))
        Y = sum(cos(az)*cos(elev))
        Z = sum(az*sin(elev))

        # solve A = uB + vC + wG , D = uE + vF + wH and W = uX + vY+ wZ
        y = np.array([[B, E, X], [C, F, Y], [G, H, Z]])
        z = np.array([A, D, W])
        # print y
        # print z
        try:
            sol = np.linalg.solve(y, z)
            # print sol
            u = sol[0]
            v = sol[1]
            w = sol[2]
            return u, v, w
        except np.linalg.linalg.LinAlgError:
            return FILL_VALUE, FILL_VALUE, FILL_VALUE
    else:
        return FILL_VALUE, FILL_VALUE, FILL_VALUE


def calc_homogeneity(raw_vr, derived_vr):
    """
    Determines homogeneity of the wind field as described in E. Paschke et. al. 2015 section 2.2.4
    :param raw_vr: Raw radial velocity
    :param derived_vr: Radial velocity derived from wind retrieval
    :return:
    """

    vr_bar = np.sum(raw_vr)

    return 1 - np.sum((raw_vr - derived_vr)**2) / np.sum((raw_vr - vr_bar)**2)


def calc_vad(az, elev, vel):
    """
    Performs a 2d (horizontal) VAD retrieval
    :param az:
    :param elev:
    :param vel:
    :return:
    """
    elev = np.deg2rad(elev)
    az = np.deg2rad(az)

    if vel.size > 1:  # If there could be sufficient data points...
        A = sum(vel * sin(az))
        B = sum(sin(az) ** 2) * cos(elev)
        C = sum(cos(az) * sin(az)) * cos(elev)

        D = sum(vel * cos(az))
        E = sum(sin(az) * cos(az)) * cos(elev)
        F = sum(cos(az) ** 2) * cos(elev)

        # solve A = uB + vC and D = uE + vF
        y = np.array([[B, E], [C, F]])
        z = np.array([A, D])
        # print y
        # print z
        try:
            sol = np.linalg.solve(y, z)
            # print sol
            u = sol[0]
            v = sol[1]
            return u, v
        except np.linalg.linalg.LinAlgError:
            return FILL_VALUE, FILL_VALUE, FILL_VALUE
    else:
        return FILL_VALUE, FILL_VALUE, FILL_VALUE


def process_file(in_file, system, height=None, sinfit_dir=None):
    """
    Processes a line of sight netcdf file and outputs the vad. If height is specified,
    it will only return values nearest that height.
    :param in_file: File to process
    :param system: System to use in lookup table
    :param height: Height to process if desired
    :param sinfit_loc: Specify if you want to output a sin fit graph. A specific height MUST be specified.
    :return:
    """
    # Open the netcdf
    nc = netCDF4.Dataset(in_file)
    date = datetime.strptime(nc.start_time, "%Y-%m-%dT%H:%M:%S")

    hgt = []
    u = []
    v = []
    w = []
    rmse = []
    r_sq = []

    for i, range in enumerate(nc[var_lookup[system]['range']][:]):

        # Get the required stuff for this range ring
        cnr = nc[var_lookup[system]['thresh_var']][:, i].transpose()
        vel = nc[var_lookup[system]['vel']][:, i].transpose()
        az = nc[var_lookup[system]['az']][:, i].transpose()
        elev = nc[var_lookup[system]['elev']][:, i]

        # Filter out the bad values based on CNR
        az = np.where(cnr <= var_lookup[system]['thresh_value'], FILL_VALUE, az)
        vel = np.where(cnr <= var_lookup[system]['thresh_value'], FILL_VALUE, vel)

        az = _list_to_masked_array(az, FILL_VALUE)
        vel = _list_to_masked_array(vel, FILL_VALUE)

        # Calculate the vad and height for this range ring
        tmp_u, tmp_v, tmp_w = calc_vad_3d(az, elev, vel)

        # Calculate the RMSE
        N = float(vel.size)
        az_rad = np.deg2rad(az)
        elev_rad = np.deg2rad(elev)

        derived_vr = (sin(az_rad) * cos(elev_rad) * tmp_u) + \
                     (cos(az_rad) * cos(elev_rad) * tmp_v) + \
                     (sin(elev_rad) * tmp_w)

        tmp_E = vel - derived_vr

        # Calculate rms error
        tmp_RMSE = np.sqrt(1 / N * np.sum(tmp_E ** 2))

        tmp_r_sq = calc_homogeneity(vel, derived_vr)

        # Append to the lists for plotting
        u.append(tmp_u)
        v.append(tmp_v)
        w.append(tmp_w)
        hgt.append(_ray_height(range, elev[0]))
        rmse.append(tmp_RMSE)
        r_sq.append(tmp_r_sq)

    if height is not None:
        i = (np.abs(np.asarray(hgt) - height)).argmin()
        u = u[i]
        v = v[i]
        w = w[i]
        hgt = hgt[i]
        rmse = rmse[i]

        if sinfit_dir is not None:
            filename = "sinfit_{height}m_{date}.png".format(height=height, date=date.strftime("%Y%m%d_%H%M%S"))
            filename = os.path.join(sinfit_dir, filename)

            cnr = nc[var_lookup[system]['thresh_var']][:, i].transpose()
            vel = nc[var_lookup[system]['vel']][:, i].transpose()
            az = nc[var_lookup[system]['az']][:, i].transpose()
            elev = np.round(np.mean(nc[var_lookup[system]['elevation']][:, i]), 2)

            vel = np.where(cnr <= var_lookup[system]['thresh_value'], np.nan, vel)

            az_rad = np.deg2rad(az)
            elev_rad = np.deg2rad(elev)

            plt.figure()
            plt.scatter(az, vel)
            plt.plot(az, (u * sin(az_rad) * cos(elev_rad) + v * cos(az_rad) * cos(elev_rad) + w * sin(elev_rad)).tolist())
            plt.ylim((-20, 20))
            plt.xlim((0, 360))
            plt.title("{date} Elev={elev} Height={height}".format(date=date.strftime("%Y%m%d_%H%M%S"),
                                                                  elev=elev,
                                                                  height=hgt))
            plt.savefig(filename)
            plt.close()

    # Close the netcdf
    nc.close()

    return u, v, w, hgt, rmse, r_sq, date, elev


def write_to_nc(filename, date, elev, u, v, w, hgt, rmse, r_sq):
    # Create the netcdf
    nc = netCDF4.Dataset(filename, 'w', format="NETCDF4")

    # Create the height dimension
    nc.createDimension('height', len(hgt))

    # Add the attributes
    nc.setncattr("elev", elev)
    nc.setncattr("date", date.isoformat())

    # Create the variables
    u_var = nc.createVariable('u', 'f8', ('height',), fill_value=FILL_VALUE)
    v_var = nc.createVariable('v', 'f8', ('height',), fill_value=FILL_VALUE)
    w_var = nc.createVariable('w', 'f8', ('height',), fill_value=FILL_VALUE)
    hgt_var = nc.createVariable('hgt', 'f8', ('height',), fill_value=FILL_VALUE)
    rms_var = nc.createVariable('rms', 'f8', ('height',), fill_value=FILL_VALUE)
    r_sq_var = nc.createVariable('r_sq', 'f8', ('height',), fill_value=FILL_VALUE)

    time_var = nc.createVariable('time', 'i8')
    time_var.setncattr('units', 'seconds since 1970-01-01 00:00:00 UTC')

    u_var[:] = np.where(np.isnan(u), FILL_VALUE, u)
    v_var[:] = np.where(np.isnan(v), FILL_VALUE, v)
    w_var[:] = np.where(np.isnan(w), FILL_VALUE, w)
    hgt_var[:] = np.where(np.isnan(hgt), FILL_VALUE, hgt)
    rms_var[:] = np.where(np.isnan(rmse), FILL_VALUE, rmse)
    r_sq_var[:] = np.where(np.isnan(r_sq), FILL_VALUE, r_sq)
    time_var[0] = (date - datetime(1970, 1, 1)).total_seconds()

    # Close the netcdf
    nc.close()


if __name__=='__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-i', dest='in_files', nargs='*')
    parser.add_argument('-O', dest='out_prefix', default='vad')
    parser.add_argument('-o', dest='out_dir', default=os.getcwd())
    parser.add_argument('-s', dest='system', default=None)

    args = parser.parse_args()

    vad_ws = np.zeros(len(args.in_files))
    vad_wd = np.zeros(len(args.in_files))
    time = np.zeros(len(args.in_files), dtype=datetime)
    vad_rmse = np.zeros(len(args.in_files))

    height = 100

    for i, f in enumerate(sorted(args.in_files)):
        print f
        u, v, w, hgt, rmse, r_sq, date, elev = process_file(f, system=args.system)#, height=height, sinfit_dir=args.out_dir)
        nc_name = "{prefix}_{date}_{elev}.nc"
        nc_name = nc_name.format(prefix=args.out_prefix, date=date.strftime("%Y%m%d_%H%M%S"), elev=int(np.mean(elev)))
        nc_name = os.path.join(args.out_dir, nc_name)

        write_to_nc(nc_name, date, elev, u, v, w, hgt, rmse, r_sq)


        #
        # ws = np.sqrt(np.asarray(u)**2 + np.asarray(v)**2)
        # wd = np.arctan2(u, v)
        #
        # vad_ws[i] = ws
        # vad_wd[i] = np.rad2deg(wd)
        # time[i] = date
        # vad_rmse[i] = rmse

        # fig = plt.figure(1, figsize=(25, 7))
        # fig.suptitle(date.isoformat())
        # plt.subplot(1, 5, 1)
        # plt.plot(u, hgt, label=date.strftime("%H:%M"))
        # plt.title("U velocity vs Height")
        # plt.xlabel('Velocity (m/s)')
        # plt.ylabel('Height (m)')
        # plt.xlim(VEL_LIM)
        # plt.ylim(HGT_LIM)
        # plt.legend()
        #
        # plt.subplot(1, 5, 2)
        # plt.plot(v, hgt)
        # plt.title("V velocity vs Height")
        # plt.xlabel('Velocity (m/s)')
        # plt.ylabel('Height (m)')
        # plt.xlim(VEL_LIM)
        # plt.ylim(HGT_LIM)
        #
        # plt.subplot(1, 5, 3)
        # plt.plot(w, hgt)
        # plt.title("W velocity vs Height")
        # plt.xlabel('Velocity (m/s)')
        # plt.ylabel('Height (m)')
        # plt.xlim((-5, 5))
        # plt.ylim(HGT_LIM)
        #
        # plt.subplot(1, 5, 4)
        # plt.plot(rmse, hgt)
        # plt.title("RMS vs Height")
        # plt.xlabel('RMS')
        # plt.ylabel('Height (m)')
        # plt.xlim((0, 10))
        # plt.ylim(HGT_LIM)
        #
        # plt.subplot(1, 5, 5)
        # plt.plot(r_sq, hgt)
        # plt.title("$R^2$ vs Height")
        # plt.xlabel('$R^2$')
        # plt.ylabel('Height (m)')
        # plt.xlim((.8, 1))
        # plt.ylim(HGT_LIM)
        #
        # # Create profile base on start time of first profile
        # if i % PROFILES_PER_PLOT == 0:
        #     image_name = "{prefix}_{date}.png"
        #     image_name = image_name.format(prefix=args.out_prefix, date=date.strftime("%Y%m%d_%H%M%S"))
        #     image_name = os.path.join(args.out_dir, image_name)
        #
        # if i % PROFILES_PER_PLOT == PROFILES_PER_PLOT - 1:
        #     # Save the image
        #     plt.savefig(image_name)
        #     plt.clf()
        #     plt.close()

    # fig, (ax1, ax2) = plt.subplots(2, sharex=True)
    # ind = np.logical_and(~np.isnan(vad_wd), time != 0)
    # vad_wd = np.where(vad_wd[ind] < 0, np.asarray(vad_wd[ind]) + 360., vad_wd[ind])
    # fig.suptitle("Time series %s" % time[1].strftime("%Y%m%d"))
    #
    # ax1.scatter(time[ind], vad_ws[ind], c=vad_rmse[ind])
    # ax1.set_ylim(0, 30)
    # ax1.set_xlim(time[0], time[-1])
    # ax1.set_title("Wind Speed ($m s^-1$)")
    #
    # ax2.scatter(time[ind], vad_wd[ind], c=vad_rmse[ind])
    # ax2.set_ylim(0, 360)
    # ax2.set_title("Wind Direciton")
    # plt.savefig("{date}_{height}m_timeseries.png".format(date=time[1].strftime("%Y%m%d"), height=height))
    # plt.close()






