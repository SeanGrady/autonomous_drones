function [  ] = plot_stuff( lat_lon_val )

lat=lat_lon_val(:,1);
lon=lat_lon_val(:,2);
val=lat_lon_val(:,3);

[x,y,z] = geodetic2enu(lat, lon, zeros(size(lat_lon_val,1),1), min(lat), min(lon), 0, wgs84Ellipsoid);

[xq,yq] = meshgrid(0:0.1:max(x),0:0.1:max(y));
zq = griddata(x,y,val,xq,yq,'natural');
% contour(xq,yq,zq,10);
contourf(xq,yq,zq,11);
c=colorbar();
c.Label.String = 'Air quality indicator';
fsize = 15;
c.Label.FontSize = fsize;
title('Air quality near the fire (fiesta island)','FontSize',fsize);
xlabel('east (m)', 'FontSize',fsize);
ylabel('north (m)','FontSize',fsize);
set(gca,'FontSize',fsize);

end

