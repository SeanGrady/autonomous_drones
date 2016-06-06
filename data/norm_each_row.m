function [ normed ] = norm_each_row( data )
%UNTITLED2 Summary of this function goes here
%   Detailed explanation goes here
normed = data;
for i = 1:size(data, 1)
   row = data(i,:);
   normed(i,:) = (row-min(data)) ./ (max(data)-min(data));
end

end

