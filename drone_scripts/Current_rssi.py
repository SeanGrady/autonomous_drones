#!/usr/bin/env python
#
# iwlistparse.py
# Hugo Chargois - 17 jan. 2010 - v.0.1
# Parses the output of iwlist scan into a table

# Modified/updated by Stephen Wayne - 5/30/2016
# Stephen Wayne, 10/15/2016
# 	Not sure what happened with scanning nearby networks, but it no longer works.
# 	Either the RPi got some update that changed formatting, or one of the networks
# 	near my house exposed a bug with the scan. Either way, getting the rssi of the
# 	connected network works now (I just deleted the other part), and that is what
# 	we care about for the demo on Oct 26/27
# More reference: https://www.raspberrypi.org/forums/viewtopic.php?f=32&t=85601

import sys
import subprocess

interface = "wlan0" # change to wlan1 when using AP also

# You can add or change the functions to parse the properties of each AP (cell)
# below. They take one argument, the bunch of text describing one cell in iwlist
# scan and return a property of that cell.

def get_name(cell):
    return matching_line(cell,"ESSID:")[1:-1]

def get_quality(cell):
    # quality = matching_line(cell,"Quality=").split()[0].split('/')
	quality = matching_line(cell,"Signal level=")[1]
    # return str(int(round(float(quality[0]) / float(quality[1]) * 100))).rjust(3) + " %"
	return str(int(quality)).rjust(3) + " %"
	### We won't use this since Raspbian no longer outputs the link quality in iwlist

def get_channel(cell):
    frequency = matching_line(cell,"Frequency:")
    channel = frequency[frequency.index("(")+9:frequency.index(")")]
    return channel

def get_signal_level(cell):
    # Signal level is on same line as Quality data so a bit of ugly
    # hacking needed...
    level = matching_line(cell,"Signal level=")
    level = level.split()[0].split('/')
    return str(int(round(float(level[0]) / float(level[1]) * 100))).rjust(3) + " %"


def get_encryption(cell):
    enc=""
    if matching_line(cell,"Encryption key:") == "off":
        enc="Open"
    else:
        for line in cell:
            matching = match(line,"IE:")
            if matching!=None:
                wpa2=match(matching,"IEEE 802.11i/WPA2 Version ")
                if wpa2!=None:
                    #enc="WPA v."+wpa
				    enc="WPA2"
                wpa=match(matching,"WPA Version ")
                if wpa!=None:
                    enc="WPA v. "+wpa
        if enc=="":
            enc="WEP"
    return enc

def get_address(cell):
    return matching_line(cell,"Address: ")

# Here's a dictionary of rules that will be applied to the description of each
# cell. The key will be the name of the column in the table. The value is a
# function defined above.

rules={"Name":get_name,
       "Quality":get_quality,
       "Channel":get_channel,
       "Encryption":get_encryption,
       "Address":get_address,
       "Signal":get_signal_level
       }

# Here you can choose the way of sorting the table. sortby should be a key of
# the dictionary rules.

def sort_cells(cells):
    sortby = "Signal"
    reverse = True
    cells.sort(None, lambda el:el[sortby], reverse)

# You can choose which columns to display here, and most importantly in what order. Of
# course, they must exist as keys in the dict rules.

columns=["Name","Signal", "Channel"]
#columns=["Name","Address","Quality","Signal", "Channel","Encryption"]




# Below here goes the boring stuff. You shouldn't have to edit anything below
# this point

def matching_line(lines, keyword):
    """Returns the first matching line in a list of lines. See match()"""
    for line in lines:
        matching=match(line,keyword)
        if matching!=None:
            return matching
    return None

def match(line,keyword):
    """If the first part of line (modulo blanks) matches keyword,
    returns the end of that line. Otherwise returns None"""
    line=line.lstrip()
    length=len(keyword)
    if line[:length] == keyword:
        return line[length:]
    else:
        return None

def parse_cell(cell):
    """Applies the rules to the bunch of text describing a cell and returns the
    corresponding dictionary"""
    parsed_cell={}
    for key in rules:
        rule=rules[key]
        parsed_cell.update({key:rule(cell)})
    return parsed_cell

def print_table(table):
    widths=map(max,map(lambda l:map(len,l),zip(*table))) #functional magic

    justified_table = []
    for line in table:
        justified_line=[]
        for i,el in enumerate(line):
            justified_line.append(el.ljust(widths[i]+2))
        justified_table.append(justified_line)
    
    for line in justified_table:
        for el in line:
            print el,
        print

def print_cells(cells):
    table=[columns]
    for cell in cells:
        cell_properties=[]
        for column in columns:
            cell_properties.append(cell[column])
        table.append(cell_properties)
    print_table(table)

def main():
    proc1 = subprocess.Popen(["iwconfig", interface],stdout=subprocess.PIPE, universal_newlines=True)
    out1, err1 = proc1.communicate()

    for line1 in out1.split("\n"):
        SSID_tok = match(line1,interface)
        Quality_tok = match(line1,"Link Quality=")
        BitRate_tok = match(line1,"Bit Rate:")
        if SSID_tok != None:
            SSID = SSID_tok.split('ESSID:')[1].split('"')[1]
        if Quality_tok != None:
            Quality = Quality_tok.split()[0].split('/')[0]
            Sig = Quality_tok.split('Signal level=')[1].split('/')[0]
            Noise = Quality_tok.split('Noise level=')[1].split('/')[0]
        if BitRate_tok != None:
            BitRate = BitRate_tok.split(' ')[0]


    out_str = str("SSID:," + SSID + ",Quality:," + Quality + ",Signal:," + \
	            Sig + ",Noise:," + Noise + ",BitRate:," + BitRate)
    print(out_str)

main()