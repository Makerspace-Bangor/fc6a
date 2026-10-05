project hmi files are largely working now. 
we can extract, disassemble, repack, remotely command, and modify HMI files. 

more testing and documentation is needed. 
but, Im also pretty tired. .. of looking at long
maintenance protocol debug msgs. we can probably push those to --debug flags.
there are about 237 testing scripts in various testing folders. 
many should be consolidated in to single commands and controls. 
extract_znx.py
deconstruct_znv.py could be parts of the same program, or option flags.

others are completly unnecisary beyond the testing they provided.
idec_checksum.py

Theres about 100 different test folders on 6 different PCs which should get 
consolidated. The testing code is mostly tests, but some of the things are 
useful, novel, or shouldnt just be deleted without review. 

Theres a boat load of ZNX/ znv files every place, and most of them are borked 
in one way or another... well that was true. 


There are still unknowns.
but we should get this repo a bit more consolidated before tackling them.

maybe make a list of known, knowns, and known unknowns. 

dl changes screen without activating the backlight. 
( I think that is interesting. )

