"""Core register map for supplying the MCP_1_4 HMI.

Derived from HMI_MCP_1_4.pdf:
- Tag Editor: PDF pages 21-24
- Base Screen 1 (Home): PDF pages 25-28
- Base Screen 3 (Config): PDF pages 29-31
- Base Screen 5 (Alarms): PDF pages 31-33
- Base Screens 12 and 13 (Diagnostics): PDF pages 35-40

Data types were checked against the companion MCP_1_4 PLC cross-reference
where the PLC report identifies them. A few member-unit mirror registers are
not typed by the PLC cross-reference because they are populated externally;
those types are documented in TYPE_INFERENCES below.

The fourth register tuple field is the logger/plotter visual flag, not a
read/write flag. It is False because this map is intended for HMI supply.
"""

PLC_CONFIGS = [
    {
        "name": "p1",
        "ip": "192.168.1.2",
        "device": "FF",
        "endian": "0",
        "registers": [
            # MCP mode, demand, probe, and HMI state words.
            ("Probe_Mode", "D0025", "W", False),
            ("Demand_Status", "D0026", "W", False),
            ("DR_Status", "D0027", "W", False),
            ("CTA_Enable", "D0028", "W", False),
            ("DR_Test_Event", "D0029", "W", False),
            ("Probe_Status_1", "D0030", "W", False),
            ("Probe_Status_2", "D0031", "W", False),
            ("Probe_Status_3", "D0032", "W", False),
            ("Probe_Status_4", "D0033", "W", False),

            # Member unit 1 summary and diagnostic values.
            ("Unit_1_Alarms", "D0100", "W", False),
            ("Comp_Run_Hours_1", "D0101", "W", False),
            ("Comp_Time_Delay_1", "D0102", "W", False),
            ("Suction_Pressure_1", "D0103", "W", False),
            ("Discharge_Pressure_1", "D0104", "W", False),
            ("Evap_Temperature_1", "D0105", "F", False),
            ("Cond_Temperature_1", "D0107", "F", False),
            ("Flow_GPM_1", "D0109", "W", False),
            ("Compressor_State_1", "D0110", "W", False),
            ("Solenoid_State_1", "D0111", "W", False),
            ("Pump_Time_Delay_1", "D0114", "W", False),

            # Member unit 2 summary and diagnostic values.
            ("Unit_2_Alarms", "D0120", "W", False),
            ("Comp_Run_Hours_2", "D0121", "W", False),
            ("Comp_Time_Delay_2", "D0122", "W", False),
            ("Suction_Pressure_2", "D0123", "W", False),
            ("Discharge_Pressure_2", "D0124", "W", False),
            ("Evap_Temperature_2", "D0125", "F", False),
            ("Cond_Temperature_2", "D0127", "F", False),
            ("Flow_GPM_2", "D0129", "W", False),
            ("Compressor_State_2", "D0130", "W", False),
            ("Solenoid_State_2", "D0131", "W", False),
            ("Pump_Time_Delay_2", "D0134", "W", False),

            # Member unit 3 summary and diagnostic values.
            ("Unit_3_Alarms", "D0140", "W", False),
            ("Comp_Run_Hours_3", "D0141", "W", False),
            ("Comp_Time_Delay_3", "D0142", "W", False),
            ("Suction_Pressure_3", "D0143", "W", False),
            ("Discharge_Pressure_3", "D0144", "W", False),
            ("Evap_Temperature_3", "D0145", "F", False),
            ("Cond_Temperature_3", "D0147", "F", False),
            ("Flow_GPM_3", "D0149", "W", False),
            ("Compressor_State_3", "D0150", "W", False),
            ("Solenoid_State_3", "D0151", "W", False),
            ("Pump_Time_Delay_3", "D0154", "W", False),

            # Member unit 4 summary and diagnostic values.
            ("Unit_4_Alarms", "D0160", "W", False),
            ("Comp_Run_Hours_4", "D0161", "W", False),
            ("Comp_Time_Delay_4", "D0162", "W", False),
            ("Suction_Pressure_4", "D0163", "W", False),
            ("Discharge_Pressure_4", "D0164", "W", False),
            ("Evap_Temperature_4", "D0165", "F", False),
            ("Cond_Temperature_4", "D0167", "F", False),
            ("Flow_GPM_4", "D0169", "W", False),
            ("Compressor_State_4", "D0170", "W", False),
            ("Solenoid_State_4", "D0171", "W", False),
            ("Pump_Time_Delay_4", "D0174", "W", False),

            # Member unit 5 summary and diagnostic values.
            ("Unit_5_Alarms", "D0180", "W", False),
            ("Comp_Run_Hours_5", "D0181", "W", False),
            ("Comp_Time_Delay_5", "D0182", "W", False),
            ("Suction_Pressure_5", "D0183", "W", False),
            ("Discharge_Pressure_5", "D0184", "W", False),
            ("Evap_Temperature_5", "D0185", "F", False),
            ("Cond_Temperature_5", "D0187", "F", False),
            ("Flow_GPM_5", "D0189", "W", False),
            ("Compressor_State_5", "D0190", "W", False),
            ("Solenoid_State_5", "D0191", "W", False),
            ("Pump_Time_Delay_5", "D0194", "W", False),

            # Member unit 6 summary and diagnostic values.
            ("Unit_6_Alarms", "D0200", "W", False),
            ("Comp_Run_Hours_6", "D0201", "W", False),
            ("Comp_Time_Delay_6", "D0202", "W", False),
            ("Suction_Pressure_6", "D0203", "W", False),
            ("Discharge_Pressure_6", "D0204", "W", False),
            ("Evap_Temperature_6", "D0205", "F", False),
            ("Cond_Temperature_6", "D0207", "F", False),
            ("Flow_GPM_6", "D0209", "W", False),
            ("Compressor_State_6", "D0210", "W", False),
            ("Solenoid_State_6", "D0211", "W", False),
            ("Pump_Time_Delay_6", "D0214", "W", False),

            # Configuration and setpoint values used by Home and Config screens.
            ("Stage_Difference", "D0268", "F", False),
            ("Stage_Time", "D0270", "W", False),
            ("Mix_Timer", "D0271", "W", False),
            ("Max_Stage", "D0272", "W", False),
            ("Tank_Difference", "D0404", "F", False),
            ("Cold_Setpoint", "D0406", "F", False),
            ("Warm_Setpoint", "D0408", "F", False),
            ("Tank_Setpoint", "D0412", "F", False),
            ("Terminal_Setpoint", "D0414", "F", False),
            ("LWT_Setpoint", "D0422", "F", False),

            # Unit status values displayed on Home and Alarm screens.
            ("Unit_Status_1", "D0520", "W", False),
            ("Unit_Status_2", "D0521", "W", False),
            ("Unit_Status_3", "D0522", "W", False),
            ("Unit_Status_4", "D0523", "W", False),
            ("Unit_Status_5", "D0524", "W", False),
            ("Unit_Status_6", "D0525", "W", False),
            ("PLC_Program_Version", "D0600", "F", False),

            # Quantity, visibility, and single-pass configuration values.
            ("Configured_Units", "D1110", "W", False),
            ("Unit_Quantity", "D1130", "W", False),
            ("Probe_Quantity", "D1140", "W", False),
            ("Max_Stage_SP", "D1172", "W", False),

            # Tank and terminal temperature values on the Home screen.
            ("Terminal_Temperature", "D2148", "F", False),
            ("Tank_Temperature_High", "D2150", "F", False),
            ("Tank_Temperature_Mid", "D2152", "F", False),
            ("Tank_Temperature", "D2154", "F", False),

            # Pump settings and diagnostic values.
            ("Pump_Setpoint_1", "D7700", "F", False),
            ("Pump_Setpoint_2", "D7702", "F", False),
            ("Pump_Setpoint_3", "D7704", "F", False),
            ("Pump_Setpoint_4", "D7706", "F", False),
            ("Pump_Setpoint_5", "D7708", "F", False),
            ("Pump_Setpoint_6", "D7710", "F", False),
            ("Pump_Percent", "D7712", "F", False),
            ("Pump_Manual", "D7716", "F", False),

            # HMI state, visibility, alarm, and connection bits.
            ("Cycle", "M0002", "B", False),
            ("Hard_Stop", "M0003", "B", False),
            ("Single_Pass_Mode", "M0025", "B", False),
            ("Maximum_Units_Mode", "M0026", "B", False),
            ("Home_Input_Enable", "M0031", "B", False),
            ("MCP_Alarm", "M0064", "B", False),
            ("Evaporator_Type", "M0096", "B", False),
            ("Evaporator_Quantity", "M0100", "B", False),
            ("System_Status_241", "M0241", "B", False),
            ("CTA_Mode_2044", "M2044", "B", False),
            ("Unit_1_Connected", "M8345", "B", False),
            ("Unit_2_Connected", "M8346", "B", False),
            ("Unit_3_Connected", "M8347", "B", False),
            ("Unit_4_Connected", "M8350", "B", False),
            ("Unit_5_Connected", "M8351", "B", False),
            ("Unit_6_Connected", "M8352", "B", False),

            # Physical E-stop input used by Home and Alarm screens.
            ("Emergency_Stop", "I0000", "B", False),
        ],
    }
]

