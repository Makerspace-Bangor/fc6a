## Serial Example Code 
<pre>

Serial_Examples/
├── basic.py               <-- basic usage example
├── basixDebugger.py
├── debug.py
├── Dev
│   ├── chk_plc.py         <-- read plc status registers
│   ├── download_zld.py    <-- download a PLC program binary w/o passwd
│   └── q1.zld             <-- PLC program binary for testing
├── imgs                   <-- images
│   ├── debug.png           
│   └── ser.png              
├── Other_serial_examples  <-- examples in other languages?
│   └── Bash               <-- example in bash
|
├── setTime.py             <-- set PLC time to system time
├── makeTime.exe           <-- set PLC time to system time windows binary
├── Start.py               <-- set 1 bit
└── Stop.py                <-- set 1 bit







# added PRECISSION variable. forget if its 4 or 6, IDEC max is 6, our most frequest use is 4
# Password:
  ENQ + device + 0 + W + V + [8 Character pass] + option + BCC + CR
  yeah its plain text. 
  [[ the password security has different operational modes
   here is the old version. sv1, and sv2 are also available.
   sv1 uses a hash. IDK what SV2 does. This method is described in the OEM docs
    ]]
</pre>


#Testing <br>
chk_plc.py: check the plc for password, and write protect over a USB (serial) connections<br>
<br>
<img src="ser.png"><br>
