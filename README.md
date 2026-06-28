<pre>
# fc6a:: A Maintenance protocol repo for python.
With this class library, you can remotely read and write IDEC Programable Logic Controlers 
 using the IDEC Maintinance protocol. 

Example use cases: Over Ethernet, or serial:
Log operations, plot sensor values.
Monitor Multiple PLCs, and registers.
 This includes the ability to concurently read and write PLCs with different endians.  
  
Send control values.
Write your own software applications for controling IDEC PLCs
 
 

#===================================================  
# System Requirements: 
#===================================================  
  IDEC PLCs
  python3

  
#===================================================  
# Optional :        
#===================================================  
  WindLDR
 
#===================================================  
# Supported Data Types:
#===================================================  
  Bit
  Word
  Float
  Counters
  
#===================================================  
# Features:
#===================================================  
  optional debugging.
  read_block: need app testing on Strings
  Force IO: override program, put IO in a state

#===================================================  
# Todo / Development
#===================================================  
  
  ZLD binary imagge downloading.
  Security bit setting.
  Factory Reset
  SD Card operations, list, read / write files, delete.
  Upload files -- for data integrity purposes

#===================================================  
# Archive:
#===================================================  

 fc6a.py, the original library is scheuduled for achival.
 The libary asserted certain functions use certain data tpyes.
 This made expanding opertations difficult. The name of the repo
 will remain the same. The libraries will adopt MiSm naming consistent
 with what a broader class of devices. 
 
 MiSmTCP:     Maintenance Protocol control over TCP sockets
 MiSmSerial:  Maintenance Protocol control over serial 
 MiSmSDCard:  Maintenance Protocol for SD Card operations. 
 MiSmFactory: Maintenance Protocol for provissioning, and reseting devices.
 MiSmHMI:     Maintenance Protocol for HMIs
</pre>
