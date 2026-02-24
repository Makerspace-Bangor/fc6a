from MiSmSerial import MiSmSerial

PORT = "/dev/ttyACM0"

plc = MiSmSerial(
    PORT,
    device="FF",
    baud=9600,
    debug=True,
    bcc_mode="auto",
)

try:
	# watchout Virtualbox with FK with your ports. 
    # Turn ON M8000 (put PLC into RUN)
    plc.write_bit("M8000", 1)
    print("M8000 set to 1 (RUN).")

finally:
    plc.close()
