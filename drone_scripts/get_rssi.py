#!/usr/bin/python
#
# iwlistparse.py
# Hugo Chargois - 17 jan. 2010 - v.0.1
# Parses the output of iwlist scan into a table

# Modified/updated by Stephen Wayne - 5/30/2016
# More reference: https://www.raspberrypi.org/forums/viewtopic.php?f=32&t=85601

import sys
import subprocess
import threading

interface = "wlan0" # change to wlan1 when using AP also

# You can add or change the functions to parse the properties of each AP (cell)
# below. They take one argument, the bunch of text describing one cell in iwlist
# scan and return a property of that cell.

class RSSISensor(threading.Thread):
    def __init__(self):
        super(RSSISensor, self).__init__()
        # Here's a dictionary of rules that will be applied to the description of each
        # cell. The key will be the name of the column in the table. The value is a
        # function defined above.
        self.rules={
            "Name":self.get_name,
            "Quality":self.get_quality,
            "Channel":self.get_channel,
            "Encryption":self.get_encryption,
            "Address":self.get_address,
            "Signal":self.get_signal_level
        }
        # You can choose which columns to display here, and most importantly in what order. Of
        # course, they must exist as keys in the dict rules.
        self.columns=["Name","Signal", "Channel"]
        #self.columns=["Name","Address","Quality","Signal", "Channel","Encryption"]

    def get_name(self, cell):
        return self.matching_line(cell,"ESSID:")[1:-1]

    def get_quality(self, cell):
        # quality = self.matching_line(cell,"Quality=").split()[0].split('/')
        quality = self.matching_line(cell,"Signal level=")[1]
        # return str(int(round(float(quality[0]) / float(quality[1]) * 100))).rjust(3) + " %"
        return str(int(quality)).rjust(3) + " %"
        ### We won't use this since Raspbian no longer outputs the link quality in iwlist

    def get_channel(self, cell):
        frequency = self.matching_line(cell,"Frequency:")
        channel = frequency[frequency.index("(")+9:frequency.index(")")]
        return channel

    def get_signal_level(self, cell):
        # Signal level is on same line as Quality data so a bit of ugly
        # hacking needed...
        level = self.matching_line(cell,"Signal level=")
        level = level.split()[0].split('/')
        return str(int(round(float(level[0]) / float(level[1]) * 100))).rjust(3) + " %"


    def get_encryption(self, cell):
        enc=""
        if self.matching_line(cell,"Encryption key:") == "off":
            enc="Open"
        else:
            for line in cell:
                matching = self.match(line,"IE:")
                if matching!=None:
                    wpa2=self.match(matching,"IEEE 802.11i/WPA2 Version ")
                    if wpa2!=None:
                        #enc="WPA v."+wpa
                        enc="WPA2"
                    wpa=self.match(matching,"WPA Version ")
                    if wpa!=None:
                        enc="WPA v. "+wpa
            if enc=="":
                enc="WEP"
        return enc

    def get_address(self, cell):
        return self.matching_line(cell,"Address: ")

    # Here you can choose the way of sorting the table. sortby should be a key of
    # the dictionary rules.
    def sort_cells(self, cells):
        sortby = "Signal"
        reverse = True
        cells.sort(None, lambda el:el[sortby], reverse)

    # Below here goes the boring stuff. You shouldn't have to edit anything below
    # this point

    def matching_line(self, lines, keyword):
        """Returns the first matching line in a list of lines. See match()"""
        for line in lines:
            matching=self.match(line,keyword)
            if matching!=None:
                return matching
        return None

    def match(self, line,keyword):
        """If the first part of line (modulo blanks) matches keyword,
        returns the end of that line. Otherwise returns None"""
        line=line.lstrip()
        length=len(keyword)
        if line[:length] == keyword:
            return line[length:]
        else:
            return None

    def parse_cell(self, cell):
        """Applies the rules to the bunch of text describing a cell and returns the
        corresponding dictionary"""
        parsed_cell={}
        for key in self.rules:
            rule=self.rules[key]
            parsed_cell.update({key:rule(cell)})
        return parsed_cell

    def print_table(self, table):
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

    def print_cells(self, cells):
        table=[self.columns]
        for cell in cells:
            cell_properties=[]
            for column in self.columns:
                cell_properties.append(cell[column])
            table.append(cell_properties)
        self.print_table(table)

    def main(self):
        """Pretty prints the output of iwlist scan into a table"""
        
        cells=[[]]
        parsed_cells=[]

        proc = subprocess.Popen(["iwlist", interface, "scan"],stdout=subprocess.PIPE, universal_newlines=True)
        out, err = proc.communicate()
        print "step 1: ", out

        for line in out.split("\n"):
            cell_line = self.match(line,"Cell ")
            if cell_line != None:
                cells.append([])
                line = cell_line[-27:]
            cells[-1].append(line.rstrip())

        cells=cells[1:]

        for cell in cells:
            parsed_cells.append(self.parse_cell(cell))

        self.sort_cells(parsed_cells)

        self.print_cells(parsed_cells)
        
        proc1 = subprocess.Popen(["iwconfig", interface],stdout=subprocess.PIPE, universal_newlines=True)
        out1, err1 = proc1.communicate()

        for line1 in out1.split("\n"):
            SSID_tok = self.match(line1,interface)
            Quality_tok = self.match(line1,"Link Quality=")
            BitRate_tok = self.match(line1,"Bit Rate:")
            if SSID_tok != None:
                SSID = SSID_tok.split('ESSID:')[1].split('"')[1]
            if Quality_tok != None:
                Quality = Quality_tok.split()[0].split('/')[0]
                Sig = Quality_tok.split('Signal level=')[1].split('/')[0]
                Noise = Quality_tok.split('Noise level=')[1].split('/')[0]
            if BitRate_tok != None:
                BitRate = BitRate_tok.split(' ')[0]


        print "things: ", SSID_tok, Quality_tok, Sig, Noise, Bitrate
        if SSID and Quality and Sig and Noise and Bitrate:
	    out_str = str("SSID:," + SSID + ",Quality:," + Quality + ",Signal:," + \
            Sig + ",Noise:," + Noise + ",BitRate:," + BitRate)
            print(out_str)

if __name__ == "__main__":
    rssi = RSSISensor()
    rssi.main()
