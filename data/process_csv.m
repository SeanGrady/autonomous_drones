function [ x,y,z ] = process_csv( data )
%UNTITLED Summary of this function goes here
%   Detailed explanation goes here
home = [32.990750 -117.128185, 234];
% values are [lat, lon, alt, value, time, roll, pitch, yaw, vx, vy, vz]
[x,y,z] = geodetic2enu(data(:,1), data(:,2), data(:,3), home(1), home(2), home(3), wgs84Ellipsoid);

disp(size(x));
% scatter3(x,y,z);

end

