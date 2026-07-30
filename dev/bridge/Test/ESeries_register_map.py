"""Core register map for supplying the ESeries_HMI_1_216 HMI.

Derived from HMI_ESeries_1_216.pdf:
- Alarm Log Settings: PDF page 5
- Tag Editor: PDF pages 21-24
- Base Screen 1 (Home / Monitor Page): PDF pages 25-26

Data types were checked against the companion ESeries_1_216 PLC cross-reference
where the HMI report alone did not identify whether a D register was Word or
Float.

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
            # Home-screen numerical and multi-state values.
            ("Heat_Call_Display", "D0080", "W", False),
            ("Target_Fan", "D0130", "F", False),
            ("GPM", "D0158", "F", False),
            ("Tank_Temperature", "D0202", "W", False),
            ("LWT_Actual", "D0203", "W", False),
            ("Tank_Setpoint", "D0219", "W", False),
            ("LWT_Setpoint", "D0220", "W", False),
            ("Target_Valve", "D0304", "F", False),
            ("EWT_Actual", "D0506", "F", False),
            ("Ambient_Air", "D0512", "F", False),

            # HMI alarm-log source words.
            ("Alarm_Register_3", "D3498", "W", False),
            ("Alarm_Register_2", "D3499", "W", False),
            ("Alarm_Register_1", "D3500", "W", False),

            # Home-screen state, output, and visibility conditions.
            ("Stop_Status", "M0001", "B", False),
            ("Cycle", "M0002", "B", False),
            ("Defrost", "M0016", "B", False),
            ("Start_Button_Select", "M0116", "B", False),
            ("Demand_Mode", "M0400", "B", False),
            ("Service_Password_Entered", "M0480", "B", False),
            ("Lockout_Alarm_Active", "M0625", "B", False),
            ("Warning_Alarm_Active", "M0626", "B", False),
            ("No_Probe", "M0670", "B", False),
            ("Fan_Only_Demand", "M0800", "B", False),
            ("Quiet_Mode_Active", "M4006", "B", False),
            ("PLC_In_Operation", "M8125", "B", False),

            # FC6A output bits used by Home / Monitor Page lamps.
            ("Pumps_Output", "Q0000", "B", False),
            ("Compressor_Output", "Q0003", "B", False),
            ("Condenser_Heat_Bank_Output", "Q0004", "B", False),
        ],
    }
]

# HMI-originated commands. Stop is also read back in PLC_CONFIGS because the
# Home screen uses it as the Local Stop status lamp.
HMI_WRITE_COMMANDS = [
    ("Start", "M0000", "B"),
    ("Stop", "M0001", "B"),
]

# Base Screen 1 reads timer current value TC0001 as the compressor delay timer.
# The present B/F/W PLC_CONFIGS schema does not directly represent TC operands.
HMI_TIMER_CURRENT_VALUES = [
    ("Compressor_Time_Delay", 1),
]

# Useful elsewhere in the HMI project, but not required to render Base Screen 1.
OPTIONAL_META_REGISTERS = [
    ("Controller_Type", "D0000", "W"),
    ("Modbus_Version", "D0001", "W"),
    ("Customer_Number", "D0002", "W"),
    ("Program_Version", "D0040", "W"),
    ("Unit_Number", "D3520", "W"),
]

# PLC clock values referenced by the HMI project. The report lists no D0566
# entry, so it is intentionally not invented here.
OPTIONAL_CLOCK_REGISTERS = [
    ("Year", "D0560", "W"),
    ("Month", "D0562", "W"),
    ("Day", "D0564", "W"),
    ("Hour", "D0568", "W"),
    ("Minute", "D0570", "W"),
    ("Second", "D0572", "W"),
]

# Quiet Mode screen devices that exceed the normal four-digit MiSmTCP operand
# path. The HMI report does not provide tag names for these addresses.
EXTENDED_REGISTERS = [
    ("Quiet_Mode_Timer_Enable_1", "M11005", "B"),
    ("Quiet_Mode_Timer_Enable_2", "M12005", "B"),
    ("Quiet_Mode_Day_1_Sunday", "M15000", "B"),
    ("Quiet_Mode_Day_1_Monday", "M15002", "B"),
    ("Quiet_Mode_Day_1_Tuesday", "M15004", "B"),
    ("Quiet_Mode_Day_1_Wednesday", "M15006", "B"),
    ("Quiet_Mode_Day_1_Thursday", "M15010", "B"),
    ("Quiet_Mode_Day_1_Friday", "M15012", "B"),
    ("Quiet_Mode_Day_1_Saturday", "M15014", "B"),
    ("Quiet_Mode_Day_2_Sunday", "M15016", "B"),
    ("Quiet_Mode_Day_2_Monday", "M15020", "B"),
    ("Quiet_Mode_Day_2_Tuesday", "M15022", "B"),
    ("Quiet_Mode_Day_2_Wednesday", "M15024", "B"),
    ("Quiet_Mode_Day_2_Thursday", "M15026", "B"),
    ("Quiet_Mode_Day_2_Friday", "M15030", "B"),
    ("Quiet_Mode_Day_2_Saturday", "M15032", "B"),
    ("Quiet_Mode_Time_1_Start", "D70000", "W"),
    ("Quiet_Mode_Time_1_Stop", "D70002", "W"),
    ("Quiet_Mode_Time_2_Start", "D80000", "W"),
    ("Quiet_Mode_Time_2_Stop", "D80002", "W"),
]

# Alarm bit labels from the HMI Alarm Log Settings table. These are included
# for decoding the three source words; the mirror loop only needs the words.
ALARM_WORD_BITS = {
    "D3500": {
        0: "High Pressure Lockout",
        1: "Low Pressure Lockout",
        2: "Condenser Flow Lockout",
        4: "Evaporator Overheat (Alarm Log; tag editor says AOTSAlarm)",
        5: "Oil Pressure",
        7: "Motor Protection Module Alarm",
        8: "Defrost Fault",
        10: "Pump Down Safety Lock",
        11: "Fan Prove Fault",
        12: "Power Fault",
        13: "Short Cycle",
    },
    "D3499": {
        1: "Freeze Protect 2 Alarm",
        2: "Evaporator Temperature Probe Fault",
        4: "High Outlet Water",
        5: "LWT Probe Fault",
        7: "EWT Probe Fault",
        10: "Ambient Air Probe Fault",
        11: "K2 Communication Alarm",
        12: "Freeze Protect 1",
        13: "Condensate Pan Freeze Protection",
    },
    "D3498": {
        0: "Tank Sensor Fault",
        1: "Drain Alarm",
        2: "High Pressure Warning",
        3: "Defrost Alarm",
        4: "Conflicting Demand",
        5: "Hot or Cold Ambient",
        6: "Fan Motor Fault",
        7: "Blower Alarm",
        8: "Low Pressure Warning (Alarm Log; tag editor says ColdAmbAirAlarm)",
        9: "Condenser Flow Alarm",
    },
}


# These names are inferred from how unnamed devices are used on Base Screen 1.
# The source report provides the addresses and conditions, but no tag names.
INFERRED_HOME_DEVICE_NAMES = {
    "M0116": "Selects which START button is visible",
    "M0625": "Lockout alarm active",
    "M0626": "Warning alarm active",
    "M0670": "No tank probe / suppress tank temperature display",
    "M4006": "Quiet mode active",
}

# The HMI report contains two alarm-label disagreements. They are preserved
# instead of silently choosing one source as universally correct.
ALARM_SOURCE_CONFLICTS = {
    "D3500.04": {
        "alarm_log": "Evaporator Overheat",
        "tag_editor": "AOTSAlarm",
    },
    "D3498.08": {
        "alarm_log": "Low Pressure Warning",
        "tag_editor": "ColdAmbAirAlarm",
    },
}
