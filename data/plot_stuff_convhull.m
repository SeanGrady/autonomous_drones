function [ xy ] = plot_stuff_convhull( lat_lon_val )
% Make a heatmap of latitude/longitude/sensor value, 
% but make the heatmap convex when looking down to eliminate outliers

lat=lat_lon_val(:,1);
lon=lat_lon_val(:,2);
val=lat_lon_val(:,3);

[x,y,z] = geodetic2enu(lat, lon, zeros(size(lat_lon_val,1),1), min(lat), min(lon), 0, wgs84Ellipsoid);

xy = [x y];

% Take convex hull of data
K = convhull(x,y,val);
idxs = reshape(K,[size(K,1)*3,1]);
xy_val = [xy val];
qverts = xy_val(idxs, :);

% Filter out points that are too low 
qverts = qverts(qverts(:,3) > 10,:);
% scatter3(qverts(:,1),qverts(:,2),qverts(:,3));
% return;

x = qverts(:,1);
y = qverts(:,2);
val = qverts(:,3) / 1.0e6;  % divide by 1e6 to convert bps -> mbps


% Add corners so the plot is rectangular
margin = 0;
max_x = max(x);
max_y = max(y);
for xchange = [-margin max_x+2]
    for ychange = [-margin max_y+4]
        x = [x;xchange];
        y = [y;ychange];
        val = [val;0];
    end
end

% csvwrite('data.csv',[x y val]);

xvals = 0:1:max(x);
yvals = 0:1:max(y);

[xq,yq] = meshgrid(xvals,yvals);
zq = griddata(x,y,val,xq,yq,'natural');
% contour(xq,yq,zq,10);
contourf(xq,yq,zq,11);
colormap(pink);
% pcolor(xq,yq,zq);

c=colorbar();
c.Label.String = 'WiFi Speed (Mbps)';
fsize = 25;
c.Label.FontSize = fsize;
title('WiFi connectivity on a moving drone','FontSize',fsize);
xlabel('east (m)', 'FontSize',fsize);
ylabel('north (m)','FontSize',fsize);
set(gca,'FontSize',fsize);

end

