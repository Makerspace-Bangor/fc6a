"""Core register map for supplying the R513A1505 HMI.

Derived from HMI_R513a1505.pdf:
- Tag Editor: PDF pages 21-29
- Base Screen 1 (Home / Monitor): PDF pages 30-33
- Alarm Log Settings: PDF page 5

The fourth register tuple field is the logger/plotter visual flag, not a
read/write flag. It is False here because this map is intended for HMI supply.
"""

PLC_CONFIGS = [
    {
        "name": "p1",
        "ip": "192.168.1.2",
        "device": "FF",
        "endian": "0",
        "registers": [
            # Home screen data values.
            ("Tank_Probe_Fahr_F", "D0054", "F", False),
            ("Cond_LWT_Fahr_F", "D0056", "F", False),
            ("Cond_EWT_Fahr_F", "D0058", "F", False),
            ("AMB_Fahr_F", "D0062", "F", False),
            ("UNUSED_Fahr_F", "D0068", "F", False),
            ("Cond_LWT_Setpoint_F", "D0280", "F", False),
            ("Heatcall_status", "D1300", "W", False),
            ("HGBV_OPSS", "D1301", "W", False),
            ("AMB_EvapEWT", "D1302", "W", False),
            ("Tank_Target_HMI_F", "D1320", "F", False),
            ("Demand_Mode_Display", "D1350", "W", False),
            ("Cond_Flow_F", "D3826", "F", False),

            # HMI alarm-log source words.
            ("Alarm_Register_1", "D3500", "W", False),
            ("Alarm_Register_2", "D3501", "W", False),
            ("Alarm_Register_3", "D3502", "W", False),

            # Home-screen state and visibility conditions.
            ("Cycle_Status", "M0002", "B", False),
            ("AS_WS_Config", "M0003", "B", False),
            ("HGBV_Config", "M0004", "B", False),
            ("SinglePass_Config", "M0005", "B", False),
            ("Demand_Mode", "M0006", "B", False),
            ("Heat_Call", "M0007", "B", False),
            ("Unit_Model_ERROR", "M0017", "B", False),
            ("OPSS_Config", "M0036", "B", False),
            ("Standby_Valve_Pos", "M0082", "B", False),
            ("Max_LWT_ACTIVE", "M0134", "B", False),
            ("Comp_Start_Delay", "M0240", "B", False),
            ("M0244_Unnamed", "M0244", "B", False),
            ("Defrost", "M0350", "B", False),
            ("Warning_Alarm_bit", "M0402", "B", False),
            ("Lockout_Alarm_bit", "M0403", "B", False),
            ("COLDTank_Probe_Fault", "M0427", "B", False),
            ("HOT_Tank_Probe_Fault", "M0430", "B", False),
            ("Cond_LWT_Probe_Fault", "M0431", "B", False),
            ("Cond_EWT_Probe_Fault", "M0432", "B", False),
            ("Amb_Air_Probe_Fault", "M0434", "B", False),
            ("Master_Comm_Status", "M0950", "B", False),
            ("Memeber_Unit_Status", "M0951", "B", False),
            ("Password_Lock", "M1080", "B", False),
            ("Service_Lock", "M1082", "B", False),
            ("RTP_Config", "M1702", "B", False),
            ("C90A_UnitModel", "M2000", "B", False),
            ("C185A_UnitModel", "M2001", "B", False),
            ("C250A_UnitModel", "M2002", "B", False),
            ("e360A_UnitModel", "M2006", "B", False),
            ("HPB_UnitModel", "M2007", "B", False),
            ("e180_UnitModel", "M2010", "B", False),
            ("O.P.S.S.", "M2035", "B", False),
            ("Circ_Pump_Output", "M2051", "B", False),
            ("Evap_Flow_Output", "M2053", "B", False),
            ("Comp_Output", "M2056", "B", False),
            ("HGBV_Output", "M2062", "B", False),
            ("Ctrl_HB_MCPLA", "M7011", "B", False),
            ("mqtt_member_status", "M7020", "B", False),
        ],
    }
]

# HMI-originated commands. These need a write/command path rather than the
# ordinary source-to-HMI mirroring loop.
HMI_WRITE_COMMANDS = [
    ("Start_Cycle", "M0000", "B"),
    ("Stop_Cycle", "M0001", "B"),
]

# Base Screen 1 also reads timer current values. The present B/F/W PLC_CONFIGS
# format and the older MiSmTCP implementation do not represent TC operands.
HMI_TIMER_CURRENT_VALUES = [
    ("TC_Comp_Off_Delay", 0),
    ("Pump_Delay_timer_TC", 22),
    ("MemStat_Timeout", 30),
    ("MQTT_Timeout", 38),
]

# Useful metadata, but not directly required by Base Screen 1.
OPTIONAL_META_REGISTERS = [
    ("Unit_Model", "D0102", "W"),
]

# Referenced elsewhere in the HMI project. These exceed the normal 4-digit
# MiSmTCP operand path and should remain separate until RA/extended addressing
# is implemented.
EXTENDED_REGISTERS = [
    ("Dev_Mode", "M10100", "B"),
    ("Connection_Error_Log", "D10392", "W"),
    ("Unit_number", "D10399", "W"),
    ("Master_IP_Octet_1", "D10400", "W"),
    ("Master_IP_Octet_2", "D10401", "W"),
    ("Master_IP_Octet_3", "D10402", "W"),
    ("Master_IP_Octet_4", "D10403", "W"),
    ("ErrorLog_Entries", "D10500", "W"),
]
