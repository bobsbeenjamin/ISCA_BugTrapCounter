#Engineering/IT began work on this in early Mar 2013 for ISCA.
#This file has been heavily modified from a previous project.

import snap          # to talk to another Snappy device
import array         # handles array objects
import time          # for time stamps
import os.path       # handles opening and closing files
import atexit        # for onKill()
import ftplib        # to talk to remote server
from xmlrpclib import Binary # to format the MAC address

global count, ftp

#Closes the ftp connection on snaploop death
def onKill():
   global ftp
   ftp.close()
   print "Disconnected from FTP"

#Accepts MAC address fed in as an array and converts it to a string, using
#proper formatting
def convertMacAddress(macAddress):
      returnString = ''
      for tuple in macAddress:
         temp = str(tuple)
         if len(temp)<4:
            temp = '0x0' + temp[2]
         returnString += temp + ' '
      returnString = returnString.strip()
      return returnString

#Searches trapNumFinder.dat for a MAC address; if found, this returns its
#associated trap number; otherwise, this returns nothing
def getTrapNum(macAddress):
      file = open('trapNumFinder.dat')
      macData = file.readlines()
      file.close()
      for line in macData:
         if str(line[1:15])==macAddress:
            return line[17:20]
      #MAC address not found
      return None

#Returns a string to be written to the trapNumFinder.dat file; this string
#essentially acts as a record that pairs a MAC address with a trap number
def getStringToWrite_tramNumFinder(macAddress, num):
      string = '\n"' + macAddress + '" '
      num = int(num) + 1 #increment by 1
      num = str(num).rjust(3,'0') #put back in 3-digit string format
      string += num + ' //added automatically by system'
      return string

#Returns a string to be written to an individual .json file; if isFirstRecord
#is true (or 1) then the optionalComma is left off of the front of the string
def getStringToWrite_Json(isFirstRecord):
      global count
      #Set up comma prepend if this is not the firstRecord
      optionalComma = ''
      if not isFirstRecord:
         optionalComma = ', '
      #Pull UTC time
      myTime = time.mktime(time.gmtime())
      #Convert to format that our JSON expects
      myTime = int(myTime)*1000
      string = optionalComma + '['
      string += str(myTime)
      string += ', ' + str(count) + ']'
      return string

#Adds new record to trapNumFinder.dat which pairs a MAC address w/ a trap number
def addNewTrap_trapNumFinder(macAddress):
      file = open('trapNumFinder.dat')
      lines = file.readlines()
      file.close()
      lastLine = lines[len(lines)-1]
      lastNum = lastLine[17:20]
      if len(lines)<2:
         print "Adding first trap to field"
         lastNum = '000'
      stringToWrite = getStringToWrite_tramNumFinder(macAddress,lastNum)
      file = open('trapNumFinder.dat','a')
      file.write(stringToWrite)
      file.close()
      return stringToWrite

#Adds new record to iscaTrap[trapNum].json which represents a single bug catch
def addNewTrap_json(trapNum):
      string = '''{
    "label":"Trap ''' + trapNum + '''",
    "data":[''' + getStringToWrite_Json(1) + ']\n}'
      with open('iscaTrap'+trapNum+'.json','a') as file:
         file.write(string)

#Sets up and calls addNewTrap_trapNumFinder() and addNewTrap_json()
def addNewTrap(macAddress):
      stringWritten = addNewTrap_trapNumFinder(macAddress)
      print "New record added to trapNumFinder.dat"
      newNum = stringWritten[18:21]
      addNewTrap_json(newNum)
      print "New file created and initialized (iscaTrap"+newNum+".json)"
      return newNum


class McastCounterConnector(object):
   #Initialize E10 counter module
   def __init__(self):
      global ftp
      # Register on onKill when closes
      atexit.register(onKill)
      # Create a SNAP instance
      self.snap = snap.Snap(funcs={'setButtonCount': self.set_button_count,'hello': self.hello})
      # Open COM1 (port 0) connected to a SNAP bridge
      self.snap.open_serial(snap.SERIAL_TYPE_RS232, '/dev/ttyS1')
      # Connect to the remote SNAP Connect instance
      self.snap.connect_tcp('127.0.0.1')

      print "Local E10 MAC addresss is:"
      addr = self.snap.local_addr()
      print hex(ord(addr[0])), hex(ord(addr[1])),hex(ord(addr[2]))

      print "Connecting to FTP..."
      ftp = ftplib.FTP('209.17.164.115','iscatech','V22TxL')
      ftp.cwd('/iscatech/engineering/BugTrap')
      print "Connected"

   def hello(self,count):
      # Report total counts to screen
      print "hello!", count

   def set_button_count(self, c):
      global ftp, count
      count = c
      macAddress = self.snap.rpc_source_addr()
      macAddress = hex(ord(macAddress[0])), hex(ord(macAddress[1])), hex(ord(macAddress[2]))

      #Convert macAddress to proper string
      macAddress = convertMacAddress(macAddress)
      print macAddress

      #Locate the correct file to be written to
      trapNum = getTrapNum(macAddress)

      if trapNum==None: #catch and handle a new trap
         print "Trap not found in records"
         trapNum = addNewTrap(macAddress)
         fileName = 'iscaTrap'+trapNum+'.json'
      else:
         print "Trap located in records"
         fileName = 'iscaTrap'+trapNum+'.json'
         #Open correct file and update record
         #Using 'with' automatically manages the file resources
         with open(fileName,'r+') as file:
            print "Local file open ("+fileName+")"
            line1 = file.readline()
            line2 = file.readline()
            line3 = file.readline()
            endOfRecordsIdx = int(len(line1)+len(line2)+len(line3)-2)
            file.seek(endOfRecordsIdx)

            #Get the properly formatted string to write
            file.write(getStringToWrite_Json(0))
            #Add back the stuff that got overwritten
            file.write(']\n}')
            file.flush()

      print "Bug trap event recorded locally"
      try:
         file = open(fileName,'r')
         string = 'STOR ' + fileName
         ftp.storbinary(string, file)
         print "Remote file overwritten with local file"
      finally:
         file.close()


if __name__ == '__main__':

   print "ISCA Technologies (c)"

   client = McastCounterConnector() # Instantiate a client instance
   client.snap.loop() # Loops waiting for SNAP messages
