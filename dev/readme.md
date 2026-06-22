<pre>

This project is a mess! Lol.
Ive had some very bad ideas about how to implement various functionality.
It says dev, but it might be called scratch. 

The main library fc6a asserts that different function have different datatypes,
and that you would pass a number to a function that function would assert the datatype.
Turns out that is a pain to maintain, and the PLCs dont really work that way. 
you can have a bit in a D register, and M registers are not allways bits.

Why the Name change?
Well, the library works on more than the FC6a series for one.
Then, there is internal naming IDEC uses, which reffers to the communication
protocols as a bunch of different things like MiSm, DsSm
no idea what that means, but DsSM is for the HMI, where MiSm is for the PLC.
So I am matching that. Well, for now. 

More confussion:!!
The Maintenance Protocol is used for everything... except downloading firmware.
That uses STX / ETX. I havent gotten into figuring all that out yet. 

I have a lot of code fragments, and this is where its all going to live for now..



</pre>