# Values that the HMI can originate. They should also be read back through
# PLC_CONFIGS where listed there, so the HMI receives the current PLC value.
HMI_WRITE_COMMANDS = [
    # Bit commands and mode selections.
    ("Start", "M0000", "B"),
    ("Stop", "M0001", "B"),
    ("Hard_Stop_VPB1", "M0020", "B"),
    ("Hard_Stop_VPB2", "M0021", "B"),
    ("Single_Multi_Pass", "M0025", "B"),
    ("Maximum_Units", "M0026", "B"),
    ("Save_HMI_Settings", "M0062", "B"),
    ("DR_Test", "M0810", "B"),
    ("Purge", "M1900", "B"),
    ("CTA_Enable_Disable", "M2045", "B"),

    # Numerical inputs.
    ("DR_Test_Event", "D0029", "W"),
    ("Stage_Difference", "D0268", "F"),
    ("Stage_Time", "D0270", "W"),
    ("Mix_Timer", "D0271", "W"),
    ("Max_Stage", "D0272", "W"),
    ("Tank_Difference", "D0404", "F"),
    ("Cold_Setpoint", "D0406", "F"),
    ("Warm_Setpoint", "D0408", "F"),
    ("Tank_Setpoint", "D0412", "F"),
    ("Terminal_Setpoint", "D0414", "F"),
    ("LWT_Setpoint", "D0422", "F"),
    ("Unit_Quantity", "D1130", "W"),
    ("Probe_Quantity", "D1140", "W"),
    ("Max_Stage_SP", "D1172", "W"),
    ("Pump_Setpoint_1", "D7700", "F"),
    ("Pump_Setpoint_2", "D7702", "F"),
    ("Pump_Setpoint_3", "D7704", "F"),
    ("Pump_Setpoint_4", "D7706", "F"),
    ("Pump_Setpoint_5", "D7708", "F"),
    ("Pump_Setpoint_6", "D7710", "F"),
    ("Pump_Manual", "D7716", "F"),
]

# These HMI tags are useful for unit identification and visual feedback, but
# they are not required to render the default Home screen.
OPTIONAL_CONTROL_BITS = [
    ("Flash_Unit_1", "M0520", "B"),
    ("Flash_Unit_2", "M0521", "B"),
    ("Flash_Unit_3", "M0522", "B"),
    ("Flash_Unit_4", "M0523", "B"),
    ("Flash_Unit_5", "M0524", "B"),
    ("Flash_Unit_6", "M0525", "B"),
]

# The Alarm screen reads individual bits from one alarm word per member unit.
# Supplying the containing words is enough when the HMI-facing server supports
# dotted D-register bit reads.
UNIT_ALARM_WORD_BITS = {
    "D0100": {
        0: "Unit 1 high-pressure alarm",
        1: "Unit 1 low-pressure alarm",
        2: "Unit 1 defrost alarm",
        3: "Unit 1 condenser alarm",
        5: "Unit 1 oil-pressure alarm",
        6: "Unit 1 evaporator alarm",
        7: "Unit 1 protection alarm",
    },
    "D0120": {
        0: "Unit 2 high-pressure alarm",
        1: "Unit 2 low-pressure alarm",
        2: "Unit 2 defrost alarm",
        3: "Unit 2 condenser alarm",
        5: "Unit 2 oil-pressure alarm",
        6: "Unit 2 evaporator alarm",
        7: "Unit 2 protection alarm",
    },
    "D0140": {
        0: "Unit 3 high-pressure alarm",
        1: "Unit 3 low-pressure alarm",
        2: "Unit 3 defrost alarm",
        3: "Unit 3 condenser alarm",
        5: "Unit 3 oil-pressure alarm",
        6: "Unit 3 evaporator alarm",
        7: "Unit 3 protection alarm",
    },
    "D0160": {
        0: "Unit 4 high-pressure alarm",
        1: "Unit 4 low-pressure alarm",
        2: "Unit 4 defrost alarm",
        3: "Unit 4 condenser alarm",
        5: "Unit 4 oil-pressure alarm",
        6: "Unit 4 evaporator alarm",
        7: "Unit 4 protection alarm",
    },
    "D0180": {
        0: "Unit 5 high-pressure alarm",
        1: "Unit 5 low-pressure alarm",
        2: "Unit 5 defrost alarm",
        3: "Unit 5 condenser alarm",
        5: "Unit 5 oil-pressure alarm",
        6: "Unit 5 evaporator alarm",
        7: "Unit 5 protection alarm",
    },
    "D0200": {
        0: "Unit 6 high-pressure alarm",
        1: "Unit 6 low-pressure alarm",
        2: "Unit 6 defrost alarm",
        3: "Unit 6 condenser alarm",
        5: "Unit 6 oil-pressure alarm",
        6: "Unit 6 evaporator alarm",
        7: "Unit 6 protection alarm",
    },
}

# This address exceeds the normal four-digit MiSmTCP operand path. It is used
# by the Config screen as the MSA Display Lock bit.
EXTENDED_REGISTERS = [
    ("MSA_Display_Lock", "D10506.00", "B"),
]

# The PLC cross-reference confirms the setpoint, status, tank temperature,
# pump, and program-version types. The member-unit data block is externally
# populated and is not fully typed in that cross-reference. These inferences
# follow the HMI formatting and address allocation:
# - D0105/D0107 and corresponding unit blocks occupy two words, so they are F.
# - CTD/PTD, pressure, GPM, compressor, and solenoid values occupy one word.
TYPE_INFERENCES = {
    "member_temperature_registers": "Float, based on two-word address spacing",
    "member_timer_pressure_flow_state_registers": "Word, based on one-word spacing",
}
